"""Instagram API with Instagram Login: publish Reels and carousels (graph.instagram.com)."""
import time

import requests

from . import config


def _check(r: requests.Response) -> dict:
    try:
        j = r.json()
    except Exception:
        raise RuntimeError(f"Instagram API non-JSON response {r.status_code}: {r.text[:300]}")
    if r.status_code >= 400 or "error" in j:
        raise RuntimeError(f"Instagram API error {r.status_code}: {j.get('error', j)}")
    return j


def _post(path: str, **params) -> dict:
    r = requests.post(f"{config.GRAPH_BASE}/{path}", data={**params, "access_token": config.IG_ACCESS_TOKEN}, timeout=120)
    return _check(r)


def _get(path: str, **params) -> dict:
    r = requests.get(f"{config.GRAPH_BASE}/{path}", params={**params, "access_token": config.IG_ACCESS_TOKEN}, timeout=60)
    return _check(r)


def _wait(container_id: str, timeout: int = 420) -> None:
    start = time.time()
    while time.time() - start < timeout:
        s = _get(container_id, fields="status_code,status")
        code = s.get("status_code")
        if code == "FINISHED":
            return
        if code in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Instagram processing failed: {s}")
        time.sleep(10)
    raise RuntimeError("Instagram processing timed out")


def _require() -> None:
    if not (config.IG_USER_ID and config.IG_ACCESS_TOKEN):
        raise RuntimeError("IG_USER_ID / IG_ACCESS_TOKEN missing")


def publish_reel(video_url: str, caption: str) -> str:
    _require()
    c = _post(f"{config.IG_USER_ID}/media", media_type="REELS", video_url=video_url,
              caption=caption, share_to_feed="true")["id"]
    _wait(c)
    return _post(f"{config.IG_USER_ID}/media_publish", creation_id=c)["id"]


def publish_carousel(image_urls: list[str], caption: str) -> str:
    _require()
    kids = []
    for u in image_urls:
        cid = _post(f"{config.IG_USER_ID}/media", image_url=u, is_carousel_item="true")["id"]
        _wait(cid)
        kids.append(cid)
    parent = _post(f"{config.IG_USER_ID}/media", media_type="CAROUSEL",
                   children=",".join(kids), caption=caption)["id"]
    _wait(parent)
    return _post(f"{config.IG_USER_ID}/media_publish", creation_id=parent)["id"]
