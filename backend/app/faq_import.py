"""
Shared CSV -> FAQ-row cleaning logic.

Used by both:
  - app/import_faqs.py         (one-off / repeatable local import script)
  - app/routers/faq.py's /faq/bulk endpoint (admin CSV upload from the UI)

so there's exactly one place that knows how to deal with messy source data:
blank rows, duplicate questions, and absolute Windows image paths exported
from someone's local machine.
"""

import csv
import io
import ntpath
import posixpath
from typing import IO, Dict, List, Union

# Column names are matched case-insensitively against these aliases, so the
# importer tolerates minor header differences between CSV exports.
COLUMN_ALIASES = {
    "question": {"question", "q"},
    "answer": {"answer", "a"},
    "category": {"category", "tag", "topic"},
    "image": {"image", "image_url", "imageurl", "image_path"},
    "image_alt": {"image_alt", "imagealt", "alt", "alt_text"},
}


def _normalize_headers(fieldnames: List[str]) -> Dict[str, str]:
    """Maps each actual CSV column name -> our canonical field name."""
    mapping = {}
    for raw in fieldnames or []:
        key = (raw or "").strip().lower().lstrip("\ufeff")  # strip BOM if present on the first header
        for canonical, aliases in COLUMN_ALIASES.items():
            if key in aliases:
                mapping[raw] = canonical
                break
    return mapping


def _clean_image_path(raw: str) -> str:
    """Turns an absolute local path (Windows or POSIX) into a web-servable
    '/images/<filename>' path. Leaves URLs (http/https) and already-relative
    paths untouched."""
    raw = (raw or "").strip()
    if not raw:
        return ""
    if raw.startswith("http://") or raw.startswith("https://") or raw.startswith("/"):
        return raw
    # Handle both Windows ("C:\...\file.png") and POSIX paths robustly,
    # regardless of which OS this import script runs on.
    filename = ntpath.basename(raw) if "\\" in raw else posixpath.basename(raw)
    return f"/images/{filename}" if filename else ""


def parse_faq_csv(file_obj: Union[IO[bytes], IO[str], bytes, str]) -> List[dict]:
    """Parses a FAQ CSV into a clean, deduplicated list of dicts:
    {question, answer, category, image_url, image_alt}

    Handles: UTF-8 BOM, blank/malformed rows, flexible column naming, and
    duplicate questions (later non-empty values win over earlier blanks —
    field by field — so a duplicate row that fills in a missing image
    doesn't get discarded in favor of an earlier, sparser one)."""
    if isinstance(file_obj, bytes):
        text = file_obj.decode("utf-8-sig")
        file_obj = io.StringIO(text)
    elif isinstance(file_obj, str):
        file_obj = io.StringIO(file_obj)
    elif hasattr(file_obj, "read"):
        raw = file_obj.read()
        text = raw.decode("utf-8-sig") if isinstance(raw, bytes) else raw
        file_obj = io.StringIO(text)

    reader = csv.DictReader(file_obj)
    header_map = _normalize_headers(reader.fieldnames or [])

    by_question: "dict[str, dict]" = {}
    order: List[str] = []
    total_rows = 0

    for row in reader:
        total_rows += 1
        parsed = {}
        for raw_col, value in row.items():
            canonical = header_map.get(raw_col)
            if canonical:
                parsed[canonical] = (value or "").strip()

        question = parsed.get("question", "")
        answer = parsed.get("answer", "")
        if not question or not answer:
            continue  # skip blank/malformed rows

        key = question.lower()
        image_url = _clean_image_path(parsed.get("image", ""))
        entry = {
            "question": question,
            "answer": answer,
            "category": parsed.get("category") or None,
            "image_url": image_url or None,
            "image_alt": parsed.get("image_alt") or None,
        }

        if key not in by_question:
            by_question[key] = entry
            order.append(key)
        else:
            # Merge: a later duplicate only overwrites fields that are
            # currently empty, so richer data wins without losing anything.
            existing = by_question[key]
            for field in ("answer", "category", "image_url", "image_alt"):
                if not existing.get(field) and entry.get(field):
                    existing[field] = entry[field]

    return [by_question[k] for k in order]
