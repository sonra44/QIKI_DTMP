from __future__ import annotations

from pathlib import Path

import pytest

from qiki.services.q_core_agent.core.event_store import EventStore
from qiki.services.q_core_agent.core.plugin_manager import PluginContext, PluginManager, PluginSpec
from qiki.services.q_core_agent.core.radar_clock import SystemClock
from qiki.services.q_core_agent.core.radar_plugins import register_builtin_radar_plugins


def _manager(store: EventStore | None = None) -> PluginManager:
    context = PluginContext(
        event_store=store,
        clock=SystemClock(),
        config={},
        capabilities={},
    )
    manager = PluginManager(context=context, event_store=store)
    register_builtin_radar_plugins(manager)
    return manager


def _write_yaml(path: Path, body: str) -> Path:
    path.write_text(body, encoding="utf-8")
    return path


def test_registry_rejects_duplicate_plugin_names() -> None:
    manager = _manager()
    with pytest.raises(ValueError, match="duplicate plugin name"):
        manager.register(
            PluginSpec(
                name="builtin.sensor_input",
                kind="sensor_input",
                version="x",
                provides=(),
                requires=(),
                factory=lambda _ctx, _params: object(),
            )
        )


def test_strict_mode_fails_for_missing_yaml(tmp_path: Path) -> None:
    manager = _manager()
    with pytest.raises(RuntimeError, match="strict"):
        manager.resolve_active_plugins(yaml_path=str(tmp_path / "missing.yaml"), strict=True, env={})


def test_non_strict_mode_falls_back_and_emits_event(tmp_path: Path) -> None:
    store = EventStore(maxlen=200, enabled=True)
    manager = _manager(store)
    result = manager.resolve_active_plugins(yaml_path=str(tmp_path / "missing.yaml"), strict=False, env={})
    assert result.source == "fallback"
    assert result.warning_reason.startswith("PLUGIN_CONFIG_FALLBACK")
    assert result.instances.get("fusion") is not None
    events = store.filter(subsystem="PLUGINS", event_type="PLUGIN_FALLBACK_USED")
    assert events


def test_dependency_order_respected(tmp_path: Path) -> None:
    calls: list[str] = []
    manager = _manager()
    manager.register(
        PluginSpec(
            name="x.base",
            kind="sensor_input",
            version="1",
            provides=("x.base",),
            requires=(),
            factory=lambda _ctx, _params: calls.append("base") or object(),
        )
    )
    manager.register(
        PluginSpec(
            name="x.dep",
            kind="fusion",
            version="1",
            provides=("x.dep",),
            requires=("x.base",),
            factory=lambda _ctx, _params: calls.append("dep") or object(),
        )
    )
    config = _write_yaml(
        tmp_path / "plugins.yaml",
        """
schema_version: 1
profiles:
  p:
    sensor_input:
      name: x.base
    fusion:
      name: x.dep
    render_policy:
      enabled: false
    render_backend:
      enabled: false
    situational_analysis:
      enabled: false
""".strip(),
    )
    manager.resolve_active_plugins(yaml_path=str(config), profile="p", strict=True, env={})
    assert calls == ["base", "dep"]


def test_unknown_plugin_kind_in_profile_fails(tmp_path: Path) -> None:
    manager = _manager()
    config = _write_yaml(
        tmp_path / "plugins.yaml",
        """
schema_version: 1
profiles:
  p:
    fusion:
      name: plugin.missing
""".strip(),
    )
    with pytest.raises(RuntimeError):
        manager.resolve_active_plugins(yaml_path=str(config), profile="p", strict=True, env={})


def test_global_strict_mode_alias_for_plugin_loader(tmp_path: Path) -> None:
    manager = _manager()
    env = {"QIKI_STRICT_MODE": "1"}
    with pytest.raises(RuntimeError, match="strict"):
        manager.resolve_active_plugins(yaml_path=str(tmp_path / "missing.yaml"), env=env)


def test_global_non_strict_mode_emits_plugin_fallback(tmp_path: Path) -> None:
    store = EventStore(maxlen=200, enabled=True)
    manager = _manager(store)
    env = {"QIKI_STRICT_MODE": "0"}
    result = manager.resolve_active_plugins(yaml_path=str(tmp_path / "missing.yaml"), env=env)
    assert result.source == "fallback"
    assert store.filter(subsystem="PLUGINS", event_type="PLUGIN_FALLBACK_USED")
