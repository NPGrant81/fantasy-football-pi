import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from schemas import user as user_schemas


def test_user_create_and_token_models():
    uc = user_schemas.UserCreate(username="bob", email="bob@example.com", password="pw")
    assert uc.username == "bob"

    token = user_schemas.Token(access_token="tok", token_type="bearer", owner_id=42, league_id=None)
    assert token.owner_id == 42
    assert token.token_type == "bearer"
