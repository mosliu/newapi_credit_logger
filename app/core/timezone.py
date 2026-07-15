from datetime import datetime, timedelta, timezone

# 全站展示统一使用东八区（UTC+8）
CST = timezone(timedelta(hours=8))


def to_cst(value: datetime | None) -> datetime | None:
    """将 UTC 时间（naive 视为 UTC）转换为东八区时间。"""
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(CST)


def fmt_cst(value: datetime | None, fmt: str = "%Y-%m-%d %H:%M:%S", default: str = "-") -> str:
    """格式化为东八区时间字符串，供 Jinja 过滤器使用。"""
    converted = to_cst(value)
    return converted.strftime(fmt) if converted else default


def cst_to_utc_naive(value: datetime | None) -> datetime | None:
    """将东八区本地时间（naive 视为东八区）转换为 naive UTC，用于与数据库时间比较。"""
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=CST)
    return value.astimezone(timezone.utc).replace(tzinfo=None)
