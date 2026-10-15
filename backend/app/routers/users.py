import random
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from fastapi.responses import StreamingResponse
import csv, io

from .. import models, schemas, security
from ..database import get_db
from ..deps import get_current_user, require_admin, require_teacher_or_admin

router = APIRouter(prefix="/users", tags=["users"])


def to_out(u: models.User) -> schemas.UserOut:
    return schemas.UserOut(
        id=u.id,
        display_id=u.display_id,
        name=u.name,
        email=u.email,
        role=u.role,
        department=u.department.name if u.department else None,
        semester=u.semester,
        course=u.course,
        specialization=u.specialization,
        designation=u.designation,
        status=u.status,
    )

@router.get("/{student_id}/report/download")
def download_student_report(student_id: int, db: Session = Depends(get_db), _=Depends(require_teacher_or_admin)):
    student = db.get(models.User, student_id)
    marks = db.query(models.MarkRecord).filter_by(student_id=student_id).all()
    att = db.query(models.AttendanceRecord).filter_by(student_id=student_id).all()
    buf = io.StringIO(); w = csv.writer(buf)
    w.writerow(["Name", "Roll", "Class", "Date/Assessment", "Value"])
    for a in att: w.writerow([student.name, student.display_id, a.class_name, str(a.date), "Present" if a.present else "Absent"])
    for m in marks: w.writerow([student.name, student.display_id, m.class_name, m.assessment, f"{m.marks}/{m.max_marks}"])
    buf.seek(0)
    return StreamingResponse(buf, media_type="text/csv", headers={"Content-Disposition": f"attachment; filename={student.display_id}_report.csv"})


@router.get("", response_model=List[schemas.UserOut])
def list_users(
    role: Optional[str] = None,
    db: Session = Depends(get_db),
    _requester: models.User = Depends(require_teacher_or_admin),
):
    q = db.query(models.User)
    if role:
        q = q.filter(models.User.role == role)
    return [to_out(u) for u in q.order_by(models.User.id).all()]


@router.get("/me", response_model=schemas.UserOut)
def get_me(current: models.User = Depends(get_current_user)):
    return to_out(current)

@router.post("/bulk-import")
async def bulk_import_students(file: UploadFile = File(...), db: Session = Depends(get_db), _=Depends(require_admin)):
    text = (await file.read()).decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    inserted = updated = 0
    for row in reader:
        roll = row.get("RollNo", "").strip()
        if not roll: continue
        student = db.query(models.User).filter_by(display_id=roll).first()
        if student:
            student.name = row.get("Name", student.name)
            student.department_id = (db.query(models.Department).filter_by(name=row.get("Department","")).first() or type('',(),{'id':student.department_id})()).id
            student.semester = row.get("Semester", student.semester)
            updated += 1
        else:
            dept = db.query(models.Department).filter_by(name=row.get("Department","")).first()
            student = models.User(display_id=roll, name=row.get("Name","Unknown"),
                email=row.get("Email") or f"{roll.lower()}@{__import__('app.config',fromlist=['COLLEGE_EMAIL_DOMAIN']).COLLEGE_EMAIL_DOMAIN}",
                hashed_password=security.hash_password("Orbit@123"), role="student",
                department_id=dept.id if dept else None, semester=row.get("Semester",""), status="Active")
            db.add(student); db.flush(); inserted += 1
        # optional marks/attendance columns in the same row
        if row.get("Marks"):
            db.add(models.MarkRecord(student_id=student.id, class_name=row.get("ClassName","General"),
                semester=row.get("Semester",""), assessment=row.get("Assessment","Imported"),
                marks=float(row["Marks"]), max_marks=20))
        if row.get("AttendanceStatus"):
            db.add(models.AttendanceRecord(student_id=student.id, class_name=row.get("ClassName","General"),
                date=date.today(), present=row["AttendanceStatus"].lower().startswith("p")))
    db.commit()
    return {"inserted": inserted, "updated": updated}

@router.post("", response_model=schemas.UserOut)
def create_user(
    payload: schemas.UserCreate,
    db: Session = Depends(get_db),
    _admin: models.User = Depends(require_admin),
):
    if payload.role not in ("student", "teacher"):
        raise HTTPException(status_code=400, detail="role must be 'student' or 'teacher'.")
    email = payload.email.lower()
    if db.query(models.User).filter(models.User.email == email).first():
        raise HTTPException(status_code=400, detail="That email (username) is already registered.")

    dept = None
    if payload.department_id is not None:
        dept = db.get(models.Department, payload.department_id)
        if not dept:
            raise HTTPException(status_code=400, detail="Unknown department_id.")
    elif payload.role == "teacher":
        raise HTTPException(status_code=400, detail="A department is required for teachers.")

    prefix = "STU" if payload.role == "student" else "FAC"
    display_id = f"{prefix}-{random.randint(1000, 9999)}"

    user = models.User(
        display_id=display_id,
        name=payload.name,
        email=email,
        hashed_password=security.hash_password(payload.password),
        role=payload.role,
        department_id=dept.id if dept else None,
        semester=payload.semester,
        course=payload.course,
        specialization=payload.specialization,
        designation=payload.designation,
        status="Active",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return to_out(user)


@router.put("/{user_id}", response_model=schemas.UserOut)
def update_user(
    user_id: int,
    payload: schemas.UserUpdate,
    db: Session = Depends(get_db),
    _admin: models.User = Depends(require_admin),
):
    """Admin edits name / username (email) / password / department / status.
    This is the endpoint the 'Edit' button in Manage Users calls."""
    user = db.get(models.User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    if payload.email and payload.email.lower() != user.email:
        new_email = payload.email.lower()
        if db.query(models.User).filter(models.User.email == new_email).first():
            raise HTTPException(status_code=400, detail="That email (username) is already in use.")
        user.email = new_email
    if payload.name:
        user.name = payload.name
    if payload.password:
        user.hashed_password = security.hash_password(payload.password)
    if payload.department_id is not None:
        dept = db.get(models.Department, payload.department_id)
        if not dept:
            raise HTTPException(status_code=400, detail="Unknown department_id.")
        user.department_id = dept.id
    if payload.semester is not None:
        user.semester = payload.semester
    if payload.course is not None:
        user.course = payload.course
    if payload.specialization is not None:
        user.specialization = payload.specialization
    if payload.designation is not None:
        user.designation = payload.designation
    if payload.status:
        user.status = payload.status

    db.commit()
    db.refresh(user)
    return to_out(user)


@router.delete("/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    _admin: models.User = Depends(require_admin),
):
    user = db.get(models.User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    db.delete(user)
    db.commit()
    return {"ok": True, "removed_id": user_id}
