from pathlib import Path

from loguru import logger

from app.core.config import Settings


def configure_logging(settings: Settings) -> None:
    log_dir = Path(settings.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    logger.remove()
    logger.configure(extra={"component": "app"})

    logger.add(
        log_dir / "app.log",
        level=settings.log_level.upper(),
        rotation=settings.log_rotation,
        retention=settings.log_retention,
        encoding="utf-8",
        enqueue=True,
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<8} | {extra[component]} | {message}",
    )
    logger.add(
        log_dir / "error.log",
        level="ERROR",
        rotation=settings.log_rotation,
        retention=settings.log_retention,
        encoding="utf-8",
        enqueue=True,
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<8} | {extra[component]} | {message}",
    )
    logger.add(
        log_dir / "scheduler.log",
        level=settings.log_level.upper(),
        rotation=settings.log_rotation,
        retention=settings.log_retention,
        encoding="utf-8",
        enqueue=True,
        filter=lambda record: record["extra"].get("component") == "scheduler",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<8} | {extra[component]} | {message}",
    )


def get_logger(component: str = "app"):
    return logger.bind(component=component)
