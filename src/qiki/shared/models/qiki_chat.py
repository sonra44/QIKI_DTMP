from __future__ import annotations

from enum import Enum
from typing import Any, Literal, Optional
from uuid import UUID

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class BilingualText(_StrictModel):
    en: str
    ru: str


class QikiMode(str, Enum):
    FACTORY = "FACTORY"
    MISSION = "MISSION"


class TelemetryFreshness(str, Enum):
    FRESH = "FRESH"
    STALE = "STALE"
    DEAD = "DEAD"
    UNKNOWN = "UNKNOWN"


class SelectionContext(_StrictModel):
    kind: Literal["event", "incident", "track", "snapshot", "none"]
    id: Optional[str] = None


class UiContext(_StrictModel):
    screen: str = "System/Система"
    selection: SelectionContext = Field(default_factory=lambda: SelectionContext(kind="none"))


class SystemSummary(_StrictModel):
    battery_pct: Optional[float] = None
    online: Optional[bool] = None


class SystemContext(_StrictModel):
    telemetry_freshness: TelemetryFreshness = TelemetryFreshness.UNKNOWN
    summary: SystemSummary = Field(default_factory=SystemSummary)


class QikiChatInput(_StrictModel):
    text: str
    lang_hint: Literal["auto", "ru", "en"] = "auto"


class QikiChatRequestV1(_StrictModel):
    version: Literal[1] = 1
    request_id: UUID = Field(validation_alias=AliasChoices("request_id", "requestId"))
    ts_epoch_ms: int
    mode_hint: QikiMode = QikiMode.FACTORY
    input: QikiChatInput
    ui_context: UiContext = Field(default_factory=UiContext)
    system_context: SystemContext = Field(default_factory=SystemContext)


class QikiErrorV1(_StrictModel):
    code: Literal["TIMEOUT", "INVALID_REQUEST", "INTERNAL", "UNAVAILABLE"]
    message: BilingualText


class QikiReplyV1(_StrictModel):
    title: BilingualText
    body: BilingualText


class QikiProposedActionV1(_StrictModel):
    kind: Literal["NATS_COMMAND"] = "NATS_COMMAND"
    subject: str
    name: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    dry_run: bool = True


class QikiProposalV1(_StrictModel):
    proposal_id: str
    title: BilingualText
    justification: BilingualText
    confidence: float = Field(ge=0.0, le=1.0)
    priority: int = Field(ge=0, le=100)
    suggested_questions: list[BilingualText] = Field(default_factory=list)
    proposed_actions: list[QikiProposedActionV1] = Field(default_factory=list)


class QikiChatResponseV1(_StrictModel):
    version: Literal[1] = 1
    request_id: UUID = Field(validation_alias=AliasChoices("request_id", "requestId"))
    ok: bool
    mode: QikiMode
    reply: Optional[QikiReplyV1] = None
    proposals: list[QikiProposalV1] = Field(default_factory=list)
    warnings: list[BilingualText] = Field(default_factory=list)
    error: Optional[QikiErrorV1] = None
