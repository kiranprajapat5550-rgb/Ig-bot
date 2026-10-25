"""Central config. Secrets come from environment variables (GitHub Secrets)."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
FONTS = ASSETS / "fonts"
MUSIC = ASSETS / "music"
OUT = ROOT / "output"
STATE = ROOT / "state"
for _d in (OUT, STATE, MUSIC, FONTS):
    _d.mkdir(parents=True, exist_ok=True)


def env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


# --- Script generation (Gemini free tier) ---
GEMINI_API_KEY = env("GEMINI_API_KEY")
# Tried in order. Override with GEMINI_MODEL secret/variable if Google renames models.
GEMINI_MODELS = [m for m in [env("GEMINI_MODEL"), "gemini-flash-latest", "gemini-2.5-flash"] if m]

# --- Stock footage (Pexels free API) ---
PEXELS_API_KEY = env("PEXELS_API_KEY")

# --- Public hosting for Instagram (Cloudinary free tier) ---
CLOUDINARY_CLOUD_NAME = env("CLOUDINARY_CLOUD_NAME")
CLOUDINARY_API_KEY = env("CLOUDINARY_API_KEY")
CLOUDINARY_API_SECRET = env("CLOUDINARY_API_SECRET")

# --- Instagram API with Instagram Login ---
IG_USER_ID = env("IG_USER_ID")
IG_ACCESS_TOKEN = env("IG_ACCESS_TOKEN")
GRAPH_VERSION = env("GRAPH_VERSION", "v26.0")
GRAPH_BASE = f"https://graph.instagram.com/{GRAPH_VERSION}"

# --- Voice ---
TTS_VOICE = env("TTS_VOICE", "hi-IN-MadhurNeural")  # female: hi-IN-SwaraNeural
TTS_RATE = env("TTS_RATE", "+5%")
TTS_PROVIDER = env("TTS_PROVIDER", "auto").lower()  # auto | edge | gemini | gtts | espeak
GEMINI_TTS_MODELS = [m for m in [env("GEMINI_TTS_MODEL"), "gemini-2.5-flash-preview-tts"] if m]
GEMINI_TTS_VOICE = env("GEMINI_TTS_VOICE", "Charon")  # male: Charon, Puck, Fenrir | female: Kore, Aoede

# --- Branding ---
HANDLE = env("IG_HANDLE", "@yourhandle")
WATERMARK = ASSETS / "watermark.png"


def _resolve_font() -> tuple[Path, str, bool]:
    """Devanagari bold font: a bundled TTF in assets/fonts wins, otherwise ask fontconfig
    (the GitHub workflow installs fonts-noto-core, which has Noto Sans Devanagari)."""
    for f in sorted(FONTS.glob("*.[to]tf")):
        if f.stat().st_size > 50_000:
            return f, env("CAPTION_FONT", "Noto Sans Devanagari"), True
    import subprocess

    out = subprocess.run(
        ["fc-match", "-f", "%{file}|%{family}", "Noto Sans Devanagari:bold:lang=hi"],
        capture_output=True, text=True, check=True,
    ).stdout
    file, fam = out.split("|", 1)
    return Path(file), fam.split(",")[0].strip(), False


FONT_FILE, FONT_FAMILY, FONT_BUNDLED = _resolve_font()

HISTORY_FILE = STATE / "history.json"
BOOKS_FILE = ASSETS / "books.json"
