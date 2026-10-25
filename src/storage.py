"""Cloudinary (free tier) as temporary public hosting: Instagram needs a public URL to pull media from."""
import hashlib
import time
from pathlib import Path

import requests

from . import config


def _sign(params: dict) -> str:
    to_sign = "&".join(f"{k}={v}" for k, v in sorted(params.items())) + config.CLOUDINARY_API_SECRET
    return hashlib.sha1(to_sign.encode()).hexdigest()


def _base(kind: str, action: str) -> str:
    return f"https://api.cloudinary.com/v1_1/{config.CLOUDINARY_CLOUD_NAME}/{kind}/{action}"


def upload(path: Path, kind: str) -> tuple[str, str]:
    """kind = 'video' or 'image'. Returns (public https url, public_id)."""
    params = {"timestamp": int(time.time())}
    with open(path, "rb") as f:
        r = requests.post(
            _base(kind, "upload"),
            data={**params, "api_key": config.CLOUDINARY_API_KEY, "signature": _sign(params)},
            files={"file": f},
            timeout=300,
        )
    if r.status_code != 200:
        raise RuntimeError(f"Cloudinary upload failed: {r.status_code} {r.text[:300]}")
    j = r.json()
    return j["secure_url"], j["public_id"]


def delete(public_id: str, kind: str) -> None:
    try:
        params = {"public_id": public_id, "timestamp": int(time.time())}
        requests.post(
            _base(kind, "destroy"),
            data={**params, "api_key": config.CLOUDINARY_API_KEY, "signature": _sign(params)},
            timeout=60,
        )
    except Exception as e:
        print(f"cloudinary cleanup skipped: {e}")
