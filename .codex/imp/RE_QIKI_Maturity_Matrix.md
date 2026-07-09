# QIKI Maturity Matrix

> REFERENCE ONLY / NOT CURRENT STATUS
>
> CURRENT TRUTH OVERRIDE:
> current project status must be read from:
> - `~/MEMORI/ACTIVE_TASKS_QIKI_DTMP.md`
> - `TASKS/TASK_20260330_qiki_freshness_threshold_ownership.md`
> - `TASK_OUT/final_stabilization_and_baseline.md`
>
> Historical package-state below may be stale. In particular, matrix rows that
> mention `G3-QIKI-009`, `proof-stage`, or `signature_changed live path` unresolved
> are retained for archaeology and drift detection only.

## Назначение

Этот документ фиксирует текущую зрелость проекта не как общий рассказ, а как рабочую систему статусов.

Его задача — отделять:
- что уже можно считать опорным каноном;
- что подтверждено, но не является центром проекта;
- что находится в proof-stage;
- что остаётся переходной или legacy-зоной;
- что ещё нельзя закрывать без дополнительного подтверждения.

Главный принцип этого документа:
**статус не должен быть сильнее, чем доступное доказательство.**

---

## Шкала статусов

### canonical
Слой или документ входят в подтверждённый рабочий хребет проекта и используются как опора для чтения системы.

### verified-support
Слой или документ подтверждены и реально поддерживают рабочий контур, но не являются центром project truth.

### proof-stage
Срез, сценарий или решение в целом описаны и частично подтверждены, но ещё не закрыты живым proof.

### duplicate-or-transition
Слой, entrypoint или реализация дублируют функции, создают ambiguity или сохраняются как переходный контур.

### suspected-legacy
Есть основания считать зону исторической или неканонической, но жёсткий вывод без дополнительной проверки делать рано.

### unresolved
Статус, ownership или поведение ещё нельзя считать подтверждёнными; нужен отдельный шаг проверки или фиксации.

---

## Матрица зрелости

| Entity | Type | Role | Status | Evidence Level | Main Risk | Next Step |
|---|---|---|---|---|---|---|
| spec stack: env/config selection + `bot_config.json` + `root config/*` | Spec layer | Источник machine specification и входных ограничений runtime | canonical | medium-high | ложное упрощение spec-owner до одного файла | зафиксировать полную цепочку выбора конфигурации и compose/env-влияния |
| `WorldModel` | Runtime core | Физическая эволюция состояния машины и среды | canonical | high | локальные рассогласования при расширении системы | держать как опорный physical truth layer |
| `q_sim_service` | Runtime service | Исполнение симуляции, тики, публикация telemetry / radar / events | canonical | high | расхождение между контрактами и реальным runtime behavior | повторно проверить active runtime path |
| shared models + CloudEvents + NATS subject model | Contract layer | Канонические форматы обмена и transport surface | canonical | high | drift схем между сервисами и вспомогательными слоями | свести contract ownership в один явный раздел пакета |
| `faststream_bridge` | Meaning / transport layer | Связывает transport, policy и часть операторской/event semantics | canonical | medium-high | незаметное расширение ответственности до полного owner of intents | явно ограничить его роль и развести ownership с decision-слоем |
| `q_core_agent` | Decision layer | BIOS / FSM / proposals / arbitration / decision | canonical | medium-high | смешение decision-логики с physical truth или с полным intents ownership | оставить canonical decision layer, но не объявлять owner физической истины |
| intents handling ownership (`faststream_bridge` / `q_core_agent` / `qiki_chat` / compose mode) | Responsibility boundary | Граница ответственности за intents, responses и decision handoff | unresolved | medium | дублирование логики и ложная канонизация одного слоя без проверки compose-режима | зафиксировать выбранный canonical path и отдельно отметить альтернативы |
| `ORION V` | Operator surface | Primary operator surface проекта | canonical | high | расползание операторского канона по параллельным entrypoints | удерживать как primary operator surface во всех core-docs |
| `registrar` | Audit layer | Audit/history trail, black-box след событий | verified-support | medium | завышение до source of world truth | оставлять audit-layer, а не event-sourced authority |
| `q_bios_service` | Support/runtime service | BIOS-related HTTP/publish слой, реально присутствующий в compose-стеках | verified-support | medium | выпадение из архитектурной картины при чтении только core spine | зафиксировать его реальную роль в runtime stack |
| `shell_os` | Secondary surface | Вторичная интерфейсная поверхность | verified-support | medium | ложное повышение до главной UI-ветки | держать как secondary surface до отдельной ревизии |
| `qiki_chat` | Edge layer | Тонкий intent/response edge-слой | verified-support | medium | переоценка как центра gameplay loop или полного intent-owner | описывать как edge layer с ограниченной ролью |
| `operator_console/main_*.py` family | Entrypoints | Исторические и переходные точки запуска operator console | duplicate-or-transition | medium-high | drift launch canon и ambiguity по главному запуску | провести entrypoint review и выбрать canonical launch path |
| `ship_*` family | Legacy candidate | Остаточный слой старой онтологии проекта | suspected-legacy | low-medium | преждевременное удаление без reference-check | провести file-to-role и reference-check |
| `mission_control*` family | Legacy candidate | Историческая/экспериментальная ветка управления | suspected-legacy | low-medium | смешение с текущим операторским каноном | вынести в отдельный legacy review |
| `G3-QIKI-009` | Active slice | Текущий product-critical рабочий срез | proof-stage | medium-high | объявление slice закрытым без live proof | закрыть runtime proof и только потом менять статус |
| `signature_changed live path` | Runtime proof item | Ключевой незакрытый доказательный элемент текущего среза | unresolved | medium | ложная фиксация готовности active slice | проверить на живом контуре и отдельно зафиксировать наблюдение |
| Docker / compose operational state | Environment | Обязательная среда для продолжения proof-stage | unresolved | medium | аналитика поверх неактуального или неполного контура | поднять stack, проверить health, контейнеры и логи |
| `QIKI_Project_Analysis_Position.md` | Meta-doc | Фиксация текущей точки проекта | verified-support | high | устаревание после изменения runtime-status | обновлять после каждого значимого статуса active slice |
| `QIKI_Analytical_Path_Map.md` | Meta-doc | Карта пройденного пути и оставшегося маршрута | verified-support | high | превращение в абстрактный план без актуальных статусов | синхронизировать с matrix, evidence и completion criteria |
| `QIKI_Document_Pack_Index.md` | Meta-doc | Реестр пакета и порядок чтения | verified-support | high | расхождение состава пакета с реальным набором файлов | обновлять при каждом изменении состава пакета |
| `QIKI_Runtime_Evidence_Notes.md` | Evidence-control doc | Граница между уже доказанным и ещё не доказанным | verified-support | high | фиксация сильных выводов без нового runtime evidence | обновлять только после реальных проверок |
| `QIKI_Risks_and_Unresolved_Zones.md` | Risk-control doc | Явная фиксация блокеров, ambiguity и governance-рисков | verified-support | high | потеря честности пакета при недообновлении риск-слоя | обновлять после каждого значимого изменения статусов |
| `QIKI_Architecture_Verification_Note.md` | Core doc | Главный as-built архитектурный документ | canonical | high | преждевременная финализация спорных зон | пересобрать с учётом spec-stack, BIOS и ownership ambiguity |
| `QIKI_Canon_Map_and_ADR.md` | Core doc | Канонический срез решений и ownership rules | canonical | medium-high | фиксация ADR сильнее, чем текущий уровень runtime proof | перепроверить ADR-формулировки после закрытия active slice |
| `QIKI_Product_Truth_and_Gate_Plan.md` | Core doc | Продуктовый канон и логика G1/G2/G3 | canonical | medium-high | расхождение product-gates с реальным runtime status | связать gate logic с evidence notes |
| `QIKI_Documentation_Completion_Criteria.md` | Control doc | Правило честного завершения документационного цикла | verified-support | high | объявление closure до выполнения criteria | синхронизировать с актуальными именами и статусами |
| `QIKI_Methodology_and_External_Findings.md` | Method doc | Методическая база architecture recovery и documentation logic | verified-support | high | подмена проектных фактов методологией | использовать как support-layer, а не как primary truth |

---

## Точка проекта по матрице

Текущая позиция по системе статусов такая:

- архитектурный spine восстановлен на рабочем уровне;
- product/operator contour в целом понятен;
- пакет документов собран как система;
- active slice остаётся в `proof-stage`;
- главный blocker — `signature_changed live path`;
- дополнительный operational blocker — runtime / compose state ещё требует подтверждения на правильном контуре;
- ownership по intents нельзя считать окончательно закрытым.

Итоговая формула состояния:

```text
package structure = assembled
architecture confidence = high
runtime proof confidence = partial
active slice = proof-stage
closure = not yet
```

---

## Ближайшая цель

Следующая цель — не создавать ещё один общий документ, а перевести несколько ключевых позиций в более сильный статус:

1. подтвердить runtime / compose state;
2. закрыть или честно переоценить `signature_changed live path`;
3. зафиксировать ownership по intents и compose-selected canonical path;
4. синхронизировать core-docs с evidence/risk-слоем;
5. только после этого решать вопрос о финальной closure-фазе.

---

## Итог

Эта матрица должна работать не как декларация завершённости, а как контрольный инструмент.

Пока активный slice не закрыт живым proof, а ownership и runtime state ещё содержат ambiguity, пакет нельзя считать финально завершённым, даже если его структура уже выглядит зрелой.
