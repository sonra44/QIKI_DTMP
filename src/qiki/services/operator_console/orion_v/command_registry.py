"""Реестр typed-команд ORION V — единый владелец командной поверхности.

Этап 8 пакета playable (§F4 04_F2_F3_F4_ZONES_SPEC, 06_COMMAND_SURFACE):
help, палитра Ctrl+P и пин-тест полноты читают ОДИН источник — этот реестр.
Реестр — проекция фактического роутера `app._route_typed_command`
(данные, не исполнение): новая команда в роутере обязана появиться здесь
(двунаправленный пин-тест), иначе она невидима для оператора.

Критерий §F4: новый оператор находит любую команду через `help` или
палитру, не читая исходников.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable


@dataclass(frozen=True, slots=True)
class CommandSpec:
    name: str  # каноничная форма, как её понимает роутер
    group: str
    summary_ru: str
    aliases: tuple[str, ...] = ()
    # palette=True → команда появляется в Ctrl+P как SystemCommand
    palette: bool = False
    # для аргументных команд: префилл поля ввода из палитры («proc run »)
    arg_hint: str | None = None
    palette_title_ru: str | None = None
    extra_probe_args: str = ""  # аргумент для поведенческой сверки реестр→роутер
    probe: bool = field(default=True)  # False — не гонять через роутер в пине


GROUP_LEVELS = "УРОВНИ"
GROUP_WORLD = "МИР"
GROUP_PROCEDURES = "ПРОЦЕДУРЫ"
GROUP_QIKI = "QIKI"
GROUP_DECISIONS = "РЕШЕНИЯ"
GROUP_FILTERS = "ФИЛЬТРЫ-СТРАНИЦЫ"
GROUP_SESSION = "СЕССИЯ"

HELP_GROUPS_ORDER: tuple[str, ...] = (
    GROUP_LEVELS,
    GROUP_WORLD,
    GROUP_PROCEDURES,
    GROUP_QIKI,
    GROUP_DECISIONS,
    GROUP_FILTERS,
    GROUP_SESSION,
)

COMMAND_REGISTRY: tuple[CommandSpec, ...] = (
    # ── УРОВНИ ───────────────────────────────────────────────────────────
    CommandSpec("f1", GROUP_LEVELS, "кокпит", palette=True, palette_title_ru="Уровень F1 · Кокпит"),
    CommandSpec("f2", GROUP_LEVELS, "системы", palette=True, palette_title_ru="Уровень F2 · Системы"),
    CommandSpec("f3", GROUP_LEVELS, "анализ", palette=True, palette_title_ru="Уровень F3 · Анализ"),
    CommandSpec("f4", GROUP_LEVELS, "консоль", palette=True, palette_title_ru="Уровень F4 · Консоль"),
    CommandSpec("f5", GROUP_LEVELS, "QIKI-диалог", palette=True, palette_title_ru="Уровень F5 · QIKI"),
    CommandSpec("f6", GROUP_LEVELS, "журнал", palette=True, palette_title_ru="Уровень F6 · Журнал"),
    CommandSpec("f7", GROUP_LEVELS, "статус", palette=True, palette_title_ru="Уровень F7 · Статус"),
    CommandSpec("f8", GROUP_LEVELS, "улики", palette=True, palette_title_ru="Уровень F8 · Улики"),
    # ── МИР ──────────────────────────────────────────────────────────────
    CommandSpec(
        "sim.start",
        GROUP_WORLD,
        "запустить мир [скорость]",
        aliases=("simulation.start", "симуляция.старт"),
        palette=True,
        palette_title_ru="Мир · sim.start",
    ),
    CommandSpec(
        "sim.pause",
        GROUP_WORLD,
        "пауза мира",
        aliases=("simulation.pause", "симуляция.пауза"),
        palette=True,
        palette_title_ru="Мир · sim.pause",
    ),
    CommandSpec(
        "sim.stop",
        GROUP_WORLD,
        "остановить мир",
        aliases=("simulation.stop", "симуляция.стоп"),
        palette=True,
        palette_title_ru="Мир · sim.stop",
    ),
    CommandSpec("пауза", GROUP_WORLD, "игровая пауза (⏸ Мир)", aliases=("pause", "старт", "start")),
    # ── ПРОЦЕДУРЫ ────────────────────────────────────────────────────────
    CommandSpec(
        "proc list", GROUP_PROCEDURES, "список процедур",
        aliases=("procedure list",), palette=True, palette_title_ru="Процедуры · список",
    ),
    CommandSpec(
        "proc run", GROUP_PROCEDURES, "запустить процедуру <имя>",
        arg_hint="proc run ", palette=True, palette_title_ru="Процедуры · запустить…",
        extra_probe_args=" x",
    ),
    CommandSpec(
        "proc status", GROUP_PROCEDURES, "статус процедуры",
        aliases=("procedure status",), palette=True, palette_title_ru="Процедуры · статус",
    ),
    # ── QIKI ─────────────────────────────────────────────────────────────
    CommandSpec(
        "q:", GROUP_QIKI, "вопрос/команда QIKI: q: <текст>",
        arg_hint="q: ", palette=True, palette_title_ru="QIKI · спросить…", probe=False,
    ),
    CommandSpec(
        "q confirm", GROUP_QIKI, "подтвердить действие QIKI",
        aliases=("q execute",), palette=True, palette_title_ru="QIKI · подтвердить действие",
    ),
    CommandSpec(
        "q cancel", GROUP_QIKI, "отменить кандидата QIKI",
        aliases=("q clear",), palette=True, palette_title_ru="QIKI · отменить кандидата",
    ),
    CommandSpec(
        "q abort", GROUP_QIKI, "прервать процедуру установки",
        palette=True, palette_title_ru="QIKI · прервать установку",
    ),
    CommandSpec("q resume", GROUP_QIKI, "продолжить установку", aliases=("q start",)),
    CommandSpec("q hold", GROUP_QIKI, "приостановить установку", aliases=("q pause",)),
    # ── РЕШЕНИЯ ──────────────────────────────────────────────────────────
    CommandSpec(
        "review confirm",
        GROUP_DECISIONS,
        "подтвердить итог наблюдения",
        aliases=("review ack", "review acknowledge"),
    ),
    CommandSpec(
        "follow-up hold",
        GROUP_DECISIONS,
        "удержание после ревью",
        aliases=("followup hold", "post-review hold", "hold for recheck"),
    ),
    CommandSpec(
        "resume observation",
        GROUP_DECISIONS,
        "возобновить наблюдение",
        aliases=("resume_observation", "observation resume"),
    ),
    # ── ФИЛЬТРЫ-СТРАНИЦЫ ─────────────────────────────────────────────────
    CommandSpec("inc next", GROUP_FILTERS, "следующий инцидент", aliases=("incident next", "next")),
    CommandSpec("inc prev", GROUP_FILTERS, "предыдущий инцидент", aliases=("incident prev", "prev")),
    CommandSpec("select", GROUP_FILTERS, "выбрать инцидент <id>", arg_hint="select ", extra_probe_args=" x"),
    CommandSpec("ack", GROUP_FILTERS, "подтвердить инцидент [id]", aliases=("acknowledge",)),
    CommandSpec("clear", GROUP_FILTERS, "снять подтверждённые", aliases=("clear acked",)),
    CommandSpec("module", GROUP_FILTERS, "фокус подсистемы <slug>", arg_hint="module ", extra_probe_args=" x"),
    CommandSpec("sev", GROUP_FILTERS, "фильтр серьёзности <...>", arg_hint="sev ", extra_probe_args=" all"),
    CommandSpec("subsys", GROUP_FILTERS, "фильтр подсистемы <...>", arg_hint="subsys ", extra_probe_args=" all"),
    CommandSpec("range", GROUP_FILTERS, "окно времени <sec|all>", arg_hint="range ", extra_probe_args=" all"),
    CommandSpec("page next", GROUP_FILTERS, "следующая страница", aliases=("next page",)),
    CommandSpec("page prev", GROUP_FILTERS, "предыдущая страница", aliases=("prev page",)),
    CommandSpec("audit", GROUP_FILTERS, "журнал <all|actions|...>", arg_hint="audit ", extra_probe_args=" all"),
    CommandSpec("replay on", GROUP_FILTERS, "анализ истории [sec]"),
    CommandSpec("replay off", GROUP_FILTERS, "выйти из анализа", aliases=("replay live",)),
    CommandSpec("replay status", GROUP_FILTERS, "статус анализа"),
    # ── СЕССИЯ ───────────────────────────────────────────────────────────
    CommandSpec(
        "help", GROUP_SESSION, "эта справка (полный список — в консоль F4)",
        aliases=("h", "?"), palette=True, palette_title_ru="Справка · все команды",
    ),
    CommandSpec("quit", GROUP_SESSION, "выход (с подтверждением)", aliases=("exit",)),
    CommandSpec("q", GROUP_SESSION, "не команда — подсказка (защита от опечатки)"),
)


def iter_help_lines() -> Iterable[str]:
    """Строки полного help — по группе на строку (≤160 симв. каждая)."""
    by_group: dict[str, list[str]] = {group: [] for group in HELP_GROUPS_ORDER}
    for spec in COMMAND_REGISTRY:
        alias_text = f" ({'/'.join(spec.aliases)})" if spec.aliases else ""
        by_group.setdefault(spec.group, []).append(f"{spec.name}{alias_text} — {spec.summary_ru}")
    for group in HELP_GROUPS_ORDER:
        entries = by_group.get(group) or []
        if not entries:
            continue
        line = f"{group}: " + " | ".join(entries)
        # группы длиннее 160 режем на продолжения с тем же префиксом
        while len(line) > 160:
            cut = line.rfind(" | ", 0, 157)
            if cut <= 0:
                break
            yield line[:cut]
            line = f"{group} (прод.): " + line[cut + 3 :]
        yield line


def iter_palette_specs() -> Iterable[CommandSpec]:
    for spec in COMMAND_REGISTRY:
        if spec.palette:
            yield spec
