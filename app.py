"""
PyCast News — Flask application
================================
Routes
------
  GET  /              Renders the single-page frontend
  GET  /api/news      JSON list of articles  (?page=1&limit=6&category=World)
  GET  /api/stats     JSON counts: total_articles, total_sources, last_updated
  GET  /api/ticker    JSON list of recent headlines for the scrolling ticker
  GET  /api/categories JSON list of available category names
  POST /api/refresh   Trigger an immediate scrape (manual refresh button)
    GET/POST /api/cron  Protected cron scrape trigger (Vercel)

Background scheduling
---------------------
On persistent hosts, APScheduler runs `run_scrape()` in a daemon thread every
config.REFRESH_INTERVAL_HOURS hours. On Vercel, scheduling is handled by
Vercel Cron calling /api/cron.
"""

import atexit
import hmac
import threading

from flask import Flask, jsonify, render_template, request
from apscheduler.schedulers.background import BackgroundScheduler

import config
import database
import scraper

# ── Flask app ───────────────────────────────────────────────────────────────────
app = Flask(__name__)

# ── Database bootstrap ──────────────────────────────────────────────────────────
database.init_db()

# ── Scrape logic ────────────────────────────────────────────────────────────────
_scrape_lock = threading.Lock()   # prevents two simultaneous scrapes

def run_scrape():
    """Fetch all RSS feeds and persist new articles to PostgreSQL."""
    if not _scrape_lock.acquire(blocking=False):
        print("[scheduler] Scrape already running — skipping this trigger.")
        return False
    try:
        print("\n[scheduler] Starting news refresh…")
        articles = scraper.scrape_all()
        n = database.save_articles(articles)
        print(f"[scheduler] Done — {n} new articles saved.\n")
        return True
    finally:
        _scrape_lock.release()

# ── APScheduler setup ───────────────────────────────────────────────────────────
scheduler = None
if config.ENABLE_SCHEDULER:
    scheduler = BackgroundScheduler(daemon=True)

    # Run once immediately at startup, then on the configured interval
    scheduler.add_job(run_scrape, "date",     id="initial_scrape")
    scheduler.add_job(run_scrape, "interval", id="recurring",
                      hours=config.REFRESH_INTERVAL_HOURS)

    scheduler.start()
    atexit.register(lambda: scheduler.shutdown(wait=False))

# ── Routes ──────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template(
        "index.html",
        refresh_interval_ms=config.REFRESH_INTERVAL_MS,
    )


@app.route("/api/news")
def api_news():
    page     = request.args.get("page",     1,    type=int)
    limit    = request.args.get("limit",    6,    type=int)
    category = request.args.get("category", None)

    # Clamp limit to avoid accidental huge queries
    limit = min(limit, 50)

    articles = database.get_articles(page=page, limit=limit, category=category)
    total    = database.get_total_count(category=category)

    return jsonify({
        "articles": articles,
        "total":    total,
        "page":     page,
        "limit":    limit,
    })


@app.route("/api/stats")
def api_stats():
    return jsonify(database.get_stats())


@app.route("/api/ticker")
def api_ticker():
    return jsonify(database.get_recent_titles(14))


@app.route("/api/categories")
def api_categories():
    return jsonify(database.get_categories())


@app.route("/api/refresh", methods=["POST"])
def api_refresh():
    if config.IS_VERCEL:
        ok = run_scrape()
        if not ok:
            return jsonify({"ok": False, "message": "Scrape already running."}), 409
        return jsonify({"ok": True, "message": "Scrape completed."})

    # Fire scrape in a background thread so the HTTP response returns instantly
    threading.Thread(target=run_scrape, daemon=True).start()
    return jsonify({"ok": True, "message": "Scrape started in background."})


@app.route("/api/cron", methods=["GET", "POST"])
def api_cron():
    expected_secret = config.CRON_SECRET
    if not expected_secret:
        return jsonify({"ok": False, "message": "CRON_SECRET is not configured."}), 500

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return jsonify({"ok": False, "message": "Unauthorized."}), 401

    token = auth_header.split(" ", 1)[1]
    if not hmac.compare_digest(token, expected_secret):
        return jsonify({"ok": False, "message": "Unauthorized."}), 401

    ok = run_scrape()
    if not ok:
        return jsonify({"ok": False, "message": "Scrape already running."}), 409

    return jsonify({"ok": True, "message": "Cron scrape completed."}), 200


@app.route("/health")
def health():
    """Used by Railway / Render / Docker health checks."""
    return jsonify({"status": "ok"}), 200


# ── Dev entry point ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # use_reloader=False stops Flask's reloader from spawning a second scheduler
    app.run(debug=True, use_reloader=False, port=5000)
