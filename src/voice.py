"""Voiceover with automatic fallback between free engines.

TTS_PROVIDER=auto (default) tries, in order, until one works for the whole reel:
  1. edge   - Microsoft Edge voices via edge-tts (best free Hindi, male/female)
  2. gemini - Gemini TTS (same GEMINI_API_KEY, natural voice, free tier has low rate limits)
  3. gtts   - Google Translate voice (always-on, female, a bit flat)
  4. espeak - offline robotic voice, last resort so the pipeline never stops

Set TTS_PROVIDER=edge|gemini|gtts|espeak to force one. Each line is synthesized
separately so caption timing is exact.
"""
import asyncio
import base64
import subprocess
import time
import wave
from pathlib import Path

import requests

from . import config


def run(cmd: list, **kw) -> subprocess.CompletedProcess:
    return subprocess.run([str(c) for c in cmd], check=True, capture_output=True, text=True, **kw)


def duration(path: Path) -> float:
    r = run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", path])
    return float(r.stdout.strip())


# ------------------------------------------------------------------ engines
# Each takes (text, out_path) and must leave an audio file at out_path (any ffmpeg-readable format).

def _edge(text: str, out: Path) -> None:
    import edge_tts

    asyncio.run(edge_tts.Communicate(text, config.TTS_VOICE, rate=config.TTS_RATE).save(str(out)))


def _gemini(text: str, out: Path) -> None:
    if not config.GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY missing")
    last = ""
    for model in config.GEMINI_TTS_MODELS:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        for attempt in range(3):
            r = requests.post(
                url,
                headers={"x-goog-api-key": config.GEMINI_API_KEY},
                json={
                    "contents": [{"parts": [{"text": f"Bolo ek josh bhare, saaf aur dosti bhare andaaz mein: {text}"}]}],
                    "generationConfig": {
                        "responseModalities": ["AUDIO"],
                        "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": config.GEMINI_TTS_VOICE}}},
                    },
                },
                timeout=120,
            )
            if r.status_code == 200:
                try:
                    b64 = r.json()["candidates"][0]["content"]["parts"][0]["inlineData"]["data"]
                except (KeyError, IndexError):
                    last = f"{model}: no audio in response"
                    break
                with wave.open(str(out), "wb") as w:  # Gemini returns raw 24 kHz 16-bit mono PCM
                    w.setnchannels(1)
                    w.setsampwidth(2)
                    w.setframerate(24000)
                    w.writeframes(base64.b64decode(b64))
                return
            last = f"{model}: {r.status_code} {r.text[:150]}"
            if r.status_code == 429:
                time.sleep(25 * (attempt + 1))  # free-tier rate limit
            elif r.status_code in (400, 404):
                break
            else:
                time.sleep(5)
    raise RuntimeError(f"gemini tts failed: {last}")


def _gtts(text: str, out: Path) -> None:
    from gtts import gTTS

    gTTS(text=text, lang="hi", slow=False).save(str(out))


def _espeak(text: str, out: Path) -> None:
    run(["espeak-ng", "-v", "hi", "-s", "150", "-w", out, text])


ENGINES = {"edge": _edge, "gemini": _gemini, "gtts": _gtts, "espeak": _espeak}
# Gemini goes second: it is natural but its free tier is rate-limited (many calls per reel).
AUTO_ORDER = ["edge", "gemini", "gtts", "espeak"]


def _tone(text: str, out: Path) -> None:  # test mode only
    run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"sine=frequency=180:duration={max(1.6, len(text) * 0.075):.2f}",
         "-af", "volume=0.05", "-ar", "44100", "-ac", "1", "-f", "mp3", out])


def _render_all(engine, name: str, lines: list[str], workdir: Path) -> list[Path]:
    wavs = []
    for i, line in enumerate(lines):
        raw = workdir / f"line{i}.src"
        wav = workdir / f"line{i}.wav"
        raw.unlink(missing_ok=True)
        err = None
        for attempt in range(3):
            try:
                engine(line, raw)
                if raw.exists() and raw.stat().st_size > 1000:
                    err = None
                    break
                err = RuntimeError("empty audio file")
            except Exception as e:
                err = e
            time.sleep(3 * (attempt + 1))
        if err:
            raise RuntimeError(f"{name}: line {i} failed: {err}")
        run(["ffmpeg", "-y", "-i", raw, "-ar", "44100", "-ac", "1", "-af", "apad=pad_dur=0.15", wav])
        wavs.append(wav)
    return wavs


def synthesize(lines: list[str], workdir: Path, offline: bool = False) -> tuple[Path, list[float]]:
    """Returns (voice.wav, per-line durations in seconds)."""
    if offline:
        wavs = _render_all(_tone, "test-tone", lines, workdir)
    else:
        order = AUTO_ORDER if config.TTS_PROVIDER == "auto" else [config.TTS_PROVIDER]
        wavs, failures = None, []
        for name in order:
            try:
                wavs = _render_all(ENGINES[name], name, lines, workdir)
                print(f"voiceover engine: {name}")
                break
            except Exception as e:
                failures.append(str(e))
                print(f"voiceover engine '{name}' failed -> trying next. ({e})")
        if wavs is None:
            raise RuntimeError("All voiceover engines failed:\n" + "\n".join(failures))

    durs = [duration(w) for w in wavs]
    listing = workdir / "voice_list.txt"
    listing.write_text("".join(f"file '{w.name}'\n" for w in wavs), encoding="utf-8")
    voice = workdir / "voice.wav"
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", listing, "-c", "copy", voice])
    total = sum(durs)
    if total > 42:
        print(f"WARNING: voiceover is {total:.1f}s (target ~30s). Consider a faster TTS_RATE like +15%.")
    return voice, durs
