from datetime import date
from difflib import get_close_matches
from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session
from .. import models
from ..database import get_db
from ..deps import require_teacher_or_admin
from ..ocr_engine import extract_lines

router = APIRouter(prefix="/ocr", tags=["ocr"])

@router.post("/attendance-sheet")
async def parse_attendance_sheet(file: UploadFile = File(...), class_name: str = "General",
                                  db: Session = Depends(get_db), _=Depends(require_teacher_or_admin)):
    lines = extract_lines(await file.read())
    students = db.query(models.User).filter(models.User.role == "student").all()
    names = [s.name for s in students]
    rows = []
    for line in lines:
        parts = line.strip().split()
        if not parts: continue
        best = get_close_matches(line, names, n=1, cutoff=0.4)
        matched = next((s for s in students if s.name == best[0]), None) if best else None
        present = parts[-1].lower().startswith("p")
        rows.append({"raw_text": line, "matched_student_id": matched.id if matched else None,
                     "matched_student_name": matched.name if matched else None, "present": present})
    return {"class_name": class_name, "rows": rows}

@router.post("/attendance-sheet/commit")
def commit_attendance_sheet(payload: dict, db: Session = Depends(get_db), teacher=Depends(require_teacher_or_admin)):
    for row in payload.get("rows", []):
        if not row.get("matched_student_id"): continue
        db.add(models.AttendanceRecord(student_id=row["matched_student_id"], class_name=payload.get("class_name","General"),
                                        date=date.today(), present=row.get("present", True), marked_by=teacher.id))
    db.commit()
    return {"message": "Attendance committed."}