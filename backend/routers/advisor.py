import os
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from database import get_db
import models

# Optional import for testing environments
# the `google-genai` SDK (>=1.64.0) provides the `genai` namespace
# older packages such as google-generativeai or google-ai-generativelanguage
# have been removed from requirements.
try:
    from google import genai
except ImportError:
    genai = None 

router = APIRouter(prefix="/advisor", tags=["AI"])


@router.get("/status")
def get_advisor_status():
    api_key = os.environ.get("GEMINI_API_KEY")
    return {"enabled": bool(api_key)}


class AdvisorRequest(BaseModel):
    user_query: str
    username: str = None
    league_id: int = None


@router.post("/ask")
def ask_gemini(request: AdvisorRequest, db: Session = Depends(get_db)):
    # 1. Check for API Key and genai availability (Lazy Load)
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key or not genai:
        return {"response": "⚠️ The Commissioner is offline. (Missing GEMINI_API_KEY or genai package)"}

    # 2. FETCH CONTEXT (League-specific rules)
    rules = []
    league_name = "your league"
    if request.league_id:
        rules = db.query(models.ScoringRule).filter(models.ScoringRule.league_id == request.league_id).all()
        league = db.query(models.League).filter(models.League.id == request.league_id).first()
        if league:
            league_name = league.name
    else:
        rules = db.query(models.ScoringRule).all()

    if not rules:
        rules_text = "Standard PPR Scoring"
    else:
        rules_text = "\n".join([f"- {r.category}: {r.points} pts" for r in rules])

    # 3. CONSTRUCT PROMPT
    prompt = f"""
    You are a Fantasy Football Assistant for the '{league_name}'.
    
    LEAGUE SCORING RULES:
    {rules_text}
    
    USER: {request.username or 'A user'}
    QUESTION:
    {request.user_query}
    
    Answer briefly and specifically based on the scoring rules above.
    """

    # 4. CALL GEMINI
    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model="gemini-flash-latest",
            contents=prompt
        )
        return {"response": response.text}
    except Exception as e:
        print(f"Gemini Error: {e}")
        return {"response": "I'm having trouble connecting to the league office. Try again later."}