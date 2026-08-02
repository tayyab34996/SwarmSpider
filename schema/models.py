from pydantic import BaseModel, Field, HttpUrl
from typing import Optional

class ProductRecord(BaseModel):
    url: str
    title: str = Field(..., min_length=1)
    price: float = Field(..., ge=0.0)
    in_stock: bool
    description: Optional[str] = None
