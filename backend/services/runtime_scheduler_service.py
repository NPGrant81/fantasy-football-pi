from collections.abc import Callable, Iterable
from dataclasses import dataclass
import logging


StartScheduler = Callable[[], object | None]
StopScheduler = Callable[[], None]


@dataclass(frozen=True)
class SchedulerRegistration:
    name: str
    start: StartScheduler
    stop: StopScheduler


class RuntimeSchedulerManager:
    def __init__(
        self,
        registrations: Iterable[SchedulerRegistration],
        logger: logging.Logger,
    ) -> None:
        self._registrations = tuple(registrations)
        self._logger = logger
        self._started: list[SchedulerRegistration] = []

    @property
    def started_names(self) -> tuple[str, ...]:
        return tuple(registration.name for registration in self._started)

    def start(self) -> None:
        if self._started:
            self._logger.warning("Runtime schedulers are already started")
            return

        for registration in self._registrations:
            try:
                scheduler = registration.start()
            except Exception:
                self._logger.exception(
                    "Runtime scheduler failed to start name=%s",
                    registration.name,
                )
                continue

            if scheduler is None:
                self._logger.info(
                    "Runtime scheduler disabled or unavailable name=%s",
                    registration.name,
                )
                continue

            self._started.append(registration)
            self._logger.info("Runtime scheduler started name=%s", registration.name)

    def stop(self) -> None:
        while self._started:
            registration = self._started.pop()
            try:
                registration.stop()
            except Exception:
                self._logger.exception(
                    "Runtime scheduler failed to stop name=%s",
                    registration.name,
                )
                continue

            self._logger.info("Runtime scheduler stopped name=%s", registration.name)
