from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, conint


# -------- Establishments --------
class EstablishmentBase(BaseModel):
    name: str = Field(min_length=1)
    city: str = Field(min_length=1)
    category: str = Field(min_length=1)


class EstablishmentCreate(EstablishmentBase):
    pass


class EstablishmentUpdate(EstablishmentBase):
    pass


class EstablishmentOut(EstablishmentBase):
    id: int

    class Config:
        from_attributes = True


# -------- Reviews --------
class ReviewBase(BaseModel):
    rating: conint(ge=1, le=5)  # 1..5
    comment: Optional[str] = None
    tags: List[str] = []


class ReviewCreate(ReviewBase):
    pass


class ReviewOut(ReviewBase):
    id: int
    establishment_id: int
    created_at: datetime

    class Config:
        from_attributes = True
