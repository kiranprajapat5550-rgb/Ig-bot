"""Reel renderer: stock footage + captions (ASS/libass) + circular photo watermark + voiceover. All FFmpeg."""
import random
import re
from pathlib import Path

import requests

from . import config
from .voice import run

W, H = 1080, 1920
FALLBACK_COLORS = ["0x0f172a", "0x1e1b4b", "0x064e3b", "0x4a044e", "0x1c1917"]


# ---------------------------------------------------------------- footage
def _is_pixabay_key() -> bool:
    """Pixabay keys look like 12345678-abcdef0123...; Pexels keys are one long alphanumeric string.
    Either one can be stored in the PEXELS_API_KEY secret."""
    return bool(re.fullmatch(r"\d+-[0-9a-f]+", config.PEXELS_API_KEY or ""))


def _pixabay_link(query: str, used: set) -> str | None:
    try:
        r = requests.get(
            "https://pixabay.com/api/videos/",
            params={"key": config.PEXELS_API_KEY, "q": query, "per_page": 20, "safesearch": "true"},
            timeout=30,
        )
        r.raise_for_status()
        hits = [h for h in r.json().get("hits", []) if h["id"] not in used and h.get("duration", 0) >= 4]
    except Exception as e:
        print(f"pixabay search failed for '{query}': {e}")
        return None
    random.shuffle(hits)
    for h in hits:
        for size in ("large", "medium"):
            v = h.get("videos", {}).get(size) or {}
            if v.get("url") and v.get("height", 0) >= 720:
                used.add(h["id"])
                return v["url"]
    return None


def _pexels_link(query: str, used: set) -> str | None:
    if not config.PEXELS_API_KEY:
        return None
    if _is_pixabay_key():
        return _pixabay_link(query, used)
    try:
        r = requests.get(
            "https://api.pexels.com/videos/search",
            headers={"Authorization": config.PEXELS_API_KEY},
            params={"query": query, "orientation": "portrait", "size": "medium", "per_page": 15},
            timeout=30,
        )
        r.raise_for_status()
        vids = [v for v in r.json().get("videos", []) if v["id"] not in used and v.get("duration", 0) >= 4]
    except Exception as e:
        print(f"pexels search failed for '{query}': {e}")
        return None
    random.shuffle(vids)
    for v in vids:
        files = [f for f in v.get("video_files", [])
                 if f.get("file_type") == "video/mp4" and f.get("height", 0) >= f.get("width", 0)
                 and f.get("height", 0) >= 1280]
        files.sort(key=lambda f: abs(f["height"] - 1920))
        if files:
            used.add(v["id"])
            return files[0]["link"]
    return None


def _download(url: str, dest: Path) -> bool:
    try:
        with requests.get(url, stream=True, timeout=60) as r:
            r.raise_for_status()
            with open(dest, "wb") as f:
                for chunk in r.iter_content(1 << 20):
                    f.write(chunk)
        return dest.stat().st_size > 10_000
    except Exception as e:
        print(f"download failed: {e}")
        return False


def _make_segment(idx: int, keyword: str, dur: float, used: set, workdir: Path) -> Path:
    seg = workdir / f"seg{idx}.mp4"
    enc = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p", "-r", "30", "-an"]
    link = _pexels_link(keyword, used)
    clip = workdir / f"clip{idx}.mp4"
    if link and _download(link, clip):
        vf = (f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1,"
              "eq=brightness=-0.14:saturation=1.05")
        run(["ffmpeg", "-y", "-stream_loop", "-1", "-i", clip, "-t", f"{dur:.3f}", "-vf", vf, *enc, seg])
    else:  # fallback: animated dark gradient so the pipeline never breaks
        col = FALLBACK_COLORS[idx % len(FALLBACK_COLORS)]
        run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c={col}:s={W}x{H}:r=30:d={dur:.3f}",
             "-vf", "noise=alls=6:allf=t", *enc, seg])
    return seg


# ---------------------------------------------------------------- captions
def _ts(t: float) -> str:
    h, m, s = int(t // 3600), int(t % 3600 // 60), t % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def _clean(text: str) -> str:
    return re.sub(r"[{}\\]", "", text).replace("\n", " ").strip()


def _chunks(line: str, n: int) -> list[str]:
    words = line.split()
    return [" ".join(words[i:i + n]) for i in range(0, len(words), n)] or [line]


def _write_ass(data: dict, durs: list[float], path: Path) -> None:
    f = config.FONT_FAMILY
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,{f},84,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,7,2,2,60,60,560,1
Style: Hook,{f},100,&H0000E5FF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,8,3,5,60,60,0,1
Style: Tag,{f},40,&H00FFFFFF,&H000000FF,&H00000000,&H99000000,-1,0,0,0,100,100,0,0,3,16,0,8,60,60,150,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    total = sum(durs)
    ev = [f"Dialogue: 0,{_ts(0)},{_ts(total)},Tag,,0,0,0,,{_clean(data['title'])[:34]}"]
    t = 0.0
    for i, (line, d) in enumerate(zip(data["lines"], durs)):
        style, n = ("Hook", 3) if i == 0 else ("Cap", 4)
        parts = _chunks(_clean(line), n)
        weights = [max(1, len(p)) for p in parts]
        span = max(0.4, d - 0.1)
        cur = t
        for p, w in zip(parts, weights):
            seg = span * w / sum(weights)
            ev.append(f"Dialogue: 1,{_ts(cur)},{_ts(cur + seg)},{style},,0,0,0,,{{\\fad(70,30)}}{p}")
            cur += seg
        t += d
    path.write_text(head + "\n".join(ev) + "\n", encoding="utf-8")


# ---------------------------------------------------------------- build
def _group_lines(durs: list[float], n_scenes: int) -> list[float]:
    """Split the timeline into n scene durations that end on line boundaries."""
    total, cum, acc = sum(durs), [], 0.0
    for d in durs:
        acc += d
        cum.append(acc)
    cuts = []
    for j in range(1, n_scenes):
        target = total * j / n_scenes
        c = min(cum[:-1], key=lambda x: abs(x - target)) if len(cum) > 1 else total
        if c not in cuts:
            cuts.append(c)
    cuts = sorted(cuts) + [total]
    out, prev = [], 0.0
    for c in cuts:
        out.append(c - prev)
        prev = c
    return out


def build_reel(data: dict, voice: Path, durs: list[float], workdir: Path) -> Path:
    keywords = data["keywords"][:5] or ["motivation sunrise"]
    scene_durs = _group_lines(durs, min(len(keywords), 5))
    scene_durs[-1] += 0.5  # tiny tail so the video never ends before the audio
    used: set = set()
    segs = [_make_segment(i, keywords[i % len(keywords)], d, used, workdir) for i, d in enumerate(scene_durs)]

    (workdir / "segs.txt").write_text("".join(f"file '{s.name}'\n" for s in segs), encoding="utf-8")
    _write_ass(data, durs, workdir / "reel.ass")

    music = sorted(config.MUSIC.glob("*.mp3"))
    out = workdir / "reel.mp4"
    fonts = f":fontsdir={config.FONTS}" if config.FONT_BUNDLED else ""
    fc = (f"[0:v]ass=reel.ass{fonts}[v1];"
          "[1:v]scale=150:150,format=rgba,colorchannelmixer=aa=0.92[wm];"
          "[v1][wm]overlay=48:210[v];"
          "[2:a]loudnorm=I=-16:TP=-1.5:LRA=11[a0];")
    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "segs.txt",
           "-i", config.WATERMARK, "-i", voice]
    if music:
        cmd += ["-stream_loop", "-1", "-i", random.choice(music)]
        fc += "[3:a]volume=0.10[m];[a0][m]amix=inputs=2:duration=first:dropout_transition=0[a]"
    else:
        fc += "[a0]anull[a]"
    cmd += ["-filter_complex", fc, "-map", "[v]", "-map", "[a]",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p", "-r", "30",
            "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", "-shortest", out]
    run(cmd, cwd=workdir)
    return out
            
