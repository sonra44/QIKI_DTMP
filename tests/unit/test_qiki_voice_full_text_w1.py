"""W1 (F5v2): полный текст реплики хранится; усечение — только на компакте F1."""

from __future__ import annotations

from uuid import uuid4

from qiki.services.operator_console.orion_v.qiki_voice import (
    QIKI_VOICE_VISIBLE_LIMIT,
    build_qiki_voice_entry,
    format_qiki_voice_lines,
)
from qiki.services.operator_console.orion_v.screens.qiki_dialog import (
    OrionVQikiDialogScreen,
    QikiDialogLine,
)
from qiki.shared.models.qiki_chat import BilingualText, QikiChatResponseV1, QikiMode, QikiReplyV1

LONG = ("QIKI: автономное машинное тело, наблюдаемое оператором через ORION V. "
        "Текущее состояние стабильное, все системы работают в норме, аномалий не выявлено, "
        "резервные каналы связи в готовности, журнал операций обновлён по последнему циклу.")


def _resp(text: str) -> QikiChatResponseV1:
    return QikiChatResponseV1(
        request_id=uuid4(), ok=True, mode=QikiMode.FACTORY,
        reply=QikiReplyV1(title=BilingualText(en="QIKI", ru="QIKI"),
                          body=BilingualText(en=text, ru=text)),
        legality=None, trust_signals=[], consequence=None, proposals=[], warnings=[], error=None,
    )


def test_ledger_keeps_full_text() -> None:
    entry = build_qiki_voice_entry(_resp(LONG), received_at="06:00:00Z")
    assert entry.text == LONG  # ничего не отрезано на входе
    assert "…" not in entry.text


def test_f1_compact_still_truncates() -> None:
    entry = build_qiki_voice_entry(_resp(LONG), received_at="06:00:00Z")
    lines = format_qiki_voice_lines([entry], limit=QIKI_VOICE_VISIBLE_LIMIT)
    assert lines and lines[0].endswith("…")  # F1 остаётся компактным
    assert len(lines[0]) < len(LONG)


def test_f5_renders_full_reply_wrapped() -> None:
    screen = OrionVQikiDialogScreen()
    screen.set_state(
        dialog_lines=[QikiDialogLine(received_at="06:00:00Z", speaker="QIKI", kind="INFO", text=LONG)],
        candidate_title=None,
        decision_preview_lines=[],
    )
    rendered = screen.rendered_text()
    # весь текст присутствует (по последнему слову) и перенесён (нет строк > ширины)
    assert "обновлён по последнему циклу." in rendered
    assert "…" not in rendered
    assert all(len(ln) <= 120 for ln in rendered.splitlines())


def test_f5_shows_input_zone() -> None:
    screen = OrionVQikiDialogScreen()
    screen.set_state(dialog_lines=[], candidate_title=None, decision_preview_lines=[])
    rendered = screen.rendered_text()
    assert "── ВВОД ──" in rendered
    assert "q:" in rendered
