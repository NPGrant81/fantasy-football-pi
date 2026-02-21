from database import SessionLocal, engine
import models
import time
import requests

models.Base.metadata.create_all(bind=engine)
db = SessionLocal()

ESPN_TEAMS_URL = 'https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams'
ESPN_ROSTER_URL = 'https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/{team_id}/roster'
ALLOWED_POSITIONS = {'QB', 'RB', 'WR', 'TE', 'K', 'DEF'}

try:
    # Fetch teams
    print('Fetching teams from ESPN...')
    response = requests.get(ESPN_TEAMS_URL, timeout=30)
    data = response.json()
    sports = data.get('sports', [])
    leagues = sports[0].get('leagues', []) if sports else []
    teams = leagues[0].get('teams', []) if leagues else []
    
    team_list = []
    for team in teams:
        team_data = team.get('team', {})
        team_id = team_data.get('id')
        abbr = team_data.get('abbreviation')
        if team_id and abbr:
            team_list.append({'id': team_id, 'abbr': abbr})
    
    print(f'Found {len(team_list)} teams')
    
    # Try to fetch roster from first team
    if team_list:
        team = team_list[0]
        print(f'Testing roster fetch for {team["abbr"]}...')
        roster = requests.get(ESPN_ROSTER_URL.format(team_id=team['id']), timeout=30).json()
        athletes = roster.get('athletes', [])
        print(f'Found {len(athletes)} athlete groups')
        
        # Show some raw data
        if athletes:
            print(f'First group has {len(athletes[0].get("items", []))} athletes')
            for item in athletes[0].get('items', [])[:3]:
                pos = item.get('position', {}).get('abbreviation')
                name = item.get('displayName', 'Unknown')
                print(f'  - {name} ({pos})')
    
except Exception as e:
    print(f'Error: {e}')
    import traceback
    traceback.print_exc()
finally:
    db.close()
