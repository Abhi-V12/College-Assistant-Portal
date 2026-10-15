from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# SQLite for zero-setup local development. Swap this one line for a Postgres
# URL (e.g. "postgresql://user:pass@localhost/orbit") when you're ready to
# move off a single-file database — no other code needs to change.
SQLALCHEMY_DATABASE_URL = "sqlite:///./orbit.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
