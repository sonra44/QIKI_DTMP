# QIKI_DTMP — Document Pack Index rev2

> REFERENCE ONLY / NOT ACTIVE CANON
>
> Этот индекс описывает документальный пакет в состоянии его сборки.
> Если его status-блок конфликтует с текущим board/task/runtime evidence, приоритет у текущего live canon.

## Назначение

Этот индекс нужен как единая точка восстановления **всего текущего пакета документации**, а не только поднабора core-docs из одного чата.

Он должен отвечать на четыре вопроса:

1. Какие документы сейчас входят в рабочий пакет.
2. Какова роль каждого документа.
3. В каком порядке пакет читать.
4. Почему пакет ещё нельзя считать полностью закрытым.

---

## 1. Статус пакета

На момент сборки пакета честная формула состояния была такой:

```text
package_structure = assembled
package_closure   = not yet
main_blocker      = signature_changed live path
active_slice      = G3-QIKI-009 (proof-stage)
```

Это означает для historical package-state:
- состав пакета уже собран в управляемую систему;
- в пакете уже есть index, position, path map, maturity matrix, architecture note, canon map, product doc, methodology, runtime evidence и risks;
- но документационный цикл ещё не был закрыт, потому что live runtime proof по активному slice тогда оставался частичным.

Текущий active-project status нужно читать иначе:
- `signature_changed` closed with evidence
- project mode for this slice = `hardening / regression / cleanup`
- active work = post-closure stabilization baseline, а не pre-closure proof-stage

---

## 2. Различие между ROOT и этим индексом

### ROOT
`00_root_index_корневой_индекс_переноса_проекта__rev1.md`

Роль ROOT — задать **вход в набор переноса**, уровни доверия, маршрут чтения и правила работы с canon / working / archive.

### Этот документ
`QIKI_Document_Pack_Index_rev2_2026-03-22.md`

Роль этого документа — быть **реестром текущего полного пакета**, чтобы по нему можно было восстановить состав документации целиком.

Иначе говоря:
- ROOT = governance entry point;
- Pack Index = полный индекс текущего документального пакета.

---

## 3. Полный состав текущего пакета

Ниже дан именно фиксированный состав пакета из 19 документов.

### A. Входной и governance-слой

1. `RE_00_QIKI_Root_Index.md`
   - Корневая точка входа в набор переноса.
   - Разводит canon / working / archive.
   - Не подменяет кодовую верификацию.

2. `RE_QIKI_Unified_Manifest.md`
   - Манифест состава пакета.
   - Даёт границы пакета и фиксирует полный набор из 19 документов.

3. `RE_QIKI_Document_Pack_Index.md`
   - Реестр полного пакета.
   - Показывает роль каждого документа и общий порядок чтения.

4. `RE_BR_01_Code_Truth_Passport.md`
   - Главный документ кодовой верификации.
   - Отделяет факт репозитория от проектной воли.

5. `RE_BR_02_QIKI_Canonization_Passport.md`
   - Семантическая ветка канонизации QIKI.
   - Держит границу между подтверждённой системной ролью и проектным решением.

6. `RE_BR_03_Orion_and_Operator_Surface_Passport.md`
   - Ветка по ORION и операторской среде.
   - Нужна для фиксации primary operator surface без сокрытия duplicate entrypoints.

7. `RE_BR_04_Product_Frame_Passport.md`
   - Продуктовая рамка проекта.
   - Фиксирует продуктовый язык без подмены кода маркетинговой формулой.

8. `RE_BR_05_Context_Transfer_and_Replication_Passport.md`
   - Governance-документ по переносу и репликации контекста.
   - Управляет дальнейшим обновлением набора.

### B. Core analytical docs

9. `RE_QIKI_Architecture_Verification_Note.md`
   - Главный as-built архитектурный документ.
   - Фиксирует spine, ownership rules, verified-support, duplicate и legacy зоны.

10. `RE_QIKI_Canon_Map_and_ADR.md`
   - Компактная карта канона.
   - Короткий ADR-пакет по ключевым архитектурным решениям.

11. `RE_QIKI_Product_Truth_and_Gate_Plan.md`
   - Продуктовый канон и gate logic.
   - Должен читаться как product-frame / gate-plan, а не как runtime-proof.

### C. Meta / control docs

12. `RE_QIKI_Analytical_Path_Map.md`
    - Полная карта аналитического пути.
    - Должна быть синхронизирована с maturity matrix и completion criteria.

13. `RE_QIKI_Project_Analysis_Position.md`
    - Документ текущей позиции.
    - Фиксирует, что уже доказано, что не доказано, где blocker и что делать дальше.

14. `RE_QIKI_Maturity_Matrix.md`
    - Рабочая система статусов.
    - Центральный документ контроля зрелости пакета и сущностей.

15. `RE_QIKI_Documentation_Completion_Criteria.md`
    - Критерии честного завершения документационного цикла.
    - Запрещает симулировать завершённость без evidence-driven closure.

### D. Evidence / unresolved docs

16. `RE_QIKI_Runtime_Evidence_Notes.md`
    - Документ живых и частично живых подтверждений.
    - Держит active slice в честном статусе `proof-stage`, пока proof не закрыт.

17. `RE_QIKI_Risks_and_Unresolved_Zones.md`
    - Отдельный реестр рисков и незакрытых зон.
    - Нужен, чтобы runtime gap, compose gap, duplicate entrypoints и ambiguity не растворялись в общих текстах.

### E. Archive verification layer

18. `RE_QIKI_Archive_Verification.md`
    - Человекочитаемая сверка полного пакета.
    - Подтверждает наличие, размер и SHA-256 у всех 19 файлов.

19. `RE_QIKI_Archive_Verification.csv`
    - Машинно-читаемая сверка полного пакета.
    - Даёт компактную таблицу проверки тех же 19 файлов.

---

## 4. Рекомендуемый порядок чтения

### Первый проход

1. `RE_00_QIKI_Root_Index.md`
2. `RE_QIKI_Unified_Manifest.md`
3. `RE_QIKI_Document_Pack_Index.md`
4. `RE_QIKI_Analytical_Path_Map.md`
5. `RE_QIKI_Project_Analysis_Position.md`
6. `RE_QIKI_Maturity_Matrix.md`

### Второй проход

7. `RE_QIKI_Architecture_Verification_Note.md`
8. `RE_QIKI_Canon_Map_and_ADR.md`
9. `RE_QIKI_Product_Truth_and_Gate_Plan.md`
10. `RE_QIKI_Documentation_Completion_Criteria.md`
11. `RE_QIKI_Runtime_Evidence_Notes.md`
12. `RE_QIKI_Risks_and_Unresolved_Zones.md`

### Третий проход

13. `RE_BR_01_Code_Truth_Passport.md`
14. `RE_BR_02_QIKI_Canonization_Passport.md`
15. `RE_BR_03_Orion_and_Operator_Surface_Passport.md`
16. `RE_BR_04_Product_Frame_Passport.md`
17. `RE_BR_05_Context_Transfer_and_Replication_Passport.md`
18. `RE_QIKI_Archive_Verification.md`
19. `RE_QIKI_Archive_Verification.csv`

---

## 5. Что уже считается собранным

На текущем этапе уже собраны все структурно обязательные слои:
- единый индексный слой;
- документ текущей позиции;
- карта аналитического пути;
- maturity/status system;
- architecture + canon + product docs;
- runtime evidence notes;
- отдельный документ risks / unresolved zones;
- closure criteria.

Это означает, что пакет **структурно собран**.

---

## 6. Что ещё не даёт считать пакет завершённым

На момент сборки пакета его нельзя было считать полностью закрытым по трём причинам:

1. `signature_changed live path` остаётся незакрытым proof item.
2. Active slice `G3-QIKI-009` остаётся в статусе `proof-stage`.
3. Часть ключевых документов ещё требует синхронизации после появления evidence/risk-слоя.

В первую очередь на пересмотр стоят:
- `QIKI_ANALYTICAL_PATH_MAP.md`
- `PROJECT_ANALYSIS_POSITION.md`
- `QIKI_MATURITY_MATRIX.md`
- `QIKI_Architecture_Verification_Note_v1.md`
- `QIKI_Canon_Map_and_ADR_v1.md`
- `QIKI_Documentation_Completion_Criteria.md` / действующий критерий-файл по реальным именам

---

## 7. Правила использования индекса

1. Если документ противоречит коду, приоритет у кода и подтверждённого runtime.
2. Если документ выражает проектное решение, это должно быть явно маркировано как решение.
3. Если документ описывает незакрытую зону, она не должна повышаться до канона только из-за уверенной формулировки.
4. Evidence и risks должны обновляться раньше, чем делаются сильные заявления о closure.
5. Support-слой полезен для проверки и происхождения выводов, но не замещает ядро пакета.

---

## 8. Текущая рабочая формула

```text
QIKI documentation package
  = root governance
  + code-truth branch layer
  + semantic/product/operator branches
  + architecture/canon/product core docs
  + meta-control docs
  + evidence/risk layer
  + support analysis layer
  - final runtime closure
```

---

## 9. Итог

Текущий индекс v1 был недостаточен не потому, что был плохим, а потому, что индексировал только core-doc subset.

Этот rev2 нужен затем, чтобы:
- индексировать весь рабочий пакет;
- развести роль ROOT и роль Pack Index;
- показать, что пакет уже собран структурно;
- одновременно не симулировать его окончательную завершённость.
