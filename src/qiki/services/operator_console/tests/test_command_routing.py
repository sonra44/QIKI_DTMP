from __future__ import annotations

from qiki.services.operator_console.main_orion import OrionApp


def test_default_routing_prefers_system_for_control_plane_commands() -> None:
    assert OrionApp._should_route_to_system_by_default("xpdr.mode spoof") is True
    assert OrionApp._should_route_to_system_by_default("rcs.forward 25 1") is True
    assert OrionApp._should_route_to_system_by_default("simulation.pause") is True
    assert OrionApp._should_route_to_system_by_default("sim.start 2") is True
    assert OrionApp._should_route_to_system_by_default("power.nbl.on") is True
    assert OrionApp._should_route_to_system_by_default("nbl.max 120") is True
    assert OrionApp._should_route_to_system_by_default("dock.engage A") is True


def test_default_routing_prefers_system_for_help_and_screens() -> None:
    assert OrionApp._should_route_to_system_by_default("help") is True
    assert OrionApp._should_route_to_system_by_default("экран system") is True
    assert OrionApp._should_route_to_system_by_default("system") is True  # screen alias
    assert OrionApp._should_route_to_system_by_default("record") is True
    assert OrionApp._should_route_to_system_by_default("record start /tmp/x.jsonl") is True
    assert OrionApp._should_route_to_system_by_default("replay /tmp/x.jsonl") is True
    assert OrionApp._should_route_to_system_by_default("trust") is True
    assert OrionApp._should_route_to_system_by_default("trust untrusted") is True
    assert OrionApp._should_route_to_system_by_default("trust status") is True
    assert OrionApp._should_route_to_system_by_default("доверие") is True
    assert OrionApp._should_route_to_system_by_default("доверие untrusted") is True
    assert OrionApp._should_route_to_system_by_default("доверие статус") is True
    assert OrionApp._should_route_to_system_by_default("доверие недоверенный") is True


def test_default_routing_keeps_free_text_as_qiki() -> None:
    assert OrionApp._should_route_to_system_by_default("привет как дела") is False
    assert OrionApp._should_route_to_system_by_default("analyze my radar") is False
