from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import inspect, text

from .config import COLLEGE_SHORT
from .database import Base, engine
from .routers import announcements, attendance, auth, chatbot, departments, faq, feedback, marks, users, ocr

Base.metadata.create_all(bind=engine)
# Safe, idempotent SQLite migrations for databases created by older versions.
# create_all() creates missing tables, but does not add columns to existing tables.
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

app = FastAPI(title=f"{COLLEGE_SHORT} College Assistant API", version="0.1.0")

# Wide-open CORS for local development against the existing frontend prototype.
# Tighten allow_origins to your actual frontend URL before deploying anywhere real.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serves FAQ images at http://127.0.0.1:8000/images/<filename>.
# Drop your actual image files into orbit-backend/static/images/ — the CSV
# importer already rewrites any local Windows/Mac path in the "Image" column
# down to just its filename under this path.
IMAGES_DIR = Path(__file__).resolve().parent.parent / "static" / "images"
IMAGES_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/images", StaticFiles(directory=str(IMAGES_DIR)), name="images")

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(departments.router)
app.include_router(attendance.router)
app.include_router(marks.router)
app.include_router(announcements.router)
app.include_router(faq.router)
app.include_router(chatbot.router)
app.include_router(feedback.router)
app.include_router(ocr.router)


@app.on_event("startup")
def warm_up_embedding_model():
    """Loads the sentence-transformer model once at server startup instead
    of on the first live chatbot request — so the person testing the demo
    doesn't experience the ~1-2s model-load delay (or the one-time ~80MB
    download, the very first time this ever runs) as chatbot "slowness"."""
    try:
        from .routers.chatbot import get_model
        get_model()
        print("Embedding model warmed up and ready.")
    except Exception as e:
        # Don't block server startup if this fails for any reason (e.g. no
        # internet on first run) — the chatbot endpoint will just load it
        # lazily on first use instead, same as before.
        print(f"Could not warm up embedding model at startup: {e}")


@app.get("/")
def root():
    return {"status": f"{COLLEGE_SHORT} API running", "docs": "/docs"}
