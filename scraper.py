"""
RSS feed scraper.
Fetches each feed via requests (with timeout), parses with feedparser,
extracts thumbnail URLs through multiple fallback strategies, and
returns a list of normalised article dicts.
"""

import re
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import feedparser
import requests
from bs4 import BeautifulSoup, MarkupResemblesLocatorWarning

import config

# Silence the spurious warning when feedparser gives us a bare URL as the summary
warnings.filterwarnings("ignore", category=MarkupResemblesLocatorWarning)

# Sent with every HTTP request so sites don't block the bot
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; PyCastBot/1.0; +https://pycast.dev)"}
TIMEOUT = config.SCRAPER_TIMEOUT_SECONDS


# ── Thumbnail extraction ────────────────────────────────────────────────────────

def _get_thumbnail(entry):
    """
    Try every common way RSS feeds embed images and return the first URL found.
    Returns an empty string if no image can be found.
    """
    # 1. media:thumbnail  (most common for news feeds)
    thumbs = getattr(entry, "media_thumbnail", None)
    if thumbs:
        return thumbs[0].get("url", "")

    # 2. media:content with an image mime-type or image file extension
    contents = getattr(entry, "media_content", None)
    if contents:
        for mc in contents:
            mime = mc.get("type", "")
            url  = mc.get("url", "")
            if "image" in mime or re.search(r"\.(jpe?g|png|webp|gif)(\?|$)", url, re.I):
                return url

    # 3. enclosure (podcasts and some news feeds)
    for enc in getattr(entry, "enclosures", []):
        if "image" in enc.get("type", ""):
            return enc.get("href", "")

    # 4. First <img> tag inside the summary / description / content fields
    for field in ("summary", "description", "content"):
        val = entry.get(field, "")
        if isinstance(val, list):          # 'content' is a list of dicts
            val = val[0].get("value", "") if val else ""
        if not val:
            continue
        m = re.search(r'<img[^>]+src=["\']([^"\']{20,})["\']', val)
        if m:
            url = m.group(1)
            # Skip 1×1 tracking pixels
            if not re.search(r'[?&](w|h|width|height)=[1-9]$', url):
                return url

    return ""


# ── Date parsing ────────────────────────────────────────────────────────────────

def _parse_date(entry):
    """Return an ISO-8601 string from feedparser's parsed time struct, or ''."""
    for attr in ("published_parsed", "updated_parsed"):
        t = getattr(entry, attr, None)
        if t:
            try:
                return datetime(*t[:6], tzinfo=timezone.utc).isoformat()
            except Exception:
                pass
    return ""


# ── Per-feed scrape ─────────────────────────────────────────────────────────────

def scrape_feed(feed_cfg):
    """
    Fetch and parse a single RSS feed.
    Returns a list of article dicts (may be empty on error).
    """
    articles = []
    try:
        resp = requests.get(feed_cfg["url"], headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
        feed = feedparser.parse(resp.content)

        for entry in feed.entries[:25]:   # cap per-feed to avoid memory spikes
            title = (entry.get("title") or "").strip()
            link  = (entry.get("link")  or "").strip()
            if not title or not link:
                continue

            # Pull the best available summary and strip HTML tags
            raw_summary = ""
            for field in ("summary", "description"):
                val = entry.get(field, "")
                if isinstance(val, list):
                    val = val[0].get("value", "") if val else ""
                if val:
                    raw_summary = val
                    break
            summary = BeautifulSoup(raw_summary, "html.parser").get_text()[:300].strip()

            articles.append({
                "title":     title,
                "summary":   summary,
                "link":      link,
                "pub_date":  _parse_date(entry),
                "image_url": _get_thumbnail(entry),
                "source":    feed_cfg["name"],
                "category":  feed_cfg.get("category", "News"),
            })

    except requests.exceptions.Timeout:
        print(f"  [scraper] ✗ {feed_cfg['name']}: timed out after {TIMEOUT}s")
    except requests.exceptions.HTTPError as e:
        print(f"  [scraper] ✗ {feed_cfg['name']}: HTTP {e.response.status_code}")
    except Exception as e:
        print(f"  [scraper] ✗ {feed_cfg['name']}: {e}")

    return articles


# ── Scrape everything ───────────────────────────────────────────────────────────

def scrape_all():
    """
    Scrape every feed in config.RSS_FEEDS concurrently.
    Final output preserves the original feed order.
    Returns a combined list of article dicts.
    """
    all_articles = []
    workers = max(1, min(config.SCRAPER_MAX_WORKERS, len(config.RSS_FEEDS)))
    ordered_batches = [None] * len(config.RSS_FEEDS)

    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_index = {
            executor.submit(scrape_feed, feed_cfg): idx
            for idx, feed_cfg in enumerate(config.RSS_FEEDS)
        }

        for future in as_completed(future_to_index):
            idx = future_to_index[future]
            feed_cfg = config.RSS_FEEDS[idx]
            try:
                ordered_batches[idx] = future.result()
            except Exception as e:
                print(f"  [scraper] ✗ {feed_cfg['name']}: {e}")
                ordered_batches[idx] = []
            print(f"  [scraper] ✓ {feed_cfg['name']}: {len(ordered_batches[idx])} articles")

    for batch in ordered_batches:
        all_articles.extend(batch)
    return all_articles
