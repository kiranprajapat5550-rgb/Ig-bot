"""Carousel slides (1080x1350, 4:5) rendered with Pillow + raqm so Devanagari shapes correctly."""
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

from . import config

W, H = 1080, 1350
PALETTES = [
    ("#0f172a", "#1e293b", "#fbbf24"),
    ("#1a1033", "#2d1b4e", "#f472b6"),
    ("#0b2a2a", "#134e4a", "#5eead4"),
    ("#2a0f0f", "#4a1d1d", "#fb923c"),
]
MARGIN = 90


def _font(size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(str(config.FONT_FILE), size, layout_engine=ImageFont.Layout.RAQM)
    except Exception:
        return ImageFont.truetype(str(config.FONT_FILE), size)


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, max_w: int) -> list[str]:
    lines, cur = [], ""
    for w in text.split():
        trial = (cur + " " + w).strip()
        if draw.textlength(trial, font=font) <= max_w:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _bg(pal) -> Image.Image:
    g = Image.linear_gradient("L").resize((W, H))
    return ImageOps.colorize(g, black=pal[0], white=pal[1]).convert("RGB")


def _wm(size: int) -> Image.Image:
    wm = Image.open(config.WATERMARK).convert("RGBA").resize((size, size), Image.LANCZOS)
    return wm


def _paste_wm(img: Image.Image, size: int, xy: tuple[int, int]) -> None:
    wm = _wm(size)
    img.paste(wm, xy, wm)


def _draw_block(d, lines, font, x, y, fill, gap):
    for ln in lines:
        d.text((x, y), ln, font=font, fill=fill)
        y += font.size + gap
    return y


def build_carousel(data: dict, outdir: Path) -> list[Path]:
    outdir.mkdir(parents=True, exist_ok=True)
    pal = random.choice(PALETTES)
    accent = pal[2]
    paths: list[Path] = []
    maxw = W - 2 * MARGIN

    # --- cover
    img = _bg(pal)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((MARGIN, 150, MARGIN + 330, 150 + 78), radius=39, outline=accent, width=4)
    d.text((MARGIN + 34, 163), "बुक समरी", font=_font(44), fill=accent)
    tf = _font(104)
    y = _draw_block(d, _wrap(d, data["cover_title"], tf, maxw), tf, MARGIN, 330, "#ffffff", 26)
    sf = _font(50)
    y = _draw_block(d, _wrap(d, data["cover_sub"], sf, maxw), sf, MARGIN, y + 30, "#cbd5e1", 18)
    bf = _font(42)
    d.text((MARGIN, 1120), f"{data['title']}  ·  {data['author']}".strip(" ·"), font=bf, fill=accent)
    d.text((MARGIN, 1230), "स्वाइप करो  →", font=_font(46), fill="#ffffff")
    _paste_wm(img, 130, (W - MARGIN - 130, H - 130 - 50))
    p = outdir / "slide_01.png"
    img.save(p)
    paths.append(p)

    # --- content slides
    n = len(data["slides"])
    for i, s in enumerate(data["slides"], start=1):
        img = _bg(pal)
        d = ImageDraw.Draw(img)
        d.text((MARGIN, 90), f"{i:02d}", font=_font(190), fill=accent)
        hf = _font(78)
        y = _draw_block(d, _wrap(d, s["heading"], hf, maxw), hf, MARGIN, 400, accent, 20)
        d.rounded_rectangle((MARGIN, y + 10, MARGIN + 120, y + 18), radius=4, fill="#ffffff")
        bf = _font(54)
        _draw_block(d, _wrap(d, s["body"], bf, maxw), bf, MARGIN, y + 60, "#f1f5f9", 22)
        d.text((MARGIN, H - 150), f"{i}/{n}", font=_font(40), fill="#94a3b8")
        _paste_wm(img, 120, (W - MARGIN - 120, H - 120 - 50))
        p = outdir / f"slide_{i + 1:02d}.png"
        img.save(p)
        paths.append(p)

    # --- final CTA slide
    img = _bg(pal)
    d = ImageDraw.Draw(img)
    _paste_wm(img, 300, ((W - 300) // 2, 190))
    cf = _font(70)
    lines = _wrap(d, data["cta"] or "ऐसी और बुक समरी के लिए फॉलो करो", cf, maxw)
    y = 560
    for ln in lines:
        w = d.textlength(ln, font=cf)
        d.text(((W - w) / 2, y), ln, font=cf, fill="#ffffff")
        y += cf.size + 22
    hf = _font(64)
    w = d.textlength(config.HANDLE, font=hf)
    d.text(((W - w) / 2, y + 50), config.HANDLE, font=hf, fill=accent)
    p = outdir / f"slide_{n + 2:02d}.png"
    img.save(p)
    paths.append(p)
    return paths
