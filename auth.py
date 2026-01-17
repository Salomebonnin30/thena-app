# auth.py
from datetime import datetime
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from database import SessionLocal
from models import Session as DbSession, User
from security import COOKIE_NAME, hash_token


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    raw = request.cookies.get(COOKIE_NAME)
    if not raw:
        raise HTTPException(status_code=401, detail="Not authenticated")

    h = hash_token(raw)
    s = db.query(DbSession).filter(DbSession.session_hash == h).first()
    if not s or s.expires_at < datetime.utcnow():
        raise HTTPException(status_code=401, detail="Session expired")

    user = db.query(User).get(s.user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return user
