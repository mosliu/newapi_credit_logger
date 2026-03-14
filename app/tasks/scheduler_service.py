from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session
import threading
import time

from app.core.logging import get_logger
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.api_key_source import ApiKeySource
from app.services.balance_collector_service import collect_balance_for_source

logger = get_logger("scheduler")


class SourceSchedulerService:
    def __init__(self) -> None:
        settings = get_settings()
        self._max_workers = max(int(settings.scheduler_max_workers), 1)
        self._misfire_grace_seconds = max(
            int(settings.scheduler_misfire_grace_seconds),
            1,
        )
        self.scheduler = BackgroundScheduler(
            timezone="UTC",
            executors={
                "default": ThreadPoolExecutor(max_workers=self._max_workers),
            },
        )
        self._job_prefix = "source-balance-"
        self._started = False
        self._request_lock = threading.Lock()
        self._last_request_started_at: float | None = None

    def _wait_before_request(self) -> None:
        delay = float(get_settings().scheduler_request_delay_seconds)
        if delay <= 0:
            return

        with self._request_lock:
            now = time.monotonic()
            if self._last_request_started_at is None:
                self._last_request_started_at = now
                return

            wait_seconds = (self._last_request_started_at + delay) - now
            if wait_seconds > 0:
                time.sleep(wait_seconds)
                now = time.monotonic()
            self._last_request_started_at = now

    def start(self) -> None:
        if self._started:
            return
        self.scheduler.start()
        self._started = True
        self.reload_jobs()
        logger.info(
            "scheduler started max_workers={} misfire_grace_seconds={}",
            self._max_workers,
            self._misfire_grace_seconds,
        )

    def shutdown(self) -> None:
        if not self._started:
            return
        self.scheduler.shutdown(wait=False)
        self._started = False
        logger.info("scheduler stopped")

    def reload_jobs(self) -> int:
        if not self._started:
            return 0

        for job in list(self.scheduler.get_jobs()):
            if job.id.startswith(self._job_prefix):
                self.scheduler.remove_job(job.id)

        with SessionLocal() as db:
            sources = (
                db.query(ApiKeySource)
                .filter(ApiKeySource.enabled.is_(True))
                .order_by(ApiKeySource.id.asc())
                .all()
            )

        for source in sources:
            self.scheduler.add_job(
                func=self.run_source_job,
                trigger="interval",
                seconds=source.interval_seconds,
                id=f"{self._job_prefix}{source.id}",
                args=[source.id],
                replace_existing=True,
                max_instances=1,
                coalesce=True,
                misfire_grace_time=self._misfire_grace_seconds,
            )

        logger.info("scheduler jobs reloaded count={}", len(sources))
        return len(sources)

    def run_source_job(self, source_id: int) -> None:
        with SessionLocal() as db:
            source = db.query(ApiKeySource).filter(ApiKeySource.id == source_id).first()
            if source is None:
                logger.error("source not found source_id={}", source_id)
                return
            if not source.enabled:
                logger.info("source disabled skip source_id={}", source_id)
                return
            self._wait_before_request()
            self._collect_once(db, source)

    def collect_now(self, source_id: int) -> bool:
        with SessionLocal() as db:
            source = db.query(ApiKeySource).filter(ApiKeySource.id == source_id).first()
            if source is None:
                return False
            self._collect_once(db, source)
            return True

    @staticmethod
    def _collect_once(db: Session, source: ApiKeySource) -> None:
        collect_balance_for_source(db, source)


source_scheduler_service = SourceSchedulerService()
