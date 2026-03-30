# RE QIKI Unified Manifest

> REFERENCE ONLY / NOT ACTIVE CANON
>
> Этот manifest описывает пересобранный `RE_`-пакет как historical/reference layer.
> Он не должен использоваться как текущий статусный источник поверх active board и текущих task dossiers.

## Назначение

Этот манифест фиксирует активный документационный контур проекта QIKI в формате `RE_`.
Он задаёт единый вход в пакет, состав активных документов, их роли, порядок чтения и границы пакета.

## Статус пакета

- package_structure = assembled
- package_normalization = largely complete
- package_closure = not yet
- historical blocker at package-assembly time = `signature_changed live path`

Current active-project status for the live canon:
- `signature_changed` is closed with evidence on the canonical path
- current mode is `hardening / regression / cleanup`
- current slice is the post-closure stabilization baseline from `~/MEMORI/ACTIVE_TASKS_QIKI_DTMP.md`

## Полный фиксированный пакет: 19 документов

1. `RE_00_QIKI_Root_Index.md` — корневая входная точка и правило чтения.
2. `RE_QIKI_Unified_Manifest.md` — манифест состава пакета и его границ.
3. `RE_QIKI_Document_Pack_Index.md` — реестр полного пакета.
4. `RE_QIKI_Analytical_Path_Map.md` — карта аналитического пути.
5. `RE_QIKI_Project_Analysis_Position.md` — текущая аналитическая позиция.
6. `RE_QIKI_Maturity_Matrix.md` — статусная матрица зрелости.
7. `RE_QIKI_Architecture_Verification_Note.md` — архитектурная верификация.
8. `RE_QIKI_Canon_Map_and_ADR.md` — канон и ADR-слой.
9. `RE_QIKI_Product_Truth_and_Gate_Plan.md` — продуктовая рамка и gate-plan.
10. `RE_QIKI_Documentation_Completion_Criteria.md` — критерии честного закрытия.
11. `RE_QIKI_Runtime_Evidence_Notes.md` — runtime evidence layer.
12. `RE_QIKI_Risks_and_Unresolved_Zones.md` — реестр рисков и незакрытых зон.
13. `RE_BR_01_Code_Truth_Passport.md` — паспорт кодовой истины.
14. `RE_BR_02_QIKI_Canonization_Passport.md` — паспорт канонизации.
15. `RE_BR_03_Orion_and_Operator_Surface_Passport.md` — паспорт операторской среды.
16. `RE_BR_04_Product_Frame_Passport.md` — паспорт продуктовой рамки.
17. `RE_BR_05_Context_Transfer_and_Replication_Passport.md` — паспорт переноса и репликации контекста.
18. `RE_QIKI_Archive_Verification.md` — проверка наличия, размеров и SHA для файлов пакета.
19. `RE_QIKI_Archive_Verification.csv` — машинно-читаемая таблица проверки 19 файлов.

## Порядок чтения

Рекомендуемый порядок:

1. `RE_00_QIKI_Root_Index.md`
2. `RE_QIKI_Unified_Manifest.md`
3. `RE_QIKI_Document_Pack_Index.md`
4. `RE_QIKI_Analytical_Path_Map.md`
5. `RE_QIKI_Project_Analysis_Position.md`
6. `RE_QIKI_Maturity_Matrix.md`
7. `RE_QIKI_Architecture_Verification_Note.md`
8. `RE_QIKI_Canon_Map_and_ADR.md`
9. `RE_QIKI_Product_Truth_and_Gate_Plan.md`
10. `RE_QIKI_Documentation_Completion_Criteria.md`
11. `RE_QIKI_Runtime_Evidence_Notes.md`
12. `RE_QIKI_Risks_and_Unresolved_Zones.md`
13. `RE_BR_01_Code_Truth_Passport.md`
14. `RE_BR_02_QIKI_Canonization_Passport.md`
15. `RE_BR_03_Orion_and_Operator_Surface_Passport.md`
16. `RE_BR_04_Product_Frame_Passport.md`
17. `RE_BR_05_Context_Transfer_and_Replication_Passport.md`
18. `RE_QIKI_Archive_Verification.md`
19. `RE_QIKI_Archive_Verification.csv`

## Что не входит в активный пакет

Не входят в активный контур:

- файлы с суффиксами `(1)`
- старые `QIKI_*` без префикса `RE_`, если есть `RE_`-версия
- `*_v1`, `*_rev*`, `*_draft`, `*_work`
- check / crosscheck / control документы как ядро пакета
- архивный и support-слой как первичный источник истины

## Правило разрешения конфликтов

1. Главный источник истины — код проекта и подтверждаемые структурные/runtime-признаки.
2. `RE_`-документы — активный аналитический контур.
3. Support/history/archive — только вспомогательный слой.
4. Если документ противоречит коду, прав код.

## Практический вывод

Пакет уже пригоден как единая документационная система для переноса, повторного анализа и постановки следующего фронта работ.
При этом сам пакет не должен подменять текущий live-canon status; для текущего runtime/closeout состояния нужно читать active board, current task dossier и stabilization baseline docs.
