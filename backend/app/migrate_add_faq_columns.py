"""
One-time migration for anyone who already has an orbit.db from before the
FAQ table gained category/image_url/image_alt columns.

SQLAlchemy's create_all() only creates *missing* tables — it never alters
an existing one, so on an existing database this script is required for
the new columns to show up. It's safe to run more than once (it checks
which columns already exist first) and it only touches the `faqs` table;
your students, teachers, departments, attendance, and marks are untouched.

Usage:
    python -m app.migrate_add_faq_columns
"""

import sqlite3

from .database import SQLALCHEMY_DATABASE_URL

DB_PATH = SQLALCHEMY_DATABASE_URL.replace("sqlite:///", "")

NEW_COLUMNS = {
    "category": "TEXT",
    "image_url": "TEXT",
    "image_alt": "TEXT",
}


def run():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='faqs'")
    if not cur.fetchone():
        conn.close()
        print("No 'faqs' table found yet — this is a fresh database. Just run "
              "`python -m app.seed` (or start the server, which auto-creates tables); "
              "no migration needed.")
        return

    cur.execute("PRAGMA table_info(faqs)")
    existing_columns = {row[1] for row in cur.fetchall()}

    added = []
    for col, col_type in NEW_COLUMNS.items():
        if col not in existing_columns:
            cur.execute(f"ALTER TABLE faqs ADD COLUMN {col} {col_type}")
            added.append(col)

    conn.commit()
    conn.close()

    if added:
        print(f"Added columns to faqs table: {', '.join(added)}")
    else:
        print("faqs table already has category/image_url/image_alt — nothing to do.")


if __name__ == "__main__":
    run()
