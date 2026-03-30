import pytest

from qiki.services.operator_console.main_orion import OrionApp


def test_summary_causal_badge_compact_for_energy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ORION_SUMMARY_COMPACT_DEFAULT", "1")
    app = OrionApp()
    value = "SoC=40%; cause=load_shedding -> effect=shed=2 -> next=reduce loads"

    out = app._summary_value_with_causal_badge("energy", value)
    assert out.startswith("[load_shedding->shed=2]")
    assert "next=reduce loads" in out
    assert "SoC=40%" in out


def test_summary_causal_badge_keeps_original_in_verbose_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ORION_SUMMARY_COMPACT_DEFAULT", "0")
    app = OrionApp()
    value = "rad=warn; cause=radiation_warning -> effect=reduced safety margin -> next=minimize exposure"

    out = app._summary_value_with_causal_badge("threats", value)
    assert out == value


def test_summary_causal_badge_ignores_non_causal_text(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ORION_SUMMARY_COMPACT_DEFAULT", "1")
    app = OrionApp()
    value = "V=2.0m/s; Hdg=90"

    out = app._summary_value_with_causal_badge("motion_safety", value)
    assert out == value
