from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import get_current_user, require_teacher_or_admin

router = APIRouter(prefix="/attendance", tags=["attendance"])


@router.get("", response_model=List[schemas.AttendanceOut])
def list_attendance(
    student_id: Optional[int] = None,
    class_name: Optional[str] = None,
    on_date: Optional[date] = None,
    db: Session = Depends(get_db),
    _user: models.User = Depends(get_current_user),
):
    q = db.query(models.AttendanceRecord)
    if student_id:
        q = q.filter(models.AttendanceRecord.student_id == student_id)
    if class_name:
        q = q.filter(models.AttendanceRecord.class_name == class_name)
    if on_date:
        q = q.filter(models.AttendanceRecord.date == on_date)
    return q.all()


@router.post("", response_model=schemas.AttendanceOut)
def upsert_attendance(
    payload: schemas.AttendanceIn,
    db: Session = Depends(get_db),
    teacher: models.User = Depends(require_teacher_or_admin),
):
    """Create or update the attendance row for this student/class/date —
    lets a teacher correct a past date within the semester, not just mark today."""
    existing = (
        db.query(models.AttendanceRecord)
        .filter(
            models.AttendanceRecord.student_id == payload.student_id,
            models.AttendanceRecord.class_name == payload.class_name,
            models.AttendanceRecord.date == payload.date,
        )
        .first()
    )
    if existing:
        existing.present = payload.present
        existing.marked_by = teacher.id
        db.commit()
        db.refresh(existing)
        return existing

    record = models.AttendanceRecord(
        student_id=payload.student_id,
        class_name=payload.class_name,
        date=payload.date,
        present=payload.present,
        marked_by=teacher.id,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record
