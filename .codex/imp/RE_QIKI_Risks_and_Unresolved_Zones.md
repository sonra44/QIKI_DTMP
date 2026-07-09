# RE_QIKI_Risks_and_Unresolved_Zones

> REFERENCE ONLY / NOT CURRENT STATUS
>
> CURRENT TRUTH OVERRIDE:
> current project status must be read from:
> - `~/MEMORI/ACTIVE_TASKS_QIKI_DTMP.md`
> - `TASKS/TASK_20260330_qiki_freshness_threshold_ownership.md`
> - `TASK_OUT/final_stabilization_and_baseline.md`
>
> Historical package-state below may be stale. In particular, risks tied to
> unresolved `signature_changed live path` or an active `proof-stage` slice are
> historical package risks unless they are re-confirmed by newer board/task/runtime evidence.

## 1. Назначение

Этот документ фиксирует не общую тревожность вокруг проекта, а **конкретные активные риски и незакрытые зоны**, которые прямо влияют:

- на честность текущей документации;
- на корректность канонизации;
- на перевод активного slice из `proof-stage` в более сильный статус;
- на возможность считать текущий цикл документации действительно закрытым.

Его задача — удерживать пакет от двух ошибок:

1. преждевременной завершённости;
2. преждевременной канонизации спорных ownership / runtime / legacy-зон.

---

## 2. Текущая рабочая формула

На текущем этапе корректная формула состояния такая:

```text
project_understanding = strong
documentation_structure = assembled
runtime_proof = partial
closure = blocked by unresolved runtime and governance-grade ambiguity zones
```

Это означает:

- пакет уже силён по структуре;
- архитектурный spine уже достаточно хорошо восстановлен;
- но есть несколько зон, которые нельзя маскировать под «почти закрытые».

---

## 3. Принцип включения риска в этот документ

Сюда попадает только то, что удовлетворяет хотя бы одному из условий:

- влияет на достоверность текущего пакета;
- влияет на статус active slice;
- создаёт риск ложной канонизации;
- может привести к расхождению между кодом, runtime-логикой и документами;
- мешает перевести пакет из `assembled` в `closed`.

---

## 4. Активный реестр рисков и незакрытых зон

## 4.1. Runtime-proof gap

### Риск
Текущий active slice остаётся в `proof-stage`, а не в `closed`.

### Суть
Главный незакрытый runtime-вопрос текущего этапа — `signature_changed live path`.

### Почему это важно
Пока этот путь не подтверждён на живом контуре, нельзя честно утверждать, что:

- критический рабочий path подтверждён;
- active slice закрыт;
- runtime evidence слой исчерпывающий;
- документационный цикл этого этапа завершён.

### Статус
`critical unresolved`

---

## 4.2. Compose / environment state gap

### Риск
Документация может продолжать уточняться поверх среды, чьё фактическое runtime-состояние не перепроверено.

### Суть
Перед любым сильным утверждением о live proof необходимо повторно проверить:

- что stack поднимается на ожидаемом контуре;
- какие контейнеры реально участвуют;
- какой compose-режим считается активным;
- не строятся ли выводы поверх частично поднятой или устаревшей среды.

### Почему это важно
Без этого можно ошибиться не в тексте, а в самой основе проверки: проверять не тот контур, не тот режим или неполную сборку.

### Статус
`open operational dependency`

---

## 4.3. Duplicate operator entrypoints

### Риск
Множественные `main_*.py` и альтернативные operator paths размывают канон операторской среды.

### Суть
Даже если ORION V уже зафиксирован как primary operator surface, в проекте остаются альтернативные entrypoints, которые создают ambiguity:

- что считать главным запуском;
- что считать переходным слоем;
- что legacy;
- что всё ещё может использоваться на практике.

### Почему это важно
Это влияет не только на UI-описание, но и на то, какие runtime-paths вообще считаются каноническими.

### Статус
`duplicate-or-transition`

---

## 4.4. Intents ownership ambiguity

### Риск
Ответственность за intents может оставаться не до конца разведённой между несколькими слоями.

### Суть
По уже собранному пакету и по кодовой картине видно, что смысловой/реактивный/decision-контур проходит как минимум через:

- `faststream_bridge`;
- `q_core_agent`;
- тонкий edge-слой `qiki_chat`.

### Почему это важно
Пока ownership по intents не зафиксирован окончательно, сохраняется риск:

- дублирования ответственности;
- смешения policy, response и decision;
- противоречия между canon-map, architecture-note и runtime-поведением.

### Статус
`needs ownership clarification`

---

## 4.5. Spec-stack ambiguity

### Риск
Spec-слой может быть описан слишком упрощённо, как будто у него один owner и один файл истины.

### Суть
На текущем этапе корректнее говорить о **spec stack**, а не об одном «корневом spec-файле». Важен не красивый тезис, а честная декомпозиция: source spec, generated config, loader/fallback логика, runtime-consumed config.

### Почему это важно
Если эту зону канонизировать слишком рано, документация зафиксирует не реальную кодовую дисциплину, а упрощённую версию истины.

### Статус
`partially clarified but not fully closed`

---

## 4.6. Audit ownership overstatement risk

### Риск
Audit-слой может быть интерпретирован сильнее, чем это реально подтверждено.

### Суть
`registrar` уже достаточно уверенно читается как audit / black-box layer, но это ещё не означает, что его можно автоматически трактовать как единственный reconstructable truth owner.

### Почему это важно
Неверная трактовка audit-слоя искажает архитектурные роли и может дать ложное ощущение полной реконструируемости событийного прошлого.

### Статус
`managed but still sensitive`

---

## 4.7. Suspected legacy: `ship_*` family

### Риск
Наследный слой может быть либо преждевременно выкинут как мусор, либо преждевременно оставлен как равноправная часть канона.

### Суть
`ship_*` family выглядит как подозрительная legacy-зона старой онтологии проекта, но для окончательного вывода всё ещё нужен аккуратный reference/live-path check.

### Почему это важно
Ошибка здесь двусторонняя:

- слишком раннее удаление искажет историю и остаточную архитектуру;
- слишком ранняя канонизация загрязнит текущую карту проекта.

### Статус
`suspected-legacy`

---

## 4.8. Suspected legacy: `mission_control*` family

### Риск
Исторические или экспериментальные поверхности могут размывать понимание текущего продуктового ядра.

### Суть
`mission_control*` family пока разумнее трактовать как historical/experimental contour, а не как центр текущего продукта.

### Почему это важно
Без жёсткой маркировки эта зона создаёт ложное ощущение множественных равноправных интерфейсов проекта.

### Статус
`suspected-legacy`

---

## 4.9. Documentation closure illusion

### Риск
Из-за объёма и структуры пакета возникает соблазн считать цикл уже закрытым.

### Суть
Пакет действительно стал сильным по составу и внутренней связности, но это ещё не равно финальной closure-фазе, пока:

- не закрыт runtime-proof gap;
- не снят главный live blocker;
- не синхронизированы статусы между maturity / runtime / risk-слоем;
- не проведена финальная closure-сверка core-пакета.

### Почему это важно
Это главный governance-риск текущего этапа.

### Статус
`active governance risk`

---

## 4.10. Over-canonization risk

### Риск
Сильные архитектурные и продуктовые формулы могут начать использоваться там, где ещё допустим только уровень `partial`, `proof-stage` или `unresolved`.

### Суть
У проекта уже есть сильный canonical spine, но не все периферийные зоны прошли одинаковый уровень проверки.

### Почему это важно
Если слишком рано назвать всё каноном, пакет перестанет быть инструментом правды и станет инструментом самоуспокоения.

### Статус
`high governance risk`

---

## 4.11. Code-to-document drift risk

### Риск
Чем больше становится пакет, тем выше риск, что часть документов начнёт отставать от фактической кодовой картины или обновлённых статусов.

### Суть
Критические линии расхождения обычно возникают между:

- maturity matrix и runtime evidence;
- canon map и risk file;
- product truth и фактическим live status;
- architecture note и реальной spec/runtime decomposition.

### Почему это важно
Это риск потери внутренней согласованности пакета даже без изменения самой кодовой базы.

### Статус
`managed but persistent`

---

## 5. Рабочая классификация рисков

```text
critical:
  - signature_changed live path unresolved
  - runtime / compose state not revalidated

high:
  - duplicate operator entrypoints
  - intents ownership ambiguity
  - documentation closure illusion
  - over-canonization risk

medium:
  - spec-stack ambiguity
  - audit ownership overstatement risk
  - suspected legacy zones
  - code-to-document drift
```

---

## 6. Что должно снизить активность рисков

Чтобы эти риски перестали быть активными или были понижены по уровню, следующий порядок остаётся самым сильным:

1. Перепроверить runtime / compose state.
2. Подтвердить или честно переоценить `signature_changed live path`.
3. Синхронизировать `Maturity Matrix`, `Runtime Evidence Notes` и этот risk-document.
4. Уточнить ownership по intents.
5. Довести spec-stack формулировку до устойчивого и непротиворечивого вида.
6. Проверить suspected legacy зоны перед любыми жёсткими выводами о выводе из канона.
7. Провести финальную closure-сверку core-пакета.

---

## 7. Что нельзя делать до снижения этих рисков

До закрытия критических и high-зон нельзя:

- объявлять active slice завершённым;
- переводить `signature_changed live path` в confirmed без live-proof;
- объявлять package closure достигнутым;
- трактовать spec owner как полностью очищенный и однозначный;
- объявлять intents ownership окончательно закрытым;
- автоматически записывать suspected legacy в мусор или в канон.

---

## 8. Итоговая формула документа

```text
Main unresolved truth of current stage:
  project understanding is strong,
  package structure is strong,
  but closure is still blocked by runtime proof,
  ownership ambiguity,
  and several governance-grade unresolved zones.
```

---

## 9. Статус документа

**Тип:** risk-control document  
**Роль:** удерживает пакет от ложной завершённости и ложной канонизации  
**Использование:** обновляется после каждого существенного изменения статусов, после закрытия runtime blockers или после новой кодовой ревизии
