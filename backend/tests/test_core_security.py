import pytest
from backend.core import security
from datetime import timedelta
from fastapi import HTTPException


def test_password_hash_and_verify():
    pw = "supersecret"
    hashed = security.get_password_hash(pw)
    assert isinstance(hashed, str)
    assert security.verify_password(pw, hashed)
    assert not security.verify_password("wrong", hashed)


def test_create_access_token_and_decode():
    token = security.create_access_token({"sub": "alice"}, expires_delta=timedelta(minutes=5))
    from jose import jwt
    payload = jwt.decode(token, security.SECRET_KEY, algorithms=[security.ALGORITHM], options={"verify_exp": False})
    assert payload.get("sub") == "alice"


@pytest.mark.asyncio
async def test_check_is_commissioner_allows_and_denies():
    class UserObj:
        pass

    good = UserObj()
    good.is_commissioner = True
    # Should return the user unchanged
    returned = await security.check_is_commissioner(good)
    assert returned is good

    bad = UserObj()
    bad.is_commissioner = False
    with pytest.raises(HTTPException):
        await security.check_is_commissioner(bad)
