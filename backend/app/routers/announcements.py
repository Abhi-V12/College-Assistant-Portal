from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import require_admin

router = APIRouter(prefix="/announcements", tags=["announcements"])


@router.get("", response_model=List[schemas.AnnouncementOut])
def list_announcements(db: Session = Depends(get_db)):
    return db.query(models.Announcement).order_by(models.Announcement.created_at.desc()).all()


@router.post("", response_model=schemas.AnnouncementOut)
def publish_announcement(
    payload: schemas.AnnouncementIn,
    db: Session = Depends(get_db),
    _admin: models.User = Depends(require_admin),
):
    ann = models.Announcement(tag=payload.tag, title=payload.title)
    db.add(ann)
    db.commit()
    db.refresh(ann)
    return ann
