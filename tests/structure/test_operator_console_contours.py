"""Contour-boundary invariants: ORION V (live) MUST NOT be confused with legacy.

This is a RED-test authored BEFORE the isolation edits (steps 2-6 of the
countermeasure plan). It encodes the END-STATE invariants that keep the two
operator-console contours physically separable even under full memory loss:

    ORION V  = src/qiki/services/operator_console/orion_v/ (OrionVApp,
               entrypoint main_orion_v.py) — the LIVE production console.
    LEGACY   = src/qiki/services/operator_console/main_orion.py (440KB monolith)
               + legacy/main_orion.py — old contour, NOT for production.

On first run some assertions PASS (orion_v has no legacy import; default compose
launches main_orion_v) and some FAIL (no console map, no sentinel, legacy compose
service not renamed, legacy launcher unguarded). The failing ones turn GREEN as
steps 2-6 land. Live qiki-operator-console is never touched by this test.
"""
from __future__ import annotations

import ast
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]
OC = REPO / "src" / "qiki" / "services" / "operator_console"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8") if p.exists() else ""


def _yaml(p: Path) -> dict:
    return yaml.safe_load(_read(p)) or {}


def _cmd(svc: dict) -> str:
    c = (svc or {}).get("command", "")
    return " ".join(c) if isinstance(c, list) else str(c)


# --- already-true invariants (regression guards: must STAY green) ---

def test_orion_v_does_not_import_legacy() -> None:
    """orion_v/** must not import the legacy monolith or the legacy package."""
    bad: list[str] = []
    import_re = re.compile(
        r"^\s*(from|import)\s+.*\b(main_orion|operator_console\.legacy|\.legacy\.main_orion)\b"
    )
    for py in (OC / "orion_v").rglob("*.py"):
        for i, line in enumerate(_read(py).splitlines(), 1):
            if import_re.search(line):
                bad.append(f"{py.relative_to(REPO)}:{i}: {line.strip()}")
    assert not bad, "orion_v imports legacy contour:\n" + "\n".join(bad)


def test_default_compose_launches_orion_v() -> None:
    """Default + operator overlays launch ORION V (YAML-exact command); the default
    compose carries NO legacy launcher command on any service."""
    for name in ("docker-compose.yml", "docker-compose.operator.yml"):
        svc = (_yaml(REPO / name).get("services") or {}).get("operator-console")
        assert svc, f"{name}: no operator-console service"
        assert "main_orion_v" in _cmd(svc), f"{name}: operator-console does not launch main_orion_v"
    for sname, svc in (_yaml(REPO / "docker-compose.yml").get("services") or {}).items():
        assert "legacy.main_orion" not in _cmd(svc), (
            f"docker-compose.yml service {sname} runs the legacy launcher"
        )


# --- target invariants (RED until steps 2-6 land) ---

def test_console_map_declares_single_live_console() -> None:
    """00_CONSOLE_MAP.md must exist and name exactly one LIVE console = ORION V."""
    cmap = _read(OC / "00_CONSOLE_MAP.md")
    assert cmap, "00_CONSOLE_MAP.md missing (step 2)"
    markers = re.findall(r"LIVE_CONSOLE:", cmap)
    assert len(markers) == 1, f"CONSOLE_MAP must declare EXACTLY ONE LIVE_CONSOLE (found {len(markers)})"
    marker_line = next(l for l in cmap.splitlines() if "LIVE_CONSOLE:" in l)
    assert "ORION V" in marker_line and "main_orion_v" in marker_line, (
        "LIVE_CONSOLE marker must name ORION V and main_orion_v"
    )


def test_legacy_sentinel_exists() -> None:
    """A self-documenting DANGER sentinel must sit in legacy/ (name = the warning)."""
    matches = list((OC / "legacy").glob("00_DANGER*NOT_PRODUCTION*"))
    assert matches, "legacy DANGER sentinel doc missing (step 3)"


def test_legacy_compose_service_is_isolated() -> None:
    """Legacy overlay must use a distinct service name + the legacy profile so an
    overlay merge can never silently override the production operator-console."""
    services = _yaml(REPO / "docker-compose.operator_legacy.yml").get("services") or {}
    assert "operator-console-legacy" in services, (
        "legacy overlay must define operator-console-legacy (step 5)"
    )
    assert "operator-console" not in services, (
        "legacy overlay still defines bare 'operator-console' (overlay merge would override production)"
    )
    svc = services["operator-console-legacy"]
    assert svc.get("container_name") == "qiki-operator-console-legacy", (
        "legacy service must set its own container_name qiki-operator-console-legacy"
    )
    assert "legacy" in (svc.get("profiles") or []), "legacy service must be profile-gated"
    assert "legacy.main_orion" in _cmd(svc), "legacy service must run the legacy launcher"
    env = svc.get("environment") or []
    env_str = " ".join(env) if isinstance(env, list) else str(env)
    assert "ALLOW_LEGACY_OPERATOR_CONSOLE" in env_str, (
        "legacy service must propagate the ALLOW_LEGACY_OPERATOR_CONSOLE opt-in into the container "
        "(else the runtime guard exits 2 and the documented run path is a lie) (step 5)"
    )


def test_legacy_monolith_main_is_guarded() -> None:
    """main() in the monolith must gate on ALLOW_LEGACY_OPERATOR_CONSOLE AND exit —
    guard on the execution path (inside main), not at import time (tests import OrionApp).
    AST-checked, not string-in-file, to close the false-green gap."""
    tree = ast.parse(_read(OC / "main_orion.py"))
    main_fn = next(
        (n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main"), None
    )
    assert main_fn is not None, "main_orion.py has no top-level main()"
    refs_env = any(
        isinstance(n, ast.Constant) and n.value == "ALLOW_LEGACY_OPERATOR_CONSOLE"
        for n in ast.walk(main_fn)
    )
    exit_nodes = [
        n for n in ast.walk(main_fn)
        if isinstance(n, ast.Raise)
        or (isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "exit")
    ]
    run_nodes = [
        n for n in ast.walk(main_fn)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "run"
    ]
    assert refs_env, "main() does not reference the ALLOW_LEGACY_OPERATOR_CONSOLE guard (step 4)"
    assert exit_nodes, "main() guard does not stop execution (raise/sys.exit) when opt-in absent (step 4)"
    if run_nodes:
        assert min(n.lineno for n in exit_nodes) < min(n.lineno for n in run_nodes), (
            "guard must exit BEFORE OrionApp().run() in main() — ordering (step 4)"
        )


def test_legacy_launcher_routes_through_guarded_main() -> None:
    """legacy/main_orion.py must call the guarded monolith main(), not bypass the guard."""
    text = _read(OC / "legacy" / "main_orion.py")
    assert text, "legacy/main_orion.py missing"
    assert "main_orion import main" in text, (
        "legacy launcher must import main() from the guarded monolith (so the guard applies)"
    )


def test_prototypes_marked_not_production() -> None:
    """Dead Rich prototypes must carry a self-evident NOT-PRODUCTION marker near the top,
    so a fresh agent that lands in one cannot mistake it for the live console (step 6)."""
    protos = ("main_full.py", "main_enhanced.py", "main_integrated.py", "main_live.py")
    unmarked: list[str] = []
    for rel in protos:
        head = "\n".join(_read(OC / rel).splitlines()[:6])
        if "DEAD PROTOTYPE" not in head or "NOT PRODUCTION" not in head:
            unmarked.append(rel)
    assert not unmarked, "prototypes missing NOT-PRODUCTION marker (step 6): " + ", ".join(unmarked)


def test_legacy_entrypoint_exits_without_optin() -> None:
    """Behavior: the legacy launcher refuses to start without opt-in (exit nonzero, guard fired).
    Skipped where project deps are unavailable (the check runs for real in Docker/venv)."""
    env = {k: v for k, v in os.environ.items() if k != "ALLOW_LEGACY_OPERATOR_CONSOLE"}
    env["PYTHONPATH"] = f"{REPO / 'src'}:{REPO / 'generated'}"
    proc = subprocess.run(
        [sys.executable, "-m", "qiki.services.operator_console.legacy.main_orion"],
        env=env, capture_output=True, text=True, timeout=90,
    )
    if "ModuleNotFoundError" in proc.stderr or "No module named" in proc.stderr:
        pytest.skip("project deps unavailable here; behavior check runs in Docker/venv")
    assert proc.returncode != 0, "legacy launcher started without opt-in"
    assert "NOT for production" in proc.stderr or "ALLOW_LEGACY_OPERATOR_CONSOLE" in proc.stderr


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
