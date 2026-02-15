"""Plugin manager v1 for radar pipeline extension points."""

from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from typing import Any, Callable

import yaml

from .event_store import EventStore, TruthState
from .radar_clock import Clock
from .runtime_contracts import resolve_strict_mode

LOGGER = logging.getLogger(__name__)

DEFAULT_PLUGINS_RESOURCE_PACKAGE = "qiki.resources"
DEFAULT_PLUGINS_RESOURCE_NAME = "plugins.yaml"
DEFAULT_PLUGIN_PROFILE = "default"


@dataclass(frozen=True)
class PluginSpec:
    name: str
    kind: str
    version: str
    provides: tuple[str, ...]
    requires: tuple[str, ...]
    factory: Callable[["PluginContext", dict[str, Any]], Any]


@dataclass(frozen=True)
class PluginContext:
    event_store: EventStore | None
    clock: Clock
    config: dict[str, Any]
    capabilities: dict[str, Any]


@dataclass(frozen=True)
class LoadedPlugins:
    instances: dict[str, Any]
    profile: str
    source: str
    warning_reason: str = ""


class PluginManager:
    """Registry + config-driven plugin loader with strict/fallback behavior."""

    def __init__(self, *, context: PluginContext, event_store: EventStore | None = None) -> None:
        self._context = context
        self._event_store = event_store
        self._registry: dict[str, PluginSpec] = {}

    def register(self, spec: PluginSpec) -> None:
        key = spec.name.strip()
        if not key:
            raise ValueError("plugin name must not be empty")
        if key in self._registry:
            raise ValueError(f"duplicate plugin name: {key}")
        self._registry[key] = spec

    def register_many(self, specs: list[PluginSpec]) -> None:
        for spec in specs:
            self.register(spec)

    def resolve_active_plugins(
        self,
        *,
        yaml_path: str | None = None,
        profile: str | None = None,
        strict: bool | None = None,
        env: dict[str, str] | None = None,
    ) -> LoadedPlugins:
        active_env = env if env is not None else dict(os.environ)
        selected_profile = (profile or active_env.get("QIKI_PLUGINS_PROFILE", DEFAULT_PLUGIN_PROFILE)).strip()
        if not selected_profile:
            selected_profile = DEFAULT_PLUGIN_PROFILE
        strict_mode = (
            resolve_strict_mode(active_env, legacy_keys=("QIKI_PLUGINS_STRICT",), default=False)
            if strict is None
            else strict
        )
        path = (yaml_path or active_env.get("QIKI_PLUGINS_YAML", "")).strip()

        try:
            doc, source = self._load_plugins_doc(path)
            selections = self._profile_selection(doc, selected_profile)
            config_hash = self._config_hash({"profile": selected_profile, "selection": selections, "source": source})
            instances = self._instantiate_selected(selections, config_hash=config_hash)
            return LoadedPlugins(instances=instances, profile=selected_profile, source=source)
        except Exception as exc:  # noqa: BLE001
            if strict_mode:
                self._append_lifecycle_event(
                    event_type="PLUGIN_FAILED",
                    reason="STRICT_MODE_LOAD_FAILURE",
                    payload={
                        "name": "<config>",
                        "kind": "config",
                        "version": "v1",
                        "error": str(exc),
                        "config_hash": "",
                    },
                    truth_state=TruthState.INVALID,
                )
                raise RuntimeError(f"Plugin config load failed (strict): {exc}") from exc

            warning = f"PLUGIN_CONFIG_FALLBACK:{exc}"
            LOGGER.warning("Plugin config fallback: %s", exc)
            selections = self._fallback_selection()
            config_hash = self._config_hash({"profile": selected_profile, "selection": selections, "source": "fallback"})
            instances = self._instantiate_selected(selections, config_hash=config_hash)
            self._append_lifecycle_event(
                event_type="PLUGIN_FALLBACK_USED",
                reason=warning,
                payload={
                    "name": "<config>",
                    "kind": "config",
                    "version": "v1",
                    "error": str(exc),
                    "config_hash": config_hash,
                },
                truth_state=TruthState.FALLBACK,
            )
            return LoadedPlugins(instances=instances, profile=selected_profile, source="fallback", warning_reason=warning)

    def _load_plugins_doc(self, path: str) -> tuple[dict[str, Any], str]:
        if path:
            doc = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
            source = "yaml:file"
        else:
            text = resources.files(DEFAULT_PLUGINS_RESOURCE_PACKAGE).joinpath(DEFAULT_PLUGINS_RESOURCE_NAME).read_text(
                encoding="utf-8"
            )
            doc = yaml.safe_load(text)
            source = "yaml:resource"
        if not isinstance(doc, dict):
            raise ValueError("plugins config must be a mapping")
        schema_version = int(doc.get("schema_version", 0))
        if schema_version != 1:
            raise ValueError(f"unsupported plugins schema_version={schema_version!r}")
        profiles = doc.get("profiles")
        if not isinstance(profiles, dict) or not profiles:
            raise ValueError("plugins.profiles must be a non-empty mapping")
        return doc, source

    def _profile_selection(self, doc: dict[str, Any], profile: str) -> dict[str, dict[str, Any]]:
        profiles = doc.get("profiles")
        assert isinstance(profiles, dict)
        block = profiles.get(profile)
        if not isinstance(block, dict):
            raise ValueError(f"profile not found: {profile!r}")
        normalized: dict[str, dict[str, Any]] = {}
        for kind, value in block.items():
            if not isinstance(value, dict):
                raise ValueError(f"profile {profile!r} kind {kind!r} must be an object")
            if value.get("enabled", True) is False:
                normalized[kind] = {"enabled": False}
                continue
            name = str(value.get("name", "")).strip()
            if not name:
                raise ValueError(f"profile {profile!r} kind {kind!r} has empty plugin name")
            params = value.get("params", {})
            if params is None:
                params = {}
            if not isinstance(params, dict):
                raise ValueError(f"profile {profile!r} kind {kind!r} params must be an object")
            normalized[kind] = {"enabled": True, "name": name, "params": dict(params)}
        return normalized

    def _fallback_selection(self) -> dict[str, dict[str, Any]]:
        return {
            "sensor_input": {"enabled": True, "name": "builtin.sensor_input", "params": {}},
            "fusion": {"enabled": True, "name": "builtin.fusion_majority", "params": {}},
            "render_policy": {"enabled": True, "name": "builtin.render_policy_v3", "params": {}},
            "render_backend": {"enabled": True, "name": "builtin.render_backends", "params": {}},
            "situational_analysis": {"enabled": True, "name": "builtin.situational_v2", "params": {}},
        }

    def _instantiate_selected(self, selection: dict[str, dict[str, Any]], *, config_hash: str) -> dict[str, Any]:
        active_names: list[str] = []
        for _kind, cfg in selection.items():
            if not cfg.get("enabled", True):
                continue
            name = str(cfg.get("name", "")).strip()
            if not name:
                continue
            active_names.append(name)

        ordered_names = self._resolve_init_order(active_names)
        by_kind: dict[str, Any] = {}
        instances_by_name: dict[str, Any] = {}

        for name in ordered_names:
            spec = self._registry.get(name)
            if spec is None:
                self._append_lifecycle_event(
                    event_type="PLUGIN_FAILED",
                    reason="PLUGIN_NOT_REGISTERED",
                    payload={
                        "name": name,
                        "kind": "unknown",
                        "version": "",
                        "error": "not registered",
                        "config_hash": config_hash,
                    },
                    truth_state=TruthState.INVALID,
                )
                raise ValueError(f"plugin not registered: {name}")
            kind_cfg = next((cfg for kind, cfg in selection.items() if cfg.get("name") == name and kind == spec.kind), None)
            params = dict(kind_cfg.get("params", {})) if isinstance(kind_cfg, dict) else {}
            try:
                instance = spec.factory(self._context, params)
            except Exception as exc:  # noqa: BLE001
                self._append_lifecycle_event(
                    event_type="PLUGIN_FAILED",
                    reason="PLUGIN_FACTORY_ERROR",
                    payload={
                        "name": spec.name,
                        "kind": spec.kind,
                        "version": spec.version,
                        "error": str(exc),
                        "config_hash": config_hash,
                    },
                    truth_state=TruthState.INVALID,
                )
                raise
            instances_by_name[spec.name] = instance
            by_kind[spec.kind] = instance
            self._append_lifecycle_event(
                event_type="PLUGIN_LOADED",
                reason="PLUGIN_READY",
                payload={
                    "name": spec.name,
                    "kind": spec.kind,
                    "version": spec.version,
                    "error": "",
                    "config_hash": config_hash,
                },
                truth_state=TruthState.OK,
            )

        for kind, cfg in selection.items():
            if cfg.get("enabled", True) is False:
                by_kind[kind] = None
                self._append_lifecycle_event(
                    event_type="PLUGIN_FALLBACK_USED",
                    reason="PLUGIN_DISABLED_BY_PROFILE",
                    payload={
                        "name": f"<disabled:{kind}>",
                        "kind": kind,
                        "version": "",
                        "error": "disabled in profile",
                        "config_hash": config_hash,
                    },
                    truth_state=TruthState.FALLBACK,
                )
        return by_kind

    def _resolve_init_order(self, active_names: list[str]) -> list[str]:
        unique_names = sorted(set(active_names))
        active_set = set(unique_names)
        for name in unique_names:
            if name not in self._registry:
                raise ValueError(f"plugin not registered: {name}")
        pending = {name: set(self._registry[name].requires) & active_set for name in unique_names}
        order: list[str] = []
        while pending:
            ready = sorted([name for name, deps in pending.items() if not deps])
            if not ready:
                cycle = ",".join(sorted(pending.keys()))
                raise ValueError(f"plugin dependency cycle detected: {cycle}")
            for name in ready:
                order.append(name)
                del pending[name]
                for deps in pending.values():
                    deps.discard(name)
        return order

    def _append_lifecycle_event(
        self,
        *,
        event_type: str,
        reason: str,
        payload: dict[str, Any],
        truth_state: TruthState,
    ) -> None:
        if self._event_store is None:
            return
        self._event_store.append_new(
            subsystem="PLUGINS",
            event_type=event_type,
            payload=payload,
            truth_state=truth_state,
            reason=reason,
        )

    @staticmethod
    def _as_bool(raw: str | None, *, default: bool) -> bool:
        if raw is None:
            return default
        return raw.strip().lower() in {"1", "true", "yes", "on"}

    @staticmethod
    def _config_hash(payload: dict[str, Any]) -> str:
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
