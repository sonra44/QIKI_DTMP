from __future__ import annotations

TERMS = {
    "ok": "НОРМА",
    "warn": "ПРЕДУПРЕЖДЕНИЕ",
    "crit": "КРИТИЧНО",
    "online": "Связь установлена",
    "offline": "Связь отсутствует",
    "reconnecting": "Переподключение",
    "soc": "Заряд батареи",
    "bus_voltage": "Напряжение шины",
    "bus_current": "Ток шины",
    "limit_mode": "Режим ограничения",
    "load_shedding": "Аварийное отключение нагрузки",
    "shed_reasons": "Причины сброса",
    "latency": "Задержка",
    "packet_loss": "Потеря пакетов",
    "rssi": "Уровень сигнала",
    "last_rx": "Последний прием",
    "speed": "Скорость",
    "heading": "Курс",
    "alignment_error": "Ошибка выравнивания",
    "core_temp": "Температура ядра",
    "radiator_temp": "Температура радиатора",
    "sink_temp": "Температура теплоотвода",
    "queue_depth": "Глубина очереди",
    "events_per_sec": "Событий в секунду",
    "bounded_store": "Хранилище событий",
    "procedure_latency": "Задержка процедуры",
    "ack_time": "Время подтверждения",
    "cpu_usage": "Загрузка CPU",
    "memory_usage": "Использование памяти",
    "active_subscriptions": "Активные подписки",
    "replay_mode": "Режим анализа истории",
}


def tr(key: str) -> str:
    return TERMS.get(key, key)


# Значения-состояния для ИГРОВОГО ПОЛЯ (показ; коды в view-model остаются кодами).
# ВАЖНО: словарь доверия §17 (trusted/missing/degraded/stale/conflicting) и
# канонические reason-codes сюда НЕ входят — они остаются машинными.
STATE_RU = {
    "online": "в строю",
    "attached": "установлен",
    "already_attached": "уже установлен",
    "validated": "проверен",
    "inactive": "неактивна",
    "active": "активна",
    "ready": "готов",
    "green": "норма",
    "yellow": "внимание",
    "orange": "внимание",
    "red": "крит",
    "nominal": "норма",
    "waiting": "ожидание",
    "pending": "ожидается",
    "unknown": "неизвестно",
    "free": "свободна",
    "occupied": "занята",
    "recorded": "записано",
    "ok": "норма",
    "blocked": "блок",
    "target": "цель",
    "limited": "ограничен",
    "critical": "крит",
    "none": "нет",
    "idle": "ожидание",
    "standby": "ожидание",
    "preview": "предпросмотр",
    "error": "ошибка",
    "hold": "удержание",
    "rejected": "отклонено",
    "shown": "показана",
    "missing": "нет данных",
}


def state_ru(value: object) -> str:
    """Русское отображение значения-состояния; незнакомое значение возвращается как есть."""
    text = str(value or "").strip()
    return STATE_RU.get(text.lower(), text)


# Проза физических последствий для игрового поля (ПОКАЗ; значения в VM остаются
# как есть — тесты держат их как честную семантику «модель не знает»).
PHYS_RU = {
    "unknown / waiting for attach": "неизвестно / ждём установки модуля",
    "unknown / requires mass + geometry": "неизвестно / нужны масса и геометрия",
    "unknown / requires mass+geometry": "неизвестно / нужны масса и геометрия",
    "unknown / requires inertia model": "неизвестно / нужна модель инерции",
    "pending; requires mass + geometry": "ожидается / нужны масса и геометрия",
    "unchanged": "без изменений",
    "TBD": "не задано",
    "aggressive burn not unlocked": "агрессивный манёвр не разблокирован",
    "none; waiting for attach self-check": "нет; ждём проверку корпуса (B)",
    "pending; do not unlock aggressive burn until real mass/CoM/inertia and "
    "Thrust/Torque maps exist":
        "ожидается; агрессивный манёвр не разблокировать до реальных массы/ЦМ/инерции "
        "и карт тяги/момента",
    "none": "нет",
}


def phys_ru(value: object) -> str:
    """Русское отображение прозы физики; незнакомое — как есть."""
    return PHYS_RU.get(str(value or "").strip(), str(value or ""))

