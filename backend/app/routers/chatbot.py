from typing import List

import numpy as np
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import get_current_user, require_admin
from ..llm_client import LLMUnavailable, chat_completion

router = APIRouter(prefix="/chatbot", tags=["chatbot"])

# Cosine similarity via normalized embeddings + inner product ranges roughly
# -1..1. 0.35 was too permissive: for a small model like MiniLM, genuinely
# UNrelated sentences routinely score 0.2-0.4 just from shared vocabulary
# and embedding-space geometry, not real relatedness — so anything near that
# range was getting returned as a confident FAQ answer when it wasn't one.
# 0.5 is a safer floor for "this is actually the right FAQ." Tune this using
# real data: the chat UI already shows "match X%" on every FAQ-sourced
# answer — watch that number on queries that *should* and *shouldn't* match,
# and adjust from there. Raise it further if wrong answers still get through;
# lower it if correct answers start getting rejected (they'll fall through to
# the LLM general-chat response instead of a dead end either way, so erring
# a little high is the safer direction of a mistake).
MATCH_THRESHOLD = 0.5

_model = None  # lazy-loaded once per process, not per-request


def get_model():
    """Loads the embedding model on first use and reuses it after that.
    First call downloads ~80MB from Hugging Face and caches it locally
    (~/.cache/torch/sentence_transformers) — subsequent runs are instant.
    main.py calls this once at server startup so the *first real user
    request* isn't the one that pays this cost."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


# ---------------------------------------------------------------------------
# FAQ embedding cache. Previously the FAQ corpus was re-embedded on *every*
# single /chatbot/ask call — fine for a handful of FAQs, but the real cause
# of the "slow" complaint: that cost was paid on every message, and it grows
# with the FAQ count. This cache re-embeds only when the FAQ table has
# actually changed (compared by a cheap signature of id+question pairs),
# so a typical request just does one query encode + one FAISS search.
#
# IMPORTANT: we cache plain dicts extracted from each FAQ row, not the
# SQLAlchemy ORM objects themselves. Each request gets its own DB session
# that closes when the request ends; a cached ORM object from an earlier
# request's (now-closed) session raises DetachedInstanceError the moment you
# touch an attribute on it on a later request. Plain dicts have no such
# session dependency, so a cache hit is always safe to read from.
# ---------------------------------------------------------------------------
_faq_cache = {"signature": None, "faqs": [], "embeddings": None}


def get_faq_embeddings(db: Session):
    faq_rows = db.query(models.FAQ).order_by(models.FAQ.id).all()
    signature = tuple((f.id, f.question) for f in faq_rows)

    if signature != _faq_cache["signature"]:
        faqs = [
            {
                "id": f.id, "question": f.question, "answer": f.answer,
                "category": f.category, "image_url": f.image_url, "image_alt": f.image_alt,
            }
            for f in faq_rows
        ]
        if faqs:
            model = get_model()
            questions = [f["question"] for f in faqs]
            _faq_cache["embeddings"] = np.asarray(
                model.encode(questions, normalize_embeddings=True), dtype="float32"
            )
        else:
            _faq_cache["embeddings"] = None
        _faq_cache["faqs"] = faqs
        _faq_cache["signature"] = signature

    return _faq_cache["faqs"], _faq_cache["embeddings"]


@router.post("/ask", response_model=schemas.ChatAnswer)
def ask(
    payload: schemas.ChatQuery,
    db: Session = Depends(get_db),
    current: models.User = Depends(get_current_user),
):
    import faiss  # imported lazily alongside the model so a missing install fails inside this route, not at server startup

    faqs, corpus_embeddings = get_faq_embeddings(db)

    if current.role in ("teacher", "admin"):
        students = db.query(models.User).filter(models.User.role == "student").all()
        q_lower = payload.query.lower()
        matched_student = next((s for s in students if s.name.lower() in q_lower or s.display_id.lower() in q_lower), None)
        if matched_student:
            wants_full = any(w in q_lower for w in ["full detail", "all detail", "everything", "profile"])
            wants_marks = "mark" in q_lower
            wants_attendance = "attendance" in q_lower

            att = db.query(models.AttendanceRecord).filter_by(student_id=matched_student.id).all()
            marks = db.query(models.MarkRecord).filter_by(student_id=matched_student.id).all()
            att_pct = round(sum(1 for a in att if a.present) / len(att) * 100, 1) if att else None
            avg_marks = round(sum(m.marks / m.max_marks * 100 for m in marks) / len(marks), 1) if marks else None

            if wants_attendance and not wants_full:
                text = f"{matched_student.name}'s attendance: {att_pct}%." if att_pct is not None else f"No attendance records for {matched_student.name}."
                dl = None
            elif wants_marks and not wants_full:
                text = f"{matched_student.name}'s average marks: {avg_marks}%." if avg_marks is not None else f"No marks records for {matched_student.name}."
                dl = None
            else:
                text = (f"{matched_student.name} ({matched_student.display_id}) — Dept: {matched_student.department.name if matched_student.department else 'N/A'}, "
                        f"Attendance: {att_pct if att_pct is not None else 'N/A'}%, Avg marks: {avg_marks if avg_marks is not None else 'N/A'}%.")
                dl = f"/users/{matched_student.id}/report/download"

            result = schemas.ChatAnswer(answer=text, score=1.0, source="student_lookup", download_url=dl)
            db.add(models.ChatLog(user_id=current.id, query_text=payload.query, matched=True, score=1.0))
            db.commit()
            return result

    result = schemas.ChatAnswer(answer=None, score=0.0, source=None)

    if faqs and corpus_embeddings is not None:
        model = get_model()
        query_embedding = np.asarray(model.encode([payload.query], normalize_embeddings=True), dtype="float32")

        index = faiss.IndexFlatIP(corpus_embeddings.shape[1])  # inner product on normalized vectors == cosine similarity
        index.add(corpus_embeddings)

        scores, indices = index.search(query_embedding, 1)
        best_score = float(scores[0][0])
        best_idx = int(indices[0][0])

        if best_score >= MATCH_THRESHOLD:
            best = faqs[best_idx]
            result = schemas.ChatAnswer(
                answer=best["answer"], score=best_score, category=best["category"],
                image_url=best["image_url"], image_alt=best["image_alt"], source="faq",
            )
        else:
            result = schemas.ChatAnswer(answer=None, score=best_score, source=None)

    # No confident FAQ match — fall back to the local LLM (if LM Studio is
    # running) for a normal conversational reply instead of a dead end.
    # This is what makes day-to-day chat work, not just FAQ lookup.
    if result.answer is None:
        try:
            llm_reply = chat_completion(payload.query)
            result = schemas.ChatAnswer(answer=llm_reply, score=result.score, source="llm")
        except LLMUnavailable:
            pass  # keep result.answer = None; frontend shows the "couldn't find a match" fallback

    # Log every exchange against the logged-in user — this is what powers
    # the real (not mock) Chat History widget and admin usage stats.
    db.add(models.ChatLog(
        user_id=current.id, query_text=payload.query,
        matched=bool(result.answer), score=result.score,
    ))
    db.commit()

    return result


@router.get("/history", response_model=List[schemas.ChatLogOut])
def my_chat_history(
    limit: int = 10,
    db: Session = Depends(get_db),
    current: models.User = Depends(get_current_user),
):
    return (
        db.query(models.ChatLog)
        .filter(models.ChatLog.user_id == current.id)
        .order_by(models.ChatLog.created_at.desc())
        .limit(limit)
        .all()
    )


@router.get("/stats", response_model=schemas.ChatStatsOut)
def chatbot_stats(
    db: Session = Depends(get_db),
    _admin: models.User = Depends(require_admin),
):
    from datetime import date, timedelta

    from sqlalchemy import func

    total = db.query(models.ChatLog).count()
    today = date.today()
    today_count = (
        db.query(models.ChatLog)
        .filter(func.date(models.ChatLog.created_at) == today.isoformat())
        .count()
    )

    day_rows = (
        db.query(func.date(models.ChatLog.created_at).label("d"), func.count().label("c"))
        .group_by("d")
        .all()
    )
    counts_by_day = {row.d: row.c for row in day_rows}

    last_7 = []
    for i in range(6, -1, -1):
        d = (today - timedelta(days=i)).isoformat()
        last_7.append(schemas.DayCount(date=d, count=counts_by_day.get(d, 0)))

    return schemas.ChatStatsOut(total_queries=total, today_queries=today_count, last_7_days=last_7)


@router.get("/recent", response_model=List[schemas.ChatLogAdminOut])
def recent_queries(
    limit: int = 15,
    db: Session = Depends(get_db),
    _admin: models.User = Depends(require_admin),
):
    rows = (
        db.query(models.ChatLog)
        .order_by(models.ChatLog.created_at.desc())
        .limit(limit)
        .all()
    )
    out = []
    for row in rows:
        user = db.get(models.User, row.user_id) if row.user_id else None
        out.append(schemas.ChatLogAdminOut(
            id=row.id, query_text=row.query_text, matched=row.matched, score=row.score,
            created_at=row.created_at, asked_by=user.name if user else "Unknown user",
        ))
    return out
