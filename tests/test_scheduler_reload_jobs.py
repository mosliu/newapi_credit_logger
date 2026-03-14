from contextlib import contextmanager
from types import SimpleNamespace

from app.tasks import scheduler_service
from app.tasks.scheduler_service import SourceSchedulerService


def test_scheduler_reload_jobs_sets_misfire_grace(monkeypatch) -> None:
    monkeypatch.setattr(
        scheduler_service,
        "get_settings",
        lambda: SimpleNamespace(
            scheduler_request_delay_seconds=1.0,
            scheduler_misfire_grace_seconds=25,
            scheduler_max_workers=4,
        ),
    )

    service = SourceSchedulerService()
    service._started = True

    source = SimpleNamespace(id=101, interval_seconds=300)

    class _FakeQuery:
        def filter(self, *_args, **_kwargs):
            return self

        def order_by(self, *_args, **_kwargs):
            return self

        def all(self):
            return [source]

    class _FakeDb:
        def query(self, *_args, **_kwargs):
            return _FakeQuery()

    @contextmanager
    def _fake_session_local():
        yield _FakeDb()

    monkeypatch.setattr(scheduler_service, "SessionLocal", _fake_session_local)
    monkeypatch.setattr(service.scheduler, "get_jobs", lambda: [])

    added_job_kwargs: dict[str, object] = {}

    def _fake_add_job(**kwargs):
        added_job_kwargs.update(kwargs)

    monkeypatch.setattr(service.scheduler, "add_job", _fake_add_job)

    count = service.reload_jobs()

    assert count == 1
    assert added_job_kwargs["id"] == f"{service._job_prefix}{source.id}"
    assert added_job_kwargs["misfire_grace_time"] == 25
    assert added_job_kwargs["max_instances"] == 1
    assert added_job_kwargs["coalesce"] is True
