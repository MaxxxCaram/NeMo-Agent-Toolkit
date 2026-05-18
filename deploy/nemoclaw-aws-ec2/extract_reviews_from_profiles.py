#!/usr/bin/env python3
"""
Aggregate reviews from saved profile HTML (div#ReviewSection) into reviews.json.
Run from deploy/nemoclaw-aws-ec2 after profile_*.html exist.

  python extract_reviews_from_profiles.py
"""

import json
import re
import warnings
from pathlib import Path

# Must run before any import of requests (pulled by recuperar_shemalewiki)
warnings.filterwarnings(
    "ignore",
    message=r".*urllib3.*doesn't match a supported version.*",
)

import recuperar_shemalewiki as rec

OUTPUT = rec.OUTPUT_DIR
HTML_DIR = OUTPUT / "html"


def main():
    pattern = re.compile(r"profile_(\d+)\.html$")
    all_rows = []
    for path in sorted(HTML_DIR.glob("profile_*.html")):
        m = pattern.search(path.name)
        if not m:
            continue
        pid = m.group(1)
        html = path.read_text(encoding="utf-8", errors="replace")
        # Name from title if possible
        name_m = re.search(r"<title>([^<]+)</title>", html, re.I)
        pname = name_m.group(1).split(" - ")[0].strip() if name_m else None
        rows = rec.extract_reviews_from_profile_html(html, pid, profile_name=pname)
        all_rows.extend(rows)

    # Dedupe by review_id (profile_embed wins duplicate listing rows)
    seen = set()
    unique = []
    for r in all_rows:
        rid = r.get("review_id")
        if rid and rid not in seen:
            seen.add(rid)
            unique.append(r)
        elif not rid:
            unique.append(r)

    by_prof = {}
    for r in unique:
        pid = r.get("profile_id")
        if pid:
            by_prof.setdefault(pid, []).append(r)

    p1 = OUTPUT / "json" / "reviews.json"
    p2 = OUTPUT / "json" / "reviews_by_profile.json"
    p1.parent.mkdir(parents=True, exist_ok=True)
    p1.write_text(json.dumps(unique, ensure_ascii=False, indent=2), encoding="utf-8")
    p2.write_text(json.dumps(by_prof, ensure_ascii=False, indent=2), encoding="utf-8")
    print("reviews from profiles:", len(unique), "->", p1)
    print("profiles with at least one review:", len(by_prof))


if __name__ == "__main__":
    main()
