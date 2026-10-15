from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import get_current_user, require_admin

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post("", response_model=schemas.FeedbackOut)
def submit_feedback(
    payload: schemas.FeedbackIn,
    db: Session = Depends(get_db),
    current: models.User = Depends(get_current_user),
):
    stars = max(1, min(5, payload.stars))
    fb = models.Feedback(
        user_id=current.id,
        author_name=f"{current.name} ({current.role.capitalize()})",
        stars=stars,
        comment=payload.comment,
        resolved=False,
    )
    db.add(fb)
    db.commit()
    db.refresh(fb)
    return fb


@router.get("", response_model=List[schemas.FeedbackOut])
def list_feedback(
    db: Session = Depends(get_db),
    _admin: models.User = Depends(require_admin),
):
    return db.query(models.Feedback).order_by(models.Feedback.created_at.desc()).all()


@router.put("/{feedback_id}/resolve", response_model=schemas.FeedbackOut)
def resolve_feedback(
    feedback_id: int,
    db: Session = Depends(get_db),
    _admin: models.User = Depends(require_admin),
):
    fb = db.get(models.Feedback, feedback_id)
    if not fb:
        raise HTTPException(status_code=404, detail="Feedback not found.")
    fb.resolved = True
    db.commit()
    db.refresh(fb)
    return fb
