from datetime import datetime, timedelta
from typing import Optional

import bcrypt
from jose import JWTError, jwt

# IMPORTANT: replace this with a long random string (e.g. `openssl rand -hex 32`)
# and load it from an environment variable before you deploy this anywhere real.
SECRET_KEY = "orbit-dev-secret-CHANGE-ME-BEFORE-PRODUCTION"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 8  # 8-hour session

# Using the `bcrypt` package directly rather than passlib's CryptContext.
# passlib (last released 2020, effectively unmaintained) probes
# `bcrypt.__about__.__version__` to detect the backend version; that
# attribute was removed in bcrypt>=4.1, which raises/crashes on import in
# some environments ("error reading bcrypt version"). Calling bcrypt's own
# hashpw/checkpw directly sidesteps that fragile version-sniffing entirely
# and works with any current bcrypt release.
BCRYPT_MAX_BYTES = 72  # bcrypt silently ignores anything past 72 bytes; we truncate explicitly instead


def hash_password(password: str) -> str:
    pw_bytes = password.encode("utf-8")[:BCRYPT_MAX_BYTES]
    return bcrypt.hashpw(pw_bytes, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    pw_bytes = plain_password.encode("utf-8")[:BCRYPT_MAX_BYTES]
    try:
        return bcrypt.checkpw(pw_bytes, hashed_password.encode("utf-8"))
    except ValueError:
        # Malformed/foreign hash format (e.g. leftover passlib-format hash) — treat as no match.
        return False


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None
