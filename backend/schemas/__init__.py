# backend/schemas/__init__.py

# 1. AUTH & USERS
from .user import User, UserCreate, UserBase, Token

# 2. LEAGUE & TEAMS
from .league import League, LeagueCreate, Team, TeamCreate
# If you have LeagueShow or LeagueBase in league.py, add them here too:
# from .league import LeagueShow 

# 3. DRAFT (The new logic we just built)
from .draft import DraftPickCreate, DraftPickShow, DraftPickBase

# 4. SCORING
from .scoring import ScoringRule, ScoringRuleCreate

# 5. WAIVERS & TRADES (Uncomment these lines once those files have classes)
# from .waiver import WaiverClaim, WaiverClaimCreate
# from .trade import TradeOffer, TradeOfferCreate

# 6. ADMIN (If needed)
# from .admin import AdminSettings
