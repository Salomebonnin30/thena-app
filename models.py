from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from database import Base


class Establishment(Base):
    __tablename__ = "establishments"

    id = Column(Integer, primary_key=True, index=True)

    google_place_id = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    address = Column(String, nullable=True)
    google_rating = Column(Float, nullable=True)

    # JSON string
    types_json = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    reviews = relationship(
        "Review",
        back_populates="establishment",
        cascade="all, delete-orphan",
    )


class Review(Base):
    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True, index=True)
    establishment_id = Column(Integer, ForeignKey("establishments.id"), nullable=False, index=True)

    # 0-10, nullable allowed
    score = Column(Integer, nullable=True)
    comment = Column(Text, nullable=False)

    role = Column(String, nullable=True)
    contract = Column(String, nullable=True)

    # NEW: logement
    housing = Column(String, nullable=True)          # "non_loge" / "loge_employeur"
    housing_quality = Column(String, nullable=True)  # "bon" / "moyen" / "mauvais"

    # Tags
    coupure = Column(Boolean, default=False)
    unpaid_overtime = Column(Boolean, default=False)
    toxic_manager = Column(Boolean, default=False)
    harassment = Column(Boolean, default=False)
    recommend = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)

    establishment = relationship("Establishment", back_populates="reviews")



