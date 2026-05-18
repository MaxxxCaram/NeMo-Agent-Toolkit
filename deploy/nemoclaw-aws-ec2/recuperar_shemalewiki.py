#!/usr/bin/env python3
"""
=============================================================
  RECUPERADOR DE SHEMALEWIKI.COM DESDE WAYBACK MACHINE
  Uso: python recuperar_shemalewiki.py
=============================================================
"""

import html as html_mod
import json
import logging
import os
import re
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import requests

# ─── CONFIGURACION ───────────────────────────────────────────
BASE_URL       = "shemalewiki.com"
WAYBACK_CDX    = "https://web.archive.org/cdx/search/cdx"
WAYBACK_BASE   = "https://web.archive.org/web"
OUTPUT_DIR     = Path("shemalewiki_recovery")
DELAY_SECONDS  = 8.0
MAX_PAGES      = 2000
PREFERRED_LANG = "en"

# ─── LOGGING ─────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("recovery.log"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)

# ─── DIRECTORIOS DE SALIDA ────────────────────────────────────
(OUTPUT_DIR / "html").mkdir(parents=True, exist_ok=True)
(OUTPUT_DIR / "json").mkdir(parents=True, exist_ok=True)
(OUTPUT_DIR / "images").mkdir(parents=True, exist_ok=True)


# ═══════════════════════════════════════════════════════════════
#  PASO 1: OBTENER INDICE COMPLETO DE WAYBACK MACHINE
# ═══════════════════════════════════════════════════════════════

def fetch_cdx_index(limit=5000):
    """Download the full URL index from Wayback Machine CDX API."""
    log.info("Descargando indice de URLs desde Wayback Machine CDX API...")

    params = {
        "url": "%s/*" % BASE_URL,
        "output": "json",
        "limit": limit,
        "fl": "timestamp,original,statuscode",
        "filter": "statuscode:200",
        "collapse": "urlkey",
        "from": "2020",
        "to": "2025"
    }

    try:
        resp = requests.get(WAYBACK_CDX, params=params, timeout=120)
        resp.raise_for_status()
        data = resp.json()

        if data and data[0] == ["timestamp", "original", "statuscode"]:
            data = data[1:]

        urls = [{"timestamp": row[0], "url": row[1]} for row in data]
        log.info("%d URLs unicas encontradas en el archivo", len(urls))
        return urls

    except Exception as exc:
        log.error("Error al descargar CDX: %s", exc)
        return []


def fetch_cdx_timestamp_for_url(original_url):
    """Latest Wayback timestamp for a single URL (status 200)."""
    params = {
        "url": original_url,
        "output": "json",
        "limit": 1,
        "fl": "timestamp,original,statuscode",
        "filter": "statuscode:200",
        "sort": "reverse",
    }
    try:
        resp = requests.get(WAYBACK_CDX, params=params, timeout=90)
        resp.raise_for_status()
        data = resp.json()
        if data and data[0] == ["timestamp", "original", "statuscode"]:
            data = data[1:]
        if data and len(data[0]) >= 1:
            return data[0][0]
    except Exception as exc:
        log.warning("CDX timestamp lookup failed for %s: %s", original_url, exc)
    return None


# ═══════════════════════════════════════════════════════════════
#  PASO 2: CLASIFICAR URLs POR TIPO
# ═══════════════════════════════════════════════════════════════

def classify_url(url):
    """Analyze URL query params and return (page_type, metadata)."""
    try:
        parsed = urlparse(url)
        qs = parse_qs(parsed.query)

        page_id    = qs.get("id", [None])[0]
        profile_id = qs.get("profileid", [None])[0]
        country_id = qs.get("countryid", [None])[0]
        city_id    = qs.get("cityid", [None])[0]
        region_id  = qs.get("regionid", [None])[0]
        vid        = qs.get("vid", [None])[0]
        lan        = qs.get("lan", [PREFERRED_LANG])[0]

        if profile_id and vid:
            return "video", {
                "profile_id": profile_id, "vid": vid,
                "lang": lan, "url": url,
            }
        if page_id == "1136" and profile_id:
            return "review", {
                "profile_id": profile_id,
                "lang": lan, "url": url,
            }
        if page_id == "998":
            return "review_index", {"lang": lan, "url": url}
        if profile_id:
            return "profile", {
                "profile_id": profile_id, "page_id": page_id,
                "lang": lan, "url": url,
            }
        if country_id:
            return "country", {"country_id": country_id, "lang": lan, "url": url}
        if city_id:
            return "city", {"city_id": city_id, "lang": lan, "url": url}
        if region_id:
            return "region", {"region_id": region_id, "lang": lan, "url": url}
        if not parsed.query:
            return "homepage", {"lang": lan, "url": url}
        return "other", {"url": url}

    except Exception:
        return "unknown", {"url": url}


def build_url_map(cdx_urls):
    """Classify all URLs, preferring English to avoid language duplicates."""
    log.info("Clasificando URLs por tipo de contenido...")

    url_map = {
        "profile":      {},
        "review":       {},
        "review_index": [],
        "video":        {},
        "country":      {},
        "city":         {},
        "region":       {},
        "homepage":     [],
        "other":        []
    }

    for entry in cdx_urls:
        url = entry["url"]
        timestamp = entry["timestamp"]
        url_type, meta = classify_url(url)

        lang = meta.get("lang", "en")

        if url_type == "profile":
            pid = meta["profile_id"]
            if pid not in url_map["profile"] or lang == PREFERRED_LANG:
                url_map["profile"][pid] = {**meta, "timestamp": timestamp}

        elif url_type == "review":
            pid = meta["profile_id"]
            if pid not in url_map["review"] or lang == PREFERRED_LANG:
                url_map["review"][pid] = {**meta, "timestamp": timestamp}

        elif url_type == "review_index":
            url_map["review_index"].append({**meta, "timestamp": timestamp})

        elif url_type == "video":
            vid_key = "%s_%s" % (meta["profile_id"], meta["vid"])
            if vid_key not in url_map["video"] or lang == PREFERRED_LANG:
                url_map["video"][vid_key] = {**meta, "timestamp": timestamp}

        elif url_type == "country":
            cid = meta["country_id"]
            if cid not in url_map["country"] or lang == PREFERRED_LANG:
                url_map["country"][cid] = {**meta, "timestamp": timestamp}

        elif url_type == "city":
            cid = meta["city_id"]
            if cid not in url_map["city"] or lang == PREFERRED_LANG:
                url_map["city"][cid] = {**meta, "timestamp": timestamp}

        elif url_type == "region":
            rid = meta["region_id"]
            if rid not in url_map["region"] or lang == PREFERRED_LANG:
                url_map["region"][rid] = {**meta, "timestamp": timestamp}

        elif url_type == "homepage":
            url_map["homepage"].append({**meta, "timestamp": timestamp})

        else:
            url_map["other"].append({**meta, "timestamp": timestamp})

    for key, val in url_map.items():
        count = len(val)
        log.info("   %10s: %4d paginas unicas", key, count)

    return url_map


# ═══════════════════════════════════════════════════════════════
#  PASO 3: DESCARGAR HTML DESDE WAYBACK MACHINE
# ═══════════════════════════════════════════════════════════════

def make_wayback_url(original_url, timestamp):
    """Build the full Wayback Machine URL for a specific capture."""
    return "%s/%s/%s" % (WAYBACK_BASE, timestamp, original_url)


SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,*/*",
    "Accept-Language": "en-US,en;q=0.9",
})


def download_page(original_url, timestamp, retries=5):
    """Download HTML from Wayback Machine with exponential backoff."""
    wayback_url = make_wayback_url(original_url, timestamp)

    for attempt in range(retries):
        backoff = min(DELAY_SECONDS * (2 ** attempt), 120)
        try:
            resp = SESSION.get(wayback_url, timeout=30)

            if resp.status_code == 200:
                return resp.text
            if resp.status_code == 404:
                return None
            if resp.status_code in (429, 503):
                log.warning(
                    "Rate limited (%d), esperando %ds...",
                    resp.status_code, backoff * 2,
                )
                time.sleep(backoff * 2)
                continue
            log.warning("Status %d para %s", resp.status_code, wayback_url)
            time.sleep(backoff)

        except requests.RequestException as exc:
            log.warning(
                "Intento %d/%d fallido (backoff %ds): %s",
                attempt + 1, retries, backoff, exc,
            )
            time.sleep(backoff)

    return None


def download_page_latest(original_url, retries=5):
    """
    Use /web/2/... so Internet Archive redirects to the latest snapshot
    for this exact URL. Needed when paginated ?p=N URLs are not in CDX
    under the same timestamp as the index page.
    """
    wayback_url = "%s/2/%s" % (WAYBACK_BASE, original_url)

    for attempt in range(retries):
        backoff = min(DELAY_SECONDS * (2 ** attempt), 120)
        try:
            resp = SESSION.get(
                wayback_url, timeout=45, allow_redirects=True
            )
            if resp.status_code == 200 and resp.text:
                return resp.text
            if resp.status_code == 404:
                return None
            if resp.status_code in (429, 503):
                log.warning(
                    "Rate limited (%d) on latest, esperando %ds...",
                    resp.status_code, backoff * 2,
                )
                time.sleep(backoff * 2)
                continue
            log.warning("Status %d para latest %s", resp.status_code, wayback_url)
            time.sleep(backoff)
        except requests.RequestException as exc:
            log.warning(
                "Intento latest %d/%d fallido: %s",
                attempt + 1, retries, exc,
            )
            time.sleep(backoff)

    return None


def download_review_listing_html(original_url):
    """
    Fetch id=998 review listing HTML: CDX timestamp, known-good snapshots,
    then /web/2/ latest redirect. Returns (html, label) or (None, None).

    Paginated URLs (?p=N) are often missing from CDX; try /web/2/ first so
    Wayback can pick a snapshot that actually has that exact URL.
    """
    has_p = bool(re.search(r"[&?]p=\d+", original_url))
    if has_p:
        html = download_page_latest(original_url, retries=8)
        if html and len(html) > 500 and "reviewid=" in html:
            return html, "latest"

    # /web/2/ before CDX (skip if has_p: already tried latest above)
    if not has_p:
        html = download_page_latest(original_url, retries=5)
        if html and len(html) > 500 and "reviewid=" in html:
            return html, "latest"

    ts = fetch_cdx_timestamp_for_url(original_url)
    candidates = []
    if ts:
        candidates.append(ts)
    candidates.extend([
        "20250219215820",
        "20240620223620",
        "20240918013543",
        "20240528232434",
    ])
    seen = set()
    for t in candidates:
        if not t or t in seen:
            continue
        seen.add(t)
        html = download_page(original_url, t)
        if html and len(html) > 500 and "reviewid=" in html:
            return html, t

    html = download_page_latest(original_url, retries=8)
    if html and "reviewid=" in html:
        return html, "latest"
    return None, None


def review_listing_original_url(eid, page_num, lan="es"):
    """
    Canonical URL for id=998 review listings. Page 0 must NOT use &p=0 —
    Wayback CDX often only has ?id=998&lan=... or ?id=998&eid=X&lan=... .
    """
    if page_num == 0:
        if eid:
            return (
                "https://www.shemalewiki.com/?id=998&eid=%s&lan=%s"
                % (eid, lan)
            )
        return "https://www.shemalewiki.com/?id=998&lan=%s" % lan
    if eid:
        return (
            "https://www.shemalewiki.com/?id=998&eid=%s&p=%d&lan=%s"
            % (eid, page_num, lan)
        )
    return "https://www.shemalewiki.com/?id=998&p=%d&lan=%s" % (page_num, lan)


def review_detail_original_url(review_id, lan="en"):
    """Canonical URL for a single review story (?id=998&reviewid=...)."""
    return (
        "https://www.shemalewiki.com/?id=998&reviewid=%s&lan=%s"
        % (review_id, lan)
    )


def _html_fragment_to_plain(fragment):
    """Turn a small HTML fragment into plain text (review body)."""
    if not fragment:
        return ""
    s = re.sub(r"<br\s*/?>", "\n", fragment, flags=re.IGNORECASE)
    s = re.sub(r"<[^>]+>", "", s)
    return html_mod.unescape(s).strip()


def extract_review_detail_body(html):
    """
    Parse full review story from archived review detail page.
    The narrative lives in <span id="Text_N"> (not TextTop_*).
    Returns None if not found or too short.
    """
    if not html:
        return None
    body = html
    if "<!-- BEGIN WAYBACK TOOLBAR" in body:
        body = re.split(r"<!-- END WAYBACK TOOLBAR", body, maxsplit=1)[-1]

    best = None
    best_len = 0
    for m in re.finditer(
        r'<span[^>]*\bid="Text_(\d+)"[^>]*>(.*?)</span>',
        body,
        re.DOTALL | re.IGNORECASE,
    ):
        inner = m.group(2)
        plain = _html_fragment_to_plain(inner)
        if len(plain) > best_len:
            best_len = len(plain)
            best = plain

    if best_len < 40:
        return None
    return best


def download_review_detail_html(review_id, lan="en"):
    """
    Fetch one review detail page from Wayback. Many review URLs were never
    archived (404) — returns (None, None) often.

    Returns:
        (html_string, label) or (None, None)
    """
    original_url = review_detail_original_url(review_id, lan)

    html = download_page_latest(original_url, retries=8)
    if html and len(html) > 1200 and extract_review_detail_body(html):
        return html, "latest"

    ts = fetch_cdx_timestamp_for_url(original_url)
    candidates = []
    if ts:
        candidates.append(ts)
    candidates.extend([
        "20250219215820",
        "20250216020046",
        "20230408154102",
        "20240620223620",
        "20240918013543",
        "20240528232434",
    ])
    seen = set()
    for t in candidates:
        if not t or t in seen:
            continue
        seen.add(t)
        html = download_page(original_url, t)
        if html and len(html) > 1200 and extract_review_detail_body(html):
            return html, t

    html = download_page_latest(original_url, retries=10)
    if html and extract_review_detail_body(html):
        return html, "latest_retry"
    return None, None


# ═══════════════════════════════════════════════════════════════
#  PASO 4: EXTRAER DATOS ESTRUCTURADOS DEL HTML
# ═══════════════════════════════════════════════════════════════

def extract_profile_data(html, profile_id, original_url):
    """Extract structured profile data including reviews from raw HTML."""
    data = {
        "profile_id": profile_id,
        "source_url": original_url,
        "name": None,
        "description": None,
        "bio": None,
        "location": None,
        "contact": {
            "phone": None,
            "email": None,
            "whatsapp": None,
        },
        "facts": {},
        "services": [],
        "images": [],
        "reviews": [],
        "tags": [],
    }

    if not html:
        return data

    # Name from title
    name_match = re.search(
        r'<title[^>]*>([^<]+)</title>', html, re.IGNORECASE
    )
    if name_match:
        data["name"] = name_match.group(1).strip()

    # Meta description
    desc_match = re.search(
        r'<meta[^>]+name=["\']description["\'][^>]+content=["\']'
        r'([^"\']+)["\']',
        html, re.IGNORECASE,
    )
    if desc_match:
        data["description"] = desc_match.group(1).strip()

    # H1 — "Name is in: City, Country"
    h1_match = re.search(r'<h1[^>]*>([^<]+)</h1>', html, re.IGNORECASE)
    if h1_match:
        h1_text = h1_match.group(1).strip()
        if not data["name"]:
            data["name"] = h1_text.split(" is in:")[0].strip()
        loc_match = re.search(r'is in:\s*(.+)', h1_text)
        if loc_match:
            data["location"] = loc_match.group(1).strip()

    # Phone numbers
    phone_matches = re.findall(
        r'<a\s+href=["\'](?:https?://web\.archive\.org/[^"]*)?'
        r'tel:([^"\']+)["\']',
        html, re.IGNORECASE,
    )
    if phone_matches:
        phones = list(set(p.strip() for p in phone_matches))
        data["contact"]["phone"] = phones[0] if len(phones) == 1 else phones

    # Email
    email_match = re.search(
        r'mailto:([^"\'<>\s]+)', html, re.IGNORECASE
    )
    if email_match:
        data["contact"]["email"] = email_match.group(1).strip()

    # WhatsApp
    wa_match = re.search(
        r'WhatsApp:\s*<a[^>]+>([^<]+)</a>', html, re.IGNORECASE
    )
    if wa_match:
        data["contact"]["whatsapp"] = wa_match.group(1).strip()

    # Profile facts (endowment, age, height, weight, type, nationality)
    fact_pattern = re.compile(
        r'<span class="LiCaption">([^<]+)</span><br/>\s*'
        r'<span class="LiValue">([^<]+)</span>',
        re.IGNORECASE,
    )
    for match in fact_pattern.finditer(html):
        data["facts"][match.group(1).strip()] = match.group(2).strip()

    fact_left_pattern = re.compile(
        r'<div class="LiCaptionLeft">([^<]+)</div>\s*'
        r'<div class="LiValue(?:Left)?">([^<]*)</div>',
        re.IGNORECASE,
    )
    for match in fact_left_pattern.finditer(html):
        val = match.group(2).strip()
        if val:
            data["facts"][match.group(1).strip()] = val

    # Services table
    service_pattern = re.compile(
        r'<tr><td>([^<]+)</td>'
        r'<td><img[^>]+/(\w+)\.png"',
        re.IGNORECASE,
    )
    for match in service_pattern.finditer(html):
        svc_name = match.group(1).strip()
        svc_val = match.group(2).strip()
        if svc_name not in ("Basic Services", "Hardcore Services"):
            data["services"].append({
                "service": svc_name,
                "available": svc_val.lower() == "yes",
            })

    # Bio text (inside div.panel after the facts section)
    bio_match = re.search(
        r'<div class="panel">([^<]{20,})</div>',
        html, re.IGNORECASE,
    )
    if bio_match:
        data["bio"] = bio_match.group(1).strip()

    # Extended bio (span with id="Text_2")
    ext_bio = re.search(
        r'<span id="Text_2"[^>]*>(.+?)</span>',
        html, re.IGNORECASE | re.DOTALL,
    )
    if ext_bio:
        bio_text = re.sub(r'<[^>]+>', '', ext_bio.group(1)).strip()
        if bio_text:
            data["bio"] = (data["bio"] or "") + "\n" + bio_text

    # Images (gallery + profile pics)
    img_pattern = re.compile(
        r'<img[^>]+src=["\']([^"\']+)["\']', re.IGNORECASE
    )
    images = []
    for match in img_pattern.finditer(html):
        src = match.group(1)
        if "shemalewiki.com" in src or "/web/" in src:
            if not any(x in src for x in [
                "toolbar", "wayback", "logo_wb", "banner",
                "favicon", "search_16", "home-24", "login-24",
                "yes.png", "no.png", "null.png", "update.png",
                "creditcards", "grooby", "icons/vr",
            ]):
                images.append(src)
    data["images"] = list(set(images))[:30]

    # Client reviews shown in sidebar #ReviewSection (also listed on id=998)
    data["reviews"] = extract_reviews_from_profile_html(
        html, profile_id, profile_name=data.get("name"),
    )

    return data


def extract_reviews_from_profile_html(html, profile_id, profile_name=None):
    """
    Parse reviews embedded in profile pages (div#ReviewSection): title, stars,
    author link to ?id=998&reviewid=...
    """
    reviews = []
    if not html:
        return reviews

    body = html
    if "<!-- BEGIN WAYBACK TOOLBAR" in body:
        body = re.split(r"<!-- END WAYBACK TOOLBAR", body, maxsplit=1)[-1]

    start = body.find('<div id="ReviewSection">')
    if start == -1:
        return reviews
    end = body.find("<!--BANNER_", start)
    if end == -1:
        block = body[start:]
    else:
        block = body[start:end]

    # One or more: h3 title, linked stars, ReviewAuthor
    entry_re = re.compile(
        r'<h3><a\s+href="[^"]*reviewid=(\d+)[^"]*">([^<]*)</a></h3>\s*'
        r'<a[^>]*>\s*<div style="white-space: nowrap;">(.*?)</div>\s*</a>'
        r'(?:<br\s*/?>)?\s*<span class="ReviewAuthor">([^<]*)</span>',
        re.DOTALL | re.IGNORECASE,
    )
    for match in entry_re.finditer(block):
        rid, title, stars_html, author = match.groups()
        rating = stars_html.count("star-icon full")
        reviews.append({
            "review_id": rid,
            "title": title.strip(),
            "profile_id": str(profile_id),
            "profile_name": (profile_name or "").strip(),
            "author": author.strip(),
            "rating": rating,
            "source": "profile_embed",
        })

    if not reviews:
        # Fallback: any reviewid in ReviewSection with h3 title
        for m in re.finditer(
            r'<h3><a\s+href="[^"]*reviewid=(\d+)[^"]*">([^<]*)</a></h3>',
            block,
            re.IGNORECASE,
        ):
            reviews.append({
                "review_id": m.group(1),
                "title": m.group(2).strip(),
                "profile_id": str(profile_id),
                "profile_name": (profile_name or "").strip(),
                "author": "",
                "rating": 0,
                "source": "profile_embed_fallback",
            })

    return reviews


def extract_reviews_from_html(html):
    """Extract review rows from review listing pages (id=998)."""
    reviews = []
    if not html:
        return reviews

    # Strip Wayback toolbar noise for more reliable matching
    body = html
    if "<!-- BEGIN WAYBACK TOOLBAR" in body:
        body = re.split(r"<!-- END WAYBACK TOOLBAR", body, maxsplit=1)[-1]

    # Full row: title, profile link, stars, author, date label
    review_pattern = re.compile(
        r'<h2><a\s+href="[^"]*reviewid=(\d+)[^"]*">([^<]*)</a>'
        r'.*?'
        r'(?:Reseña de|Review of|Review from|Review for)\s*:\s*'
        r'<a[^>]*profileid=(\d+)[^>]*>([^<]+)</a>'
        r'.*?'
        r'((?:<span class="star-icon[^"]*">[^<]*</span>\s*)+)'
        r'.*?'
        r'<br\s*/?>\s*([^,<]+),\s*(?:Publicado|Published|Posted)\s*:',
        re.IGNORECASE | re.DOTALL,
    )

    for match in review_pattern.finditer(body):
        review_id = match.group(1)
        title = match.group(2).strip()
        profile_id = match.group(3)
        profile_name = match.group(4).strip()
        stars_html = match.group(5)
        author = re.sub(r'<[^>]+>', '', match.group(6)).strip()

        star_count = stars_html.count("star-icon full")

        reviews.append({
            "review_id": review_id,
            "title": title,
            "profile_id": profile_id,
            "profile_name": profile_name,
            "author": author,
            "rating": star_count,
            "source": "review_listing",
        })

    # Fallback: at least collect reviewid + profileid from each row block
    if not reviews:
        row_blocks = re.findall(
            r'<div class="large-9 columns">(.{200,1200}?)</div>\s*</div>\s*<div class="row">',
            body,
            re.DOTALL,
        )
        for block in row_blocks:
            rid_m = re.search(r'reviewid=(\d+)', block)
            pid_m = re.search(r'profileid=(\d+)', block)
            title_m = re.search(
                r'<h2><a[^>]*>([^<]*)</a></h2>', block, re.IGNORECASE
            )
            if rid_m and pid_m:
                reviews.append({
                    "review_id": rid_m.group(1),
                    "title": (
                        title_m.group(1).strip() if title_m else ""
                    ),
                    "profile_id": pid_m.group(1),
                    "source": "review_listing_fallback",
                })

    # Review IDs only (for pagination / partial pages)
    review_links = re.findall(r'reviewid=(\d+)', body)
    found_ids = {r["review_id"] for r in reviews}
    for rid in set(review_links) - found_ids:
        reviews.append({
            "review_id": rid,
            "source": "review_link_only",
        })

    return reviews


def extract_listing_data(html, listing_type, listing_id):
    """Extract listing data (country/city/region) from raw HTML."""
    data = {
        "type": listing_type,
        "id": listing_id,
        "title": None,
        "profiles_found": [],
        "raw_html_snippet": html[:3000] if html else None
    }

    if not html:
        return data

    title_match = re.search(
        r'<title[^>]*>([^<]+)</title>', html, re.IGNORECASE
    )
    if title_match:
        data["title"] = title_match.group(1).strip()

    profile_links = re.findall(r'profileid=(\d+)', html)
    data["profiles_found"] = list(set(profile_links))

    return data


# ═══════════════════════════════════════════════════════════════
#  PASO 5: EJECUTAR LA RECUPERACION COMPLETA
# ═══════════════════════════════════════════════════════════════

def run_recovery(url_map, max_pages=MAX_PAGES):
    """Download and extract content from all catalogued pages."""
    all_profiles  = {}
    all_listings  = {}
    errors        = []
    downloaded    = 0

    # ─── Descargar PERFILES ───
    log.info("\n" + "=" * 50)
    log.info(
        "DESCARGANDO PERFILES (%d encontrados)",
        len(url_map["profile"]),
    )
    log.info("=" * 50)

    for pid, meta in list(url_map["profile"].items())[:max_pages]:
        if downloaded >= max_pages:
            log.info("Limite de %d paginas alcanzado", max_pages)
            break

        html_path = OUTPUT_DIR / "html" / ("profile_%s.html" % pid)
        if html_path.exists():
            log.info("  Perfil %s ya en disco, re-parseando...", pid)
            html_disk = html_path.read_text(encoding="utf-8")
            all_profiles[pid] = extract_profile_data(
                html_disk, pid, meta["url"],
            )
            downloaded += 1
            continue

        log.info(
            "  Perfil %s (%s) -> %s...", pid, meta["lang"], meta["url"][:60]
        )
        html = download_page(meta["url"], meta["timestamp"])

        if html:
            profile_data = extract_profile_data(html, pid, meta["url"])
            all_profiles[pid] = profile_data

            html_path = OUTPUT_DIR / "html" / ("profile_%s.html" % pid)
            html_path.write_text(html, encoding="utf-8")
            downloaded += 1
        else:
            errors.append({"type": "profile", "id": pid, "url": meta["url"]})
            log.warning("  No se pudo descargar perfil %s", pid)

        time.sleep(DELAY_SECONDS)

    # ─── Descargar LISTADOS POR PAIS ───
    log.info("\n" + "=" * 50)
    log.info(
        "DESCARGANDO PAISES (%d encontrados)",
        len(url_map["country"]),
    )
    log.info("=" * 50)

    for cid, meta in list(url_map["country"].items())[:200]:
        log.info("  Pais %s -> descargando...", cid)
        html = download_page(meta["url"], meta["timestamp"])

        if html:
            listing_data = extract_listing_data(html, "country", cid)
            all_listings["country_%s" % cid] = listing_data

            for new_pid in listing_data["profiles_found"]:
                if (new_pid not in url_map["profile"]
                        and new_pid not in all_profiles):
                    log.info("    -> Nuevo perfil encontrado: %s", new_pid)
        else:
            errors.append({"type": "country", "id": cid, "url": meta["url"]})

        time.sleep(DELAY_SECONDS)

    # ─── Descargar LISTADOS POR CIUDAD ───
    log.info("\n" + "=" * 50)
    log.info(
        "DESCARGANDO CIUDADES (%d encontradas)",
        len(url_map["city"]),
    )
    log.info("=" * 50)

    for cid, meta in list(url_map["city"].items())[:300]:
        html = download_page(meta["url"], meta["timestamp"])

        if html:
            listing_data = extract_listing_data(html, "city", cid)
            all_listings["city_%s" % cid] = listing_data

        time.sleep(DELAY_SECONDS)

    # ─── Descargar REVIEW LISTING PAGES (id=998, paginadas) ───
    log.info("\n" + "=" * 50)
    log.info("DESCARGANDO REVIEW LISTING PAGES (id=998)")
    log.info("=" * 50)

    all_reviews = []
    # Most ?id=998&p=N URLs are not in Wayback CDX; page 0 per tab is reliable.
    max_review_pages = 1
    ethnicities = ["", "1", "2", "3", "4", "5"]
    review_lan = "es"

    log.info(
        "Review listings: lan=%s (CDX + fallbacks + /web/2/ latest per URL)",
        review_lan,
    )

    for eid in ethnicities:
        eid_label = eid if eid else "all"
        for page_num in range(max_review_pages):
            fname = "reviewlist_e%s_p%d.html" % (eid_label, page_num)
            review_html_path = OUTPUT_DIR / "html" / fname

            if review_html_path.exists():
                html = review_html_path.read_text(encoding="utf-8")
            else:
                review_url = review_listing_original_url(
                    eid, page_num, lan=review_lan
                )
                log.info(
                    "  Reviews eid=%s page %d -> %s",
                    eid_label, page_num, review_url,
                )
                html, ts_label = download_review_listing_html(review_url)
                if html:
                    review_html_path.write_text(html, encoding="utf-8")
                    log.info("    -> OK (%s)", ts_label)
                else:
                    log.info(
                        "  Sin HTML util para eid=%s page %d",
                        eid_label, page_num,
                    )
                    break
                time.sleep(DELAY_SECONDS)

            if html:
                n_rid = len(re.findall(r'reviewid=\d+', html))
                extracted = extract_reviews_from_html(html)
                all_reviews.extend(extracted)
                log.info(
                    "    -> %d entradas parseadas, %d reviewid en HTML "
                    "(eid=%s p=%d)",
                    len(extracted), n_rid, eid_label, page_num,
                )
                if n_rid == 0:
                    log.info(
                        "  Fin paginacion eid=%s (sin reviewid en HTML)",
                        eid_label,
                    )
                    break

    # Deduplicate reviews by review_id
    seen_ids = set()
    unique_reviews = []
    for rev in all_reviews:
        rid = rev.get("review_id")
        if rid and rid not in seen_ids:
            seen_ids.add(rid)
            unique_reviews.append(rev)
        elif not rid:
            unique_reviews.append(rev)

    # Save reviews JSON
    reviews_path = OUTPUT_DIR / "json" / "reviews.json"
    reviews_path.write_text(
        json.dumps(unique_reviews, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    log.info("Reviews guardados: %d reviews unicos", len(unique_reviews))

    # Also group reviews by profile_id
    reviews_by_profile = {}
    for rev in unique_reviews:
        pid = rev.get("profile_id")
        if pid:
            if pid not in reviews_by_profile:
                reviews_by_profile[pid] = []
            reviews_by_profile[pid].append(rev)

    reviews_by_profile_path = OUTPUT_DIR / "json" / "reviews_by_profile.json"
    reviews_by_profile_path.write_text(
        json.dumps(reviews_by_profile, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    log.info(
        "Reviews por perfil: %d perfiles con reviews",
        len(reviews_by_profile),
    )

    # ─── GUARDAR RESULTADOS ───
    log.info("\n" + "=" * 50)
    log.info("GUARDANDO RESULTADOS")
    log.info("=" * 50)

    profiles_path = OUTPUT_DIR / "json" / "profiles.json"
    listings_path = OUTPUT_DIR / "json" / "listings.json"
    errors_path   = OUTPUT_DIR / "json" / "errors.json"
    summary_path  = OUTPUT_DIR / "json" / "summary.json"

    profiles_path.write_text(
        json.dumps(all_profiles, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    listings_path.write_text(
        json.dumps(all_listings, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    errors_path.write_text(
        json.dumps(errors, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    recovery_summary = {
        "total_profiles_downloaded": len(all_profiles),
        "total_listings_downloaded": len(all_listings),
        "total_errors": len(errors),
        "total_pages_in_archive": {
            "profiles": len(url_map["profile"]),
            "videos":   len(url_map["video"]),
            "countries": len(url_map["country"]),
            "cities":    len(url_map["city"]),
            "regions":   len(url_map["region"]),
        }
    }
    summary_path.write_text(
        json.dumps(recovery_summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    log.info("Perfiles descargados : %d", len(all_profiles))
    log.info("Listados descargados : %d", len(all_listings))
    log.info("Errores              : %d", len(errors))
    log.info("Archivos guardados en: %s/", OUTPUT_DIR)

    return recovery_summary


# ═══════════════════════════════════════════════════════════════
#  PASO 6: GENERAR SITE ESTATICO HTML
# ═══════════════════════════════════════════════════════════════

def generate_static_site():
    """Delegate to build_recovery_site.py for full relaunch-ready output."""
    try:
        from build_recovery_site import build_site
    except ImportError:
        log.error(
            "build_recovery_site.py not found (same folder as this script)."
        )
        return None

    profiles_path = OUTPUT_DIR / "json" / "profiles.json"
    if not profiles_path.exists():
        log.error(
            "No hay perfiles recuperados todavia. Ejecuta el recovery primero."
        )
        return None

    site_dir, n_prof, n_rev = build_site(OUTPUT_DIR / "site")
    log.info("Sitio estatico generado en: %s/", site_dir)
    log.info("   %d perfiles, %d filas de reviews en indice", n_prof, n_rev)
    return site_dir


# ═══════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("""
============================================================
   SHEMALEWIKI.COM - RECUPERADOR DE WAYBACK MACHINE
============================================================
""")

    map_path = OUTPUT_DIR / "json" / "url_map.json"
    if map_path.exists():
        log.info("Usando url_map.json cacheado desde ejecucion anterior")
        url_map = json.loads(map_path.read_text(encoding="utf-8"))
    else:
        cdx_urls = fetch_cdx_index(limit=5000)

        if not cdx_urls:
            print("No se pudo obtener el indice. Verifica tu conexion.")
            exit(1)

        url_map = build_url_map(cdx_urls)

        map_path.parent.mkdir(parents=True, exist_ok=True)
        map_path.write_text(
            json.dumps(url_map, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        log.info("Mapa de URLs guardado en %s", map_path)

    total = sum([
        len(url_map["profile"]),
        len(url_map["country"]),
        len(url_map["city"])
    ])
    print("\nResumen de lo que se va a descargar:")
    print("   Perfiles  : %d" % len(url_map["profile"]))
    print("   Paises    : %d" % len(url_map["country"]))
    print("   Ciudades  : %d" % len(url_map["city"]))
    print("   Regiones  : %d" % len(url_map["region"]))
    print("   Videos    : %d" % len(url_map["video"]))
    print("\n   Tiempo estimado: ~%d minutos" % (total * DELAY_SECONDS / 60))
    print("   (con %ss de pausa entre requests)" % DELAY_SECONDS)

    summary = run_recovery(url_map)

    generate_static_site()

    print("""
============================================================
   RECUPERACION COMPLETADA

   Archivos en: shemalewiki_recovery/
   html/       -> HTML original de cada pagina
   json/       -> Datos estructurados
     profiles.json   -> Todos los perfiles
     listings.json   -> Paises/ciudades
     summary.json    -> Resumen estadistico
     url_map.json    -> Mapa completo de URLs
   site/       -> Sitio HTML listo para subir
============================================================
""")
