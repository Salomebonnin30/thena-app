from fastapi import FastAPI, Depends, HTTPException
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine, Column, Integer, String, Float, Text
from sqlalchemy.orm import sessionmaker, declarative_base, Session
import requests
import os
import json
from dotenv import load_dotenv

# ======================
# ENV
# ======================
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if not GOOGLE_API_KEY:
    raise RuntimeError("GOOGLE_API_KEY manquante dans .env")

# ======================
# DATABASE
# ======================
DATABASE_URL = "sqlite:///./thena.db"

engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ======================
# MODEL
# ======================
class Establishment(Base):
    __tablename__ = "establishments"

    id = Column(Integer, primary_key=True, index=True)
    google_place_id = Column(String, unique=True, index=True)
    name = Column(String)
    address = Column(String)
    rating = Column(Float)
    types = Column(Text)


Base.metadata.create_all(bind=engine)

# ======================
# APP
# ======================
app = FastAPI(title="THENA")

# ======================
# GOOGLE — AUTOCOMPLETE
# ======================
@app.get("/api/google/autocomplete")
def google_autocomplete(q: str):
    url = "https://maps.googleapis.com/maps/api/place/autocomplete/json"
    params = {
        "input": q,
        "key": GOOGLE_API_KEY,
        "language": "fr",
    }

    r = requests.get(url, params=params)
    data = r.json()

    if data.get("status") != "OK":
        return []

    return [
        {
            "place_id": p["place_id"],
            "description": p["description"],
        }
        for p in data.get("predictions", [])
    ]


# ======================
# GOOGLE — PLACE DETAILS
# ======================
@app.get("/api/google/place")
def google_place(place_id: str):
    url = "https://maps.googleapis.com/maps/api/place/details/json"
    params = {
        "place_id": place_id,
        "key": GOOGLE_API_KEY,
        "language": "fr",
        "fields": "place_id,name,formatted_address,rating,types",
    }

    r = requests.get(url, params=params)
    data = r.json()

    result = data.get("result")
    if not result:
        raise HTTPException(status_code=400, detail="No result from Google")

    return {
        "google_place_id": result.get("place_id"),
        "name": result.get("name"),
        "address": result.get("formatted_address"),
        "rating": result.get("rating"),
        "types": result.get("types"),
    }


# ======================
# ESTABLISHMENTS — CREATE
# ======================
@app.post("/establishments")
def create_establishment(payload: dict, db: Session = Depends(get_db)):
    existing = (
        db.query(Establishment)
        .filter(Establishment.google_place_id == payload["google_place_id"])
        .first()
    )

    if existing:
        return {
            "id": existing.id,
            "message": "Déjà présent",
        }

    est = Establishment(
        google_place_id=payload["google_place_id"],
        name=payload["name"],
        address=payload["address"],
        rating=payload.get("rating"),
        types=json.dumps(payload.get("types")),
    )

    db.add(est)
    db.commit()
    db.refresh(est)

    return {
        "id": est.id,
        "message": "Ajouté",
    }


# ======================
# ESTABLISHMENTS — LIST
# ======================
@app.get("/establishments")
def list_establishments(db: Session = Depends(get_db)):
    rows = db.query(Establishment).all()
    return [
        {
            "id": r.id,
            "google_place_id": r.google_place_id,
            "name": r.name,
            "address": r.address,
            "rating": r.rating,
            "types": json.loads(r.types) if r.types else None,
        }
        for r in rows
    ]


# ======================
# FRONTEND
# ======================
app.mount("/", StaticFiles(directory="ui", html=True), name="ui")
