import json
from typing import List, Optional

from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session

from database import SessionLocal, engine
import models
import schemas

# Crée les tables si elles n'existent pas
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="THENA", version="0.2.0")


# ---- DB Dependency ----
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---- Root / Health ----
@app.get("/")
def root():
    return {"app": "THENA", "message": "API running"}


@app.get("/health")
def health():
    return {"status": "ok"}


# =========================================================
# Establishments CRUD
# =========================================================
@app.post("/establishments", response_model=schemas.EstablishmentOut, status_code=201)
def create_establishment(payload: schemas.EstablishmentCreate, db: Session = Depends(get_db)):
    # évite les doublons exacts (name+city+category)
    existing = (
        db.query(models.Establishment)
        .filter(
            models.Establishment.name == payload.name,
            models.Establishment.city == payload.city,
            models.Establishment.category == payload.category,
        )
        .first()
    )
    if existing:
        return existing

    est = models.Establishment(
        name=payload.name,
        city=payload.city,
        category=payload.category,
    )
    db.add(est)
    db.commit()
    db.refresh(est)
    return est


@app.get("/establishments", response_model=List[schemas.EstablishmentOut])
def list_establishments(
    city: Optional[str] = None,
    category: Optional[str] = None,
    db: Session = Depends(get_db),
):
    q = db.query(models.Establishment)
    if city:
        q = q.filter(models.Establishment.city == city)
    if category:
        q = q.filter(models.Establishment.category == category)
    return q.order_by(models.Establishment.id.asc()).all()


@app.get("/establishments/{establishment_id}", response_model=schemas.EstablishmentOut)
def get_establishment(establishment_id: int, db: Session = Depends(get_db)):
    est = db.query(models.Establishment).filter(models.Establishment.id == establishment_id).first()
    if not est:
        raise HTTPException(status_code=404, detail="Establishment not found.")
    return est


@app.put("/establishments/{establishment_id}", response_model=schemas.EstablishmentOut)
def update_establishment(
    establishment_id: int,
    payload: schemas.EstablishmentUpdate,
    db: Session = Depends(get_db),
):
    est = db.query(models.Establishment).filter(models.Establishment.id == establishment_id).first()
    if not est:
        raise HTTPException(status_code=404, detail="Establishment not found.")

    est.name = payload.name
    est.city = payload.city
    est.category = payload.category

    db.commit()
    db.refresh(est)
    return est


@app.delete("/establishments/{establishment_id}", status_code=204)
def delete_establishment(establishment_id: int, db: Session = Depends(get_db)):
    est = db.query(models.Establishment).filter(models.Establishment.id == establishment_id).first()
    if not est:
        raise HTTPException(status_code=404, detail="Establishment not found.")
    db.delete(est)
    db.commit()
    return None


# =========================================================
# Reviews (avec tags)
# =========================================================
def _serialize_tags(tags: List[str]) -> str:
    # normalise: trim + lower + unique + pas vides
    cleaned = []
    seen = set()
    for t in tags:
        t2 = (t or "").strip().lower()
        if not t2:
            continue
        if t2 in seen:
            continue
        seen.add(t2)
        cleaned.append(t2)
    return json.dumps(cleaned, ensure_ascii=False)


def _deserialize_tags(tags_json: str) -> List[str]:
    try:
        data = json.loads(tags_json or "[]")
        if isinstance(data, list):
            return [str(x) for x in data]
    except Exception:
        pass
    return []


@app.post(
    "/establishments/{establishment_id}/reviews",
    response_model=schemas.ReviewOut,
    status_code=201,
)
def create_review(
    establishment_id: int,
    payload: schemas.ReviewCreate,
    db: Session = Depends(get_db),
):
    est = db.query(models.Establishment).filter(models.Establishment.id == establishment_id).first()
    if not est:
        raise HTTPException(status_code=404, detail="Establishment not found.")

    review = models.Review(
        establishment_id=establishment_id,
        rating=int(payload.rating),
        comment=payload.comment,
        tags_json=_serialize_tags(payload.tags),
    )
    db.add(review)
    db.commit()
    db.refresh(review)

    return schemas.ReviewOut(
        id=review.id,
        establishment_id=review.establishment_id,
        rating=review.rating,
        comment=review.comment,
        tags=_deserialize_tags(review.tags_json),
        created_at=review.created_at,
    )


@app.get(
    "/establishments/{establishment_id}/reviews",
    response_model=List[schemas.ReviewOut],
)
def list_reviews_for_establishment(establishment_id: int, db: Session = Depends(get_db)):
    est = db.query(models.Establishment).filter(models.Establishment.id == establishment_id).first()
    if not est:
        raise HTTPException(status_code=404, detail="Establishment not found.")

    reviews = (
        db.query(models.Review)
        .filter(models.Review.establishment_id == establishment_id)
        .order_by(models.Review.id.desc())
        .all()
    )

    return [
        schemas.ReviewOut(
            id=r.id,
            establishment_id=r.establishment_id,
            rating=r.rating,
            comment=r.comment,
            tags=_deserialize_tags(r.tags_json),
            created_at=r.created_at,
        )
        for r in reviews
    ]


@app.delete("/reviews/{review_id}", status_code=204)
def delete_review(review_id: int, db: Session = Depends(get_db)):
    r = db.query(models.Review).filter(models.Review.id == review_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Review not found.")
    db.delete(r)
    db.commit()
    return None


