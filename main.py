import os
import json
import requests
from dotenv import load_dotenv
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sqlalchemy import func

from database import SessionLocal, engine, Base
from models import Establishment, Review
from schemas import (
    EstablishmentCreate, EstablishmentOut,
    ReviewCreate, ReviewOut,
    EstablishmentWithStats
)

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")

app = FastAPI(title="THENA", version="0.1.0")

# DB init
Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ---------------- Google API helpers ----------------

def require_google_key():
    if not GOOGLE_API_KEY:
        raise HTTPException(status_code=500, detail="GOOGLE_API_KEY missing in .env")

@app.get("/api/google/autocomplete")
def google_autocomplete(q: str = Query(min_length=1), db: Session = Depends(get_db)):
    require_google_key()

    url = "https://maps.googleapis.com/maps/api/place/autocomplete/json"
    params = {
        "input": q,
        "types": "establishment",
        "key": GOOGLE_API_KEY,
        "language": "fr",
    }
    r = requests.get(url, params=params, timeout=15)
    data = r.json()

    status = data.get("status")
    if status not in ("OK", "ZERO_RESULTS"):
        raise HTTPException(status_code=400, detail={"google_status": status, "raw": data})

    preds = data.get("predictions", [])
    return [
        {
            "place_id": p.get("place_id"),
            "description": p.get("description"),
        }
        for p in preds
    ]

@app.get("/api/google/place")
def google_place(place_id: str):
    require_google_key()

    url = "https://maps.googleapis.com/maps/api/place/details/json"
    params = {
        "place_id": place_id,
        "fields": "place_id,name,formatted_address,rating,types",
        "key": GOOGLE_API_KEY,
        "language": "fr",
    }
    r = requests.get(url, params=params, timeout=15)
    data = r.json()

    status = data.get("status")
    if status != "OK":
        raise HTTPException(status_code=400, detail={"google_status": status, "raw": data})

    result = data.get("result") or {}
    return {
        "google_place_id": result.get("place_id"),
        "name": result.get("name"),
        "address": result.get("formatted_address"),
        "google_rating": result.get("rating"),
        "types": result.get("types") or [],
    }

# ---------------- Establishments ----------------

@app.post("/establishments", response_model=EstablishmentOut)
def create_establishment(payload: EstablishmentCreate, db: Session = Depends(get_db)):
    existing = db.query(Establishment).filter(Establishment.google_place_id == payload.google_place_id).first()
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

@app.get("/establishments", response_model=list[EstablishmentOut])
def list_establishments(db: Session = Depends(get_db)):
    return db.query(Establishment).order_by(Establishment.id.desc()).all()

@app.get("/establishments/by_google/{google_place_id}", response_model=EstablishmentWithStats)
def get_by_google(google_place_id: str, db: Session = Depends(get_db)):
    est = db.query(Establishment).filter(Establishment.google_place_id == google_place_id).first()
    if not est:
        raise HTTPException(status_code=404, detail="Not in THENA DB")

    return build_establishment_stats(est.id, db)

@app.get("/establishments/{establishment_id}", response_model=EstablishmentWithStats)
def get_establishment(establishment_id: int, db: Session = Depends(get_db)):
    est = db.query(Establishment).filter(Establishment.id == establishment_id).first()
    if not est:
        raise HTTPException(status_code=404, detail="Not found")
    return build_establishment_stats(est.id, db)

def build_establishment_stats(establishment_id: int, db: Session) -> EstablishmentWithStats:
    est = db.query(Establishment).filter(Establishment.id == establishment_id).first()
    if not est:
        raise HTTPException(status_code=404, detail="Not found")

    reviews = db.query(Review).filter(Review.establishment_id == establishment_id).order_by(Review.created_at.desc()).all()

    # moyenne sur scores non-null
    scored = [r.score for r in reviews if r.score is not None]
    thena_avg = round(sum(scored) / len(scored), 1) if scored else None

    # parse types
    try:
        types = json.loads(est.types_json) if est.types_json else []
    except Exception:
        types = []

    est_out = EstablishmentOut(
        id=est.id,
        google_place_id=est.google_place_id,
        name=est.name,
        address=est.address,
        google_rating=est.google_rating,
        types=types,
        created_at=est.created_at,
    )

    rev_out = [ReviewOut.model_validate(r) for r in reviews]

    return EstablishmentWithStats(
        establishment=est_out,
        reviews=rev_out,
        thena_avg=thena_avg,
        thena_count_scored=len(scored),
        thena_count_total=len(reviews),
    )

# ---------------- Reviews ----------------

@app.post("/reviews", response_model=ReviewOut)
def create_review(payload: ReviewCreate, db: Session = Depends(get_db)):
    est = db.query(Establishment).filter(Establishment.id == payload.establishment_id).first()
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
    r = db.query(Review).filter(Review.id == review_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Review not found")
    db.delete(r)
    db.commit()
    return {"ok": True}

# ---------------- UI static ----------------

app.mount("/ui", StaticFiles(directory="ui", html=True), name="ui")

@app.get("/")
def root():
    return FileResponse("ui/index.html")
