# backend/uat/seed_draft.py
import random
from sqlalchemy.orm import Session
from backend import models
from backend.services import player_service

def get_safe_player(db: Session, pool, position, owner_id):
    # 1.1 VALIDATION: Use existing player if available
    if pool:
        return pool.pop(0)
    
    fallback_positions = [position] if position in {'QB', 'RB', 'WR', 'TE', 'K', 'DEF'} else ['RB', 'WR', 'TE']
    fallback_rows = []
    for fallback_position in fallback_positions:
        fallback_rows.extend(
            db.query(models.Player)
            .filter(models.Player.position == fallback_position)
            .all()
        )

    valid_rows = [row for row in fallback_rows if player_service.is_valid_player_row(row)]
    if valid_rows:
        print(f"⚠️  Warning: Out of unique {position}s! Reusing existing player for Owner {owner_id}.")
        return random.choice(valid_rows)

    raise RuntimeError(f"Unable to seed draft because no valid {position} players are available")

def seed_draft(db: Session, league_id: int | None = None):
    print("🎲 SEEDING DRAFT: Fast-Forwarding to Season Start...")

    # 1.1 DATA: Fetch owners and shuffle position pools
    owners_query = db.query(models.User).filter(models.User.league_id.isnot(None))
    if league_id is not None:
        owners_query = owners_query.filter(models.User.league_id == league_id)
    owners = owners_query.all()
    if not owners:
        print("❌ No owners found!")
        return {"owners": 0, "picks_created": 0}

    pools = {
        'QB': db.query(models.Player).filter(models.Player.position == 'QB').all(),
        'RB': db.query(models.Player).filter(models.Player.position == 'RB').all(),
        'WR': db.query(models.Player).filter(models.Player.position == 'WR').all(),
        'TE': db.query(models.Player).filter(models.Player.position == 'TE').all(),
        'K': db.query(models.Player).filter(models.Player.position == 'K').all(),
        'DEF': db.query(models.Player).filter(models.Player.position == 'DEF').all()
    }
    for pool in pools.values(): random.shuffle(pool)

    picks_created = 0

    # 2.1 EXECUTION: Draft Loop
    for owner in owners:
        starters = []
        # 2.1.1 CORE STARTERS
        starters.append(get_safe_player(db, pools['QB'], 'QB', owner.id))
        starters.append(get_safe_player(db, pools['RB'], 'RB', owner.id))
        starters.append(get_safe_player(db, pools['RB'], 'RB', owner.id))
        starters.append(get_safe_player(db, pools['WR'], 'WR', owner.id))
        starters.append(get_safe_player(db, pools['WR'], 'WR', owner.id))
        starters.append(get_safe_player(db, pools['TE'], 'TE', owner.id))
        starters.append(get_safe_player(db, pools['K'], 'K', owner.id))
        starters.append(get_safe_player(db, pools['DEF'], 'DEF', owner.id))
        
        # 2.1.2 FLEX STARTER: Using the safe logic on the combined pool
        # We pass 'RB' as the label, but it could be any valid flex pos
        flex_pool = pools['RB'] + pools['WR'] + pools['TE']
        random.shuffle(flex_pool)
        starters.append(get_safe_player(db, flex_pool, 'FLEX', owner.id))

        # Update the original pools so players aren't "double-drafted"
        # (This is why we shuffle the combined pool but must sync back)
        for player in starters:
            db.add(models.DraftPick(
                year=2026, current_status="STARTER", owner_id=owner.id, 
                player_id=player.id, league_id=owner.league_id, amount=random.randint(15,60),
                session_id="TEST_2026-UAT"
            ))
            picks_created += 1

        # 2.1.3 BENCH: 5 Slots using safe logic
        for _ in range(5):
            bench_pool = pools['RB'] + pools['WR'] + pools['TE']
            random.shuffle(bench_pool)
            bench_player = get_safe_player(db, bench_pool, 'BENCH', owner.id)
            db.add(models.DraftPick(
                year=2026, current_status="BENCH", owner_id=owner.id, 
                player_id=bench_player.id, league_id=owner.league_id, amount=random.randint(1,10),
                session_id="TEST_2026-UAT"
            ))
            picks_created += 1
    
    db.commit()
    print("✨ DRAFT SEEDING SUCCESSFUL.")
    return {"owners": len(owners), "picks_created": picks_created}