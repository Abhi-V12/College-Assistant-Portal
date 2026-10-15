from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas, security
from ..database import get_db

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=schemas.Token)
def login(payload: schemas.LoginRequest, db: Session = Depends(get_db)):
    user = (
        db.query(models.User)
        .filter(models.User.email == payload.email.lower(), models.User.role == payload.role)
        .first()
    )
    if not user or not security.verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password for the selected role.")
    if user.status == "On Leave":
        raise HTTPException(status_code=403, detail="This account is marked On Leave and cannot sign in.")
    if user.status == "Pending":
        raise HTTPException(status_code=403, detail="Your admin account is pending approval.")

    token = security.create_access_token({"sub": str(user.id), "role": user.role})
    return schemas.Token(access_token=token, role=user.role, name=user.name, display_id=user.display_id)

@router.post("/signup-admin")
def signup_admin(payload: schemas.AdminSignupIn, db: Session = Depends(get_db)):
    email = payload.email.lower()
    if db.query(models.User).filter(models.User.email == email).first():
        raise HTTPException(status_code=400, detail="Email already registered.")
    admin_dept = db.query(models.Department).filter_by(name="Administration").first()
    user = models.User(
        display_id=f"ADM-{__import__('random').randint(1000,9999)}",
        name=payload.name, email=email,
        hashed_password=security.hash_password(payload.password),
        role="admin", department_id=admin_dept.id if admin_dept else None,
        status="Pending",
    )
    db.add(user); db.commit()
    return {"message": "Signup request submitted. Awaiting approval from an existing admin."}