# RE_QIKI Root Index

> REFERENCE ONLY / NOT ACTIVE CANON
>
> Этот пакет полезен как governance/analysis layer, но не определяет текущий active slice.
> Для текущего продуктового статуса приоритет имеют:
> - `~/MEMORI/ACTIVE_TASKS_QIKI_DTMP.md`
> - `TASKS/TASK_20260313_g3_qiki_second_observation_result_signature_changed.md`
> - `TASK_OUT/final_stabilization_and_baseline.md`
>
> Историческая оговорка:
> часть формулировок ниже была собрана до live-closure `signature_changed` и должна читаться как pre-closure package context, а не как текущая truth-state сводка.

## 1. Назначение

Этот документ является **корневой точкой входа** в пересобранный пакет QIKI.

Его роль — не пересказывать весь проект и не подменять собой кодовую верификацию, а задать:

- правильный вход в пакет;
- порядок чтения;
- уровни доверия к разным слоям;
- правило разрешения конфликтов между кодом, evidence-слоем, каноном и архивом.

ROOT не должен:

- доказывать архитектуру вместо `RE_QIKI_Architecture_Verification_Note.md`;
- определять зрелость вместо `RE_QIKI_Maturity_Matrix.md`;
- объявлять closure достигнутым вместо `RE_QIKI_Documentation_Completion_Criteria.md`;
- подменять кодовую истину управленческой волей.

---

## 2. Текущий статус пакета

На момент сборки пакета корректная формула была такой:

```text
package_structure = assembled
package_normalization = largely complete
package_closure = not yet
main_blocker = signature_changed live path
active_slice = G3-QIKI-009 (proof-stage)
```

Это означает для исторического package-state:

- пакет уже собран как система;
- его основной мета- и branch-слой пересобран;
- evidence- и risk-слой встроены в общий контур;
- но финальная closure-фаза пакета на момент сборки ещё не была достигнута.

Текущий active-project baseline уже другой:

```text
signature_changed = closed_with_evidence
current_mode = hardening / regression / cleanup
current_slice = post-signature_changed stabilization baseline
```

---

## 3. Что именно делает ROOT

ROOT вводит не технический канон сам по себе, а **управляемую рамку чтения и интерпретации**.

Он отвечает на 5 вопросов:

1. С чего входить в пакет.
2. Какие документы являются опорными.
3. Какие документы выражают кодовую истину, а какие — управленческую или смысловую нормализацию.
4. Какой слой имеет приоритет при конфликте.
5. Когда можно и когда нельзя говорить о завершённости.

---

## 4. Базовые правила доверия

### 4.1. Код и подтверждённый runtime выше документа

Если документ конфликтует с кодом или подтверждённым runtime-наблюдением, приоритет имеет код и evidence.

### 4.2. Не все документы одного типа

В пакете есть как минимум 4 разных природы документов:

- **code-truth**;
- **meta/status/governance**;
- **canon/product/operator interpretation**;
- **evidence/risk**.

Следовательно, одинаковый вес всем текстам придавать нельзя.

### 4.3. Проектное решение не равно установленному факту

Если формулировка относится к желаемому устройству проекта, к нормализации языка или к управлению пакетом, она должна читаться как **решение**, а не как прямой факт репозитория.

### 4.4. Архив и support-слой полезны, но не первичны

Support-материалы и архив нужны для salvage-review, происхождения выводов и ретроспективной сверки, но не должны автоматически определять активный канон.

---

## 5. Состав корневого маршрута

### Layer A — Entry and Control

1. `RE_00_QIKI_Root_Index.md`
2. `RE_QIKI_Document_Pack_Index.md`
3. `RE_QIKI_Project_Analysis_Position.md`
4. `RE_QIKI_Analytical_Path_Map.md`
5. `RE_QIKI_Maturity_Matrix.md`

Этот слой нужен, чтобы понять:

- где находится пакет сейчас;
- что уже пересобрано;
- где незакрытые зоны;
- что считать сильным утверждением, а что — пока нет.

### Layer B — Core Verification and Canon

6. `RE_QIKI_Architecture_Verification_Note.md`
7. `RE_QIKI_Canon_Map_and_ADR.md`
8. `RE_QIKI_Product_Truth_and_Gate_Plan.md`

Этот слой нужен, чтобы собрать:

- архитектурный spine;
- границы канона;
- продуктовую рамку;
- правила, где документ говорит о факте, а где — о проектном направлении.

### Layer C — Evidence and Closure

9. `RE_QIKI_Runtime_Evidence_Notes.md`
10. `RE_QIKI_Risks_and_Unresolved_Zones.md`
11. `RE_QIKI_Documentation_Completion_Criteria.md`

Этот слой нужен, чтобы не симулировать завершённость:

- что реально подтверждено;
- что остаётся unresolved;
- что именно мешает closure;
- по каким критериям пакет вообще может перейти из `assembled` в `closed`.

### Layer D — Branch Layer

12. `RE_BR_01_Code_Truth_Passport.md`
13. `RE_BR_02_QIKI_Canonization_Passport.md`
14. `RE_BR_03_Orion_and_Operator_Surface_Passport.md`
15. `RE_BR_04_Product_Frame_Passport.md`
16. `RE_BR_05_Context_Transfer_and_Replication_Passport.md`

Этот слой нужен для устойчивого разбиения логики пакета на ветки:

- кодовая истина;
- канонизация QIKI;
- операторская поверхность;
- продуктовая рамка;
- правила переноса и обновления контекста.

---

## 6. Рекомендуемый порядок чтения

### Первый проход

1. `RE_00_QIKI_Root_Index.md`
2. `RE_QIKI_Document_Pack_Index.md`
3. `RE_BR_01_Code_Truth_Passport.md`
4. `RE_QIKI_Project_Analysis_Position.md`
5. `RE_QIKI_Maturity_Matrix.md`

Цель первого прохода:

- отделить подтверждаемое от интерпретации;
- понять текущее состояние пакета;
- зафиксировать active blocker и текущую степень зрелости.

### Второй проход

6. `RE_QIKI_Analytical_Path_Map.md`
7. `RE_QIKI_Architecture_Verification_Note.md`
8. `RE_QIKI_Canon_Map_and_ADR.md`
9. `RE_BR_02_QIKI_Canonization_Passport.md`
10. `RE_BR_03_Orion_and_Operator_Surface_Passport.md`
11. `RE_BR_04_Product_Frame_Passport.md`

Цель второго прохода:

- понять, как проект был восстановлен;
- собрать архитектурную и смысловую рамку;
- увидеть, где ещё действуют downgrade-ограничения.

### Третий проход

12. `RE_QIKI_Product_Truth_and_Gate_Plan.md`
13. `RE_QIKI_Runtime_Evidence_Notes.md`
14. `RE_QIKI_Risks_and_Unresolved_Zones.md`
15. `RE_QIKI_Documentation_Completion_Criteria.md`
16. `RE_BR_05_Context_Transfer_and_Replication_Passport.md`

Цель третьего прохода:

- увидеть продуктовый контур;
- проверить evidence;
- увидеть реальные unresolved-зоны;
- понять, почему closure ещё не зафиксирован.

---

## 7. Уровни доверия

### Level A — Operational Canon

Сюда входят пересобранные `RE_`-документы ядра пакета.

Но даже внутри этого уровня есть различие:

- `RE_BR_01_Code_Truth_Passport.md` и `RE_QIKI_Architecture_Verification_Note.md` ближе всего к кодовой верификации;
- `RE_QIKI_Project_Analysis_Position.md`, `RE_QIKI_Maturity_Matrix.md`, `RE_QIKI_Documentation_Completion_Criteria.md` управляют статусом;
- `RE_QIKI_Canon_Map_and_ADR.md`, `RE_BR_02...`, `RE_BR_03...`, `RE_BR_04...` содержат нормализованный канон, но не должны отменять кодовую фактичность;
- `RE_BR_05...` и ROOT — governance-слой.

### Level B — Support / Working

Сюда входят:

- промежуточные аналитические фиксации;
- deep-research слои;
- технические разборы;
- рабочие карты и черновики.

Их можно использовать для уточнения, но не как первичную основу сильного вывода.

### Level C — Archive / Legacy

Сюда относятся:

- superseded-версии;
- старые root/branch-версии;
- snapshot/handover/history материалы;
- legacy-centred формулировки.

Они нужны для:

- проверки происхождения решений;
- сравнения старой и новой трактовки;
- salvage-review.

Но не должны быть первым входом в активный пакет.

---

## 8. Правило разрешения конфликта

Если возникает конфликт, маршрут проверки такой:

1. код и подтверждённый runtime;
2. `RE_QIKI_Runtime_Evidence_Notes.md`;
3. `RE_QIKI_Risks_and_Unresolved_Zones.md`;
4. `RE_BR_01_Code_Truth_Passport.md` и `RE_QIKI_Architecture_Verification_Note.md`;
5. maturity / position / completion criteria;
6. canon/product/operator docs;
7. support и archive.

Это правило нужно затем, чтобы:

- не поднимать риторику выше evidence;
- не превращать незакрытую зону в канон;
- не маскировать uncertainty красивой формулировкой.

---

## 9. Что уже считается достигнутым

На текущем этапе уже можно считать достигнутым следующее:

- пакет собран как единая система;
- мета-документы пересобраны и синхронизированы на базовом уровне;
- core architecture / canon / product docs пересобраны;
- evidence и risk слой вынесены отдельно;
- BR-ветки пересобраны в согласованной логике;
- основные завышения по spec-stack, intent ownership, BIOS, operator surface и product identity ослаблены до более честной формулы.

---

## 10. Что ещё не даёт объявить closure

Closure пока нельзя объявлять по следующим причинам:

1. `signature_changed live path` остаётся главным blocker.
2. `G3-QIKI-009` остаётся в `proof-stage`.
3. Runtime-proof остаётся частичным.
4. Пакет хоть и нормализован, но ещё требует финальной сквозной сверки как единой системы.

Следовательно, текущая корректная формула такая:

```text
assembled = yes
normalized = mostly yes
verified = partial
closed = no
```

---

## 11. Практическое правило использования ROOT

Если нужно быстро понять, как входить в пакет, ROOT отвечает так:

- сначала понять статус и правила;
- затем отделить code-truth от канона;
- потом читать architecture/canon/product;
- после этого переходить к evidence/risk;
- и только затем делать выводы о степени завершённости.

ROOT не нужен для того, чтобы спорить с кодом.  
Он нужен для того, чтобы **не дать пакету снова распасться на случайные точки входа и на неравные по статусу тексты**.

---

## 12. Итог

`RE_00_QIKI_Root_Index.md` фиксирует вход в уже пересобранный пакет QIKI как в управляемую систему.

Он не утверждает, что проект полностью закрыт.  
Он утверждает более узкую и честную вещь:

**пакет уже собран, в основном нормализован и пригоден для системного чтения, но ещё не имеет права на финальную closure-формулу без добивки runtime-proof и контрольной сквозной сверки.**
