from pydantic import BaseModel
from typing import Optional

# Base class (shared fields)
class UserBase(BaseModel):
    username: str
    email: Optional[str] = None

# Input (What we need to create a user)
class UserCreate(UserBase):
    password: str

# Output (What we show the frontend)
class User(UserBase):
    id: int
    is_commissioner: bool = False  # Default to False if missing
    league_id: Optional[int] = None
    team_name: Optional[str] = None 
    
    # We removed 'role' because it doesn't exist in your DB yet
    # We added 'league_id' so the frontend knows which league you are in

    class Config:
        from_attributes = True

# The Login Response (Must match routers/auth.py!)
class Token(BaseModel):
    access_token: str
    token_type: str
    owner_id: int             # Matches user.id
    league_id: Optional[int]  # Critical for the frontend to know where to go
