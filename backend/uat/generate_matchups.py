# backend/uat/generate_matchups.py
from services.generate_schedule import generate_schedule

def run():
    print("\n⚡ Generating matchups after seeding...")
    generate_schedule()
    print("✅ Matchups generated!")

if __name__ == "__main__":
    run()
