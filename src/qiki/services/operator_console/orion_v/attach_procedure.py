"""Процедурная установка модуля (ADR-0020 §1): состояние с захватом решения.

Процедура ВЛАДЕЕТ своим CommandDecision (захвачен при старте, immutable) и
никогда не читает глобальные однокадровые переменные консоли — новый разговор
с ботом не может ни убить процедуру, ни подменить её пломбу (ревизия C1/C2).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from qiki.shared.command_decision import CommandDecision

# Статусы процедуры.
STATUS_RUNNING = "running"
STATUS_AWAITING = "awaiting_operator"
STATUS_HOLDING = "holding"
STATUS_DONE = "done"
STATUS_FAILED = "failed"
STATUS_ABORTED = "aborted"

ACTIVE_STATUSES = frozenset({STATUS_RUNNING, STATUS_AWAITING, STATUS_HOLDING})

# Стадии (ADR-0020 §2).
STAGE_S1_INSPECT = "s1_inspect"
STAGE_S2_PREPARE = "s2_prepare"
STAGE_S3_TRANSFER = "s3_transfer"
STAGE_S4_POWER = "s4_power"
STAGE_S5_DOCK = "s5_dock"


def transfer_ticks_for_mount(mount: str) -> int:
    """Fixture-длительность переноса per-грань (данные темпа, не физика тела).

    F00-F03 — 2 тика, F04-F07 — 3, F08-F11 — 4: дальняя грань дольше.
    """
    try:
        index = int(str(mount).strip().upper().lstrip("F"))
    except (TypeError, ValueError):
        return 3
    return 2 + max(0, min(index, 11)) // 4


@dataclass
class AttachProcedure:
    """Захваченное решение + ход стадий. Отчёт — только своим каналом."""

    decision: CommandDecision  # захвачено при старте; НЕ перечитывается
    origin_request_id: str  # ответ бота, породивший процедуру (для атрибуции)
    params: dict[str, Any]  # параметры из пломбы захваченного решения
    stage: str = STAGE_S1_INSPECT
    status: str = STATUS_RUNNING
    complication: str = ""  # PASSPORT_DAMAGED | BRIDGE_* | WORLD_PAUSED | TELEM_STALE | OPERATOR_HOLD
    stage_log: list[str] = field(default_factory=list)
    # P2: протяжённый перенос (тик = принятый снапшот с paused=false)
    ticks_required: int = 0
    ticks_done: int = 0
    # авто-hold (WORLD_PAUSED/TELEM_STALE) снимается сам; операторский/оконный — нет
    auto_hold: bool = False

    @property
    def active(self) -> bool:
        return self.status in ACTIVE_STATUSES

    @property
    def paused(self) -> bool:
        """Кнопка Пауза/Старт: процедура стоит и ждёт оператора."""
        return self.status in {STATUS_AWAITING, STATUS_HOLDING}

    def module_id(self) -> str:
        return str(self.params.get("module_id") or "")

    def mount(self) -> str:
        return str(self.params.get("mount") or "")
