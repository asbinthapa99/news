# PyCast News

A fully automated news aggregator built with Flask and PostgreSQL. Scrapes 14 image-rich RSS feeds every hour, stores articles in Neon PostgreSQL, and serves them through a JSON API consumed by a real-time dark-theme frontend — no page reloads, no manual intervention needed after the first deploy.

---

## How it works

```
GitHub Actions (free, hourly cron)
  → POST /api/refresh on Vercel
  → scraper.py fetches 14 feeds concurrently (ThreadPoolExecutor)
  → database.py inserts new articles into Neon PostgreSQL
    (ON CONFLICT DO NOTHING — duplicates silently skipped)
  → oldest rows trimmed to keep MAX_ARTICLES = 300

Browser
  → polls /api/news every hour via Fetch API
  → re-renders news cards without a full page reload
  → manual Refresh button triggers an immediate scrape
```

On persistent hosts (Railway / Render / Docker) APScheduler runs the same loop in-process — no GitHub Actions needed.

---

## Features

- **14 image-rich RSS sources** — TechCrunch, The Verge, Wired, VentureBeat, Ars Technica, MIT Tech Review, BBC News, Al Jazeera, NPR, The Guardian, NASA, New Scientist, Real Python, Hacker News
- **Thumbnail extraction** — 4 fallback strategies: `media:thumbnail`, `media:content`, enclosure, inline `<img>` tag
- **Category filter tabs** — AI & Tech / World / Science / Python / Tech (auto-populated from DB)
- **Pagination** — 6 cards per page, prev/next controls
- **Scrolling headline ticker** — latest 14 headlines from DB
- **Duplicate prevention** — `UNIQUE` constraint on article URL; duplicates skipped on every scrape
- **Concurrent scraping** — all feeds fetched in parallel to minimise refresh time
- **Graceful feed errors** — a failing feed logs a one-liner and is skipped; others continue
- **Manual refresh** — POST `/api/refresh` button re-scrapes immediately
- **Free CI/CD** — GitHub Actions validates syntax + builds Docker image on every push

---

## Tech Stack

| Layer | Tool |
|---|---|
| Web framework | Flask 3 |
| WSGI server | Gunicorn |
| RSS parsing | feedparser 6 |
| HTML stripping | BeautifulSoup 4 + lxml |
| HTTP client | requests |
| Scheduling | GitHub Actions cron (Vercel) · APScheduler 3 (persistent hosts) |
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
│       ├── ci.yml                # Syntax check + Docker build on every push
│       └── scrape.yml            # Hourly cron: POST /api/refresh on Vercel
├── api/
│   └── index.py                  # Vercel entry point (imports app from app.py)
├── templates/
│   └── index.html                # Single-page dark-theme frontend
├── app.py                        # Flask routes + APScheduler setup
├── config.py                     # All tunable settings (loads .env)
├── scraper.py                    # RSS feed fetcher + thumbnail extractor
├── database.py                   # PostgreSQL helpers (init, save, query)
├── requirements.txt
├── vercel.json                   # Vercel rewrite rule (routes everything to api/index)
├── Procfile                      # For Railway / Heroku
├── Dockerfile                    # For any container platform
├── docker-compose.yml            # Local Docker dev
├── railway.json                  # Railway deployment config
└── render.yaml                   # Render.com deployment config
```

---

## Local Development

```bash
git clone <your-repo>
cd news-1

python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Create .env with your Neon connection string:
echo 'DATABASE_URL=postgresql://user:pass@host/db' > .env

python app.py
```

Open [http://localhost:5000](http://localhost:5000). APScheduler runs a scrape immediately at startup — articles appear within ~15 seconds.

---

## Deploy to Vercel (recommended)

Vercel runs the Flask app as a serverless function. Hourly scraping is handled by a free GitHub Actions workflow — Vercel's built-in cron requires a paid plan.

### Step 1 — Deploy to Vercel

1. Push this repo to GitHub
2. Go to [vercel.com](https://vercel.com) → **Add New Project** → import this repo
3. In **Environment Variables**, add:

   | Variable | Value |
   |---|---|
   | `DATABASE_URL` | Your Neon connection string |
   | `VERCEL` | `1` |
   | `ENABLE_SCHEDULER` | `0` |
   | `SCRAPER_TIMEOUT_SECONDS` | `8` |
   | `SCRAPER_MAX_WORKERS` | `8` |

4. Click **Deploy**

### Step 2 — Set up hourly scraping via GitHub Actions

1. Copy your Vercel deployment URL (e.g. `https://your-app.vercel.app`)
2. In your GitHub repo → **Settings → Secrets and variables → Actions** → **New repository secret**:

   | Secret name | Value |
   |---|---|
   | `VERCEL_APP_URL` | `https://your-app.vercel.app` |

3. That's it. `.github/workflows/scrape.yml` runs at the top of every hour and POSTs to `/api/refresh`, which triggers a full scrape.

You can also trigger a manual run from **Actions → Hourly News Scrape → Run workflow**.

---

## Deploy to Railway (persistent host — alternative)

Railway runs the app as a long-lived process with APScheduler handling the hourly scrape in-process. No GitHub Actions cron needed.

1. Push this repo to GitHub
2. Go to [railway.app](https://railway.app) → **New Project → Deploy from GitHub repo**
3. Select this repo
4. **Variables** tab → add `DATABASE_URL`
5. Click **Deploy**

Railway reads `railway.json` and `Dockerfile` automatically. Every `git push main` triggers a new deploy after GitHub Actions CI passes.

---

## Deploy to Render (persistent host — alternative)

1. Push this repo to GitHub
2. Go to [render.com](https://render.com) → **New Web Service → Connect repo**
3. Render auto-detects `render.yaml`
4. Set `DATABASE_URL` in the Environment section
5. Click **Create Web Service**

Auto-deploys on every push to `main`.

---

## Deploy with Docker (any VPS)

```bash
# Build
docker build -t pycast-news .

# Run
docker run -d --env-file .env -p 5000:8080 --restart unless-stopped pycast-news
```

Or with Docker Compose:

```bash
docker compose up -d
```

---

## CI/CD Pipeline

Two GitHub Actions workflows run automatically:

### `ci.yml` — runs on every push and PR to `main`

| Step | What it does |
|---|---|
| **Validate** | Installs deps, compiles all `.py` files, verifies all modules import |
| **Docker build** | Builds the Docker image to catch container issues early |

Failed checks block merges to `main`.

### `scrape.yml` — runs every hour at `:00`

| Step | What it does |
|---|---|
| **Trigger scrape** | POSTs to `$VERCEL_APP_URL/api/refresh`; fails the run if the response is not HTTP 200 |

Can also be triggered manually via **Actions → Hourly News Scrape → Run workflow**.

---

## Configuration

All tunable settings live in `config.py`:

```python
REFRESH_INTERVAL_HOURS = 1   # how often APScheduler scrapes (persistent hosts)
MAX_ARTICLES = 300           # oldest rows trimmed when this limit is exceeded
SCRAPER_TIMEOUT_SECONDS = 8  # per-feed HTTP timeout
SCRAPER_MAX_WORKERS = 8      # parallel feed fetchers
```

Environment variables (set in `.env` locally, or in Vercel / Railway / Render dashboard):

| Variable | Description |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string (required) |
| `VERCEL` | Set to `1` on Vercel to enable serverless mode |
| `ENABLE_SCHEDULER` | Set to `0` to disable APScheduler (recommended on Vercel) |
| `CRON_SECRET` | Optional bearer token for the protected `/api/cron` endpoint |
| `SCRAPER_TIMEOUT_SECONDS` | Per-feed timeout in seconds (default: `8`) |
| `SCRAPER_MAX_WORKERS` | ThreadPoolExecutor worker count (default: `8`) |

### Adding a news source

Append to `RSS_FEEDS` in `config.py`:

```python
{"name": "My Blog", "url": "https://example.com/feed.xml", "category": "Tech"}
```

Categories shown in the filter tabs are auto-populated from whatever is in the database — no other changes needed.

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Frontend (single-page app) |
| `GET` | `/health` | Health check — returns `{"status": "ok"}` |
| `GET` | `/api/news` | Articles — supports `?page=1&limit=6&category=World` |
| `GET` | `/api/stats` | `{"total_articles", "total_sources", "last_updated"}` |
| `GET` | `/api/ticker` | Latest 14 headlines for the scrolling ticker |
| `GET` | `/api/categories` | Distinct category names currently in the DB |
| `POST` | `/api/refresh` | Trigger an immediate scrape (no auth required) |
| `GET/POST` | `/api/cron` | Protected scrape trigger — requires `Authorization: Bearer <CRON_SECRET>` |

`/api/news` response shape:

```json
{
  "articles": [
    {
      "id": 1,
      "title": "...",
      "summary": "...",
      "link": "https://...",
      "pub_date": "...",
      "image_url": "https://...",
      "source": "TechCrunch",
      "category": "AI & Tech",
      "created_at": "2026-04-24T13:00:00+00:00"
    }
  ],
  "total": 300,
  "page": 1,
  "limit": 6
}
```

---

## News Sources

| Source | Category |
|---|---|
| TechCrunch | AI & Tech |
| The Verge | AI & Tech |
| Ars Technica | AI & Tech |
| Wired | AI & Tech |
| VentureBeat | AI & Tech |
| MIT Tech Review | AI & Tech |
| BBC News | World |
| Al Jazeera | World |
| NPR | World |
| The Guardian | World |
| NASA | Science |
| New Scientist | Science |
| Real Python | Python |
| Hacker News | Tech |

All sources were selected for reliable image availability in their feeds (`media:thumbnail` / enclosure).

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
