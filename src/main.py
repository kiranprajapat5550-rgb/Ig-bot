"""Entry point.

  python -m src.main reel                # generate + post one reel
  python -m src.main carousel            # generate + post one carousel
  python -m src.main reel --dry-run      # build only, no posting
  python -m src.main reel --offline --dry-run   # no internet needed (pipeline test with sample script)
"""
import argparse
import json
import shutil
import tempfile
from pathlib import Path

from . import books, config, instagram, script_gen, storage, voice
from .carousel import build_carousel
from .video import build_reel


def _caption(d: dict) -> str:
    return (d["caption"] + "\n\n" + " ".join(d["hashtags"])).strip()


def run_reel(args) -> None:
    if args.offline:
        data = json.loads((config.ASSETS / "sample_reel.json").read_text(encoding="utf-8"))
    else:
        book, prev = books.pick_book("reel", args.book)
        data = script_gen.reel_script(book, prev)
    print("HOOK:", data["lines"][0])

    work = Path(tempfile.mkdtemp(prefix="reel_", dir=config.OUT))
    vo, durs = voice.synthesize(data["lines"], work, offline=args.offline)
    video = build_reel(data, vo, durs, work)
    final = config.OUT / f"reel_{work.name}.mp4"
    shutil.copy(video, final)
    print(f"Reel ready: {final} ({sum(durs):.1f}s voice)")
    (config.OUT / f"{final.stem}.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    if args.dry_run:
        return

    url, pid = storage.upload(final, "video")
    try:
        media_id = instagram.publish_reel(url, _caption(data))
    finally:
        storage.delete(pid, "video")
    books.add_history({"kind": "reel", "book": data["title"], "hook": data["lines"][0], "media_id": media_id})
    print("Posted reel:", media_id)


def run_carousel(args) -> None:
    book, prev = books.pick_book("carousel", args.book)
    data = script_gen.carousel_script(book, prev)
    print("COVER:", data["cover_title"])
    outdir = config.OUT / f"carousel_{book['title'].replace(' ', '_')[:20]}"
    slides = build_carousel(data, outdir)
    print(f"{len(slides)} slides ready in {outdir}")
    if args.dry_run:
        return

    uploaded = [storage.upload(p, "image") for p in slides]
    try:
        media_id = instagram.publish_carousel([u for u, _ in uploaded], _caption(data))
    finally:
        for _, pid in uploaded:
            storage.delete(pid, "image")
    books.add_history({"kind": "carousel", "book": data["title"], "hook": data["cover_title"], "media_id": media_id})
    print("Posted carousel:", media_id)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("kind", choices=["reel", "carousel"])
    ap.add_argument("--dry-run", action="store_true", help="build the media but do not post")
    ap.add_argument("--offline", action="store_true", help="reel only: use sample script and silent tone (testing)")
    ap.add_argument("--book", help="force a specific book title")
    args = ap.parse_args()
    (run_reel if args.kind == "reel" else run_carousel)(args)


if __name__ == "__main__":
    main()
