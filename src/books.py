"""Book picker + posting history (so content never repeats)."""
import json
import random
from datetime import datetime, timezone

from . import config


def load_books() -> list[dict]:
    return json.loads(config.BOOKS_FILE.read_text(encoding="utf-8"))


def load_history() -> list[dict]:
    if config.HISTORY_FILE.exists():
        return json.loads(config.HISTORY_FILE.read_text(encoding="utf-8"))
    return []


def add_history(entry: dict) -> None:
    hist = load_history()
    entry["ts"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    hist.append(entry)
    config.HISTORY_FILE.write_text(json.dumps(hist, ensure_ascii=False, indent=1), encoding="utf-8")


def pick_book(kind: str, forced_title: str | None = None) -> tuple[dict, list[str]]:
    """Least-used book for this kind first. Returns (book, previous hooks for that book)."""
    books = load_books()
    hist = [h for h in load_history() if h.get("kind") == kind]
    if forced_title:
        book = next((b for b in books if b["title"].lower() == forced_title.lower()), None)
        if not book:
            book = {"title": forced_title, "author": ""}
    else:
        counts = {b["title"]: 0 for b in books}
        for h in hist:
            if h.get("book") in counts:
                counts[h["book"]] += 1
        low = min(counts.values())
        book = random.choice([b for b in books if counts[b["title"]] == low])
    prev = [h.get("hook", "") for h in hist if h.get("book") == book["title"]][-8:]
    return book, prev
