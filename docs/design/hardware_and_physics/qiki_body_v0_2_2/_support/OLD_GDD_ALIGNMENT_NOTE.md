# QIKI Body v0.2.2 — Old GDD Alignment Note

Generated: 2026-06-21T04:25:01+00:00

## 0. Назначение

Этот документ нужен для аккуратного согласования старого QIKI GDD с новым пакетом:

`QIKI Body v0.2.2 Documentation Package`

Он не удаляет старый GDD.

Он не переписывает старый GDD целиком.

Он не объявляет runtime implemented.

Он фиксирует, что старый GDD остаётся историческим и игровым слоем, а аппаратная логика тела QIKI теперь должна сверяться с новым body canon.

## 1. Статус старого GDD

Старый GDD сохраняется как:

- game-design context;
- historical layer;
- source of early ideas;
- reference for earlier wording and evolution of the project.

Но по вопросам body hardware / physics приоритет имеет:

`docs/design/hardware_and_physics/qiki_body_v0_2_2/`

## 2. Что теперь считается актуальным body canon

Актуальный документационный канон тела QIKI:

`docs/design/hardware_and_physics/qiki_body_v0_2_2/00_INDEX.md`

Главный source по телу:

`docs/design/hardware_and_physics/qiki_body_v0_2_2/01_BODY_CANON.md`

Требования:

`docs/design/hardware_and_physics/qiki_body_v0_2_2/02_REQUIREMENTS.md`

Расчётный каркас:

`docs/design/hardware_and_physics/qiki_body_v0_2_2/04_CALCULATION_FRAME.md`

Инженерное обоснование:

`docs/design/hardware_and_physics/qiki_body_v0_2_2/05_ENGINEERING_RATIONALE.md`

Интерфейсы:

`docs/design/hardware_and_physics/qiki_body_v0_2_2/06_INTERFACE_CONTROL.md`

ADR:

`docs/design/hardware_and_physics/qiki_body_v0_2_2/07_ADR/`

## 3. Рекомендуемая вставка в начало старого GDD

```md
> Alignment note — QIKI Body v0.2.2
>
> QIKI Body v0.2.2 is the current target documentation canon for body hardware / physics / machine-body constraints.
>
> This older GDD file remains available as game-design and historical context.
>
> Hardware, body, power, thermal, RCS, bayonet, NBL, protection, modularity, command gating and evidence claims should be checked against:
>
> `docs/design/hardware_and_physics/qiki_body_v0_2_2/`
>
> Older conflicting statements should be treated as superseded by QIKI Body v0.2.2 unless explicitly re-accepted by a later ADR.
```

## 4. Superseded-зоны

Следующие старые формулировки должны считаться устаревшими или требующими сверки с QIKI Body v0.2.2.

### 4.1. Магнитный замок как основной силовой байонет

Старый риск:

байонет может быть описан как магнитный замок.

Актуальная позиция:

магнит допустим только как `magnetic_pre_align`.

Для bridge требуется:

`mechanical hard lock → structural check → electrical safety → umbilical mate → module handshake → passport validation → bridge allowed`.

Связанный ADR:

`ADR-0009-bayonet-mechanical-hard-lock.md`

### 4.2. RTG как обычная батарейка

Старый риск:

RTG может звучать как маленькая вечная батарейка или boost-source.

Актуальная позиция:

RTG-class source is heavy / trickle source, not boost-source.

Связанный ADR:

`ADR-0004-rtg-trickle-not-boost.md`

### 4.3. Реактор как обычный модуль на грань

Старый риск:

reactor-class source может быть описан как обычный face-mounted upgrade.

Актуальная позиция:

reactor-class source is external / station / sled / heavy infrastructure.

Связанный ADR:

`ADR-0005-reactor-external-source.md`

### 4.4. NBL как широкополосная связь

Старый риск:

NBL может звучать как internet-through-everything или normal telemetry.

Актуальная позиция:

baseline NBL is emergency low-rate only.

Связанный ADR:

`ADR-0006-nbl-emergency-low-rate.md`

### 4.5. Щит как абсолютная защита

Старый риск:

защита может быть описана как absolute shield.

Актуальная позиция:

protection is a constrained mechanism / deployable deflector, not absolute shield.

Связанный ADR:

`ADR-0007-deflector-not-absolute-shield.md`

### 4.6. Field drive как baseline

Старый риск:

field drive может быть описан как штатная тяга от чистой энергии.

Актуальная позиция:

field drive is not baseline. If used, it is Terta-exotic and must have explicit cost, limits and evidence path.

Связанный ADR:

`ADR-0008-field-drive-not-baseline.md`

### 4.7. RCS как равномерная тяга без расчёта

Старый риск:

RCS может быть описана как balanced / isotropic без Thrust Map и Torque Map.

Актуальная позиция:

RCS requires Thrust Map and Torque Map before balanced thrust or full control can be claimed.

Связанный ADR:

`ADR-0010-rcs-thrust-torque-maps-required.md`

### 4.8. Модуль без паспорта

Старый риск:

модуль может считаться установленным или активным по названию.

Актуальная позиция:

module passport is mandatory for runtime-ready status.

Связанный ADR:

`ADR-0011-module-passport-mandatory.md`

### 4.9. Команда как мгновенный эффект

Старый риск:

команда может быть описана как прямое действие.

Актуальная позиция:

command lifecycle must distinguish request, validation, publish, ACK, effect confirmation and audit.

Связанный ADR:

`ADR-0015-ack-not-effect-confirmation.md`

### 4.10. ORION как декоративный HUD

Старый риск:

ORION может быть описан как красивая панель состояния.

Актуальная позиция:

ORION is evidence station, not decorative HUD.

Связанный ADR:

`ADR-0014-orion-evidence-station.md`

## 5. Что не делать

Не удалять старый GDD первым patch.

Не переписывать его целиком автоматически.

Не объявлять старый GDD “ошибочным полностью”.

Не переносить старые формулировки в новый package без статуса.

Не объявлять runtime implemented.

Не менять runtime в этом шаге.

## 6. Правильное действие

Добавить alignment note.

Сохранить старый GDD как historical / game-design layer.

По аппаратным вопросам сверяться с QIKI Body v0.2.2.

Если нужно изменить фундаментальное решение — создавать новый ADR, а не молча переписывать историю.
