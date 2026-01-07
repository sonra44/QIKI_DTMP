from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Optional

import yaml
from pydantic import BaseModel, Field, ValidationError, field_validator


ALLOWED_SEVERITIES = {"I", "W", "C", "A"}
ALLOWED_OPS = {">", ">=", "<", "<=", "=", "!="}


class IncidentRuleMatch(BaseModel):
    type: Optional[str] = None
    source: Optional[str] = None
    subject: Optional[str] = None
    field: Optional[str] = None


class IncidentRuleThreshold(BaseModel):
    op: str
    value: float
    min_duration_s: Optional[float] = None
    cooldown_s: Optional[float] = None

    @field_validator("op")
    @classmethod
    def _validate_op(cls, v: str) -> str:
        token = (v or "").strip()
        if token not in ALLOWED_OPS:
            raise ValueError(f"Unsupported op: {v}")
        return token


class IncidentRule(BaseModel):
    id: str
    enabled: bool = True
    title: str
    description: Optional[str] = None
    match: IncidentRuleMatch
    threshold: Optional[IncidentRuleThreshold] = None
    severity: str = Field(default="W")
    require_ack: bool = False
    auto_clear: bool = True

    @field_validator("severity")
    @classmethod
    def _validate_severity(cls, v: str) -> str:
        token = (v or "").strip().upper()
        if token not in ALLOWED_SEVERITIES:
            raise ValueError(f"Unsupported severity: {v}")
        return token


class IncidentRulesConfig(BaseModel):
    version: int = 1
    rules: list[IncidentRule]


@dataclass
class RulesReloadResult:
    config: IncidentRulesConfig
    old_hash: str
    new_hash: str


class RulesRepository:
    def load(self) -> IncidentRulesConfig:  # pragma: no cover - interface
        raise NotImplementedError

    def reload(self, *, source: str = "file/reload") -> RulesReloadResult:  # pragma: no cover - interface
        raise NotImplementedError


class FileRulesRepository(RulesRepository):
    def __init__(self, rules_path: str, history_path: Optional[str] = None) -> None:
        self._rules_path = rules_path
        self._history_path = history_path
        self._current_hash: Optional[str] = None
        self._current_config: Optional[IncidentRulesConfig] = None

    def load(self) -> IncidentRulesConfig:
        config, content_hash = self._read_and_validate()
        self._current_hash = content_hash
        self._current_config = config
        return config

    def reload(self, *, source: str = "file/reload") -> RulesReloadResult:
        old_hash = self._current_hash or ""
        config, content_hash = self._read_and_validate()
        self._append_history(old_hash, content_hash, source)
        self._current_hash = content_hash
        self._current_config = config
        return RulesReloadResult(config=config, old_hash=old_hash, new_hash=content_hash)

    def set_rule_enabled(self, rule_id: str, enabled: bool, *, source: str = "ui/toggle") -> RulesReloadResult:
        rid = (rule_id or "").strip()
        if not rid:
            raise ValueError("rule_id is required")

        config, old_hash = self._read_and_validate()
        updated_rules: list[IncidentRule] = []
        found = False
        for rule in config.rules:
            if rule.id == rid:
                updated_rules.append(rule.model_copy(update={"enabled": bool(enabled)}))
                found = True
            else:
                updated_rules.append(rule)
        if not found:
            raise KeyError(f"Unknown rule_id: {rid}")

        updated_config = IncidentRulesConfig(version=config.version, rules=updated_rules)
        payload = updated_config.model_dump()
        raw = yaml.safe_dump(payload, sort_keys=False, allow_unicode=True)

        os.makedirs(os.path.dirname(self._rules_path) or ".", exist_ok=True)
        tmp_path = f"{self._rules_path}.tmp"
        with open(tmp_path, "w", encoding="utf-8") as handle:
            handle.write(raw)
        os.replace(tmp_path, self._rules_path)

        new_hash = sha256(raw.encode("utf-8")).hexdigest()
        self._append_history(old_hash, new_hash, source)
        self._current_hash = new_hash
        self._current_config = updated_config
        return RulesReloadResult(config=updated_config, old_hash=old_hash, new_hash=new_hash)

    def _read_and_validate(self) -> tuple[IncidentRulesConfig, str]:
        if not os.path.exists(self._rules_path):
            raise FileNotFoundError(self._rules_path)
        with open(self._rules_path, "r", encoding="utf-8") as handle:
            raw = handle.read()
        payload = yaml.safe_load(raw)
        if not isinstance(payload, dict):
            raise ValueError("incident rules must be a YAML mapping")
        try:
            config = IncidentRulesConfig.model_validate(payload)
        except ValidationError as exc:
            raise ValueError(str(exc)) from exc
        content_hash = sha256(raw.encode("utf-8")).hexdigest()
        return config, content_hash

    def _append_history(self, old_hash: str, new_hash: str, source: str) -> None:
        if not self._history_path:
            return
        entry = {
            "timestamp": time.time(),
            "old_hash": old_hash,
            "new_hash": new_hash,
            "source": source,
        }
        os.makedirs(os.path.dirname(self._history_path), exist_ok=True)
        with open(self._history_path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")

    @property
    def current_config(self) -> Optional[IncidentRulesConfig]:
        return self._current_config
