import os
from fastapi import APIRouter, Depends, HTTPException
from google import genai
from sqlalchemy.orm import Session
from database import get_db
import models 

router = APIRouter(prefix="/advisor", tags=["AI"])

@router.post("/ask")
def ask_gemini(user_query: str, db: Session = Depends(get_db)):
    # 1. Check for API Key (Lazy Load)
    # We check here inside the function so the server doesn't crash on startup if it's missing
    api_key = os.environ.get("GEMINI_API_KEY")
    
    if not api_key:
        # Return a polite error in the chat window instead of crashing the server
        return {"response": "⚠️ The Commissioner is offline. (Missing GEMINI_API_KEY in .env)"}

    # 2. FETCH CONTEXT (Your specific league rules)
    # We grab the rules from the DB to "teach" the AI about your league
    rules = db.query(models.ScoringRule).all()
    if not rules:
        rules_text = "Standard PPR Scoring" # Fallback if DB is empty
    else:
        rules_text = "\n".join([f"- {r.category}: {r.points} pts" for r in rules])

    # 3. CONSTRUCT PROMPT
    prompt = f"""
    You are a Fantasy Football Assistant for the 'Post Pacific League'.
    
    LEAGUE SCORING RULES:
    {rules_text}
    
    USER QUESTION:
    {user_query}
    
    Answer briefly and specifically based on the scoring rules above.
    """

    # 4. CALL GEMINI
    try:
        # CONNECT HERE (Inside the function)
        client = genai.Client(api_key=api_key)
        
        response = client.models.generate_content(
            model="gemini-2.0-flash", 
            contents=prompt
        )
        return {"response": response.text}
    except Exception as e:
        # If Google is down or the key is wrong, tell the user gracefully
        print(f"Gemini Error: {e}")
        return {"response": "I'm having trouble connecting to the league office. Try again later."}