#!/usr/bin/env python3
"""
Download full review story text from Wayback (?id=998&reviewid=...) and save
json/review_bodies.json as { "review_id": "plain text", ... }.

Many review detail URLs were never archived — expect partial coverage.

Usage:
  python fetch_review_bodies.py
  python fetch_review_bodies.py --limit 200 --delay 6
  python fetch_review_bodies.py --review-id 26102
"""

import argparse
import json
import logging
import sys
import time
import warnings
from pathlib import Path

warnings.filterwarnings(
    "ignore",
    message=r".*urllib3.*doesn't match a supported version.*",
)

import recuperar_shemalewiki as rec  # noqa: E402

OUTPUT = Path("shemalewiki_recovery")
JSON_DIR = OUTPUT / "json"
REVIEW_JSON = JSON_DIR / "reviews.json"
BODIES_JSON = JSON_DIR / "review_bodies.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)


def load_existing_bodies():
    if not BODIES_JSON.exists():
        return {}
    data = json.loads(BODIES_JSON.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        return {str(k): v for k, v in data.items() if isinstance(v, str) and v}
    return {}


def unique_review_ids_from_file():
    if not REVIEW_JSON.exists():
        log.error("Missing %s — run extract_reviews_from_profiles.py first", REVIEW_JSON)
        return []
    rows = json.loads(REVIEW_JSON.read_text(encoding="utf-8"))
    seen = []
    done = set()
    for r in rows:
        rid = r.get("review_id")
        if not rid:
            continue
        s = str(rid)
        if s not in done:
            done.add(s)
            seen.append(s)
    return seen


def main():
    ap = argparse.ArgumentParser(description="Fetch review story bodies from Wayback")
    ap.add_argument("--limit", type=int, default=0, help="Max new fetches (0 = all missing)")
    ap.add_argument("--delay", type=float, default=8.0, help="Seconds between requests")
    ap.add_argument("--lan", default="en", help="lan= query param")
    ap.add_argument("--review-id", default="", help="Fetch only this review id")
    args = ap.parse_args()

    bodies = load_existing_bodies()
    if args.review_id:
        todo = [args.review_id.strip()]
    else:
        todo = [r for r in unique_review_ids_from_file() if r not in bodies]

    if args.limit and not args.review_id:
        todo = todo[: args.limit]

    log.info(
        "review bodies: already=%d to_fetch=%d delay=%ss",
        len(bodies),
        len(todo),
        args.delay,
    )

    ok = 0
    fail = 0
    for i, rid in enumerate(todo):
        html, label = rec.download_review_detail_html(rid, lan=args.lan)
        if not html:
            log.warning("[%d/%d] review %s — no snapshot", i + 1, len(todo), rid)
            fail += 1
            time.sleep(args.delay)
            continue
        text = rec.extract_review_detail_body(html)
        if not text:
            log.warning("[%d/%d] review %s — parse failed (%s)", i + 1, len(todo), rid, label)
            fail += 1
            time.sleep(args.delay)
            continue
        bodies[rid] = text
        ok += 1
        log.info("[%d/%d] review %s OK (%s, %d chars)", i + 1, len(todo), rid, label, len(text))
        BODIES_JSON.write_text(
            json.dumps(bodies, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        time.sleep(args.delay)

    log.info("done: new_ok=%d fail=%d total_saved=%d -> %s", ok, fail, len(bodies), BODIES_JSON)
    return 0 if ok or not todo else 1


if __name__ == "__main__":
    sys.exit(main() or 0)
