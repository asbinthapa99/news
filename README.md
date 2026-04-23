# PyCast — Automated Python & World News

A fully automated news aggregator. The Flask backend scrapes 14 RSS feeds on a configurable schedule, stores articles in Neon PostgreSQL, and serves them through a JSON API. The frontend renders everything in real-time with no page reloads.

The app supports both deployment models:
- **Vercel (serverless):** Vercel Cron calls `/api/cron` hourly.
- **Persistent hosts (Railway / Render / Docker):** APScheduler runs in-process.

---

## How it works (fully automated)

```
Vercel mode (serverless)
  Vercel Cron (hourly)
    → GET /api/cron (Authorization: Bearer $CRON_SECRET)
    → scraper.py fetches feeds concurrently
    → database.py saves new articles to Neon PostgreSQL (duplicates skipped)

Persistent-host mode (Railway / Render / Docker)
  APScheduler (background thread)
    → scraper.py fetches feeds concurrently
    → database.py saves new articles to Neon PostgreSQL (duplicates skipped)

Every page load / N hours
  Browser JS polls /api/news
    → fresh cards render without a full reload
```

No manual scripts to run after initial deploy.

---

## Features

- **Multi-source RSS scraping** — Planet Python, Real Python, BBC News, Reuters, TechCrunch, Ars Technica, Hacker News, NASA, and more (14 sources).
- **Thumbnail extraction** — pulls images from `media:thumbnail`, `media:content`, enclosures, and inline `<img>` tags.
- **Duplicate prevention** — `UNIQUE` constraint on `link`; duplicates silently skipped on every scrape.
- **Graceful error handling** — a failed feed logs a one-liner and is skipped; the rest continues.
- **Concurrent feed fetching** — feeds are fetched in parallel to reduce total refresh time.
- **Category filter tabs** — Python / World / Technology / Science / Tech (auto-populated from DB).
- **Pagination** — 6 cards per page, prev/next controls.
- **Manual refresh button** — POSTs to `/api/refresh`, waits 3 s, re-renders the grid.

---

## Tech Stack

| Layer | Tool |
|---|---|
| Web framework | Flask 3 |
| WSGI server | Gunicorn |
| RSS parsing | feedparser 6 |
| HTML stripping | BeautifulSoup 4 + lxml |
| HTTP client | requests |
| Scheduling | Vercel Cron (serverless) or APScheduler 3 (persistent hosts) |
| Database | PostgreSQL on Neon (psycopg2-binary) |
| Config / secrets | python-dotenv |
| CI/CD | GitHub Actions |
| Container | Docker |
| Frontend | Vanilla JS + Fetch API |

---

## Project Structure

```
news-1/
├── .env                          # DATABASE_URL — never commit this
├── .gitignore
├── .github/
│   └── workflows/
│       └── ci.yml                # Validates + builds Docker on every push
├── app.py                        # Flask routes + APScheduler setup
├── config.py                     # All tunable settings (loads .env)
├── scraper.py                    # RSS feed fetcher and thumbnail extractor
├── database.py                   # PostgreSQL helpers (init, save, query)
├── requirements.txt
├── Procfile                      # For Railway / Heroku
├── Dockerfile                    # For any container platform
├── docker-compose.yml            # Local Docker dev
├── vercel.json                   # Vercel serverless + cron config
├── railway.json                  # Railway deployment config
├── render.yaml                   # Render.com deployment config
└── templates/
    └── index.html                # Single-page frontend (Jinja2 template)
```

---

## Local development (zero setup)

```bash
git clone <your-repo>
cd news-1

python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# .env already contains DATABASE_URL — just run:
python app.py
```

Open [http://localhost:5000](http://localhost:5000). News appears within ~15 seconds.

---

## Deploy to Vercel (recommended for this repo)

1. Push this repo to GitHub
2. Go to [vercel.com](https://vercel.com) → **Add New Project**
3. Import this repository
4. In **Environment Variables**, set:
  ```
  DATABASE_URL = <your Neon connection string>
  CRON_SECRET = <a strong random secret>
  VERCEL = 1
  ENABLE_SCHEDULER = 0
  SCRAPER_TIMEOUT_SECONDS = 8
  SCRAPER_MAX_WORKERS = 8
  ```
5. Deploy

`vercel.json` configures an hourly cron to call `/api/cron`.
Vercel automatically sends `Authorization: Bearer <CRON_SECRET>` for cron invocations when `CRON_SECRET` is set.

Notes:
- On Vercel Hobby, function duration is strict. Keep feed timeouts low and use concurrency.
- On Pro, higher execution limits give more headroom.

---

## Deploy to Railway (alternative — persistent host)

**One-time setup (~5 minutes):**

1. Push this repo to GitHub
2. Go to [railway.app](https://railway.app) → **New Project → Deploy from GitHub repo**
3. Select this repo
4. Go to **Variables** tab → add:
   ```
   DATABASE_URL = <your Neon connection string>
   ```
5. Click **Deploy**

That's it. Railway reads `railway.json` and `Dockerfile` automatically. Every future `git push` to `main` triggers a new deploy — GitHub Actions validates the code first, then Railway picks it up.

---

## Deploy to Render (alternative — persistent host)

1. Push this repo to GitHub
2. Go to [render.com](https://render.com) → **New Web Service → Connect repo**
3. Render auto-detects `render.yaml`
4. Set `DATABASE_URL` in the Environment section
5. Click **Create Web Service**

Auto-deploys on every push to `main`.

---

## Deploy with Docker (any VPS / cloud)

```bash
# Build
docker build -t pycast-news .

# Run (reads DATABASE_URL from .env)
docker run -d --env-file .env -p 5000:8080 --restart unless-stopped pycast-news
```

Or with Docker Compose:
```bash
docker compose up -d
```

---

## CI/CD pipeline (GitHub Actions)

On every push or PR to `main`, `.github/workflows/ci.yml` runs automatically:

| Step | What it does |
|---|---|
| **Validate** | Installs deps, checks Python syntax, verifies all modules import |
| **Docker build** | Builds the Docker image to catch any container issues |

If either step fails, the PR is blocked. Railway / Render only deploy after checks pass.

---

## Configuration

All tunable settings are in `config.py`:

```python
REFRESH_INTERVAL_HOURS = 1   # 1 = hourly, 5 = every 5 hours
MAX_ARTICLES = 300           # oldest rows trimmed beyond this
SCRAPER_TIMEOUT_SECONDS = 8
SCRAPER_MAX_WORKERS = 8
```

`DATABASE_URL` is loaded from `.env` — edit that file to point at a different database.

Additional env vars:
- `VERCEL=1` enables serverless runtime mode.
- `ENABLE_SCHEDULER=0` disables APScheduler (recommended on Vercel).
- `CRON_SECRET` is required for `/api/cron` authorization.

To add a news source, append to `RSS_FEEDS` in `config.py`:
```python
{"name": "My Blog", "url": "https://example.com/feed.xml", "category": "Tech"}
```

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Frontend |
| `GET` | `/health` | Health check (used by Railway / Render / Docker) |
| `GET` | `/api/news` | Articles (`?page=1&limit=6&category=World`) |
| `GET` | `/api/stats` | `total_articles`, `total_sources`, `last_updated` |
| `GET` | `/api/ticker` | Latest 14 headlines |
| `GET` | `/api/categories` | Distinct category names |
| `POST` | `/api/refresh` | Trigger an immediate scrape |
| `GET` / `POST` | `/api/cron` | Protected cron trigger (Vercel) |

---

## Color Scheme

| Token | Hex |
|---|---|
| Background | `#0d0e0f` |
| Surface | `#141516` |
| Primary accent (lime) | `#c8f135` |
| Secondary accent (mint) | `#3bffbd` |

---

## License

MIT
