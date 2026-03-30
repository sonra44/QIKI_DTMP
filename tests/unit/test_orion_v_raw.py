from __future__ import annotations

from qiki.services.operator_console.orion_v.screens.raw import OrionVRawScreen


class _CaptureRaw(OrionVRawScreen):
    def __init__(self) -> None:
        super().__init__()
        self.last_render = ""

    def update(self, renderable) -> None:  # noqa: ANN001
        self.last_render = str(renderable)


def test_raw_screen_renders_literal_payload_with_markup_like_tokens() -> None:
    screen = _CaptureRaw()
    payload = '{"err":"Markup [@click=bad] = q-sim-service"}'

    # Must not raise MarkupError on literal JSON-like payload.
    screen.set_text(payload)
    assert "[F4] Консоль/Console" in screen.last_render
    assert "[@click=bad]" in screen.last_render
