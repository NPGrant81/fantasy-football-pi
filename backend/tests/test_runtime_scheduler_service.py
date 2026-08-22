import logging

from backend.services.runtime_scheduler_service import (
    RuntimeSchedulerManager,
    SchedulerRegistration,
)


def test_manager_starts_enabled_schedulers_and_stops_in_reverse_order():
    events: list[str] = []

    registrations = [
        SchedulerRegistration(
            name=name,
            start=lambda name=name: events.append(f"start:{name}") or object(),
            stop=lambda name=name: events.append(f"stop:{name}"),
        )
        for name in ("watchdog", "polling", "news")
    ]
    manager = RuntimeSchedulerManager(registrations, logging.getLogger(__name__))

    manager.start()
    manager.stop()

    assert events == [
        "start:watchdog",
        "start:polling",
        "start:news",
        "stop:news",
        "stop:polling",
        "stop:watchdog",
    ]
    assert manager.started_names == ()


def test_manager_does_not_own_disabled_scheduler():
    events: list[str] = []
    manager = RuntimeSchedulerManager(
        [
            SchedulerRegistration(
                name="disabled",
                start=lambda: None,
                stop=lambda: events.append("stop:disabled"),
            )
        ],
        logging.getLogger(__name__),
    )

    manager.start()
    manager.stop()

    assert events == []
    assert manager.started_names == ()


def test_manager_continues_after_scheduler_start_failure():
    events: list[str] = []

    def fail_start():
        raise RuntimeError("simulated start failure")

    manager = RuntimeSchedulerManager(
        [
            SchedulerRegistration("broken", fail_start, lambda: events.append("stop:broken")),
            SchedulerRegistration(
                "healthy",
                lambda: events.append("start:healthy") or object(),
                lambda: events.append("stop:healthy"),
            ),
        ],
        logging.getLogger(__name__),
    )

    manager.start()
    manager.stop()

    assert events == ["start:healthy", "stop:healthy"]


def test_manager_continues_cleanup_after_stop_failure_and_is_idempotent():
    events: list[str] = []

    def fail_stop():
        events.append("stop:broken")
        raise RuntimeError("simulated stop failure")

    manager = RuntimeSchedulerManager(
        [
            SchedulerRegistration(
                "healthy",
                lambda: object(),
                lambda: events.append("stop:healthy"),
            ),
            SchedulerRegistration("broken", lambda: object(), fail_stop),
        ],
        logging.getLogger(__name__),
    )

    manager.start()
    manager.stop()
    manager.stop()

    assert events == ["stop:broken", "stop:healthy"]
    assert manager.started_names == ()
