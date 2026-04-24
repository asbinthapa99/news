# ── PyCast News — Configuration ────────────────────────────────────────────────
import os
from dotenv import load_dotenv

load_dotenv()   # reads DATABASE_URL (and any other vars) from .env


def _env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}

# Change REFRESH_INTERVAL_HOURS to set how often the backend fetches fresh news.
# 1 = every hour, 5 = every 5 hours, etc.
REFRESH_INTERVAL_HOURS = 1
REFRESH_INTERVAL_MS    = REFRESH_INTERVAL_HOURS * 3600 * 1000  # sent to frontend JS

# Runtime flags for deployment targets.
IS_VERCEL = _env_bool("VERCEL", False)
ENABLE_SCHEDULER = _env_bool("ENABLE_SCHEDULER", not IS_VERCEL)
CRON_SECRET = os.environ.get("CRON_SECRET", "")

# Scraper tuning for serverless limits.
SCRAPER_TIMEOUT_SECONDS = int(os.environ.get("SCRAPER_TIMEOUT_SECONDS", "8"))
SCRAPER_MAX_WORKERS = int(os.environ.get("SCRAPER_MAX_WORKERS", "8"))

# PostgreSQL connection string — set in .env (never commit that file)
DATABASE_URL = os.environ.get("DATABASE_URL", "")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set. Add it to your .env file.")

MAX_ARTICLES = 300   # maximum rows kept in the database (oldest are trimmed)

# ── RSS feed sources ────────────────────────────────────────────────────────────
# All sources below include images in their feeds (media:thumbnail / enclosure).
# PyPI New Packages and Python Insider removed — no images, spammy volume.
RSS_FEEDS = [
    # AI & Technology (image-rich)
    {"name": "TechCrunch",           "url": "https://techcrunch.com/feed/",                                    "category": "AI & Tech"},
    {"name": "The Verge",            "url": "https://www.theverge.com/rss/index.xml",                         "category": "AI & Tech"},
    {"name": "Ars Technica",         "url": "https://feeds.arstechnica.com/arstechnica/index",                 "category": "AI & Tech"},
    {"name": "Wired",                "url": "https://www.wired.com/feed/rss",                                  "category": "AI & Tech"},
    {"name": "VentureBeat",          "url": "https://venturebeat.com/feed/",                                   "category": "AI & Tech"},
    {"name": "MIT Tech Review",      "url": "https://www.technologyreview.com/feed/",                          "category": "AI & Tech"},
    # World news (image-rich)
    {"name": "BBC News",             "url": "http://feeds.bbci.co.uk/news/rss.xml",                           "category": "World"},
    {"name": "Al Jazeera",           "url": "https://www.aljazeera.com/xml/rss/all.xml",                      "category": "World"},
    {"name": "NPR",                  "url": "https://feeds.npr.org/1001/rss.xml",                              "category": "World"},
    {"name": "The Guardian",         "url": "https://www.theguardian.com/world/rss",                           "category": "World"},
    # Science & Space
    {"name": "NASA",                 "url": "https://www.nasa.gov/rss/dyn/breaking_news.rss",                  "category": "Science"},
    {"name": "New Scientist",        "url": "https://www.newscientist.com/feed/home/",                         "category": "Science"},
    # Python / Dev
    {"name": "Real Python",          "url": "https://realpython.com/atom.xml",                                 "category": "Python"},
    {"name": "Hacker News",          "url": "https://hnrss.org/frontpage",                                     "category": "Tech"},
]
