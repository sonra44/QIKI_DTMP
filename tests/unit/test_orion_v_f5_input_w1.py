"""W1 (И1): на F5 голый текст = вопрос QIKI, поле остаётся; вне F5 — команда."""

from __future__ import annotations

from qiki.services.operator_console.orion_v.app import OrionVApp


class _StubInput:
    def __init__(self, value: str) -> None:
        self.value = value


class _Evt:
    def __init__(self, value: str) -> None:
        self.value = value
        self.input = _StubInput(value)


def _app(level: str) -> tuple[OrionVApp, dict]:
    calls = {"intent": [], "help": [], "reopen": 0, "close": 0}
    app = OrionVApp()
    app._current_level = level
    app._command_mode_open = True

    async def _intent(text: str) -> None:
        calls["intent"].append(text)

    app._publish_qiki_intent = _intent  # type: ignore
    app._set_help_text = lambda text="", *a, **k: calls["help"].append(str(text))  # type: ignore
    app._reopen_f5_input = lambda: calls.__setitem__("reopen", calls["reopen"] + 1)  # type: ignore
    app.action_close_command_mode = lambda: calls.__setitem__("close", calls["close"] + 1)  # type: ignore
    app._request_refresh_ui = lambda: None  # type: ignore
    return app, calls


def _submit(app: OrionVApp, text: str) -> None:
    import asyncio

    async def _run():
        app.on_input_submitted(_Evt(text))  # create_task внутри нуждается в loop
        await asyncio.sleep(0)  # дать запланированным задачам выполниться

    asyncio.run(_run())


def test_f5_bare_text_is_qiki_intent() -> None:
    app, calls = _app("f5")
    _submit(app, "ты сейчас в полёте?")
    assert calls["intent"] == ["ты сейчас в полёте?"]  # голый текст → QIKI
    assert calls["reopen"] == 1  # поле осталось открытым
    assert calls["close"] == 0  # на F5 не закрываем


def test_f5_q_prefix_still_intent() -> None:
    app, calls = _app("f5")
    _submit(app, "q: доложи режим")
    assert calls["intent"] == ["доложи режим"]


def test_f5_empty_reopens_input() -> None:
    app, calls = _app("f5")
    _submit(app, "   ")
    assert calls["intent"] == []
    assert calls["reopen"] == 1


def test_non_f5_bare_text_is_unknown_command_not_intent() -> None:
    app, calls = _app("f1")
    _submit(app, "просто болтовня")
    assert calls["intent"] == []  # вне F5 голый текст НЕ уходит боту
    assert any("Неизвестная команда" in h for h in calls["help"])
    assert calls["close"] == 1  # вне F5 поле закрывается


def test_f5_control_verb_not_swallowed_as_chat() -> None:
    """q confirm на F5 остаётся control-командой, не уходит боту как текст."""
    app, calls = _app("f5")
    fired = {"confirm": 0}
    app._confirm_qiki_pending_action = lambda: fired.__setitem__("confirm", 1)  # type: ignore
    _submit(app, "q confirm")
    assert fired["confirm"] == 1
    assert calls["intent"] == []  # не ушло в LLM


def test_entering_f5_opens_input() -> None:
    app, calls = _app("f1")
    opened = {"n": 0}
    app.action_open_command_mode = lambda: opened.__setitem__("n", opened["n"] + 1)  # type: ignore
    app._refresh_visible_level = lambda: None  # type: ignore
    app._prefer_f8_evidence_card_for_current_context = lambda: None  # type: ignore

    async def _noaudit(*a, **k):
        return None

    app._publish_audit_event = _noaudit  # type: ignore

    async def _run():
        app.action_show_level("f5")  # create_task внутри нуждается в running loop

    __import__("asyncio").run(_run())
    assert opened["n"] >= 1  # вход на F5 открыл поле ввода
