from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from . import models, security
from .database import get_db


def get_current_user(authorization: str = Header(None), db: Session = Depends(get_db)) -> models.User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header.")
    token = authorization.split(" ", 1)[1]
    payload = security.decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token. Please log in again.")
    user = db.get(models.User, int(payload["sub"]))
    if not user:
        raise HTTPException(status_code=401, detail="User no longer exists.")
    return user


def require_admin(user: models.User = Depends(get_current_user)) -> models.User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required for this action.")
    return user


def require_teacher_or_admin(user: models.User = Depends(get_current_user)) -> models.User:
    if user.role not in ("teacher", "admin"):
        raise HTTPException(status_code=403, detail="Teacher or admin access required.")
    return user
