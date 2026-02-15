# backend/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Internal Imports
import models
from database import engine

# Import All Routers
from routers import admin, team, matchups, league, advisor, dashboard, players, waivers, draft, auth

# Load Environment Variables
load_dotenv()

# --- APP SETUP ---
# WARNING: This deletes all data! We do this ONCE to fix the columns.
#models.Base.metadata.drop_all(bind=engine) 
models.Base.metadata.create_all(bind=engine)
app = FastAPI()

# --- SECURITY: CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- CONNECT ROUTERS ---
app.include_router(auth.router)       # Handles /token and /me
app.include_router(draft.router)      # Handles /draft-pick and /draft-history
app.include_router(admin.router)
app.include_router(team.router)
app.include_router(matchups.router)
app.include_router(league.router)
app.include_router(advisor.router)
app.include_router(dashboard.router)
app.include_router(players.router) 
app.include_router(waivers.router) 

@app.get("/")
def read_root():
    return {"message": "Fantasy Football API is Running!"}