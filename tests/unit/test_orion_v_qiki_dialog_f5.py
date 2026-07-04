"""M1: экран F5 QIKI/ДИАЛОГ — read-only лента + гейт «нет нового execute-пути»."""

from __future__ import annotations

import ast
from pathlib import Path

from qiki.services.operator_console.orion_v.qiki_voice import QikiVoiceEntry
from qiki.services.operator_console.orion_v.screens.qiki_dialog import (
    OrionVQikiDialogScreen,
    QikiDialogLine,
    merge_dialog_lines,
)

_SCREEN_SRC = Path("src/qiki/services/operator_console/orion_v/screens/qiki_dialog.py")


def test_merge_interleaves_by_received_at():
    ops = [("06:00:12Z", "доложи состояние"), ("06:02:00Z", "займи орбиту 5км")]
    voice = [
        QikiVoiceEntry(
            received_at="06:00:45Z",
            kind="ACK",
            text="состояние стабильное",
            legality_code=None,
            trust_code=None,
        )
    ]
    merged = merge_dialog_lines(operator_lines=ops, voice_entries=voice)
    assert [(m.speaker, m.received_at) for m in merged] == [
        ("ОПЕРАТОР", "06:00:12Z"),
        ("QIKI", "06:00:45Z"),
        ("ОПЕРАТОР", "06:02:00Z"),
    ]


def test_empty_state_text_rendered():
    screen = OrionVQikiDialogScreen()
    screen.set_state(dialog_lines=[], candidate_title=None, decision_preview_lines=[])
    rendered = screen.rendered_text()
    assert "QIKI — не внешний чат-бот" in rendered
    assert "q: <запрос>" in rendered
    # Зоны КАНДИДАТ/РЕШЕНИЕ show-when: без кандидата их нет.
    assert "КАНДИДАТ" not in rendered
    assert "РЕШЕНИЕ" not in rendered


def test_candidate_marked_not_executable():
    screen = OrionVQikiDialogScreen()
    screen.set_state(
        dialog_lines=[QikiDialogLine("06:00:00Z", "QIKI", "INFO", "готова")],
        candidate_title="Возобновить наблюдение безопасно",
        decision_preview_lines=["validation: — | publish: — | ack: — | effect: — (не схлопывать)"],
    )
    rendered = screen.rendered_text()
    assert "КАНДИДАТ" in rendered
    assert "candidate_only" in rendered
    assert "НЕ исполняется" in rendered
    assert "не схлопывать" in rendered


def test_qiki_codes_shown_when_present():
    screen = OrionVQikiDialogScreen()
    screen.set_state(
        dialog_lines=[
            QikiDialogLine(
                "06:01:32Z", "QIKI", "REJECT", "манёвр отклонён",
                legality_code="blocked [zone] ZONE_DENY", trust_code="degraded conf=0.62",
            )
        ],
        candidate_title=None,
        decision_preview_lines=[],
    )
    rendered = screen.rendered_text()
    assert "REJECT" in rendered
    assert "LEGALITY blocked [zone] ZONE_DENY" in rendered
    assert "TRUST degraded conf=0.62" in rendered


def test_screen_module_has_no_execute_path():
    """Гейт M1: экран не вызывает исполнение и не мутирует _qiki_pending_action."""
    tree = ast.parse(_SCREEN_SRC.read_text())
    forbidden = {
        "_execute_qiki_pending_action",
        "_execute_qiki_pending_procedure",
        "_confirm_qiki_pending_action",
        "publish_command",
        "publish",
    }
    called = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert not (called & forbidden), f"F5 screen must be read-only, found: {called & forbidden}"
