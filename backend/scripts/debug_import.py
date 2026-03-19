import sys, importlib, os
from pathlib import Path

# make project root importable (same trick used by import_scoring_rules)
# add repo root to path (script lives under backend/scripts)
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# set up environment variable similar to test
path = Path('temp.db')
url = f"sqlite:///{path.as_posix()}"
print('setting DATABASE_URL to', url)
os.environ['DATABASE_URL'] = url

import backend.database as database
importlib.reload(database)
import backend.scripts.import_scoring_rules as importer
importlib.reload(importer)

print('engine url after reload', database.engine.url)

records = [importer.sanitize_row({'Event':'A','Range_Yds':'1-2','Point_Value':'1','PostionID':'8002'})]
importer.insert_rules(5, records)

from backend.database import SessionLocal
from sqlalchemy import text
sess = SessionLocal()
res = sess.execute(text('SELECT count(*) FROM scoring_rules WHERE league_id = :lid'), {'lid': 5})
print('row count after insert', res.scalar())
sess.close()
