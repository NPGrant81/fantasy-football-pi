import csv
from sqlalchemy.orm import Session
from database import SessionLocal
import models

CSV_PATH = 'backend/data/scoring_logic.csv'
LEAGUE_ID = 1  # Change as needed for testing

def import_scoring_logic(league_id=LEAGUE_ID):
    db: Session = SessionLocal()
    with open(CSV_PATH, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            rule = models.ScoringRule(
                event=row['Event'],
                range_yds=row['Range_Yds'],
                point_value=row['Point_Value'],
                position_ids=row['PostionID'],
                league_id=league_id
            )
            db.add(rule)
        db.commit()
    db.close()
    print(f"Imported scoring logic for league {league_id} from {CSV_PATH}")

if __name__ == '__main__':
    import_scoring_logic()
