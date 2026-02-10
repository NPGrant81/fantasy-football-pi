from pydantic import BaseModel
from typing import Optional

class UserBase(BaseModel):
    username: str
    email: Optional[str] = None

class UserCreate(UserBase):
    password: str

class User(UserBase):
    id: int
    role: str  # Sends "admin", "commish", or "user" to frontend
    is_commissioner: bool
    division: Optional[str] = None
    team_name: Optional[str] = None 

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str
    role: str       
    user_id: int
