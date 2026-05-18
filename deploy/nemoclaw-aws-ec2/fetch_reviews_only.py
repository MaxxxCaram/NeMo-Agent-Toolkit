#!/usr/bin/env python3
"""
URGENT: download only id=998 review listing pages from Wayback, write reviews.json.

Default: page 0 only per ethnicity tab (Todas + eid 1..5) — Wayback rarely archives
?p=1+ for the same snapshot. Use --full to also try pagination (slow, often empty).

Usage (from deploy/nemoclaw-aws-ec2):
  python fetch_reviews_only.py
  python fetch_reviews_only.py 4          # delay seconds
  python fetch_reviews_only.py 4 --full  # delay + pagination attempts
"""

import json
import re
import sys
import time

import recuperar_shemalewiki as rec

FULL_PAGINATION = "--full" in sys.argv
_args = [a for a in sys.argv[1:] if a != "--full"]
_DELAY = 4.0
if _args:
    try:
        _DELAY = float(_args[0])
    except ValueError:
        pass
rec.DELAY_SECONDS = _DELAY

OUTPUT = rec.OUTPUT_DIR
log = rec.log


def merge_dedupe(rows):
    seen = set()
    out = []
    for r in rows:
        rid = r.get("review_id")
        if rid and rid not in seen:
            seen.add(rid)
            out.append(r)
        elif not rid:
            out.append(r)
    return out


def save_reviews(all_rows):
    uniq = merge_dedupe(all_rows)
    by_prof = {}
    for r in uniq:
        pid = r.get("profile_id")
        if pid:
            by_prof.setdefault(pid, []).append(r)
    p1 = OUTPUT / "json" / "reviews.json"
    p2 = OUTPUT / "json" / "reviews_by_profile.json"
    p1.parent.mkdir(parents=True, exist_ok=True)
    p1.write_text(json.dumps(uniq, ensure_ascii=False, indent=2), encoding="utf-8")
    p2.write_text(json.dumps(by_prof, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("Saved %d unique reviews -> %s", len(uniq), p1)
    return len(uniq)


def fetch_with_retries(url, attempts=4):
    for i in range(attempts):
        html, label = rec.download_review_listing_html(url)
        if html:
            return html, label
        wait = rec.DELAY_SECONDS * (i + 1)
        log.warning("Retry %d/%d after %ss: %s", i + 1, attempts, wait, url)
        time.sleep(wait)
    return None, None


def main():
    review_lan = "es"
    max_pages = 400 if FULL_PAGINATION else 1
    ethnicities = ["", "1", "2", "3", "4", "5"]

    log.info(
        "fetch_reviews_only: lan=%s delay=%ss full_pagination=%s max_pages=%d",
        review_lan, rec.DELAY_SECONDS, FULL_PAGINATION, max_pages,
    )

    all_reviews = []

    for eid in ethnicities:
        label = eid or "all"
        for page_num in range(max_pages):
            fname = "reviewlist_e%s_p%d.html" % (label, page_num)
            fpath = OUTPUT / "html" / fname
            review_url = rec.review_listing_original_url(
                eid, page_num, lan=review_lan
            )

            if fpath.exists():
                html = fpath.read_text(encoding="utf-8")
            else:
                log.info("Fetch eid=%s p=%d", label, page_num)
                log.info("  URL %s", review_url)
                html, ts_label = fetch_with_retries(review_url)
                if html:
                    fpath.write_text(html, encoding="utf-8")
                    log.info("  -> OK (%s)", ts_label)
                else:
                    log.warning("  -> FAIL, stop ethnicity %s", label)
                    break
                time.sleep(rec.DELAY_SECONDS)

            if not html:
                break

            n_rid = len(re.findall(r"reviewid=\d+", html))
            extracted = rec.extract_reviews_from_html(html)
            all_reviews.extend(extracted)
            log.info(
                "  parsed=%d reviewid_in_html=%d",
                len(extracted), n_rid,
            )
            save_reviews(all_reviews)

            if n_rid == 0:
                log.info("No reviewid on page — end ethnicity %s", label)
                break

    n = save_reviews(all_reviews)
    print("DONE. Total unique reviews:", n)
    print("Files:", OUTPUT / "json" / "reviews.json")


if __name__ == "__main__":
    main()
