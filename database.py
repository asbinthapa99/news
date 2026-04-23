"""
PostgreSQL data layer (Neon).

Every public function opens its own connection, commits, and closes it so
the code is safe to call from both the Flask request threads and the
APScheduler background thread.

psycopg2 placeholders use %s (not ? like SQLite).
Duplicate links are silently ignored via ON CONFLICT (link) DO NOTHING.
"""

from contextlib import contextmanager
from datetime import datetime

import psycopg2
import psycopg2.extras

import config


# ── Connection helper ───────────────────────────────────────────────────────────

@contextmanager
def _conn():
    """Yield an open connection; commit on success, rollback + close on error."""
    conn = psycopg2.connect(config.DATABASE_URL)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Schema ─────────────────────────────────────────────────────────────────────

def init_db():
    """Create the articles table if it doesn't already exist."""
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS articles (
                    id         SERIAL PRIMARY KEY,
                    title      TEXT    NOT NULL,
                    summary    TEXT,
                    link       TEXT    UNIQUE NOT NULL,
                    pub_date   TEXT,
                    image_url  TEXT,
                    source     TEXT,
                    category   TEXT,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            # Index for fast category + recency queries
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_articles_category_created
                ON articles (category, created_at DESC)
            """)


# ── Writes ─────────────────────────────────────────────────────────────────────

def save_articles(articles):
    """
    Insert new articles; skip duplicates via ON CONFLICT (link) DO NOTHING.
    Uses per-row savepoints so a single bad row never aborts the whole batch.
    After inserting, trims the table to MAX_ARTICLES rows (oldest removed).
    Returns the count of newly inserted rows.
    """
    new_count = 0
    with _conn() as conn:
        with conn.cursor() as cur:
            for a in articles:
                try:
                    cur.execute("SAVEPOINT sp")
                    cur.execute(
                        """
                        INSERT INTO articles
                            (title, summary, link, pub_date, image_url, source, category)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (link) DO NOTHING
                        """,
                        (
                            a["title"], a["summary"], a["link"],
                            a["pub_date"], a["image_url"],
                            a["source"],  a["category"],
                        ),
                    )
                    new_count += cur.rowcount   # 1 if inserted, 0 if duplicate
                    cur.execute("RELEASE SAVEPOINT sp")
                except psycopg2.Error as e:
                    cur.execute("ROLLBACK TO SAVEPOINT sp")
                    print(f"  [db] row error: {e}")

            # Keep only the most-recent MAX_ARTICLES rows
            cur.execute("""
                DELETE FROM articles
                WHERE id NOT IN (
                    SELECT id FROM articles ORDER BY created_at DESC LIMIT %s
                )
            """, (config.MAX_ARTICLES,))

    return new_count


# ── Reads ───────────────────────────────────────────────────────────────────────

def _row_to_dict(row):
    """Convert a RealDictRow to a plain dict, serialising datetime fields."""
    d = dict(row)
    # created_at is a Python datetime from psycopg2; make it JSON-safe
    if isinstance(d.get("created_at"), datetime):
        d["created_at"] = d["created_at"].isoformat()
    return d


def get_articles(page=1, limit=6, category=None):
    """Return a page of articles ordered by pub_date (newest first)."""
    offset = (page - 1) * limit
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            if category:
                cur.execute(
                    """
                    SELECT * FROM articles WHERE category = %s
                    ORDER BY pub_date DESC NULLS LAST, created_at DESC
                    LIMIT %s OFFSET %s
                    """,
                    (category, limit, offset),
                )
            else:
                cur.execute(
                    """
                    SELECT * FROM articles
                    ORDER BY pub_date DESC NULLS LAST, created_at DESC
                    LIMIT %s OFFSET %s
                    """,
                    (limit, offset),
                )
            return [_row_to_dict(r) for r in cur.fetchall()]


def get_total_count(category=None):
    with _conn() as conn:
        with conn.cursor() as cur:
            if category:
                cur.execute(
                    "SELECT COUNT(*) FROM articles WHERE category = %s", (category,)
                )
            else:
                cur.execute("SELECT COUNT(*) FROM articles")
            return cur.fetchone()[0]


def get_recent_titles(limit=14):
    """Latest headlines for the scrolling ticker."""
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT title FROM articles ORDER BY created_at DESC LIMIT %s",
                (limit,),
            )
            return [r[0] for r in cur.fetchall()]


def get_stats():
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM articles")
            total = cur.fetchone()[0]

            cur.execute("SELECT COUNT(DISTINCT source) FROM articles")
            sources = cur.fetchone()[0]

            cur.execute("SELECT MAX(created_at) FROM articles")
            last_up = cur.fetchone()[0]

    return {
        "total_articles": total,
        "total_sources":  sources,
        "last_updated":   last_up.isoformat() if last_up else None,
    }


def get_categories():
    """Distinct category names currently in the database."""
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT DISTINCT category FROM articles WHERE category IS NOT NULL ORDER BY category"
            )
            return [r[0] for r in cur.fetchall()]
