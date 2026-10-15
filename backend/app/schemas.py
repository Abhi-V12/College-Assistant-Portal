from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, EmailStr


# ---------- auth ----------
class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    role: str  # "student" | "teacher" | "admin"


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    name: str
    display_id: str


# ---------- departments ----------
class DepartmentCreate(BaseModel):
    name: str
    hod: str = ""
    courses: int = 0


class DepartmentUpdate(BaseModel):
    name: Optional[str] = None
    hod: Optional[str] = None
    courses: Optional[int] = None


class DepartmentOut(BaseModel):
    id: int
    name: str
    hod: str
    courses: int

    class Config:
        from_attributes = True


# ---------- users (students / teachers / admins) ----------
class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str
    role: str  # "student" | "teacher"
    department_id: Optional[int] = None
    semester: Optional[str] = None
    course: Optional[str] = None
    specialization: Optional[str] = None
    designation: Optional[str] = None


class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    password: Optional[str] = None  # set to change the password; omit to leave unchanged
    department_id: Optional[int] = None
    semester: Optional[str] = None
    course: Optional[str] = None
    specialization: Optional[str] = None
    designation: Optional[str] = None
    status: Optional[str] = None  # "Active" | "On Leave"


class UserOut(BaseModel):
    id: int
    display_id: str
    name: str
    email: str
    role: str
    department: Optional[str] = None
    semester: Optional[str] = None
    course: Optional[str] = None
    specialization: Optional[str] = None
    designation: Optional[str] = None
    status: str


# ---------- attendance ----------
class AttendanceIn(BaseModel):
    student_id: int
    class_name: str
    date: date
    present: bool


class AttendanceOut(AttendanceIn):
    id: int

    class Config:
        from_attributes = True


# ---------- marks ----------
class MarkIn(BaseModel):
    student_id: int
    class_name: str
    semester: str
    assessment: str
    marks: float


class MarkOut(MarkIn):
    id: int
    max_marks: float

    class Config:
        from_attributes = True


# ---------- announcements ----------
class AnnouncementIn(BaseModel):
    tag: str = "General"
    title: str


class AnnouncementOut(AnnouncementIn):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


# ---------- FAQ / chatbot ----------
class FAQIn(BaseModel):
    question: str
    answer: str
    category: Optional[str] = None
    image_url: Optional[str] = None
    image_alt: Optional[str] = None


class FAQOut(FAQIn):
    id: int

    class Config:
        from_attributes = True


class FAQBulkResult(BaseModel):
    inserted: int
    updated: int
    skipped: int
    total_in_file: int


class ChatQuery(BaseModel):
    query: str


class ChatAnswer(BaseModel):
    answer: Optional[str] = None
    score: float = 0.0
    category: Optional[str] = None
    image_url: Optional[str] = None
    image_alt: Optional[str] = None
    source: Optional[str] = None  # "faq" | "llm" | None (no match, no LLM available)
    download_url: Optional[str] = None


# ---------- feedback ----------
class FeedbackIn(BaseModel):
    stars: int  # 1-5
    comment: Optional[str] = None


class FeedbackOut(BaseModel):
    id: int
    author_name: str
    stars: int
    comment: Optional[str] = None
    resolved: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ---------- chat history ----------
class ChatLogOut(BaseModel):
    id: int
    query_text: str
    matched: bool
    score: float
    created_at: datetime

    class Config:
        from_attributes = True


class DayCount(BaseModel):
    date: str
    count: int


class ChatStatsOut(BaseModel):
    total_queries: int
    today_queries: int
    last_7_days: list[DayCount]


class ChatLogAdminOut(BaseModel):
    id: int
    query_text: str
    matched: bool
    score: float
    created_at: datetime
    asked_by: str

class AdminSignupIn(BaseModel):
    name: str
    email: EmailStr
    password: str
