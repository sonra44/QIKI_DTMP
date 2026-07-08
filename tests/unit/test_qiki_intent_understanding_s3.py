"""Срез 3 (понимание): живые формулировки attach-намерения — не магические фразы.

Оператор говорит как человек («пристыкуй датчик к F09», «приладь антенну»),
а не заклинаниями («установи модуль»). Расширяется ДЕТЕРМИНИРОВАННЫЙ словарь
policy (глаголы + синонимы объектов) — не LLM (CaMeL цел: Mercury не чеканит
команды). Неоднозначность класса — честный переспрос (MODULE_AMBIGUOUS),
не угадывание.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from qiki.services.q_core_agent.qiki_orion_intents_service import (
    _is_attach_module_command,
    _parse_attach_request_text,
)


@dataclass(frozen=True)
class _Entry:
    module_id: str
    module_class: str
    display_name_ru: str = ""
    provided_capabilities: tuple[str, ...] = field(default_factory=tuple)


CATALOG = (
    _Entry("test_sensor_module_001", "sensor"),
    _Entry("comm_antenna_module_001", "antenna"),
    _Entry("science_probe_module_001", "science"),
    _Entry("rcs_cluster_module_001", "rcs-cluster"),
    _Entry("salvage_sensor_damaged_001", "sensor"),
)


def test_live_verbs_match_attach_intent() -> None:
    """Живые глаголы установки понимаются, не только «установи»."""
    for phrase in (
        "пристыкуй датчик к F09",
        "приладь антенну на F03",
        "воткни сенсор в F06",
        "закрепи научный зонд на F02",
        "подключи антенну к F03",
        "прикрути rcs на F05",
        "навесь сенсор на F01",
    ):
        assert _is_attach_module_command(phrase), f"не понята живая фраза: {phrase!r}"


def test_datchik_is_sensor_synonym_with_honest_ambiguity() -> None:
    """«датчик» = класс sensor; два сенсора в каталоге → честный переспрос."""
    assert _is_attach_module_command("пристыкуй датчик к F09")
    entry, mount, err = _parse_attach_request_text("пристыкуй датчик к F09", CATALOG)
    assert mount == "F09"
    assert entry is None and err == "MODULE_AMBIGUOUS"  # не угадываем между штатным и повреждённым


def test_live_phrase_resolves_unambiguous_class() -> None:
    """«приладь антенну на F03» → однозначный модуль + гнездо из фразы."""
    entry, mount, err = _parse_attach_request_text("приладь антенну на F03", CATALOG)
    assert err is None
    assert entry is not None and entry.module_id == "comm_antenna_module_001"
    assert mount == "F03"


def test_existing_canonical_phrases_still_match() -> None:
    """Регресс: канонические формы работают как раньше."""
    for phrase in ("установи модуль на F06", "установить сенсорный модуль", "attach sensor module", "install antenna"):
        assert _is_attach_module_command(phrase)


def test_mention_without_verb_is_not_command() -> None:
    """Негатив: упоминание объекта без глагола установки — НЕ команда (беседа)."""
    for phrase in (
        "расскажи про датчик в отсеке",
        "что умеет антенна?",
        "сенсор барахлит, посмотри телеметрию",
    ):
        assert not _is_attach_module_command(phrase), f"ложная команда: {phrase!r}"


def test_verb_without_object_is_not_command() -> None:
    """Негатив: глагол без объекта установки — НЕ команда."""
    for phrase in ("подключи связь со станцией", "закрепи успех", "воткни музыку"):
        assert not _is_attach_module_command(phrase), f"ложная команда: {phrase!r}"


def test_negation_is_not_command() -> None:
    """Находка ревью [MED]: отрицание — беседа, не команда установки."""
    for phrase in (
        "не надо подключать антенну",
        "не устанавливай сенсор",
        "нельзя воткнуть модуль сюда",
    ):
        assert not _is_attach_module_command(phrase), f"отрицание принято за команду: {phrase!r}"


def test_question_is_not_command() -> None:
    """Вопрос — беседа, не команда (кандидат на риторический вопрос запрещён)."""
    for phrase in (
        "можно ли установить сенсор?",
        "почему нельзя воткнуть модуль?",
        "установить антенну — это долго?",
    ):
        assert not _is_attach_module_command(phrase), f"вопрос принят за команду: {phrase!r}"
