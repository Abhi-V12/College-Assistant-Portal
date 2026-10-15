"""
Run this once after creating the database to populate it with the same
departments / demo accounts / FAQs the frontend prototype ships with, so
login credentials stay identical while you wire the two together.

Usage:
    python -m app.seed
"""

from . import models, security
from .config import COLLEGE_EMAIL_DOMAIN
from sqlalchemy import inspect, text

from .database import Base, SessionLocal, engine

Base.metadata.create_all(bind=engine)
# Keep seeding safe on both fresh databases and databases from older versions.
# This must run before SessionLocal ORM queries, because older tables may lack
# columns now present in the SQLAlchemy models.
with engine.begin() as connection:
    user_columns = {column["name"] for column in inspect(engine).get_columns("users")}
    if "course" not in user_columns:
        connection.execute(text("ALTER TABLE users ADD COLUMN course VARCHAR"))
    if "specialization" not in user_columns:
        connection.execute(text("ALTER TABLE users ADD COLUMN specialization VARCHAR"))

    faq_columns = {column["name"] for column in inspect(engine).get_columns("faqs")}
    if "category" not in faq_columns:
        connection.execute(text("ALTER TABLE faqs ADD COLUMN category VARCHAR"))
    if "image_url" not in faq_columns:
        connection.execute(text("ALTER TABLE faqs ADD COLUMN image_url VARCHAR"))
    if "image_alt" not in faq_columns:
        connection.execute(text("ALTER TABLE faqs ADD COLUMN image_alt VARCHAR"))

db = SessionLocal()


def email(local_part: str) -> str:
    """Builds an address on the configured college domain, e.g.
    email('aria.nair') -> 'aria.nair@orbit.edu' (or whatever
    COLLEGE_EMAIL_DOMAIN in app/config.py is set to)."""
    return f"{local_part}@{COLLEGE_EMAIL_DOMAIN}"


def get_or_create_department(name: str, hod: str = "", courses: int = 0) -> models.Department:
    dept = db.query(models.Department).filter_by(name=name).first()
    if dept:
        return dept
    dept = models.Department(name=name, hod=hod, courses=courses)
    db.add(dept)
    db.commit()
    db.refresh(dept)
    return dept


def get_or_create_user(display_id, name, email_address, password, role, dept, **extra):
    existing = db.query(models.User).filter_by(email=email_address).first()
    if existing:
        return existing
    user = models.User(
        display_id=display_id,
        name=name,
        email=email_address,
        hashed_password=security.hash_password(password),
        role=role,
        department_id=dept.id if dept else None,
        status="Active",
        **extra,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def run():
    cs = get_or_create_department("Computer Science", "Dr. Rekha Menon", 8)
    ece = get_or_create_department("Electronics & Communication", "Dr. Kavya Nambiar", 6)
    mech = get_or_create_department("Mechanical Engineering", "Prof. Anil Kumar", 7)
    civil = get_or_create_department("Civil Engineering", "Dr. Prakash Rao", 6)
    ba = get_or_create_department("Business Administration", "Dr. Sunita Ghosh", 5)
    eee = get_or_create_department("Electrical Engineering", "Dr. Vikram Shah", 6)
    admin_dept = get_or_create_department("Administration", "—", 0)

    # --- students (same credentials as the frontend demo) ---
    get_or_create_user("CS21B045", "Aria Nair", email("aria.nair"), "Aria@2026", "student", cs, semester="6th")
    get_or_create_user("CS21B012", "Rohan Iyer", email("rohan.iyer"), "Rohan@2026", "student", cs, semester="6th")
    get_or_create_user("EC20B078", "Meera Pillai", email("meera.pillai"), "Meera@2026", "student", ece, semester="8th")
    get_or_create_user("ME21B033", "Farhan Sheikh", email("farhan.sheikh"), "Orbit@123", "student", mech, semester="6th")
    get_or_create_user("CS22B091", "Diya Kapoor", email("diya.kapoor"), "Orbit@123", "student", cs, semester="4th")
    get_or_create_user("BA21B056", "Sneha Reddy", email("sneha.reddy"), "Orbit@123", "student", ba, semester="6th")

    # --- teachers ---
    get_or_create_user("FAC-0231", "Dr. Samuel Roy", email("samuel.roy"), "Samuel@2026", "teacher", cs, designation="Associate Professor")
    get_or_create_user("FAC-0117", "Dr. Meera Iyer", email("meera.iyer"), "MeeraI@2026", "teacher", cs, designation="Assistant Professor")
    get_or_create_user("FAC-0298", "Dr. Rekha Menon", email("rekha.menon"), "Rekha@2026", "teacher", cs, designation="Professor")
    get_or_create_user("FAC-0056", "Prof. Anil Kumar", email("anil.kumar"), "Orbit@123", "teacher", mech, designation="Professor")

    # --- admin ---
    get_or_create_user(
        "ADM-004", "Priya Kulkarni", email("priya.kulkarni"), "Admin@2026", "admin",
        admin_dept, designation="System Administrator",
    )

    # --- starter FAQs ---
    if not db.query(models.FAQ).first():
        starter_faqs = [
            ("how much is the admission fee for computer science",
             "The admission fee for the Computer Science program is ₹85,000 per year, payable in two installments."),
            ("when is the last date to pay semester fees",
             "The last date for this semester's fee payment is 20 August 2026. A late fee applies after that."),
            ("what is the minimum attendance required to sit for exams",
             "Students must maintain at least 75% attendance in each subject to be eligible for semester exams."),
            ("what are the hostel mess timings",
             "Breakfast 7:30–9:30, Lunch 12:30–2:30, Dinner 7:30–9:30."),
            ("how many hours is the library open",
             "The library is open 8 AM–8 PM on regular days, extended to 7 AM–11 PM during exam weeks."),
            ("how do i reset my portal password",
             "Ask your department admin to reset it from Admin → Manage Users → Edit."),
        ]
        for question, answer in starter_faqs:
            db.add(models.FAQ(question=question, answer=answer))
        db.commit()

    print("Seed complete: departments, demo accounts, and starter FAQs are in orbit.db")


if __name__ == "__main__":
    run()
    db.close()
