# backend/reset_password.py
from database import SessionLocal
import models
from core.security import get_password_hash

# 1. Start a DB Session
db = SessionLocal()

# 2. Find the user
username = "Nick Grant"
user = db.query(models.User).filter(models.User.username == username).first()

if user:
    # 3. Generate a brand new hash using YOUR current auth.py logic
    new_hash = get_password_hash("password")
    
    # 4. Update the user
    user.hashed_password = new_hash
    db.commit()
    
    print(f"✅ SUCCESS: Password for '{username}' has been reset to 'password'")
    print(f"New Hash: {new_hash}")
else:
    print(f"❌ ERROR: User '{username}' not found in database!")

db.close()