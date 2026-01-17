# security.py
import hashlib
import secrets
from datetime import datetime, timedelta

COOKIE_NAME = "thena_session"
SESSION_DAYS = 30
LOGINLINK_MINUTES = 10


def new_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def expires_in_minutes(minutes: int) -> datetime:
    return datetime.utcnow() + timedelta(minutes=minutes)


def expires_in_days(days: int) -> datetime:
    return datetime.utcnow() + timedelta(days=days)
