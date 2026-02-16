from database import engine
from sqlalchemy import text

def reset_table():
    print("🗑️  Dropping old 'draft_picks' table...")
    
    with engine.connect() as connection:
        # We use CASCADE because 'draft_picks' is referenced by other constraints
        connection.execute(text("DROP TABLE IF EXISTS draft_picks CASCADE"))
        connection.commit()
        
    print("✅ Table dropped. Now run 'python seed_draft.py' to rebuild it!")

if __name__ == "__main__":
    reset_table()