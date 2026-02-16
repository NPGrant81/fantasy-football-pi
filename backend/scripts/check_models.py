# backend/check_models.py
import google.generativeai as genai
import os
from dotenv import load_dotenv

# 1. Load the specific .env file
load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("❌ Error: GEMINI_API_KEY not found in .env")
else:
    print(f"✅ Found API Key: {api_key[:5]}...{api_key[-4:]}")
    
    try:
        genai.configure(api_key=api_key)
        print("\n🔍 Listing available models for this key...")
        
        count = 0
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                print(f"   - {m.name}")
                count += 1
        
        if count == 0:
            print("\n⚠️  No models found! This usually means the key doesn't have permissions yet.")
        else:
            print(f"\n✨ Found {count} available models!")
            
    except Exception as e:
        print(f"\n❌ Connection Failed: {e}")