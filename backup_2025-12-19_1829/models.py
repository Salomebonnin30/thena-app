from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from database import Base


class Establishment(Base):
    __tablename__ = "establishments"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, index=True)
    city = Column(String, nullable=False, index=True)
    category = Column(String, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    reviews = relationship(
        "Review",
        back_populates="establishment",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class Review(Base):
    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True, index=True)

    establishment_id = Column(
        Integer,
        ForeignKey("establishments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    rating = Column(Integer, nullable=False)  # 1..5
    comment = Column(String, nullable=True)

    # Tags stockés en JSON string (SQLite friendly)
    tags_json = Column(String, nullable=False, default="[]")

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    establishment = relationship("Establishment", back_populates="reviews")
