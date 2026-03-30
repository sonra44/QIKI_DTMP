---
id: BR-03
status: reconstructed
owner: Макс
type: context-branch
priority: critical
canonical-layer: operator-environment
source-basis: code-first, package-synchronized
related:
  - RE_BR_01_Code_Truth_Passport
  - RE_BR_02_QIKI_Canonization_Passport
  - RE_QIKI_Architecture_Verification_Note
  - RE_QIKI_Canon_Map_and_ADR
  - RE_QIKI_Maturity_Matrix
  - RE_QIKI_Risks_and_Unresolved_Zones
---

# RE_BR_03 — Orion and Operator Surface Passport

## Карточка

**Роль:** зафиксировать операторский слой проекта без смешения трёх разных вещей: наблюдаемого кода, канонического направления и ещё не закрытых переходных зон.

**Главный вывод:** ORION уже подтверждается как реальный operator layer и как primary operator surface проекта, но этот слой ещё нельзя объявлять полностью консолидированным и окончательно очищенным. В репозитории сохраняются множественные operator entrypoints и следы переходного состояния.

**Когда читать:** после BR-01 и BR-02.

**Когда не читать:** если нужна только локальная UI-справка без связи с runtime, incidents, procedures и audit.

**Статус:** canonical-direction with transition constraints.

**Критическое правило:** ORION допустимо трактовать как основной операторский контур проекта, но нельзя выдавать это за доказанный факт полной консолидации всего operator stack.

---

## 1. Назначение

Этот паспорт нужен не для описания интерфейса как эстетического слоя, а для фиксации operator environment как части причинной архитектуры проекта.

Документ должен удерживать различие между:

1. **подтверждённым кодом operator layer;**
2. **каноническим направлением в сторону ORION как primary surface;**
3. **незакрытым переходным состоянием operator stack.**

---

## 2. Что подтверждено достаточно надёжно

### F1. ORION — это не декоративная оболочка

ORION подтверждается кодом как реальный операторский контур проекта, а не как внешний UI-слой «поверх симуляции». Это уже было зафиксировано и в предыдущем BR-03, и в техническом разборе: операторская подсистема включает не только отображение состояния, но и incidents, procedures, replay/record, acknowledgements и audit-публикацию.

### F2. Operator layer субъектен

Операторская среда не только читает runtime truth, но и производит операционные акты. Это следует из наличия procedural / incident контуров, action-flow для подтверждения и очистки инцидентов, а также audit-событий, связанных с операторскими действиями.

### F3. ORION работает как слой интерпретации

BR-03 должен удерживать разницу между raw-state и operator-view. ORION не является физическим владельцем истины, но он консолидирует, объясняет и делает систему операционно значимой. Это согласуется с canon rule о том, что UI имеет право агрегировать, визуализировать и пояснять, но не подменять source-of-truth.

### F4. ORION уже является strongest candidate на primary operator surface

Старый BR-03 уже честно формулировал, что Orion V — наиболее близкий кандидат на канонический операторский фронт. Эта мысль сохраняется и после пересборки, но без завышения зрелости.

---

## 3. Что нельзя утверждать как полностью доказанный факт

### N1. Нельзя говорить, что весь operator layer уже консолидирован в один окончательный вход

Это запрещено, потому что в проекте остаются множественные `main_*.py` и альтернативные пути запуска. Риск duplicate operator entrypoints уже вынесен в отдельный unresolved/risk слой.

### N2. Нельзя говорить, что legacy-следы в operator layer уже очищены

Следы переходного и старого vocabulary всё ещё сохраняются. Их можно считать ограничением и фактором дрейфа, но нельзя делать вид, что они исчезли.

### N3. Нельзя отрывать ORION от runtime / incidents / procedures / audit

Если читать ORION просто как интерфейс, теряется сама операторская природа слоя. Для текущего проекта это архитектурная ошибка.

---

## 4. Корректная формула ветки

На текущем этапе наиболее точная формула такая:

```text
ORION / operator surface
  = real operator environment
  + incident / procedure / replay / audit-aware layer
  + strongest canonical candidate for primary surface
  - unresolved entrypoint duplication
  - residual transition / legacy contamination
```

---

## 5. Границы ветки

### Что входит

- ORION как primary operator direction;
- operator_console как кодовая база operator layer;
- incidents, procedures, acknowledgements, replay/record, audit-related actions;
- различие между raw-state и operator-view;
- проблема duplicate entrypoints и незавершённой консолидации operator stack.

### Что не входит

- утверждение о полной UX-завершённости;
- превращение ORION в owner physical truth;
- объявление всего operator stack уже очищенным;
- стирание legacy-слоя без отдельной проверки.

---

## 6. Связь с общим каноном

BR-03 должен читаться в составе более широкой цепочки:

```text
spec stack
  -> physical runtime truth
  -> transport/contracts
  -> meaning/policy
  -> decision/arbitration
  -> operator surface
  -> audit trail
```

В этой цепочке ORION — не центр всей системы и не владелец физической истины, а канонический операторский полюс, через который truthful runtime становится наблюдаемым, интерпретируемым и управляемым.

---

## 7. Риски и ограничения

### R1. Duplicate operator entrypoints

Пока сохраняются несколько путей запуска, канон operator layer остаётся частично размытым.

### R2. Over-canonization risk

Главный риск документа — принять направление канонизации ORION за уже завершённое состояние репозитория.

### R3. UI-overreach risk

Если operator surface начнёт читаться как самостоятельный truth-owner, документ войдёт в противоречие с architecture/canon rules.

---

## 8. Рабочий статус ветки

Текущий статус BR-03 корректно описывать так:

- **operator layer = verified as real**
- **ORION = primary canonical direction**
- **operator consolidation = not yet complete**
- **entrypoint unification = unresolved**

---

## 9. Практический вывод

BR-03 после пересборки должен делать одну вещь очень чётко: удерживать ORION как реальную и сильную операторскую среду, но не подменять этим фактом незавершённость консолидации operator stack.

Это значит:

- ORION уже нельзя понижать до декоративного UI;
- но ORION ещё нельзя описывать как окончательно единственный и полностью очищенный вход проекта.

---

## 10. Итоговая формула

**ORION в текущем каноне QIKI — это уже реальная операторская среда и основной кандидат на primary operator surface, но ещё не полностью замкнутый и окончательно унифицированный operator stack.**
