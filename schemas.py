from pydantic import BaseModel
from typing import Optional, List

class EstablishmentCreate(BaseModel):
    google_place_id: str
    name: str
    address: str
    rating: Optional[float] = None
    types: Optional[List[str]] = None

class EstablishmentOut(BaseModel):
    id: int
    google_place_id: str
    name: str
    address: str
    rating: Optional[float] = None
    types: Optional[List[str]] = None

    class Config:
        from_attributes = True

