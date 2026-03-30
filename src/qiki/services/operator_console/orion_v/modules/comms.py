from __future__ import annotations

from typing import Any

from qiki.services.operator_console.orion_v.modules.base import SubsystemModule
from qiki.services.operator_console.orion_v.modules.common import (
    pick_num,
    pick_text,
    status_tag,
    telemetry_from_state,
)
from qiki.services.operator_console.orion_v.i18n_ru import tr


class CommsSubsystemModule(SubsystemModule):
    slug = "comms"
    title = "Связь"

    def render_summary(self, state: dict[str, Any]) -> str:
        telemetry = telemetry_from_state(state)
        link = pick_text(telemetry, ["comms", "link"]).lower()
        if not link:
            link = pick_text(telemetry, ["comms", "link_state"]).lower()
        latency = pick_num(telemetry, ["comms", "latency_ms"])
        loss = pick_num(telemetry, ["comms", "packet_loss_pct"])

        crit = (
            link in {"down", "offline"} or (latency is not None and latency > 3000) or (loss is not None and loss > 20)
        )
        warn = (link == "") or (latency is not None and latency > 800) or (loss is not None and loss > 5)
        ok = link in {"up", "online"} or latency is not None or loss is not None
        status = status_tag(ok=ok, warn=warn, crit=crit)

        link_value = "Нет данных"
        if link in {"up", "online"}:
            link_value = tr("online")
        elif link in {"down", "offline"}:
            link_value = tr("offline")
        elif link:
            link_value = link
        link_text = f"Состояние канала {link_value}"
        lat_text = f"{tr('latency')} {latency:.0f}мс" if latency is not None else f"{tr('latency')} —"
        loss_text = f"{tr('packet_loss')} {loss:.1f}%" if loss is not None else f"{tr('packet_loss')} —"
        return f"{status} | {link_text} | {lat_text} | {loss_text}"

    def render_details(self, state: dict[str, Any]) -> str:
        telemetry = telemetry_from_state(state)
        link = pick_text(telemetry, ["comms", "link"])
        if not link:
            link = pick_text(telemetry, ["comms", "link_state"])
        latency = pick_num(telemetry, ["comms", "latency_ms"])
        loss = pick_num(telemetry, ["comms", "packet_loss_pct"])
        rssi = pick_num(telemetry, ["comms", "rssi_dbm"])
        snr = pick_num(telemetry, ["comms", "snr_db"])
        tx_power = pick_num(telemetry, ["comms", "tx_power_w"])
        data_rate = pick_num(telemetry, ["comms", "data_rate_kbps"])
        antenna_status = pick_text(telemetry, ["comms", "antenna_status"])
        last_rx_s = pick_num(telemetry, ["comms", "age_s"])
        if last_rx_s is None:
            last_rx_s = pick_num(telemetry, ["comms", "last_rx_s"])
        warning = pick_text(telemetry, ["comms", "warning"])

        lines = [
            f"{self.title}: детали",
            f"- Состояние канала: {link or 'Нет данных'}",
            f"- {tr('latency')}: {f'{latency:.1f}мс' if latency is not None else 'Нет данных'}",
            f"- {tr('packet_loss')}: {f'{loss:.2f}%' if loss is not None else 'Нет данных'}",
            f"- {tr('rssi')}: {f'{rssi:.1f} dBm' if rssi is not None else 'Нет данных'}",
            f"- SNR: {f'{snr:.1f} dB' if snr is not None else 'Нет данных'}",
            f"- TX Power: {f'{tx_power:.1f} Вт' if tx_power is not None else 'Нет данных'}",
            f"- Data Rate: {f'{data_rate:.1f} kbps' if data_rate is not None else 'Нет данных'}",
            f"- Антенна: {antenna_status or 'Нет данных'}",
            f"- Время с последнего приема: {f'{last_rx_s:.1f}с' if last_rx_s is not None else 'Нет данных'}",
            f"- Предупреждение: {warning or '—'}",
            "",
            "Источники истины:",
        ]
        lines.extend(f"- {src}" for src in self.sources_of_truth())
        return "\n".join(lines)

    def sources_of_truth(self) -> tuple[str, ...]:
        return (
            "comms.link",
            "comms.link_state",
            "comms.latency_ms",
            "comms.packet_loss_pct",
            "comms.rssi_dbm",
            "comms.snr_db",
            "comms.tx_power_w",
            "comms.data_rate_kbps",
            "comms.antenna_status",
            "comms.age_s",
            "comms.last_rx_s",
            "comms.warning",
        )
