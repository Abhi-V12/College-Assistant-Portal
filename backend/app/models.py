from datetime import datetime

from sqlalchemy import Boolean, Column, Date, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from .database import Base


class Department(Base):
    __tablename__ = "departments"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    hod = Column(String, default="")
    courses = Column(Integer, default=0)


class User(Base):
    """Covers students, teachers, and admins via the `role` column."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    display_id = Column(String, unique=True, index=True)  # e.g. CS21B045 / FAC-0231 / ADM-004
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)  # doubles as the login username
    hashed_password = Column(String, nullable=False)
    role = Column(String, nullable=False)  # "student" | "teacher" | "admin"
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True)
    semester = Column(String, nullable=True)      # students only
    course = Column(String, nullable=True)        # B.Tech / M.Tech
    specialization = Column(String, nullable=True)  # branch / specialization
    designation = Column(String, nullable=True)   # teachers/admin only
    status = Column(String, default="Active")     # "Active" | "On Leave"
    created_at = Column(DateTime, default=datetime.utcnow)

    department = relationship("Department")


class AttendanceRecord(Base):
    __tablename__ = "attendance_records"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    class_name = Column(String, nullable=False)
    date = Column(Date, nullable=False)
    present = Column(Boolean, default=True)
    marked_by = Column(Integer, ForeignKey("users.id"), nullable=True)


class MarkRecord(Base):
    __tablename__ = "mark_records"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    class_name = Column(String, nullable=False)
    semester = Column(String, nullable=False)
    assessment = Column(String, nullable=False)
    marks = Column(Float, nullable=False)
    max_marks = Column(Float, default=20)


class Announcement(Base):
    __tablename__ = "announcements"

    id = Column(Integer, primary_key=True, index=True)
    tag = Column(String, default="General")
    title = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class FAQ(Base):
    __tablename__ = "faqs"

    id = Column(Integer, primary_key=True, index=True)
    question = Column(String, nullable=False)
    answer = Column(String, nullable=False)
    category = Column(String, nullable=True)     # e.g. "Fees", "Admission", "Courses" — optional
    image_url = Column(String, nullable=True)     # e.g. "/images/College_Fee_BTech_CSE_Allied.png" — optional
    image_alt = Column(String, nullable=True)     # accessible alt text for the image — optional


class Feedback(Base):
    """Chatbot feedback — either a quick thumbs up/down reaction on an
    answer, or a detailed star rating + comment submitted from a dashboard."""
    __tablename__ = "feedback"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    author_name = Column(String, nullable=False)  # denormalized so it still displays if the user is later removed
    stars = Column(Integer, default=5)
    comment = Column(String, nullable=True)
    resolved = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class ChatLog(Base):
    """One row per chatbot exchange — powers the student's Chat History
    widget and gives admin a real (not simulated) usage log."""
    __tablename__ = "chat_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    query_text = Column(String, nullable=False)
    matched = Column(Boolean, default=False)
    score = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
