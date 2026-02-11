import os
from fastapi import APIRouter, Depends, HTTPException
from google import genai
from sqlalchemy.orm import Session
from database import get_db
import models 

router = APIRouter(prefix="/advisor", tags=["AI"])

# Initialize the Client (It will look for GEMINI_API_KEY in env)
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

@router.post("/ask")
def ask_gemini(user_query: str, db: Session = Depends(get_db)):
    if not os.environ.get("GEMINI_API_KEY"):
        raise HTTPException(status_code=500, detail="Gemini API Key not configured")

    # 1. FETCH CONTEXT (Your specific league rules)
    rules = db.query(models.ScoringRule).all()
    # Format rules into a readable list for the AI
    rules_text = "\n".join([f"- {r.category}: {r.points} pts" for r in rules])

    # 2. CONSTRUCT PROMPT
    prompt = f"""
    You are a Fantasy Football Assistant for the 'Post Pacific League'.
    
    LEAGUE SCORING RULES:
    {rules_text}
    
    USER QUESTION:
    {user_query}
    
    Answer briefly and specifically based on the scoring rules above.
    """

    # 3. CALL GEMINI (Using the 2.0 Flash model for speed)
    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash", 
            contents=prompt
        )
        return {"response": response.text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
