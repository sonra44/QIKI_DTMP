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

