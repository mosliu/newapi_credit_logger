from types import SimpleNamespace

import pytest

from app.tasks import scheduler_service
from app.tasks.scheduler_service import SourceSchedulerService


def test_scheduler_wait_before_request_throttles(monkeypatch) -> None:
    service = SourceSchedulerService()

    # Make delay deterministic and avoid real sleep.
    monkeypatch.setattr(
        scheduler_service,
        "get_settings",
        lambda: SimpleNamespace(scheduler_request_delay_seconds=1.0),
    )

    monotonic_values = iter([10.0, 10.2, 11.0])
    monkeypatch.setattr(
        scheduler_service.time,
        "monotonic",
        lambda: next(monotonic_values),
    )

    slept: list[float] = []
    monkeypatch.setattr(
        scheduler_service.time,
        "sleep",
        lambda seconds: slept.append(float(seconds)),
    )

    service._wait_before_request()
    service._wait_before_request()

    assert len(slept) == 1
    assert slept[0] == pytest.approx(0.8, abs=1e-6)
