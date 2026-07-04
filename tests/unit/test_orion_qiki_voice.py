"""DISPLAY_CANON №8в (G-C, голос QIKI): маппинг QikiChatResponseV1 в реплику ленты QIKI ▸.

RED-негативы первыми (урок ORION overclaim): отказ/арбитраж не должен схлопываться
в ACK, текст реплики не выдумывается — только честные источники (reply → legality.reason
→ error.message → явный маркер отсутствия текста).
"""

from __future__ import annotations

import pytest

from qiki.services.operator_console.orion_v.qiki_voice import (
    QIKI_VOICE_VISIBLE_LIMIT,
    build_qiki_voice_entry,
    format_qiki_voice_lines,
    format_qiki_voice_tooltip,
)
from qiki.shared.models.qiki_chat import (
    BilingualText,
    QikiChatResponseV1,
    QikiErrorV1,
    QikiLegalityV1,
    QikiMode,
    QikiReplyV1,
    QikiTrustSignalV1,
)


def _response(**kwargs: object) -> QikiChatResponseV1:
    base: dict[str, object] = {
        "request_id": "00000000-0000-0000-0000-0000000000aa",
        "ok": True,
        "mode": QikiMode.FACTORY,
    }
    base.update(kwargs)
    return QikiChatResponseV1.model_validate(base)


def _legality(status: str, *, reason_ru: str = "зона запрета") -> QikiLegalityV1:
    return QikiLegalityV1(
        status=status,  # type: ignore[arg-type]
        domain="zone",
        reason_code="ZONE_DENY",
        reason=BilingualText(en="deny", ru=reason_ru),
    )


# --- негативы первыми: не-allowed НИКОГДА не ACK, текст не выдумывается ---


@pytest.mark.parametrize("status", ["blocked", "unsafe", "deferred"])
def test_non_allowed_legality_maps_to_reject_not_ack(status: str) -> None:
    entry = build_qiki_voice_entry(_response(legality=_legality(status)), received_at="04:11:07Z")
    assert entry.kind == "REJECT"
    assert entry.kind != "ACK"


def test_reply_without_legality_is_info_not_ack() -> None:
    reply = QikiReplyV1(
        title=BilingualText(en="obs", ru="наблюдение"),
        body=BilingualText(en="watching", ru="наблюдаю цель, данные неполные"),
    )
    entry = build_qiki_voice_entry(_response(reply=reply), received_at="04:09:41Z")
    assert entry.kind == "INFO"
    assert entry.text == "наблюдаю цель, данные неполные"


def test_no_text_sources_yields_honest_marker_not_invented_text() -> None:
    entry = build_qiki_voice_entry(_response(), received_at="04:00:00Z")
    assert entry.kind == "INFO"
    assert entry.text == "ответ без текста"


def test_missing_reply_falls_back_to_legality_reason_ru() -> None:
    entry = build_qiki_voice_entry(
        _response(legality=_legality("blocked", reason_ru="манёвр отклонён: зона запрета")),
        received_at="04:11:07Z",
    )
    assert entry.text == "манёвр отклонён: зона запрета"


def test_error_message_used_when_no_reply_and_no_legality() -> None:
    error = QikiErrorV1(code="TIMEOUT", message=BilingualText(en="timeout", ru="таймаут ответа"))
    entry = build_qiki_voice_entry(_response(ok=False, error=error), received_at="04:02:00Z")
    assert entry.kind == "INFO"
    assert entry.text == "таймаут ответа"


# --- позитив: allowed → ACK с текстом реплики ---


def test_allowed_with_reply_maps_to_ack() -> None:
    reply = QikiReplyV1(
        title=BilingualText(en="ok", ru="принято"),
        body=BilingualText(en="done", ru="самопроверка корпуса выполнена"),
    )
    entry = build_qiki_voice_entry(
        _response(reply=reply, legality=_legality("allowed")),
        received_at="04:12:33Z",
    )
    assert entry.kind == "ACK"
    assert entry.text == "самопроверка корпуса выполнена"


# --- лента: формат строки, новейшая сверху, лимит видимых ---


def test_voice_line_format_is_exact() -> None:
    reply = QikiReplyV1(
        title=BilingualText(en="ok", ru="принято"),
        body=BilingualText(en="done", ru="самопроверка корпуса выполнена"),
    )
    entry = build_qiki_voice_entry(
        _response(reply=reply, legality=_legality("allowed")),
        received_at="04:12:33Z",
    )
    assert format_qiki_voice_lines([entry]) == [
        "QIKI ▸ 04:12:33Z ACK | самопроверка корпуса выполнена"
    ]


def test_voice_lines_newest_first_and_limited() -> None:
    entries = [
        build_qiki_voice_entry(_response(legality=_legality("allowed")), received_at=f"04:0{i}:00Z")
        for i in range(QIKI_VOICE_VISIBLE_LIMIT + 2)
    ]
    lines = format_qiki_voice_lines(entries)
    assert len(lines) == QIKI_VOICE_VISIBLE_LIMIT
    # хвост списка = новейшие записи; первая строка ленты — самая свежая
    assert lines[0].startswith(f"QIKI ▸ 04:0{QIKI_VOICE_VISIBLE_LIMIT + 1}:00Z")


# --- tooltip: коды LEGALITY/TRUST новейшей реплики, без кодов — None ---


def test_tooltip_carries_legality_and_trust_codes() -> None:
    trust = QikiTrustSignalV1(
        label=BilingualText(en="track", ru="трек"),
        state="degraded",
        source="sensor",
        confidence=0.62,
        reason_code="STATION_TRACK_LOW_QUALITY",
        reason=BilingualText(en="noisy", ru="зашумлён"),
    )
    entry = build_qiki_voice_entry(
        _response(legality=_legality("blocked"), trust_signals=[trust]),
        received_at="04:11:07Z",
    )
    tooltip = format_qiki_voice_tooltip([entry])
    assert tooltip == "LEGALITY blocked [zone] ZONE_DENY · TRUST degraded conf=0.62"


def test_tooltip_is_none_when_newest_entry_has_no_codes() -> None:
    entry = build_qiki_voice_entry(_response(), received_at="04:00:00Z")
    assert format_qiki_voice_tooltip([entry]) is None
    assert format_qiki_voice_tooltip([]) is None
