# QIKI Body v0.2.2 — JSON Companion Package

Generated: 2026-06-20T21:06:42+00:00

## Что это

Это JSON companion-пакет для `QIKI Body v0.2.2 Documentation Package`.

Он нужен для машинного чтения: агентом, скриптом, проверкой, индексатором, репозиторным помощником или будущим toolchain.

## Что это не

Это не замена Markdown-пакета.

Это не runtime implementation.

Это не telemetry schema.

Это не proto / NATS / gRPC contract.

Это не ORION UI schema.

Это не доказательство `implemented`.

Это не доказательство `verified`.

## Главная логика

Markdown-файлы остаются primary source.

JSON-файлы являются companion index.

`10_READER_MANUAL.md` остаётся derived reader manual.

Если JSON конфликтует с Markdown, приоритет у Markdown.

## Что к чему

- `00_package_manifest.json` — общая карточка JSON-пакета.
- `01_document_catalog.json` — что делает каждый Markdown-документ.
- `02_status_legend.json` — статусы `canon`, `target-only`, `template-only`, `rules-only`, `calculation-required`, `implemented`, `verified`.
- `03_source_priority.json` — порядок приоритета source files.
- `04_requirements_catalog.json` — namespaces требований и извлечённые REQ-ID.
- `05_viewpoints_catalog.json` — архитектурные viewpoints.
- `06_calculation_catalog.json` — расчётные таблицы и шаблоны.
- `07_interface_catalog.json` — интерфейсы IF-*.
- `08_adr_index.json` — индекс ADR-0001–ADR-0015.
- `09_repository_insertion.json` — правила вставки в репозиторий.
- `10_acceptance_summary.json` — результат приёмки пакета.
- `11_traceability_map.json` — связь тем с source files, requirements, viewpoints, interfaces, ADR.
- `12_forbidden_wording.json` — опасные формулировки и корректные замены.
- `13_source_file_inventory.json` — inventory исходных Markdown-файлов с SHA-256.
- `qiki_body_v0_2_2_companion_aggregate.json` — всё основное в одном JSON.

## Рекомендуемый путь в репозитории

`docs/design/hardware_and_physics/qiki_body_v0_2_2/_json/`

## Жёсткое правило

Нельзя делать вывод `implemented` из JSON.

Нельзя делать вывод `verified` из JSON.

Нельзя использовать JSON как замену runtime evidence.

JSON нужен для навигации, трассировки и машинного чтения документационного пакета.
