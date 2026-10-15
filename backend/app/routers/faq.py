from typing import List
import csv
import io
from fastapi.responses import StreamingResponse

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import require_admin
from ..faq_import import parse_faq_csv

router = APIRouter(prefix="/faq", tags=["faq"])


@router.get("", response_model=List[schemas.FAQOut])
def list_faqs(db: Session = Depends(get_db)):
    return db.query(models.FAQ).order_by(models.FAQ.id).all()


@router.get("/export")
def export_faqs_csv(
    db: Session = Depends(get_db),
    _admin: models.User = Depends(require_admin),
):
    """Export the current FAQ table, including optional image metadata, as CSV."""
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(["id", "question", "answer", "category", "image_url", "image_alt"])
    for faq in db.query(models.FAQ).order_by(models.FAQ.id).all():
        writer.writerow([faq.id, faq.question, faq.answer, faq.category or "", faq.image_url or "", faq.image_alt or ""])
    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=orbit_faqs.csv"},
    )


@router.post("", response_model=schemas.FAQOut)
def add_faq(
    payload: schemas.FAQIn,
    db: Session = Depends(get_db),
    _admin: models.User = Depends(require_admin),
):
    faq = models.FAQ(
        question=payload.question,
        answer=payload.answer,
        category=payload.category,
        image_url=payload.image_url,
        image_alt=payload.image_alt,
    )
    db.add(faq)
    db.commit()
    db.refresh(faq)
    return faq


@router.post("/bulk", response_model=schemas.FAQBulkResult)
async def bulk_import_faqs(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _admin: models.User = Depends(require_admin),
):
    """CSV bulk import — same cleaning/dedup logic as the app.import_faqs
    script, exposed over the API so the admin UI's Import FAQ Dataset page
    can drive it directly. Upserts by question, so importing the same file
    twice (or a corrected version of it) never creates duplicates."""
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Please upload a .csv file.")

    raw_bytes = await file.read()
    rows = parse_faq_csv(raw_bytes)
    if not rows:
        raise HTTPException(status_code=400, detail="No valid question/answer rows found in that CSV.")

    inserted = updated = 0
    for row in rows:
        existing = db.query(models.FAQ).filter(models.FAQ.question.ilike(row["question"])).first()
        if existing:
            existing.answer = row["answer"]
            existing.category = row["category"]
            existing.image_url = row["image_url"]
            existing.image_alt = row["image_alt"]
            updated += 1
        else:
            db.add(models.FAQ(
                question=row["question"], answer=row["answer"],
                category=row["category"], image_url=row["image_url"], image_alt=row["image_alt"],
            ))
            inserted += 1
    db.commit()

    return schemas.FAQBulkResult(inserted=inserted, updated=updated, skipped=0, total_in_file=len(rows))


@router.delete("/{faq_id}")
def delete_faq(
    faq_id: int,
    db: Session = Depends(get_db),
    _admin: models.User = Depends(require_admin),
):
    faq = db.get(models.FAQ, faq_id)
    if not faq:
        raise HTTPException(status_code=404, detail="FAQ not found.")
    db.delete(faq)
    db.commit()
    return {"ok": True}
