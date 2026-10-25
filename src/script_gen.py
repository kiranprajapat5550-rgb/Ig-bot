"""Script writing with Gemini (free tier). Output is validated JSON."""
import json
import random
import re
import time

import requests

from . import config

REEL_FORMATS = [
    "Is book ke 3 sabse kaam ke lessons",
    "Ek common galti jo log karte hain aur book ka solution",
    "Myth vs Truth: book ka ek bada idea",
    "Agar sirf aaj se kuch badalna ho to book ke 3 chhote actions",
    "Wo baat jo book ne sikhayi aur school ne nahi sikhayi",
]

REEL_PROMPT = """Tum ek popular Hindi self-improvement Instagram creator ke liye 30 second ki Reel ka script likh rahe ho.

Book: {title} (writer: {author})
Is baar ka format: {fmt}
Pehle use ho chuke hooks (inse bilkul alag angle lo, repeat mat karo): {prev}

Rules:
- Book ka summary APNE SHABDON mein likho. Book se koi line, quote ya paragraph copy mat karo.
- Bhasha: simple bolchaal wali Hindi, Devanagari script mein. Sirf book ka naam aur writer ka naam Latin script mein likh sakte ho.
- Pehli line (hook) 12 shabd se kam, itni strong ki log scroll rok dein (sawal, chonkane wali baat ya seedha dard-point).
- Kul 6 se 8 chhoti lines, har line 6 se 14 shabd. Total 70 se 85 shabd.
- Structure: hook, phir 1 line mein book ka naam, phir 3 practical insights (har ek amal mein laane layak), last line CTA (follow karne ke liye, har baar alag tareeke se).
- Koi nakli statistic, jhooth ya guarantee wala daava mat karo.
- keywords: 4 English phrases (2-3 shabd) portrait stock video search ke liye, script ke mood se match karein, koi brand ya naam nahi.
- caption: 2-3 chhoti Hindi lines + end mein comments ke liye ek sawal. Hashtags caption mein mat do.
- hashtags: exactly 5 relevant hashtags (# ke saath).

Sirf JSON do:
{{"lines": ["..."], "keywords": ["..."], "caption": "...", "hashtags": ["#..."]}}
"""

CAROUSEL_PROMPT = """Tum ek popular Hindi self-improvement Instagram creator ke liye carousel post likh rahe ho.

Book: {title} (writer: {author})
Pehle use ho chuke angles (alag angle lo): {prev}

Rules:
- Summary APNE SHABDON mein, book se koi line ya quote copy mat karo.
- Simple Hindi, Devanagari script mein. Sirf book/writer ka naam Latin script mein.
- cover_title: 8 shabd se kam, curiosity jagane wala. cover_sub: 1 chhoti line.
- Exactly 6 slides. Har slide: heading (max 6 shabd) aur body (max 28 shabd, ek clear actionable idea).
- cta: ek line (save/share/follow ke liye).
- Koi nakli statistic ya guarantee wala daava nahi.
- caption: 2-3 chhoti Hindi lines + comments ke liye ek sawal, hashtags nahi.
- hashtags: exactly 5.

Sirf JSON do:
{{"cover_title": "...", "cover_sub": "...", "slides": [{{"heading": "...", "body": "..."}}], "cta": "...", "caption": "...", "hashtags": ["#..."]}}
"""


def _gemini_json(prompt: str) -> dict:
    if not config.GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY missing")
    last = ""
    for model in config.GEMINI_MODELS:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        for attempt in range(3):
            try:
                r = requests.post(
                    url,
                    headers={"x-goog-api-key": config.GEMINI_API_KEY},
                    json={
                        "contents": [{"parts": [{"text": prompt}]}],
                        "generationConfig": {"temperature": 0.9, "responseMimeType": "application/json"},
                    },
                    timeout=90,
                )
                if r.status_code == 200:
                    text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
                    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
                    return json.loads(text)
                last = f"{model} -> {r.status_code}: {r.text[:200]}"
                if r.status_code in (400, 404):
                    break  # try next model name
                time.sleep(6 * (attempt + 1))
            except Exception as e:  # network / JSON problems
                last = f"{model} -> {e}"
                time.sleep(4)
    raise RuntimeError(f"Gemini failed: {last}")


def _clean_tags(tags) -> list[str]:
    out = []
    for t in tags or []:
        t = "#" + re.sub(r"[^\w]", "", str(t).lstrip("#"))
        if len(t) > 1 and t not in out:
            out.append(t)
    return out[:5]


def reel_script(book: dict, prev_hooks: list[str]) -> dict:
    fmt = random.choice(REEL_FORMATS)
    prompt = REEL_PROMPT.format(
        title=book["title"], author=book.get("author", ""), fmt=fmt, prev=prev_hooks or "koi nahi"
    )
    for _ in range(3):
        d = _gemini_json(prompt)
        lines = [str(x).strip() for x in d.get("lines", []) if str(x).strip()]
        words = sum(len(x.split()) for x in lines)
        if 5 <= len(lines) <= 9 and 45 <= words <= 105 and len(d.get("keywords", [])) >= 2:
            return {
                "title": book["title"],
                "author": book.get("author", ""),
                "lines": lines,
                "keywords": [str(k) for k in d["keywords"]][:5],
                "caption": str(d.get("caption", "")).strip(),
                "hashtags": _clean_tags(d.get("hashtags")),
            }
    raise RuntimeError("Gemini returned an unusable reel script 3 times")


def carousel_script(book: dict, prev_hooks: list[str]) -> dict:
    prompt = CAROUSEL_PROMPT.format(
        title=book["title"], author=book.get("author", ""), prev=prev_hooks or "koi nahi"
    )
    for _ in range(3):
        d = _gemini_json(prompt)
        slides = [
            {"heading": str(s.get("heading", "")).strip(), "body": str(s.get("body", "")).strip()}
            for s in d.get("slides", [])
            if s.get("heading") and s.get("body")
        ]
        if len(slides) >= 5 and d.get("cover_title"):
            return {
                "title": book["title"],
                "author": book.get("author", ""),
                "cover_title": str(d["cover_title"]).strip(),
                "cover_sub": str(d.get("cover_sub", "")).strip(),
                "slides": slides[:7],
                "cta": str(d.get("cta", "")).strip(),
                "caption": str(d.get("caption", "")).strip(),
                "hashtags": _clean_tags(d.get("hashtags")),
            }
    raise RuntimeError("Gemini returned an unusable carousel script 3 times")
