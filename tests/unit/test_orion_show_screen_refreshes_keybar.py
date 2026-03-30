import pytest


def test_orion_action_show_screen_refreshes_keybar() -> None:
    pytest.importorskip("textual")

    from qiki.services.operator_console.main_orion import OrionApp

    app = OrionApp()

    class _FakeKeybar:
        def __init__(self) -> None:
            self.refresh_count = 0

        def refresh(self) -> None:
            self.refresh_count += 1

    keybar = _FakeKeybar()

    def _fake_query_one(selector, _cls=None):  # noqa: ANN001
        if selector == "#orion-keybar":
            return keybar  # type: ignore[return-value]
        raise LookupError(selector)

    app.query_one = _fake_query_one  # type: ignore[method-assign]

    app.action_show_screen("radar")

    assert app.active_screen == "radar"
    assert keybar.refresh_count == 1


def test_orion_action_show_screen_radar_enables_mouse_tracking(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("textual")

    import qiki.services.operator_console.main_orion as orion_mod
    from qiki.services.operator_console.main_orion import OrionApp

    app = OrionApp()
    calls: list[bool] = []

    def _fake_emit(*, enabled: bool) -> None:
        calls.append(enabled)

    class _FakeKeybar:
        def refresh(self) -> None:
            return

    def _fake_query_one(selector, _cls=None):  # noqa: ANN001
        if selector == "#orion-keybar":
            return _FakeKeybar()  # type: ignore[return-value]
        raise LookupError(selector)

    monkeypatch.setattr(orion_mod, "_emit_xterm_mouse_tracking", _fake_emit)
    app.query_one = _fake_query_one  # type: ignore[method-assign]

    app.action_show_screen("radar")

    assert calls == [True]
