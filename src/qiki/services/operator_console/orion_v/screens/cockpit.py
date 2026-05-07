from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from textual.app import ComposeResult
from textual.containers import Container
from textual.css.query import NoMatches
from textual.widgets import Button, Static

from qiki.shared.models.qiki_chat import QikiChatResponseV1

if TYPE_CHECKING:
    from qiki.services.operator_console.orion_v.operator_state import OperatorShellState


@dataclass(slots=True)
class OperatorUsefulFact:
    title_ru: str
    value_ru: str
    severity: str = "ok"
    source_path: str = "unknown"
    freshness: str = "unknown"
    trust: str = "unknown"
    reason_code: str = ""
    operator_meaning_ru: str = ""
    next_step_ru: str = ""


class OrionVCockpitScreen(Static):
    """F1: Russian MFD cockpit for operator-useful telemetry, not raw data dumps."""

    DEFAULT_CSS = """
    OrionVCockpitScreen {
        layout: vertical;
    }

    #orionv-mfd-root {
        height: 1fr;
        layout: vertical;
    }

    #orionv-mfd-status {
        height: auto;
        border: round $surface-lighten-1 15%;
        background: $panel-darken-1 5%;
        padding: 0 1;
        margin: 0 0 1 0;
    }

    #orionv-mfd-main {
        height: 2fr;
        layout: horizontal;
        margin: 0 0 1 0;
    }

    #orionv-mfd-left-buttons,
    #orionv-mfd-right-buttons {
        width: 12;
        layout: vertical;
        border: round $surface-lighten-1 15%;
        padding: 0 1;
    }

    #orionv-cockpit-body,
    #orionv-mfd-right-screen {
        width: 1fr;
        border: round $surface-lighten-1 15%;
        background: $panel-darken-1 4%;
        padding: 0 1;
        margin: 0 1;
    }

    #orionv-cockpit-intervention {
        height: 1fr;
        min-height: 10;
        border: round $surface-lighten-1 15%;
        background: $panel-darken-1 4%;
        padding: 0 1;
    }

    #orionv-cockpit-actions {
        display: none;
    }

    OrionVCockpitScreen Button {
        width: 100%;
        margin: 0 0 1 0;
    }
    """

    LEFT_PAGES = (
        ("radar", "РАДАР"),
        ("nav", "НАВ"),
        ("target", "ЦЕЛЬ"),
        ("sector", "СЕКТОР"),
        ("mission", "МИССИЯ"),
    )
    RIGHT_PAGES = (
        ("systems", "СИСТ"),
        ("sensors", "СЕНС"),
        ("power", "ПИТ"),
        ("thermal", "ТЕПЛО"),
        ("comms", "СВЯЗЬ"),
        ("propulsion", "ДВИГ"),
        ("docking", "СТЫК"),
        ("journal", "ЖУРН"),
        ("procedures", "ПРОЦ"),
    )

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._telemetry: dict[str, Any] = {}
        self._nats_connected = False
        self._active_incidents = 0
        self._incidents: list[dict[str, str]] = []
        self._safe_mode: dict[str, Any] = {}
        self._observation_objective: dict[str, Any] | None = None
        self._objective_event_lines: list[str] = []
        self._qiki_response: QikiChatResponseV1 | None = None
        self._qiki_pending_action_title: str | None = None
        self._qiki_plan_preview_lines: list[str] = []
        self._qiki_procedure_status: str | None = None
        self._operator_shell_state: Any | None = None
        self._left_page = "radar"
        self._right_page = "systems"
        self._fallback_render = ""

    def compose(self) -> ComposeResult:
        with Container(id="orionv-mfd-root"):
            yield Static("", id="orionv-mfd-status")
            with Container(id="orionv-mfd-main"):
                with Container(id="orionv-mfd-left-buttons"):
                    for page, label in self.LEFT_PAGES:
                        yield Button(label, id=f"orionv-mfd-left-{page}")
                yield Static("", id="orionv-cockpit-body")
                yield Static("", id="orionv-mfd-right-screen")
                with Container(id="orionv-mfd-right-buttons"):
                    for page, label in self.RIGHT_PAGES:
                        yield Button(label, id=f"orionv-mfd-right-{page}")
            yield Static("", id="orionv-cockpit-intervention")
            with Container(id="orionv-cockpit-actions"):
                yield Button("Маршрут", id="orionv-cockpit-jump-navigation")
                yield Button("Стыковка", id="orionv-cockpit-jump-docking")
                yield Button("Питание", id="orionv-cockpit-jump-power")
                yield Button("Связь", id="orionv-cockpit-jump-comms")
                yield Button("Тепло", id="orionv-cockpit-jump-thermal")
                yield Button("Инциденты", id="orionv-cockpit-jump-incidents")
                yield Button("Процедуры", id="orionv-cockpit-jump-procedures")
                yield Button("Подтвердить QIKI", id="orionv-cockpit-qiki-confirm", variant="primary")
                yield Button("Отменить QIKI", id="orionv-cockpit-qiki-cancel")

    def on_mount(self) -> None:
        self._set_border("#orionv-mfd-status", "ОРИОН / СТАТУС", "операторская пригодность состояния")
        self._set_border("#orionv-mfd-left-buttons", "ЛКН", "левый MFD")
        self._set_border("#orionv-mfd-right-buttons", "ПКН", "правый MFD")
        self._set_border("#orionv-cockpit-body", "ЛЕВЫЙ MFD", "внешний мир")
        self._set_border("#orionv-mfd-right-screen", "ПРАВЫЙ MFD", "тело QIKI")
        self._set_border("#orionv-cockpit-intervention", "QIKI / ОПЕРАТОР", "решение | доверие | последствие")
        self._refresh_text()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        if button_id.startswith("orionv-mfd-left-"):
            self._left_page = button_id.removeprefix("orionv-mfd-left-")
            self._refresh_text()
        elif button_id.startswith("orionv-mfd-right-"):
            self._right_page = button_id.removeprefix("orionv-mfd-right-")
            self._refresh_text()

    def set_state(
        self,
        *,
        telemetry: dict[str, Any],
        nats_connected: bool,
        active_incidents: int,
        incidents: list[dict[str, str]] | None = None,
        safe_mode: dict[str, Any] | None = None,
        observation_objective: dict[str, Any] | None = None,
        objective_event_lines: list[str] | None = None,
        qiki_response: QikiChatResponseV1 | None = None,
        qiki_pending_action_title: str | None = None,
        qiki_plan_preview_lines: list[str] | None = None,
        qiki_procedure_status: str | None = None,
        operator_shell_state: "OperatorShellState | None" = None,
    ) -> None:
        self._telemetry = telemetry or {}
        self._nats_connected = bool(nats_connected)
        self._active_incidents = int(active_incidents or 0)
        self._incidents = incidents or []
        self._safe_mode = safe_mode or {}
        self._observation_objective = dict(observation_objective or {}) or None
        self._objective_event_lines = list(objective_event_lines or [])
        self._qiki_response = qiki_response
        self._qiki_pending_action_title = qiki_pending_action_title
        self._qiki_plan_preview_lines = list(qiki_plan_preview_lines or [])
        self._qiki_procedure_status = qiki_procedure_status
        self._operator_shell_state = operator_shell_state
        self._refresh_text()

    def _refresh_text(self) -> None:
        status_text = self._status_strip()
        left_text = self._render_left_mfd()
        right_text = self._render_right_mfd()
        chat_text = self._render_qiki_chat()
        self._fallback_render = "\n\n".join([status_text, left_text, right_text, chat_text])
        self._update_static("#orionv-mfd-status", status_text)
        self._update_static("#orionv-cockpit-body", left_text)
        self._update_static("#orionv-mfd-right-screen", right_text)
        self._update_static("#orionv-cockpit-intervention", chat_text)
        try:
            confirm = self.query_one("#orionv-cockpit-qiki-confirm", Button)
            cancel = self.query_one("#orionv-cockpit-qiki-cancel", Button)
            visible = self._qiki_pending_action_title is not None
            confirm.display = visible
            cancel.display = visible
            confirm.disabled = not visible
            cancel.disabled = not visible
        except NoMatches:
            self.update(self._fallback_render)

    def _status_strip(self) -> str:
        facts = [
            self._telemetry_status_fact(),
            self._sim_status_fact(),
            self._safe_mode_fact(),
            self._power_fact(),
            self._thermal_fact(),
            self._sensor_summary_fact(),
            self._qiki_status_fact(),
            self._incident_fact(),
        ]
        return " | ".join(f"{fact.title_ru}: {fact.value_ru}" for fact in facts)

    def _render_left_mfd(self) -> str:
        title = self._page_label(self.LEFT_PAGES, self._left_page)
        if self._left_page == "radar":
            lines = self._radar_lines()
        elif self._left_page == "nav":
            lines = self._navigation_lines()
        elif self._left_page == "target":
            lines = self._target_lines()
        elif self._left_page == "sector":
            lines = self._sector_lines()
        else:
            lines = self._mission_lines()
        return self._mfd_text(title, lines)

    def _render_right_mfd(self) -> str:
        title = self._page_label(self.RIGHT_PAGES, self._right_page)
        if self._right_page == "sensors":
            lines = self._sensor_lines()
        elif self._right_page == "power":
            lines = self._power_lines()
        elif self._right_page == "thermal":
            lines = self._thermal_lines()
        elif self._right_page == "comms":
            lines = self._comms_lines()
        elif self._right_page == "propulsion":
            lines = self._propulsion_lines()
        elif self._right_page == "docking":
            lines = self._docking_lines()
        elif self._right_page == "journal":
            lines = self._journal_lines()
        elif self._right_page == "procedures":
            lines = self._procedure_lines()
        else:
            lines = self._systems_lines()
        return self._mfd_text(title, lines)

    def _render_qiki_chat(self) -> str:
        lines = ["КАНАЛ QIKI / ОПЕРАТОР", "Операторский ввод: q: <команда>"]
        if self._qiki_pending_action_title:
            lines.append(f"Ожидает подтверждения: {self._qiki_pending_action_title}")
        if self._qiki_procedure_status:
            lines.append(f"Процедура: {self._qiki_procedure_status}")
        if self._qiki_plan_preview_lines:
            lines.append("План:")
            lines.extend(f"  {line}" for line in self._qiki_plan_preview_lines[:4])
        response = self._qiki_response
        if response is None:
            lines.extend([
                "QIKI: готова к запросу.",
                "Смысл: нижний канал предназначен для команды, объяснения и подтверждения последствия.",
                "Следующий шаг: q: проверь текущую пригодность сенсоров",
            ])
            return "\n".join(lines)
        if response.reply is not None:
            lines.append(f"Ответ: {response.reply.title.ru}")
            lines.append(response.reply.body.ru)
        if response.legality is not None:
            legality = response.legality
            lines.append(f"Решение: {legality.status} | домен={legality.domain} | причина={legality.reason_code}")
            lines.append(f"Почему: {legality.reason.ru}")
            if legality.allowed_when is not None:
                lines.append(f"Когда можно: {legality.allowed_when.ru}")
        if response.trust_signals:
            lines.append("Доверие:")
            for signal in response.trust_signals[:4]:
                lines.append(
                    f"  {signal.label.ru}: {signal.state} | источник={signal.source} | "
                    f"conf={signal.confidence:.2f} | {signal.reason_code}"
                )
        if response.consequence is not None:
            consequence = response.consequence
            lines.append(f"Последствие: {consequence.status} | {consequence.summary.ru}")
            if consequence.telemetry_confirmation is not None:
                lines.append(f"Подтверждение: {consequence.telemetry_confirmation.ru}")
        if response.warnings:
            lines.append("Предупреждения:")
            lines.extend(f"  {warning.ru}" for warning in response.warnings[:3])
        if response.error is not None:
            lines.append(f"Ошибка: {response.error.code} | {response.error.message.ru}")
        return "\n".join(lines)

    def _systems_lines(self) -> list[str]:
        return [
            self._format_fact(self._power_fact()),
            self._format_fact(self._thermal_fact()),
            self._format_fact(self._comms_fact()),
            self._format_fact(self._sensor_summary_fact()),
            self._format_fact(self._incident_fact()),
            "Смысл: правый MFD показывает тело QIKI, а не внешний мир.",
        ]

    def _radar_lines(self) -> list[str]:
        radar = self._pick_dict("radar") or {}
        tracks = self._pick_any("radar_tracks", "tracks")
        track_count = len(tracks) if isinstance(tracks, (list, tuple, dict)) else self._pick_num("radar", "track_count")
        track_text = self._fmt_num(track_count, "целей", "Нет данных")
        state = self._pick_text("radar", "state") or self._pick_text("radar", "status") or self._sensor_status("radar_360")
        quality = self._pick_any("radar", "quality") or self._pick_any("radar", "confidence")
        return [
            f"Радар: {state or 'Нет данных'}",
            f"Треки: {track_text}",
            f"Качество: {self._fmt_optional(quality)}",
            "Влияние: используется для внешней картины, цели и безопасного наблюдения.",
            "Следующий шаг: q: оцени качество радарной картины",
            "Источник: qiki.radar.v1.tracks / qiki.telemetry.radar",
        ]

    def _navigation_lines(self) -> list[str]:
        speed = self._pick_any("speed_m_s") or self._pick_any("nav", "speed_m_s")
        heading = self._pick_any("heading_deg") or self._pick_any("nav", "heading_deg")
        orbit = self._pick_dict("orbit") or {}
        return [
            f"Скорость: {self._fmt_num(speed, 'м/с')}",
            f"Курс: {self._fmt_num(heading, '°')}",
            f"Орбита: {orbit.get('state', 'Нет данных')} | conf={self._fmt_optional(orbit.get('confidence'))}",
            "Влияние: определяет допустимость манёвра и стабилизации.",
            "Следующий шаг: q: предложи безопасную стабилизацию",
            "Источник: qiki.telemetry.nav / orbit / velocity",
        ]

    def _target_lines(self) -> list[str]:
        objective = self._observation_objective or {}
        target = objective.get("target_designator") or objective.get("track_label") or objective.get("public_track_label")
        status = objective.get("status") or objective.get("observation_result_status")
        return [
            f"Цель: {target or 'Нет данных'}",
            f"Статус: {status or 'Нет данных'}",
            f"Стиль наблюдения: {objective.get('observation_style', 'Нет данных')}",
            "Влияние: без цели нельзя честно разрешать route/observation action.",
            "Следующий шаг: q: уточни активную цель наблюдения",
            "Источник: active observation objective / qiki.events",
        ]

    def _sector_lines(self) -> list[str]:
        sector = self._pick_dict("sector") or {}
        radiation = self._pick_any("radiation", "level") or self._pick_any("radiation_level")
        return [
            f"Сектор: {sector.get('name', 'Сектор Терта')}",
            f"Радиация: {self._fmt_optional(radiation)}",
            f"Зона: {sector.get('zone_state', sector.get('state', 'Нет данных'))}",
            "Влияние: зона может ограничивать QIKI по domain=zone/trust.",
            "Следующий шаг: q: проверь ограничения зоны",
            "Источник: qiki.telemetry.sector / qiki.events",
        ]

    def _mission_lines(self) -> list[str]:
        objective = self._observation_objective or {}
        return [
            f"Миссия: {objective.get('summary_ru') or objective.get('title_ru') or 'Нет данных'}",
            f"Маршрут: {objective.get('route_role', 'Нет данных')}",
            f"Процедура: {objective.get('procedure_name', self._qiki_procedure_status or 'Нет данных')}",
            "Влияние: миссия задаёт контекст полезности всех остальных экранов.",
            "Следующий шаг: q: сформулируй ближайшую безопасную цель",
            "Источник: active objective / QIKI response / procedure state",
        ]

    def _sensor_lines(self) -> list[str]:
        sensors = [
            ("radar_360", "Радар 360", "радар и треки", "qiki.radar.v1.tracks"),
            ("lidar_front", "Лидар фронт", "сближение и препятствия", "sensor_plane.lidar_front"),
            ("lidar", "Лидар", "локальная геометрия", "sensor_plane.lidar"),
            ("imu_main", "ИМУ", "ориентация и стабилизация", "sensor_plane.imu_main"),
            ("sensor_thermal", "Тепловой сенсор", "перегрев и ограничения нагрузки", "qiki.telemetry.thermal"),
            ("sensor_radiation", "Радиация", "доверие к сенсорам", "qiki.telemetry.radiation"),
            ("sensor_proximity", "Сближение", "стыковка и collision risk", "qiki.telemetry.docking"),
            ("sensor_solar", "Солнечный сенсор", "энергия и ориентация", "qiki.telemetry.power"),
            ("sensor_star_tracker", "Звёздный трекер", "навигационная привязка", "sensor_plane.sensor_star_tracker"),
            ("spectrometer", "Спектрометр", "состав цели; runtime source не подтверждён", "sensor_plane.spectrometer"),
            ("magnetometer", "Магнитометр", "аномалии и ориентация", "sensor_plane.magnetometer"),
        ]
        lines = ["Сенсоры показываются как пригодность восприятия QIKI, не как список железа."]
        for key, label, meaning, source in sensors:
            status = self._sensor_status(key)
            conf = self._sensor_value(key, "confidence")
            age = self._sensor_value(key, "age_s")
            lines.append(
                f"{label}: {status} | доверие={self._fmt_optional(conf)} | age={self._fmt_num(age, 'с')} | смысл={meaning} | источник={source}"
            )
        return lines

    def _power_lines(self) -> list[str]:
        power = self._pick_dict("power") or {}
        return [
            f"SOC: {self._fmt_num(power.get('soc_pct'), '%')}",
            f"Шина: {self._fmt_num(power.get('bus_v'), 'В')} | {self._fmt_num(power.get('bus_a'), 'А')}",
            f"Load shedding: {'ВКЛ' if power.get('load_shedding') else 'выкл'}",
            f"Причины сброса: {', '.join(power.get('shed_reasons') or []) or 'Нет данных'}",
            "Влияние: питание ограничивает длительные процедуры, связь и тягу.",
            "Следующий шаг: q: оцени допустимые действия по энергии",
            "Источник: qiki.telemetry.power",
        ]

    def _thermal_lines(self) -> list[str]:
        thermal = self._pick_dict("thermal") or {}
        nodes = thermal.get("nodes") if isinstance(thermal.get("nodes"), list) else []
        lines = [
            f"Core: {self._fmt_num(self._core_temp(), '°C')}",
            f"External: {self._fmt_num(self._pick_any('temp_external_c'), '°C')}",
        ]
        for node in nodes[:5]:
            if isinstance(node, dict):
                state = "TRIP" if node.get("tripped") else "WARN" if node.get("warned") else "OK"
                lines.append(f"{node.get('id', 'node')}: {self._fmt_num(node.get('temp_c'), '°C')} | {state}")
        lines.extend([
            "Влияние: тепло ограничивает манёвр, вычисления, связь и длительные действия.",
            "Следующий шаг: q: предложи снижение тепловой нагрузки",
            "Источник: qiki.telemetry.thermal / temp_core_c",
        ])
        return lines

    def _comms_lines(self) -> list[str]:
        comms = self._pick_dict("comms") or {}
        return [
            f"Канал: {comms.get('link') or comms.get('link_state') or 'Нет данных'}",
            f"Latency: {self._fmt_num(comms.get('latency_ms'), 'мс')}",
            f"Packet loss: {self._fmt_num(comms.get('packet_loss_pct'), '%')}",
            f"SNR: {self._fmt_num(comms.get('snr_db'), 'dB')}",
            f"Antenna: {comms.get('antenna_status', 'Нет данных')}",
            "Влияние: связь определяет доступность удалённых процедур и station contact.",
            "Следующий шаг: q: проверь пригодность связи для команды",
            "Источник: qiki.telemetry.comms",
        ]

    def _propulsion_lines(self) -> list[str]:
        propulsion = self._pick_dict("propulsion") or {}
        return [
            f"Статус: {propulsion.get('status', propulsion.get('state', 'Нет данных'))}",
            f"RCS: {propulsion.get('rcs_state', 'Нет данных')}",
            f"Тяга: {self._fmt_num(propulsion.get('thrust_n'), 'Н')}",
            "Влияние: двигатель определяет манёвр, отстыковку и combat-entry.",
            "Следующий шаг: q: оцени допустимый импульс",
            "Источник: qiki.telemetry.propulsion",
        ]

    def _docking_lines(self) -> list[str]:
        docking = self._pick_dict("docking") or {}
        return [
            f"Состояние: {docking.get('state', 'Нет данных')}",
            f"Дистанция: {self._fmt_num(docking.get('distance_m'), 'м')}",
            f"Скорость сближения: {self._fmt_num(docking.get('approach_mps') or docking.get('rel_speed_mps'), 'м/с')}",
            f"Замки: {docking.get('locks', 'Нет данных')}",
            "Влияние: стыковка требует свежих proximity/docking данных.",
            "Следующий шаг: q: проверь безопасность стыковки",
            "Источник: qiki.telemetry.docking",
        ]

    def _journal_lines(self) -> list[str]:
        lines = ["Последние операторские события:"]
        for incident in self._incidents[:6]:
            lines.append(f"{incident.get('severity', '?')}: {incident.get('id', 'нет id')} | {incident.get('description', 'Нет данных')}")
        if not self._incidents:
            lines.append("Нет активных инцидентов.")
        lines.append("Источник: qiki.events.v1 / локальный incidents store")
        return lines

    def _procedure_lines(self) -> list[str]:
        return [
            f"QIKI procedure: {self._qiki_procedure_status or 'Нет данных'}",
            f"Pending action: {self._qiki_pending_action_title or 'Нет данных'}",
            "Влияние: pending требует ручного подтверждения; автодействий нет.",
            "Следующий шаг: подтвердить/отменить или спросить QIKI о риске.",
            "Источник: qiki.responses.qiki / qiki.responses.control",
        ]

    def _telemetry_status_fact(self) -> OperatorUsefulFact:
        return OperatorUsefulFact("ТЕЛЕМЕТРИЯ", "fresh" if self._nats_connected else "Нет данных", source_path="qiki.telemetry")

    def _sim_status_fact(self) -> OperatorUsefulFact:
        sim = self._pick_dict("sim_state") or {}
        state = sim.get("fsm_state") or ("PAUSED" if sim.get("paused") else "RUNNING" if sim else "Нет данных")
        return OperatorUsefulFact("СИМ", str(state), source_path="qiki.telemetry.sim_state")

    def _safe_mode_fact(self) -> OperatorUsefulFact:
        active = self._safe_mode.get("active")
        if active is True:
            value = f"ВКЛ | {self._safe_mode.get('reason') or 'без причины'}"
            severity = "crit"
        elif active is False or active is None:
            value = f"выкл | {self._safe_mode.get('reason') or 'signal clear'}"
            severity = "ok"
        else:
            value = "Нет данных"
            severity = "warn"
        return OperatorUsefulFact("SAFE", value, severity, "qiki.events.safe_mode")

    def _power_fact(self) -> OperatorUsefulFact:
        soc = self._pick_any("power", "soc_pct")
        if isinstance(soc, (int, float)):
            severity = "crit" if soc < 15 else "warn" if soc < 25 else "ok"
            value = f"{soc:.1f}%"
        else:
            severity = "warn"
            value = "Нет данных"
        return OperatorUsefulFact("ЭНЕРГИЯ", value, severity, "qiki.telemetry.power", operator_meaning_ru="ресурсный лимит")

    def _thermal_fact(self) -> OperatorUsefulFact:
        core = self._core_temp()
        if isinstance(core, (int, float)):
            severity = "crit" if core >= 90 else "warn" if core >= 80 else "ok"
            value = f"{core:.1f}°C"
        else:
            severity = "warn"
            value = "Нет данных"
        return OperatorUsefulFact("ТЕПЛО", value, severity, "qiki.telemetry.thermal", operator_meaning_ru="ограничение нагрузки")

    def _comms_fact(self) -> OperatorUsefulFact:
        link = self._pick_any("comms", "link") or self._pick_any("comms", "link_state")
        return OperatorUsefulFact("СВЯЗЬ", str(link or "Нет данных"), "ok" if link == "online" else "warn", "qiki.telemetry.comms")

    def _sensor_summary_fact(self) -> OperatorUsefulFact:
        statuses = [self._sensor_status(key) for key in ("radar_360", "imu_main", "lidar_front", "sensor_thermal")]
        if any(status in {"failed", "off"} for status in statuses):
            severity = "crit"
            value = "отказ"
        elif any(status in {"degraded", "Нет данных"} for status in statuses):
            severity = "warn"
            value = "деградация"
        else:
            severity = "ok"
            value = "норма"
        return OperatorUsefulFact("СЕНСОРЫ", value, severity, "sensor_plane / telemetry")

    def _qiki_status_fact(self) -> OperatorUsefulFact:
        if self._qiki_pending_action_title:
            value = "ждёт подтверждения"
            severity = "warn"
        elif self._qiki_response and not self._qiki_response.ok:
            value = "ошибка"
            severity = "crit"
        elif self._qiki_response:
            value = self._qiki_response.mode.value
            severity = "ok"
        else:
            value = "готова"
            severity = "ok"
        return OperatorUsefulFact("QIKI", value, severity, "qiki.responses.qiki")

    def _incident_fact(self) -> OperatorUsefulFact:
        if self._active_incidents:
            return OperatorUsefulFact("ИНЦ", str(self._active_incidents), "crit", "qiki.events.v1")
        return OperatorUsefulFact("ИНЦ", "0", "ok", "qiki.events.v1")

    def _mfd_text(self, title: str, lines: list[str]) -> str:
        return "\n".join([f"[{title}]", *lines])

    def _format_fact(self, fact: OperatorUsefulFact) -> str:
        parts = [f"{fact.title_ru}: {fact.value_ru}"]
        if fact.operator_meaning_ru:
            parts.append(f"смысл={fact.operator_meaning_ru}")
        parts.append(f"источник={fact.source_path}")
        return " | ".join(parts)

    def _page_label(self, pages: tuple[tuple[str, str], ...], page: str) -> str:
        return next((label for key, label in pages if key == page), page.upper())

    def _set_border(self, selector: str, title: str, subtitle: str = "") -> None:
        try:
            widget = self.query_one(selector)
            widget.border_title = title
            if subtitle:
                widget.border_subtitle = subtitle
        except NoMatches:
            pass

    def _update_static(self, selector: str, text: str) -> None:
        try:
            self.query_one(selector, Static).update(text)
        except NoMatches:
            self.update(self._fallback_render or text)

    def _pick_dict(self, *path: str) -> dict[str, Any] | None:
        value = self._pick_any(*path)
        return value if isinstance(value, dict) else None

    def _pick_any(self, *path: str) -> Any:
        current: Any = self._telemetry
        for part in path:
            if not isinstance(current, dict) or part not in current:
                return None
            current = current[part]
        return current

    def _pick_text(self, *path: str) -> str | None:
        value = self._pick_any(*path)
        return str(value) if value is not None else None

    def _pick_num(self, *path: str) -> float | None:
        value = self._pick_any(*path)
        return float(value) if isinstance(value, (int, float)) else None

    def _core_temp(self) -> float | None:
        value = self._pick_any("temp_core_c")
        if isinstance(value, (int, float)):
            return float(value)
        thermal = self._pick_dict("thermal") or {}
        for node in thermal.get("nodes") or []:
            if isinstance(node, dict) and node.get("id") == "core" and isinstance(node.get("temp_c"), (int, float)):
                return float(node["temp_c"])
        return None

    def _sensor_status(self, key: str) -> str:
        value = self._sensor_value(key, "status")
        if value is not None:
            return str(value)
        if key == "radar_360" and (self._pick_any("radar") or self._pick_any("radar_tracks")):
            return "healthy"
        if key == "imu_main" and (self._pick_any("imu") or self._pick_any("attitude")):
            return "healthy"
        if key == "sensor_thermal" and (self._pick_any("thermal") or self._pick_any("temp_core_c")):
            return "healthy"
        if key == "sensor_proximity" and self._pick_any("docking"):
            return "healthy"
        if key == "sensor_solar" and self._pick_any("power"):
            return "healthy"
        return "Нет данных"

    def _sensor_value(self, key: str, field: str) -> Any:
        return (
            self._pick_any("sensor_plane", key, field)
            or self._pick_any("sensors", key, field)
            or self._pick_any(key, field)
        )

    def _fmt_num(self, value: Any, unit: str, missing: str = "Нет данных") -> str:
        if isinstance(value, (int, float)):
            return f"{float(value):.2f} {unit}"
        return missing

    def _fmt_optional(self, value: Any) -> str:
        if isinstance(value, float):
            return f"{value:.2f}"
        if isinstance(value, int):
            return str(value)
        return str(value) if value not in (None, "") else "Нет данных"
