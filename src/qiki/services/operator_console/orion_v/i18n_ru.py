from __future__ import annotations

TERMS = {
    "ok": "НОРМА",
    "warn": "ПРЕДУПРЕЖДЕНИЕ",
    "crit": "КРИТИЧНО",
    "online": "Связь установлена",
    "offline": "Связь отсутствует",
    "reconnecting": "Переподключение",
    "soc": "Уровень заряда",
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
