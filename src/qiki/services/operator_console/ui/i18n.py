from __future__ import annotations

from typing import Any, Optional


def bidi(en: str, ru: str) -> str:
    return f"{en}/{ru}"


NA = bidi("N/A", "НД")
INVALID = bidi("INVALID", "НЕКОРР")
YES = bidi("yes", "да")
NO = bidi("no", "нет")


def yes_no(value: bool) -> str:
    return YES if value else NO


def online_offline(value: bool) -> str:
    return bidi("ONLINE", "В СЕТИ") if value else bidi("OFFLINE", "НЕТ СВЯЗИ")


def stale(value: str) -> str:
    return f"{bidi('STALE', 'УСТАР')}: {value}"


NO_TRACKS_YET = bidi("no tracks yet", "треков нет")
UNKNOWN = bidi("unknown", "неизвестно")


def _is_num(value: Any) -> bool:
    return isinstance(value, (int, float))


def num(value: Any, *, digits: int = 2) -> Optional[str]:
    if not _is_num(value):
        return None
    return str(round(float(value), digits))


def num_unit(value: Any, en_unit: str, ru_unit: str, *, digits: int = 2) -> str:
    n = num(value, digits=digits)
    if n is None:
        return NA
    if en_unit == ru_unit:
        return f"{n}{en_unit}"
    if len(en_unit) <= 2 and len(ru_unit) <= 2:
        return f"{n}{en_unit}/{n}{ru_unit}"
    return f"{n} {en_unit}/{n} {ru_unit}"


def pct(value: Any, *, digits: int = 2, min_value: float = 0.0, max_value: float = 100.0) -> str:
    """Format a percent value with basic sanity bounds.

    Returns `INVALID/НЕКОРР` when the value is numeric but outside [min_value, max_value].
    """

    if not _is_num(value):
        return NA
    v = float(value)
    if v < min_value or v > max_value:
        return INVALID
    return num_unit(v, "%", "%", digits=digits)


def fmt_na(value: Any) -> str:
    if value is None:
        return NA
    if isinstance(value, str) and not value.strip():
        return NA
    return str(value)


def fmt_age(seconds: Any) -> str:
    """Format a time duration for UI in strict EN/RU, no-mocks.

    - None/invalid -> N/A/НД
    - <60s -> "12.3 seconds/12.3 секунды"
    - <60m -> "5.2 minutes/5.2 минуты"
    - else -> "1.0 hours/1.0 часы"
    """

    if not _is_num(seconds):
        return NA
    s = max(0.0, float(seconds))
    if s < 60.0:
        return num_unit(s, "seconds", "секунды", digits=1)
    m = s / 60.0
    if m < 60.0:
        return num_unit(m, "minutes", "минуты", digits=1)
    h = m / 60.0
    return num_unit(h, "hours", "часы", digits=1)
