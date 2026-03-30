import pytest


def _has_braille(s: str) -> bool:
    return any(0x2801 <= ord(ch) <= 0x28FF for ch in s)


@pytest.mark.asyncio
async def test_orion_seed_radar_ppi_draws_overlays() -> None:
    pytest.importorskip("textual")

    from qiki.services.operator_console.main_orion import OrionApp

    app = OrionApp()

    captured: dict[str, str] = {}

    class _FakeStatic:
        def update(self, value):  # noqa: ANN001
            captured["ppi"] = str(value)

    def _fake_query_one(selector, _cls=None):  # noqa: ANN001
        if selector == "#radar-ppi":
            return _FakeStatic()
        raise LookupError(selector)

    app.query_one = _fake_query_one  # type: ignore[method-assign]
    app._seed_radar_ppi()

    assert "ppi" in captured
    assert _has_braille(captured["ppi"])
