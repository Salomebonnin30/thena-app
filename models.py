from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, UniqueConstraint
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class Establishment(Base):
    __tablename__ = "establishments"
    __table_args__ = (UniqueConstraint("google_place_id", name="uq_google_place_id"),)

    id = Column(Integer, primary_key=True, index=True)
    google_place_id = Column(String, nullable=False, index=True)

    name = Column(String, nullable=False)
    address = Column(String, nullable=False)

    rating = Column(Float, nullable=True)
    types = Column(Text, nullable=True)  # JSON string

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


