# main.py
import os
import json
import requests
from datetime import datetime
from dotenv import load_dotenv

from fastapi import FastAPI, Depends, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from database import SessionLocal, engine, Base
from models import Establishment, Review, User, LoginToken, Session as DbSession
from schemas import (
    EstablishmentCreate, EstablishmentOut,
    ReviewCreate, ReviewOut,
    EstablishmentWithStats,
    AuthRequestLink, MeOut, UserOut
)
from security import (
    new_token, hash_token, expires_in_minutes, expires_in_days,
    COOKIE_NAME, LOGINLINK_MINUTES, SESSION_DAYS
)
from auth import get_current_user


# ---------------- ENV ----------------
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")  # peut être None sur Render si pas set


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


# ---------------- HELPERS ----------------
def require_google_key():
    if not GOOGLE_API_KEY:
        raise HTTPException(status_code=500, detail="GOOGLE_API_KEY missing (Render env var)")


def to_review_out(r: Review) -> ReviewOut:
    return ReviewOut(
        id=r.id,
        establishment_id=r.establishment_id,
        user_id=r.user_id,
        user_pseudo=r.user.pseudo if r.user else "Anon",
        score=r.score,
        comment=r.comment,
        role=r.role,
        contract=r.contract,
        housing=r.housing,
        housing_quality=r.housing_quality,
        coupure=r.coupure,
        unpaid_overtime=r.unpaid_overtime,
        toxic_manager=r.toxic_manager,
        harassment=r.harassment,
        recommend=r.recommend,
        created_at=r.created_at,
    )


# ---------------- AUTH ----------------
@app.get("/me", response_model=MeOut)
def me(user: User = Depends(get_current_user)):
    return {"user": UserOut.model_validate(user)}


@app.post("/auth/magic-link")
def auth_magic_link(payload: AuthRequestLink, request: Request, db: Session = Depends(get_db)):
    # create user if needed
    user = db.query(User).filter(User.email == payload.email).first()
    if not user:
        user = User(email=payload.email, pseudo=payload.pseudo)
        db.add(user)
        db.commit()
        db.refresh(user)

    raw = new_token()
    token_h = hash_token(raw)

    lt = LoginToken(
        user_id=user.id,
        token_hash=token_h,
        expires_at=expires_in_minutes(LOGINLINK_MINUTES),
        used_at=None,
    )
    db.add(lt)
    db.commit()

    link = str(request.base_url) + f"auth/verify?token={raw}"

    # DEV MODE: tu peux le voir dans les logs
    print("MAGIC LINK:", link)

    # En prod tu mettras un vrai email. Pour l’instant on renvoie aussi le lien (pratique).
    return {"ok": True, "dev_link": link}


@app.get("/auth/verify")
def auth_verify(token: str, response: Response, db: Session = Depends(get_db)):
    token_h = hash_token(token)
    lt = db.query(LoginToken).filter(LoginToken.token_hash == token_h).first()

    if not lt:
        raise HTTPException(status_code=400, detail="Invalid token")
    if lt.used_at is not None:
        raise HTTPException(status_code=400, detail="Token already used")
    if lt.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Token expired")

    # mark token used
    lt.used_at = datetime.utcnow()
    db.commit()

    # create session cookie (new token)
    session_raw = new_token()
    session_h = hash_token(session_raw)

    s = DbSession(
        user_id=lt.user_id,
        session_hash=session_h,
        expires_at=expires_in_days(SESSION_DAYS),
    )
    db.add(s)
    db.commit()

    # set cookie
    response.set_cookie(
        key=COOKIE_NAME,
        value=session_raw,
        httponly=True,
        secure=False,      # mettre True quand tu es en https (Render => https)
        samesite="lax",
        max_age=60 * 60 * 24 * SESSION_DAYS,
        path="/",
    )

    # redirect UI
    response.status_code = 302
    response.headers["Location"] = "/ui/"
    return response


@app.post("/auth/logout")
def logout(response: Response):
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True}


# ---------------- GOOGLE API ----------------
@app.get("/api/google/autocomplete")
def google_autocomplete(q: str = Query(min_length=1)):
    require_google_key()

    url = "https://maps.googleapis.com/maps/api/place/autocomplete/json"
    params = {"input": q, "types": "establishment", "language": "fr", "key": GOOGLE_API_KEY}

    r = requests.get(url, params=params, timeout=15)
    data = r.json()

    if data.get("status") not in ("OK", "ZERO_RESULTS"):
        raise HTTPException(status_code=400, detail=data)

    return [{"place_id": p["place_id"], "description": p["description"]} for p in data.get("predictions", [])]


@app.get("/api/google/place")
def google_place(place_id: str):
    require_google_key()

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
        "address": result.get("formatted_address"),
        "google_rating": result.get("rating"),
        "types": result.get("types", []),
    }


# ---------------- ESTABLISHMENTS ----------------
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


@app.get("/establishments/by_google/{google_place_id}", response_model=EstablishmentWithStats)
def get_by_google(google_place_id: str, db: Session = Depends(get_db)):
    est = db.query(Establishment).filter(Establishment.google_place_id == google_place_id).first()
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

    try:
        types = json.loads(est.types_json) if est.types_json else []
    except Exception:
        types = []

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
        reviews=[to_review_out(r) for r in reviews],
        thena_avg=avg,
        thena_count_scored=len(scores),
        thena_count_total=len(reviews),
    )


# ---------------- REVIEWS (AUTH REQUIRED) ----------------
@app.post("/reviews", response_model=ReviewOut)
def create_or_update_review(
    payload: ReviewCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    est = db.query(Establishment).get(payload.establishment_id)
    if not est:
        raise HTTPException(status_code=404, detail="Establishment not found")

    # 1 avis max -> update si déjà existant (best UX)
    existing = db.query(Review).filter(
        Review.establishment_id == payload.establishment_id,
        Review.user_id == user.id
    ).first()

    if existing:
        existing.score = payload.score
        existing.comment = payload.comment
        existing.role = payload.role
        existing.contract = payload.contract
        existing.housing = payload.housing
        existing.housing_quality = payload.housing_quality
        existing.coupure = payload.coupure
        existing.unpaid_overtime = payload.unpaid_overtime
        existing.toxic_manager = payload.toxic_manager
        existing.harassment = payload.harassment
        existing.recommend = payload.recommend
        db.commit()
        db.refresh(existing)
        return to_review_out(existing)

    review = Review(
        establishment_id=payload.establishment_id,
        user_id=user.id,
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
    return to_review_out(review)


@app.delete("/reviews/{review_id}")
def delete_review(
    review_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    r = db.query(Review).get(review_id)
    if not r:
        raise HTTPException(status_code=404, detail="Review not found")

    if r.user_id != user.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    db.delete(r)
    db.commit()
    return {"ok": True}


# ---------------- UI ----------------
app.mount("/ui", StaticFiles(directory="ui", html=True), name="ui")


@app.get("/")
def root():
    return FileResponse("ui/index.html")

