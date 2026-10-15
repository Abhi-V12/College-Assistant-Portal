"""
Single source of truth for college branding.

Change these two lines (and the matching COLLEGE_NAME/COLLEGE_SHORT/
COLLEGE_EMAIL_DOMAIN constants at the top of app.js on the frontend) to
rename the college everywhere — the API title, LLM system prompt, and every
seeded demo account all read from here.

IMPORTANT: changing COLLEGE_EMAIL_DOMAIN only affects *new* accounts created
after the change (via seed.py or Admin -> Manage Users -> Add). It does not
retroactively rename usernames already saved in orbit.db. If you've already
seeded/added real accounts under the old domain, either leave them as-is
and use the new domain going forward, or bulk-update them via Admin ->
Manage Users -> Edit (one at a time) or a one-off SQL update.
"""

COLLEGE_NAME = "Orbit College"
COLLEGE_SHORT = "Orbit"
COLLEGE_EMAIL_DOMAIN = "orbit.edu"
