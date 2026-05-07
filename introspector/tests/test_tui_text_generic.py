from __future__ import annotations

from project_introspector.tui_text import localize_semantic_text


def test_generic_semantic_text_localizes_known_generic_codes_in_russian() -> None:
    assert localize_semantic_text(
        "ru",
        "Process module-specific inputs into structured results.",
        code="resp.generic.process_inputs",
        kind="responsibility",
    ) == "Обрабатывает входы, специфичные для модуля, в структурированные результаты."
    assert localize_semantic_text(
        "ru",
        "Run the main workflow exposed by this module.",
        code="resp.generic.run_main_workflow",
        kind="responsibility",
    ) == "Запускает основной workflow, который экспортирует этот модуль."


def test_generic_semantic_text_falls_back_to_original_text_for_unknown_codes() -> None:
    assert localize_semantic_text(
        "ru",
        "Unknown text",
        code="resp.unknown.code",
        kind="responsibility",
    ) == "Unknown text"
