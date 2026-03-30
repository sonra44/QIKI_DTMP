from __future__ import annotations

from typing import Any

from textual.widgets import Static

from qiki.services.operator_console.orion_v.i18n_ru import tr


class OrionVSystemHealthScreen(Static):
    """Runtime health and load metrics view (F7)."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._metrics: dict[str, Any] = {}

    def on_mount(self) -> None:
        self._refresh_text()

    def set_state(self, metrics: dict[str, Any]) -> None:
        self._metrics = metrics
        self._refresh_text()

    def _refresh_text(self) -> None:
        m = self._metrics
        body = [
            "[F7] Состояние системы",
            "",
            f"NATS: {m.get('nats_state', 'lost')}",
            f"{tr('events_per_sec')}: {m.get('events_per_sec', 0.0):.2f}",
            f"{tr('queue_depth')}: {m.get('queue_depth', 0)}",
            f"{tr('bounded_store')}: {m.get('bounded_store_size', 0)} / {m.get('bounded_store_limit', 0)}",
            f"{tr('procedure_latency')}: {m.get('procedure_latency_ms', 0.0):.1f} мс",
            f"{tr('ack_time')}: {m.get('ack_time_ms', 0.0):.1f} мс",
            f"Загрузка процессора: {m.get('cpu_percent', 0.0):.2f}%",
            f"{tr('memory_usage')}: {m.get('memory_mb', 0.0):.1f} MiB",
            f"{tr('active_subscriptions')}: {m.get('active_subscriptions', 0)}",
            f"{tr('replay_mode')}: {bool(m.get('replay_mode', False))}",
        ]
        self.update("\n".join(body))
