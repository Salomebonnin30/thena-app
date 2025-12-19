from sqlalchemy import create_engine, Column, String, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime
import uuid

DB_URL = "sqlite:///./thena.db"

engine = create_engine(DB_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

Base = declarative_base()

class Establishment(Base):
    __tablename__ = "establishments"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    city = Column(String, nullable=False)
    est_type = Column(String, nullable=False, default="restaurant")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

def init_db():
    Base.metadata.create_all(bind=engine)
