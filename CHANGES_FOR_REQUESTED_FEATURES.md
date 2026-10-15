# Orbit College Assistant Portal — Changes

## Implemented
- Admin-only department deletion endpoint with a safe guard: deletion is blocked if any users are assigned to that department.
- Department cards now include a Delete button and a confirmation modal.
- Admin dashboard now has an Admins tab listing approved/existing admin accounts. Passwords are represented by a masked placeholder; password hashes and plaintext passwords are never returned by the API.
- Added an admin-only `GET /faq/export` endpoint and an Export CSV button in FAQ Manager. Export includes id, question, answer, category, image_url, and image_alt from the live database.
- Student create/edit forms now use dropdowns for program, branch/specialization, and semester. B.Tech has 8 semesters and the requested branches; M.Tech has 4 semesters and its requested branches.
- Added `course` and `specialization` fields to the User model/API. On startup, the backend automatically adds these columns to an existing SQLite database if they are missing.
- Student list now shows course/branch and semester.

## Important existing-architecture note
The original project does not have a Course table. `Department.courses` is only an integer count, not a list of individual course records. Therefore the existing department can be deleted, but individual catalog branches do not yet have persistent admin add/edit/delete CRUD. The program/branch options requested for student enrollment are currently defined in the frontend catalog. A full persistent course-catalog manager would require adding a Course model/API and an admin UI for course records.

## Checks
- Python source syntax checked with `py_compile`.
- Inline frontend JavaScript syntax checked with `node --check`.
- Full runtime/API integration testing was not possible in the packaging environment because the backend dependency `bcrypt` is not installed here. Install `backend/requirements.txt` in the project environment before running the backend.
