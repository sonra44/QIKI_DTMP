"""Alt+1..6 keyboard parity for the clickable status-bar chips (DESIGN-2A tail)."""

from __future__ import annotations

from types import SimpleNamespace

from qiki.services.operator_console.orion_v.app import OrionVApp
from qiki.services.operator_console.orion_v.operator_state import SubsystemChip


def test_status_chip_bindings_present_for_all_six_chips() -> None:
    keys = {binding[0]: binding[1] for binding in OrionVApp.BINDINGS}
    for index, slug in enumerate(("power", "thermal", "propulsion", "hull", "compute", "qiki"), start=1):
        assert keys.get(f"alt+{index}") == f"status_chip('{slug}')"


def test_action_status_chip_routes_chip_action_by_slug() -> None:
    routed: list[tuple[str, str]] = []
    chip = SubsystemChip(
        slug="power",
        label="Power",
        status="ok",
        severity="normal",
        short_summary="",
        hint="",
        action="select_subsystem",
        target="power",
    )
    stub = SimpleNamespace(
        _operator_shell_state=SimpleNamespace(chips=(chip,)),
        _route_metric_action=lambda action, target: routed.append((action, target)),
    )

    # Alt+1 parity: routes the chip's own action/target — identical to clicking it.
    OrionVApp.action_status_chip(stub, "power")
    assert routed == [("select_subsystem", "power")]

    # Unknown slug -> no-op (no crash, no spurious route).
    OrionVApp.action_status_chip(stub, "does-not-exist")
    assert routed == [("select_subsystem", "power")]
