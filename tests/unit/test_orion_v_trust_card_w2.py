"""W2 (F5V2): Trust/Legality-карта — «спина G1» на дисплее F5.

Show-when: карта живёт только при кандидате/активном действии; состав:
законность / доверие / источник / условие разблокировки. Всё из готовых
view-model (И5: ноль новых деривов, ноль provider-markdown).
"""

from __future__ import annotations

from qiki.services.operator_console.orion_v.screens.qiki_dialog import (
    OrionVQikiDialogScreen,
    TrustCard,
)


def _card(**over) -> TrustCard:
    base = dict(
        action_title="Возобновить наблюдение",
        action_command="qiki.commands.control ▸ sim.dock.release",
        source="провайдер (карантин)",
        legality_code="blocked [zone] ZONE_DENY",
        legality_status="blocked",
        trust_code="degraded conf=0.62",
        unlock_condition="выйти из зоны запрета",
    )
    base.update(over)
    return TrustCard(**base)


def _render(card: TrustCard | None, *, with_candidate: bool = True) -> str:
    screen = OrionVQikiDialogScreen()
    screen.set_state(
        dialog_lines=[],
        candidate_title="Возобновить наблюдение" if with_candidate else None,
        decision_preview_lines=[],
        trust_card=card,
    )
    return screen.rendered_text()


def test_show_when_no_card_no_zone() -> None:
    rendered = _render(None, with_candidate=False)
    assert "ДОВЕРИЕ/ЗАКОННОСТЬ" not in rendered


def test_card_renders_all_rows() -> None:
    rendered = _render(_card())
    assert "── ДОВЕРИЕ/ЗАКОННОСТЬ ──" in rendered
    assert "ЗАКОННОСТЬ" in rendered and "blocked [zone] ZONE_DENY" in rendered
    assert "ДОВЕРИЕ" in rendered and "degraded conf=0.62" in rendered
    assert "ИСТОЧНИК" in rendered and "провайдер (карантин)" in rendered
    assert "РАЗБЛОКИРОВКА" in rendered and "выйти из зоны запрета" in rendered


def test_card_codes_survive_render() -> None:
    """Коды в [скобках] не съедаются рендером (инвариант a58fd97)."""
    rendered = _render(_card(legality_code="deferred [trust] CATALOG_UNAVAILABLE"))
    assert "[trust]" in rendered and "CATALOG_UNAVAILABLE" in rendered


def test_unlock_row_show_when() -> None:
    rendered = _render(_card(unlock_condition=""))
    assert "РАЗБЛОКИРОВКА" not in rendered  # нет условия — строка не торчит


def test_card_styles_follow_hmi() -> None:
    """HMI: blocked → red, degraded → amber; allowed/trusted — приглушены."""
    screen = OrionVQikiDialogScreen()
    screen.set_state(
        dialog_lines=[], candidate_title="t", decision_preview_lines=[],
        trust_card=_card(),
    )
    styles = {text: style for text, style in screen._styled_lines()}
    legality_row = next(t for t in styles if t.startswith("ЗАКОННОСТЬ"))
    trust_row = next(t for t in styles if t.startswith("ДОВЕРИЕ"))
    assert "red" in styles[legality_row]
    assert "yellow" in styles[trust_row] or "amber" in styles[trust_row]

    screen.set_state(
        dialog_lines=[], candidate_title="t", decision_preview_lines=[],
        trust_card=_card(legality_status="allowed",
                         legality_code="allowed [physics] BODY_ATTACH_READY",
                         trust_code="trusted conf=0.95"),
    )
    styles2 = {text: style for text, style in screen._styled_lines()}
    legality_row2 = next(t for t in styles2 if t.startswith("ЗАКОННОСТЬ"))
    assert "red" not in styles2[legality_row2]  # норма не кричит (dark cockpit)


def test_app_builder_procedure_takes_priority() -> None:
    """Активная процедура приоритетнее кандидата; условие G1 в карте."""
    from qiki.services.operator_console.orion_v.app import OrionVApp
    from qiki.services.operator_console.orion_v.attach_procedure import (
        STAGE_S3_TRANSFER,
        STATUS_HOLDING,
        AttachProcedure,
    )
    from qiki.shared.command_decision import CommandIntent, seal_decision

    app = OrionVApp()
    intent = CommandIntent(kind="BODY_ATTACH", subject="orionv.body", name="attach.module",
                           parameters={"module_id": "m1", "mount": "F09"},
                           operator_facing_title="t")
    proc = AttachProcedure(
        decision=seal_decision(decision_id="w2-1", intent=intent),
        origin_request_id="r1",
        params={"module_id": "m1", "mount": "F09"},
    )
    proc.stage = STAGE_S3_TRANSFER
    proc.status = STATUS_HOLDING
    proc.complication = "OPERATOR_HOLD"
    app._attach_procedure = proc
    card = app._build_qiki_trust_card()
    assert card is not None
    assert "УСТАНОВКА m1 → F09" in card.action_title
    assert "holding" in card.legality_code and "OPERATOR_HOLD" in card.legality_code
    assert card.source.startswith("policy")
