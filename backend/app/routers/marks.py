from typing import List, Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import get_current_user, require_teacher_or_admin

router = APIRouter(prefix="/marks", tags=["marks"])


@router.get("", response_model=List[schemas.MarkOut])
def list_marks(
    student_id: Optional[int] = None,
    class_name: Optional[str] = None,
    semester: Optional[str] = None,
    assessment: Optional[str] = None,
    db: Session = Depends(get_db),
    _user: models.User = Depends(get_current_user),
):
    q = db.query(models.MarkRecord)
    if student_id:
        q = q.filter(models.MarkRecord.student_id == student_id)
    if class_name:
        q = q.filter(models.MarkRecord.class_name == class_name)
    if semester:
        q = q.filter(models.MarkRecord.semester == semester)
    if assessment:
        q = q.filter(models.MarkRecord.assessment == assessment)
    return q.all()


@router.post("", response_model=schemas.MarkOut)
def upsert_mark(
    payload: schemas.MarkIn,
    db: Session = Depends(get_db),
    _teacher: models.User = Depends(require_teacher_or_admin),
):
    existing = (
        db.query(models.MarkRecord)
        .filter(
            models.MarkRecord.student_id == payload.student_id,
            models.MarkRecord.class_name == payload.class_name,
            models.MarkRecord.semester == payload.semester,
            models.MarkRecord.assessment == payload.assessment,
        )
        .first()
    )
    if existing:
        existing.marks = payload.marks
        db.commit()
        db.refresh(existing)
        return existing

    record = models.MarkRecord(
        student_id=payload.student_id,
        class_name=payload.class_name,
        semester=payload.semester,
        assessment=payload.assessment,
        marks=payload.marks,
        max_marks=20,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record
