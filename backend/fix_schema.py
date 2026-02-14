from database import engine
from sqlalchemy import text

# Connect to the database
with engine.connect() as connection:
    # Run the SQL command directly
    connection.execute(text("ALTER TABLE users ADD COLUMN is_superuser BOOLEAN DEFAULT FALSE"))
    connection.commit()
    print("✅ Success! 'is_superuser' column added.")