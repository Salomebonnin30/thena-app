from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


# ------------------
# Establishments
# ------------------

class EstablishmentBase(BaseModel):
    google_place_id: str
    name: str
    address: Optional[str] = None
    google_rating: Optional[float] = None
    types: Optional[List[str]] = None


class EstablishmentCreate(EstablishmentBase):
    pass


class EstablishmentOut(EstablishmentBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


# ------------------
# Reviews
# ------------------

class ReviewCreate(BaseModel):
    establishment_id: int
    score: Optional[int] = Field(default=None, ge=0, le=10)
    comment: str = Field(min_length=1)

    role: Optional[str] = None
    contract: Optional[str] = None

    # NEW: logement
    # values attendues côté UI (ex): "non_loge" / "loge_employeur"
    housing: Optional[str] = None
    # values attendues côté UI (ex): "bon" / "moyen" / "mauvais"
    housing_quality: Optional[str] = None

    # Tags (booleans)
    coupure: bool = False
    unpaid_overtime: bool = False
    toxic_manager: bool = False
    harassment: bool = False
    recommend: bool = False


class ReviewOut(BaseModel):
    id: int
    establishment_id: int

    score: Optional[int] = None
    comment: str

    role: Optional[str] = None
    contract: Optional[str] = None

    # NEW: logement
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


# ------------------
# Full establishment card
# ------------------

class EstablishmentWithStats(BaseModel):
    establishment: EstablishmentOut
    reviews: List[ReviewOut]

    thena_avg: Optional[float] = None
    thena_count_scored: int = 0
    thena_count_total: int = 0

