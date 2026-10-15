"""
Imports a FAQ CSV into the real database (orbit.db).

Expected columns (case-insensitive, order doesn't matter):
    Question, Answer, Category (optional), Image (optional), Image_Alt (optional)

"Image" may be an absolute local path (e.g. from your own machine while
building the dataset) — it's automatically converted to a "/images/<file>"
web path. Copy the actual image files into orbit-backend/static/images/
so they're served at that path (see main.py's static mount).

This is an UPSERT by question text (case-insensitive): re-running the
script with an updated CSV updates existing FAQs in place instead of
duplicating them, so it's safe to use as a repeatable seed step.

Usage:
    python -m app.import_faqs path/to/your_faqs.csv
"""

import sys

from . import models
from .database import Base, SessionLocal, engine
from .faq_import import parse_faq_csv

Base.metadata.create_all(bind=engine)


def run(csv_path: str):
    with open(csv_path, "rb") as f:
        rows = parse_faq_csv(f)

    db = SessionLocal()
    inserted = updated = 0
    try:
        for row in rows:
            existing = (
                db.query(models.FAQ)
                .filter(models.FAQ.question.ilike(row["question"]))
                .first()
            )
            if existing:
                existing.answer = row["answer"]
                existing.category = row["category"]
                existing.image_url = row["image_url"]
                existing.image_alt = row["image_alt"]
                updated += 1
            else:
                db.add(models.FAQ(
                    question=row["question"],
                    answer=row["answer"],
                    category=row["category"],
                    image_url=row["image_url"],
                    image_alt=row["image_alt"],
                ))
                inserted += 1
        db.commit()
    finally:
        db.close()

    with_images = sum(1 for r in rows if r["image_url"])
    print(f"Parsed {len(rows)} clean, de-duplicated FAQ rows from {csv_path}")
    print(f"  -> {inserted} inserted, {updated} updated")
    print(f"  -> {with_images} of them have an image reference")
    print("Done. These are now live for the /chatbot/ask endpoint immediately.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python -m app.import_faqs path/to/your_faqs.csv")
        sys.exit(1)
    run(sys.argv[1])
