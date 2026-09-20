from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class LoginRequest(BaseModel):
    phone: str = Field(..., description="Worker or supervisor phone number")
    password: str = Field(..., description="User password")


class LoginResponse(BaseModel):
    access_token: str
    role: str
    user_id: str


class UserResponse(BaseModel):
    id: str
    name: str
    phone: str
    role: str
    location_id: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
