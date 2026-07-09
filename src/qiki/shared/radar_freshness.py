"""Владелец порогов свежести радар-треков (M5 карты AUDIT_2026-07-09_POSTFIX).

Канон-грунт (RAG 2026-07-09): BODY_CANON §17 требует freshness/stale data как
обязательный атрибут честности данных; численный TTL канон не задаёт —
инженерная константа. Числа зеркалят дефолты `sensor_runtime.freshness`
(stale_after_s=5.0, dead_after_s=30.0) — единая шкала свежести для сенсоров
и треков; менять согласованно.

Потребители: мозговая WorldModel (эвикция мёртвых треков — фантом умершего
сенсора не держит вечный critical-гвард) и страница РАДАР консоли (пометка
устаревших, скрытие мёртвых с честным счётчиком).
"""

from __future__ import annotations

import math

RADAR_TRACK_STALE_S = 5.0
RADAR_TRACK_DEAD_S = 30.0

FRESH = "fresh"
STALE = "stale"
DEAD = "dead"


def classify_track_freshness(age_s: float | None) -> str:
    """Возраст последнего приёма → fresh | stale | dead.

    None/не-конечный возраст = свежесть неизвестна: честный минимум — stale
    (не хороним данные молча, но и не выдаём за свежие).
    """
    if age_s is None or not math.isfinite(float(age_s)):
        return STALE
    age = float(age_s)
    if age >= RADAR_TRACK_DEAD_S:
        return DEAD
    if age >= RADAR_TRACK_STALE_S:
        return STALE
    return FRESH
