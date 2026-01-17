# models.py
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, ForeignKey, Text, Boolean,
    UniqueConstraint
)
from sqlalchemy.orm import relationship

from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(320), unique=True, index=True, nullable=False)
    pseudo = Column(String(50), index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    reviews = relationship("Review", back_populates="user", cascade="all, delete-orphan")
    login_tokens = relationship("LoginToken", back_populates="user", cascade="all, delete-orphan")
    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")


class LoginToken(Base):
    """
    Token "one-shot" envoyé par email (magic link).
    On ne stocke jamais le token brut, uniquement son hash.
    """
    __tablename__ = "login_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    token_hash = Column(String(64), unique=True, index=True, nullable=False)

    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="login_tokens")


class Session(Base):
    """
    Session long-terme stockée côté navigateur via cookie (HttpOnly).
    """
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    session_hash = Column(String(64), unique=True, index=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="sessions")


class Establishment(Base):
    __tablename__ = "establishments"

    id = Column(Integer, primary_key=True, index=True)
    google_place_id = Column(String(128), unique=True, index=True, nullable=False)

    name = Column(String(255), nullable=False)
    address = Column(String(500), nullable=True)

    google_rating = Column(Float, nullable=True)
    types_json = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    reviews = relationship("Review", back_populates="establishment", cascade="all, delete-orphan")


class Review(Base):
    __tablename__ = "reviews"
    __table_args__ = (
        UniqueConstraint("establishment_id", "user_id", name="uq_review_establishment_user"),
    )

    id = Column(Integer, primary_key=True, index=True)

    establishment_id = Column(Integer, ForeignKey("establishments.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    score = Column(Float, nullable=True)
    comment = Column(Text, nullable=False)

    role = Column(String(80), nullable=True)
    contract = Column(String(40), nullable=True)

    housing = Column(String(40), nullable=True)          # NON_LOGE / LOGE
    housing_quality = Column(String(40), nullable=True)  # TOP / OK / MOYEN / MAUVAIS / INSALUBRE

    coupure = Column(Boolean, default=False, nullable=False)
    unpaid_overtime = Column(Boolean, default=False, nullable=False)
    toxic_manager = Column(Boolean, default=False, nullable=False)
    harassment = Column(Boolean, default=False, nullable=False)
    recommend = Column(Boolean, default=False, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    establishment = relationship("Establishment", back_populates="reviews")
    user = relationship("User", back_populates="reviews")



