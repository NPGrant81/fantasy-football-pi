import os
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import models
from backend.routers.advisor import ask_gemini, get_advisor_status, AdvisorRequest


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    models.Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


def make_league(db):
    l = models.League(name="TestLeague")
    db.add(l)
    db.commit()
    db.refresh(l)
    return l


def make_scoring_rule(db, league_id, category="passing", points=1):
    r = models.ScoringRule(
        league_id=league_id,
        category=category,
        event_name="Event",
        point_value=points,
        calculation_type="flat_bonus",
    )
    db.add(r)
    db.commit()
    db.refresh(r)
    return r


def make_user(db, league_id, username="bob", team_name="TeamX"):
    u = models.User(
        username=username,
        hashed_password="pw",
        league_id=league_id,
        team_name=team_name,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def test_status_reflects_env(monkeypatch):
    # no API key -> disabled
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert get_advisor_status()["enabled"] is False
    # set key -> enabled
    monkeypatch.setenv("GEMINI_API_KEY", "fake")
    assert get_advisor_status()["enabled"] is True


def test_ask_returns_offline_when_no_key(monkeypatch, db_session):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    # ensure genai import is present (could be None)
    monkeypatch.setattr("backend.routers.advisor.genai", None)
    req = AdvisorRequest(user_query="hi")
    result = ask_gemini(req, db=db_session)
    assert "Commissioner is offline" in result["response"]


def test_ask_uses_point_value_and_includes_team(monkeypatch, db_session):
    # arrange league, user, and scoring rule
    league = make_league(db_session)
    make_scoring_rule(db_session, league.id, category="QB", points=6)
    make_user(db_session, league.id, username="alice", team_name="Aces")

    # stub gemini client and capture prompt
    captured = {}

    class FakeGenAI:
        class Client:
            def __init__(self, api_key):
                pass

            class models:
                @staticmethod
                def generate_content(model, contents):
                    captured["prompt"] = contents
                    class R:
                        text = "dummy response"
                    return R()

    monkeypatch.setenv("GEMINI_API_KEY", "key123")
    monkeypatch.setattr("backend.routers.advisor.genai", FakeGenAI)

    req = AdvisorRequest(user_query="what about my team?", username="alice", league_id=league.id)
    resp = ask_gemini(req, db=db_session)

    assert resp["response"] == "dummy response"
    # prompt should mention point value and team name
    # point_value is formatted with two decimals in the prompt
    assert "QB: 6" in captured["prompt"]
    assert "Aces" in captured["prompt"]


def test_ask_handles_empty_rules(monkeypatch, db_session):
    league = make_league(db_session)
    # no rules inserted
    monkeypatch.setenv("GEMINI_API_KEY", "key123")

    # reuse the same pattern as above but return a simple OK text
    class FakeGenAI2:
        class Client:
            def __init__(self, api_key):
                pass

            class models:
                @staticmethod
                def generate_content(model, contents):
                    return type("R", (), {"text": "ok"})()

    monkeypatch.setattr("backend.routers.advisor.genai", FakeGenAI2)
    req = AdvisorRequest(user_query="foo", username=None, league_id=None)
    resp = ask_gemini(req, db=db_session)
    assert resp["response"] == "ok"


