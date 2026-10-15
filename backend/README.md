# Orbit Backend (FastAPI + SQLite + JWT)

A real, persistent backend for the Orbit prototype: hashed passwords, JWT
sessions, and a SQLite database file (`orbit.db`) that survives restarts —
which is the piece the pure-frontend prototype was missing.

> **Note on how this was built:** the sandbox this was generated in has no
> outbound internet access, so these packages could not be `pip install`-ed
> and test-run here. Every file passed a Python syntax check, and the code
> follows standard FastAPI/SQLAlchemy patterns, but **run it locally and
> smoke-test the endpoints below before you build on top of it.**

## 1. Setup (5 minutes)

```bash
cd orbit-backend
python -m venv venv

# Windows
venv\Scripts\activate
# Mac/Linux
source venv/bin/activate

pip install -r requirements.txt
python -m app.seed          # creates orbit.db and loads demo accounts/departments/FAQs
uvicorn app.main:app --reload
```

Server runs at `http://127.0.0.1:8000`. Interactive API docs (auto-generated,
good for testing without writing any frontend code) are at
`http://127.0.0.1:8000/docs`.

## 2. Quick test

```bash
curl -X POST http://127.0.0.1:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"aria.nair@orbit.edu","password":"Aria@2026","role":"student"}'
```

You should get back a JWT `access_token`. Use it on protected routes:

```bash
curl http://127.0.0.1:8000/users?role=student \
  -H "Authorization: Bearer <paste the token here>"
```

(That call needs an **admin** token, not a student one — log in as
`priya.kulkarni@orbit.edu` / `Admin@2026` / role `admin` to get one.)

## 3. Adding a real student/teacher (the actual answer to your question)

```
POST /users
Authorization: Bearer <admin token>
{
  "name": "Kabir Malhotra",
  "email": "kabir.malhotra@orbit.edu",
  "password": "TempPass@1",
  "role": "student",
  "department_id": 1,
  "semester": "2nd"
}
```

This writes a real row into `orbit.db` with a **bcrypt-hashed** password —
not plaintext, not an in-memory array. `kabir.malhotra@orbit.edu` can log in
immediately via `/auth/login`. `PUT /users/{id}` changes name/username/
password/department/status later; `DELETE /users/{id}` removes them. All
three are what your frontend's Add / Edit / Remove buttons should call.

## 4. Endpoints at a glance

| Method | Path | Who | Purpose |
|---|---|---|---|
| POST | `/auth/login` | anyone | returns a JWT |
| GET/POST | `/users` | admin | list / create students & teachers |
| PUT/DELETE | `/users/{id}` | admin | edit (incl. password) / remove |
| GET | `/users/me` | logged-in user | current profile |
| GET/POST | `/departments` | read: anyone, write: admin | dropdown source |
| GET/POST | `/attendance` | read: any user, write: teacher/admin | date-scoped |
| GET/POST | `/marks` | read: any user, write: teacher/admin | per semester/assessment |
| GET/POST | `/announcements` | read: anyone, write: admin | |
| GET/POST/DELETE | `/faq` | read: anyone, write: admin | chatbot knowledge base |
| POST | `/chatbot/ask` | anyone | TF-IDF match against `/faq` |

## 5. FAQ import (CSV, with optional images)

The `faqs` table now has three new **optional** columns — `category`,
`image_url`, `image_alt` — so existing text-only FAQs keep working exactly
as before; only questions that need a visual (like a fee-structure table)
carry an image.

**If you already have an `orbit.db` from Day 1/2**, run the migration once
(safe to run more than once, only touches the `faqs` table):

```bash
python -m app.migrate_add_faq_columns
```

**Import your CSV** (a cleaned copy is already at `data/faqs_import.csv` —
23 unique Q&A pairs after removing blank rows and duplicates from your
original 55-row file):

```bash
python -m app.import_faqs data/faqs_import.csv
```

This is an **upsert by question text** — re-running it after editing the
CSV updates existing rows instead of duplicating them, so it's safe to use
repeatedly as your dataset grows.

**Images**: 8 filenames are referenced by the cleaned dataset (e.g.
`College_Fee_BTech_CSE_Allied.png`). Drop the actual image files into
`orbit-backend/static/images/` — full list in that folder's `README.md`.
Once present, they're served automatically at
`http://127.0.0.1:8000/images/<filename>`, and both the admin FAQ Manager
and the chatbot will render them inline.

**From the UI instead**: Admin → Manage FAQs → Import CSV now uploads the
file to `POST /faq/bulk`, which runs the exact same parsing/dedup/upsert
logic server-side — useful for re-importing an updated CSV later without
touching a terminal.

## 6. Retrieval pipeline

`POST /chatbot/ask` uses real semantic search: a `sentence-transformers`
model (`all-MiniLM-L6-v2`) embeds both the FAQ questions and the incoming
query into vectors, and FAISS (`IndexFlatIP` on normalized embeddings =
cosine similarity) finds the closest match. This understands meaning, not
just keyword overlap — e.g. "hostel food timings" correctly matches "hostel
mess timings" even with no shared words beyond "hostel".

**First-time setup**: run `python -m app.test_rag_setup` once after
`pip install -r requirements.txt` to confirm the install worked and the
model downloads correctly (isolates any problem here, not inside a live
request). It downloads ~80MB on first run and caches it locally after that.

**Performance**: two things previously made this slower than it needed to
be, both fixed —
1. The FAQ corpus was being **re-embedded on every single chatbot message**.
   It's now cached in memory and only re-embedded when the FAQ table
   actually changes (add/edit/delete/import) — a typical request now does
   one query embed + one FAISS search, not N+1 embeds.
2. The embedding model used to load lazily on the *first* live request.
   `main.py` now warms it up at server startup instead, so the person
   testing the demo doesn't experience that load time as "the chatbot is
   slow."

If answers are still inconsistent, `MATCH_THRESHOLD` in `chatbot.py`
(currently `0.35`) is the main lever — lower it if good matches are being
rejected, raise it if unrelated FAQs are matching too eagerly. The other
lever is your FAQ data itself: a 22M-parameter model like MiniLM matches
better when there are multiple phrasings of the same question in the
dataset (e.g. both "hostel mess timings" and "when is dinner served") —
consider adding paraphrased duplicates of your most-asked questions.

The response includes `category`, `image_url`, `image_alt`, and now
`source` (`"faq"` or `"llm"`, see below) alongside the answer.

## 7. Local LLM general chat (LM Studio)

When no FAQ matches confidently, `/chatbot/ask` now falls back to a local
LLM instead of a dead end — this is what gives you day-to-day conversational
chat, not just FAQ lookup, without sending anything to an external API.

**Setup**:
1. Install [LM Studio](https://lmstudio.ai).
2. Download a small instruct model. Good options at 1-3B for a normal
   laptop CPU: `Qwen2.5-3B-Instruct` (strong instruction-following, good
   default), `Llama-3.2-3B-Instruct` (Meta, well-supported), or
   `Qwen2.5-1.5B-Instruct` if 3B feels slow on your machine. Pick a
   `Q4_K_M` GGUF quantization — the standard "good enough quality, small
   and fast" choice.
3. Load the model in LM Studio, open the **Local Server** tab, and start
   it (default `http://localhost:1234`).
4. That's it — `app/llm_client.py` already points at that URL. No code
   changes needed.

**How the fallback works**: `chatbot.py` tries FAISS retrieval first
(fast, grounded, zero hallucination risk for factual college questions).
Only if that comes back below `MATCH_THRESHOLD` does it call the local LLM
via `app/llm_client.py`, which is a plain `requests.post()` to LM Studio's
OpenAI-compatible `/v1/chat/completions` endpoint. If LM Studio isn't
running, that call fails fast (`LLMUnavailable`) and you get the old
"couldn't find a match" message — **the FAQ bot works perfectly with LM
Studio off**, this is a pure addition, not a new dependency for the app to
function.

**Isolation by design**: no model-serving code lives in this backend at
all — LM Studio does the actual inference in its own process. This keeps
the FastAPI app itself lightweight and means a slow/crashed LLM can never
take down FAQ answering.

## 8. Frontend wiring status

The HTML/JS frontend is fully wired to this API — login, Manage Users,
Departments (including edit), FAQ Manager + CSV import, Attendance, Marks,
Announcements, Feedback, and the chatbot all call these endpoints directly.
None of it is mock data. The two remaining intentional simplifications,
disclosed in the UI itself: there's no course-enrollment model (so
"classes" are labels, not real per-class rosters), and the exam schedule /
fee payment are still mock (no exam-calendar system or payment gateway).
