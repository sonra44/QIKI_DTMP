from __future__ import annotations

from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class LangHint(str, Enum):
    AUTO = "auto"
    RU = "ru"
    EN = "en"


class EnvironmentMode(str, Enum):
    FACTORY = "FACTORY"
    MISSION = "MISSION"


class SelectionV1(_StrictModel):
    kind: Literal["event", "incident", "track", "snapshot", "none"] = "none"
    id: Optional[str] = None


class IntentV1(_StrictModel):
    version: Literal[1] = 1
    text: str
    lang_hint: LangHint = LangHint.AUTO
    screen: str
    selection: SelectionV1 = Field(default_factory=SelectionV1)
    ts: int
    environment_mode: EnvironmentMode = EnvironmentMode.FACTORY
    snapshot_min: dict[str, Any] = Field(default_factory=dict)


class ProposalV1(_StrictModel):
    proposal_id: str
    title: str
    justification: str
    priority: int = Field(ge=0, le=100)
    confidence: float = Field(ge=0.0, le=1.0)
    proposed_actions: list[Any] = Field(default_factory=list)

    @field_validator("proposed_actions")
    @classmethod
    def _must_be_empty_in_stage_a(cls, v: list[Any]) -> list[Any]:
        if v:
            raise ValueError("proposed_actions must be empty in Stage A")
        return v


class ProposalsBatchV1(_StrictModel):
    version: Literal[1] = 1
    ts: int
    proposals: list[ProposalV1] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

