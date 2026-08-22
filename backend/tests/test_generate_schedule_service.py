from backend.services import generate_schedule as schedule_service


def test_generate_schedule_closes_session_on_early_return(monkeypatch):
    events = []

    class FakeQuery:
        def all(self):
            return []

    class FakeSession:
        def __enter__(self):
            events.append("enter")
            return self

        def __exit__(self, *_args):
            events.append("exit")

        def query(self, _model):
            return FakeQuery()

    monkeypatch.setattr(schedule_service, "SessionLocal", FakeSession)
    monkeypatch.setattr(schedule_service, "assert_schema_ready", lambda *_args: None)

    schedule_service.generate_schedule()

    assert events == ["enter", "exit"]