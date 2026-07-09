"""W7 (F5v2): подсветка синтаксиса в свободном теле реплики QIKI.

Тело QIKI рендерится как Markdown-блок (код-фенс/списки подсвечены), НО
коды в [скобках] не съедаются (И4). Оператор/ПРОЦЕДУРА остаются plain.
"""

from __future__ import annotations

from rich.console import Console

from qiki.services.operator_console.orion_v.screens.qiki_dialog import (
    OrionVQikiDialogScreen,
    QikiDialogLine,
)

_REPLY = (
    "Отсек F09 готов. Проверь командой:\n"
    "```bash\n"
    "q status --bay F09\n"
    "```\n"
    "Замечания: код [OPERATOR_HOLD] активен, зона [zone] ZONE_DENY.\n"
    "Дальше:\n"
    "- release dock\n"
    "- mount module"
)


def _screen() -> OrionVQikiDialogScreen:
    s = OrionVQikiDialogScreen()
    s.set_state(
        dialog_lines=[
            QikiDialogLine("06:00:12Z", "ОПЕРАТОР", "", "доложи по отсеку F09"),
            QikiDialogLine("06:00:45Z", "QIKI", "INFO", _REPLY),
        ],
        candidate_title=None,
        decision_preview_lines=[],
    )
    return s


def _render_ansi(s: OrionVQikiDialogScreen) -> str:
    # color_system пинован: без TERM (docker exec) Rich деградирует до 8 цветов
    # и фоновые эскейпы подсветки исчезают — тест должен быть детерминирован.
    console = Console(width=90, force_terminal=True, color_system="truecolor")
    with console.capture() as cap:
        console.print(s._blocks_to_rich(s._render_blocks()))
    return cap.get()


def test_qiki_body_is_markdown_block() -> None:
    """Тело реплики QIKI попадает в «md»-блок; ПРОЦЕДУРА/оператор — «line»."""
    blocks = _screen()._render_blocks()
    kinds = [b[0] for b in blocks]
    assert "md" in kinds  # свободный голос QIKI — Markdown
    md_sources = [b[1] for b in blocks if b[0] == "md"]
    assert any("q status --bay F09" in src for src in md_sources)


def test_code_fence_is_highlighted() -> None:
    """Код-фенс несёт ANSI-фон подсветки (pygments/monokai), не голый текст."""
    out = _render_ansi(_screen())
    assert "48;2;" in out  # background escape → блок кода подсвечен
    assert "q status --bay F09".split()[0] in out


def test_bracket_codes_survive_markdown() -> None:
    """И4: коды в [скобках] переживают Markdown-рендер (не съедены ссылками)."""
    out = _render_ansi(_screen())
    assert "OPERATOR_HOLD" in out
    assert "[zone]" in out
    assert "ZONE_DENY" in out


def test_operator_stays_plain_no_bar() -> None:
    """Асимметрия голосов: оператор — компактный «я ▸», без Markdown/┃-бара."""
    out = _render_ansi(_screen())
    assert "я ▸ 06:00" in out
    assert "QIKI ▸ 06:00:45Z INFO" in out


def test_rendered_text_stays_plain_and_wrapped() -> None:
    """rendered_text (снапшот) — plain: полный текст, строки в пределах ширины."""
    rendered = _screen().rendered_text()
    assert "mount module" in rendered
    assert "OPERATOR_HOLD" in rendered
    assert all(len(ln) <= 120 for ln in rendered.splitlines())
