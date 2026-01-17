import os
import json
import requests
from dotenv import load_dotenv
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from database import SessionLocal, engine, Base
from models import Establishment, Review
from schemas import (
    EstablishmentCreate,
    EstablishmentOut,
    ReviewCreate,
    ReviewOut,
    EstablishmentWithStats
)

# ---------------- ENV ----------------
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if not GOOGLE_API_KEY:
    raise RuntimeError("GOOGLE_API_KEY missing in .env")

# ---------------- APP ----------------
app = FastAPI(title="THENA", version="1.0.0")

Base.metadata.create_all(bind=engine)

# ---------------- DB ----------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ---------------- GOOGLE API ----------------
@app.get("/api/google/autocomplete")
def google_autocomplete(q: str = Query(min_length=1)):
    url = "https://maps.googleapis.com/maps/api/place/autocomplete/json"
    params = {
        "input": q,
        "types": "establishment",
        "language": "fr",
        "key": GOOGLE_API_KEY,
    }

    r = requests.get(url, params=params, timeout=15)
    data = r.json()

    if data.get("status") not in ("OK", "ZERO_RESULTS"):
        raise HTTPException(status_code=400, detail=data)

    return [
        {
            "place_id": p["place_id"],
            "description": p["description"],
        }
        for p in data.get("predictions", [])
    ]


@app.get("/api/google/place")
def google_place(place_id: str):
    url = "https://maps.googleapis.com/maps/api/place/details/json"
    params = {
        "place_id": place_id,
        "fields": "place_id,name,formatted_address,rating,types",
        "language": "fr",
        "key": GOOGLE_API_KEY,
    }

    r = requests.get(url, params=params, timeout=15)
    data = r.json()

    if data.get("status") != "OK":
        raise HTTPException(status_code=400, detail=data)

    result = data["result"]

    return {
        "google_place_id": result["place_id"],
        "name": result["name"],
        "address": result["formatted_address"],
        "google_rating": result.get("rating"),
        "types": result.get("types", []),
    }

# ---------------- ESTABLISHMENTS ----------------
@app.post("/establishments", response_model=EstablishmentOut)
def create_establishment(payload: EstablishmentCreate, db: Session = Depends(get_db)):
    existing = db.query(Establishment).filter(
        Establishment.google_place_id == payload.google_place_id
    ).first()

    if existing:
        return existing

    est = Establishment(
        google_place_id=payload.google_place_id,
        name=payload.name,
        address=payload.address,
        google_rating=payload.google_rating,
        types_json=json.dumps(payload.types or []),
    )

    db.add(est)
    db.commit()
    db.refresh(est)
    return est


@app.get("/establishments/by_google/{google_place_id}", response_model=EstablishmentWithStats)
def get_by_google(google_place_id: str, db: Session = Depends(get_db)):
    est = db.query(Establishment).filter(
        Establishment.google_place_id == google_place_id
    ).first()

    if not est:
        raise HTTPException(status_code=404, detail="Not in THENA")

    return build_establishment_stats(est.id, db)


@app.get("/establishments/{establishment_id}", response_model=EstablishmentWithStats)
def get_establishment(establishment_id: int, db: Session = Depends(get_db)):
    est = db.query(Establishment).get(establishment_id)
    if not est:
        raise HTTPException(status_code=404, detail="Not found")

    return build_establishment_stats(est.id, db)


def build_establishment_stats(est_id: int, db: Session) -> EstablishmentWithStats:
    est = db.query(Establishment).get(est_id)
    reviews = (
        db.query(Review)
        .filter(Review.establishment_id == est_id)
        .order_by(Review.created_at.desc())
        .all()
    )

    scores = [r.score for r in reviews if r.score is not None]
    avg = round(sum(scores) / len(scores), 1) if scores else None

    types = json.loads(est.types_json) if est.types_json else []

    return EstablishmentWithStats(
        establishment=EstablishmentOut(
            id=est.id,
            google_place_id=est.google_place_id,
            name=est.name,
            address=est.address,
            google_rating=est.google_rating,
            types=types,
            created_at=est.created_at,
        ),
        reviews=[ReviewOut.model_validate(r) for r in reviews],
        thena_avg=avg,
        thena_count_scored=len(scores),
        thena_count_total=len(reviews),
    )

# ---------------- REVIEWS ----------------
@app.post("/reviews", response_model=ReviewOut)
def create_review(payload: ReviewCreate, db: Session = Depends(get_db)):
    est = db.query(Establishment).get(payload.establishment_id)
    if not est:
        raise HTTPException(status_code=404, detail="Establishment not found")

    review = Review(
        establishment_id=payload.establishment_id,
        score=payload.score,
        comment=payload.comment,
        role=payload.role,
        contract=payload.contract,

        housing=payload.housing,
        housing_quality=payload.housing_quality,

        coupure=payload.coupure,
        unpaid_overtime=payload.unpaid_overtime,
        toxic_manager=payload.toxic_manager,
        harassment=payload.harassment,
        recommend=payload.recommend,
    )

    db.add(review)
    db.commit()
    db.refresh(review)
    return review


@app.delete("/reviews/{review_id}")
def delete_review(review_id: int, db: Session = Depends(get_db)):
    r = db.query(Review).get(review_id)
    if not r:
        raise HTTPException(status_code=404, detail="Review not found")

    db.delete(r)
    db.commit()
    return {"ok": True}

# ---------------- UI ----------------
app.mount("/ui", StaticFiles(directory="ui", html=True), name="ui")

@app.get("/")
def root():
    return FileResponse("ui/index.html")
