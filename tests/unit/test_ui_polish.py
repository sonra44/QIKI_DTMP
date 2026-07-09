"""UI-полировка (пост-ревью): подсветка полных статус-слов и IFF-кодов.

Находки UI-ревью 2026-07-09: `WARN|WARNING` в _STATUS_RE матчил короткий
префикс, boundary-check его отбрасывал — полные слова WARNING/CRITICAL нигде
не подсвечивались; IFF-коды (FOE — враг!) не имели стиля вовсе.
"""

from __future__ import annotations

from qiki.services.operator_console.orion_v.ui_rich import (
    ORION_UI_COLORS,
    _STATUS_RE,
    _style_for_token,
)


def _match(text: str) -> str | None:
    match = _STATUS_RE.search(text)
    return match.group("token") if match else None


def test_full_status_words_match_entirely() -> None:
    assert _match("статус WARNING сейчас") == "WARNING"
    assert _match("статус CRITICAL сейчас") == "CRITICAL"
    assert _match("UNKNOWN контакт") == "UNKNOWN"


def test_iff_codes_have_semantic_styles() -> None:
    assert ORION_UI_COLORS["crit"] in _style_for_token("FOE")
    assert ORION_UI_COLORS["ok"] in _style_for_token("FRND")
    assert ORION_UI_COLORS["warn"] in _style_for_token("UNK")
    assert _match("IFF FOE рядом") == "FOE"
    assert _match("IFF FRND рядом") == "FRND"
    assert _match("IFF UNK рядом") == "UNK"
