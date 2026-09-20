from typing import Optional
from pydantic import BaseModel, Field


class ChildCreate(BaseModel):
    name: str = Field(..., min_length=1)
    dob: str = Field(..., description="YYYY-MM-DD")
    gender: str = Field(default="O", pattern="^(M|F|O)$")
    guardian_name: Optional[str] = None
    village: Optional[str] = None


class ChildResponse(BaseModel):
    child_id: str
    name: str
    dob: str
    gender: str
    guardian_name: Optional[str] = None
    village: Optional[str] = None

    class Config:
        from_attributes = True
