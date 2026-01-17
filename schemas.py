# schemas.py
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field


# ---------- AUTH ----------
class AuthRequestLink(BaseModel):
    email: EmailStr
    pseudo: str = Field(min_length=2, max_length=50)


class UserOut(BaseModel):
    id: int
    pseudo: str
    created_at: datetime

    class Config:
        from_attributes = True


class MeOut(BaseModel):
    user: UserOut


# ---------- ESTABLISHMENTS ----------
class EstablishmentCreate(BaseModel):
    google_place_id: str
    name: str
    address: Optional[str] = None
    google_rating: Optional[float] = None
    types: List[str] = []


class EstablishmentOut(BaseModel):
    id: int
    google_place_id: str
    name: str
    address: Optional[str] = None
    google_rating: Optional[float] = None
    types: List[str] = []
    created_at: datetime

    class Config:
        from_attributes = True


# ---------- REVIEWS ----------
class ReviewCreate(BaseModel):
    establishment_id: int
    score: Optional[float] = None
    comment: str

    role: Optional[str] = None
    contract: Optional[str] = None

    housing: Optional[str] = None
    housing_quality: Optional[str] = None

    coupure: bool = False
    unpaid_overtime: bool = False
    toxic_manager: bool = False
    harassment: bool = False
    recommend: bool = False


class ReviewOut(BaseModel):
    id: int
    establishment_id: int

    user_id: int
    user_pseudo: str

    score: Optional[float] = None
    comment: str

    role: Optional[str] = None
    contract: Optional[str] = None

    housing: Optional[str] = None
    housing_quality: Optional[str] = None

    coupure: bool
    unpaid_overtime: bool
    toxic_manager: bool
    harassment: bool
    recommend: bool

    created_at: datetime

    class Config:
        from_attributes = True


class EstablishmentWithStats(BaseModel):
    establishment: EstablishmentOut
    reviews: List[ReviewOut]
    thena_avg: Optional[float] = None
    thena_count_scored: int
    thena_count_total: int



