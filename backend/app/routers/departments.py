from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import require_admin

router = APIRouter(prefix="/departments", tags=["departments"])


@router.get("", response_model=List[schemas.DepartmentOut])
def list_departments(db: Session = Depends(get_db)):
    # Public read (the frontend needs this list to populate dropdowns for anyone,
    # not just admins) — only creation is admin-gated below.
    return db.query(models.Department).order_by(models.Department.name).all()


@router.post("", response_model=schemas.DepartmentOut)
def create_department(
    payload: schemas.DepartmentCreate,
    db: Session = Depends(get_db),
    _admin: models.User = Depends(require_admin),
):
    if db.query(models.Department).filter(models.Department.name == payload.name).first():
        raise HTTPException(status_code=400, detail="That department already exists.")
    dept = models.Department(name=payload.name, hod=payload.hod, courses=payload.courses)
    db.add(dept)
    db.commit()
    db.refresh(dept)
    return dept


@router.put("/{department_id}", response_model=schemas.DepartmentOut)
def update_department(
    department_id: int,
    payload: schemas.DepartmentUpdate,
    db: Session = Depends(get_db),
    _admin: models.User = Depends(require_admin),
):
    dept = db.get(models.Department, department_id)
    if not dept:
        raise HTTPException(status_code=404, detail="Department not found.")
    if payload.name and payload.name != dept.name:
        if db.query(models.Department).filter(models.Department.name == payload.name).first():
            raise HTTPException(status_code=400, detail="Another department already has that name.")
        dept.name = payload.name
    if payload.hod is not None:
        dept.hod = payload.hod
    if payload.courses is not None:
        dept.courses = payload.courses
    db.commit()
    db.refresh(dept)
    return dept


@router.delete("/{department_id}")
def delete_department(
    department_id: int,
    db: Session = Depends(get_db),
    _admin: models.User = Depends(require_admin),
):
    dept = db.get(models.Department, department_id)
    if not dept:
        raise HTTPException(status_code=404, detail="Department not found.")
    assigned = db.query(models.User).filter(models.User.department_id == department_id).count()
    if assigned:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot delete this department because {assigned} user account(s) are assigned to it. Reassign or remove those users first.",
        )
    db.delete(dept)
    db.commit()
    return {"ok": True, "removed_id": department_id}
