from database import engine
from sqlalchemy import text

def reset_table():
    print("🗑️  Dropping old 'matchups' table...")
    
    with engine.connect() as connection:
        connection.execute(text("DROP TABLE IF EXISTS matchups CASCADE"))
        connection.commit()
        
    print("✅ Table dropped. Now run 'python generate_schedule.py' to rebuild it!")

if __name__ == "__main__":
    reset_table()