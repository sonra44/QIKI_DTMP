# ORION Profile Evidence (2026-01-24)

## Context

- Feature: `Profile/Профиль` screen (read-only bot profile view)
- Stack: `docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml up -d --build operator-console`
- Terminal size: 86x25 (tmux split pane)

## tmux capture

```
Ext temp/Нар темп -60.0°C                 Core temp/Темп ядра -44.2°C
Mode/Режим N/A/—                          Sim/Сим Running/Работает
Bot profile/Профиль бота
╭──────────────────────── Profile summary/Сводка профиля ────────────────────────╮
│ Repo root/Корень репо           /workspace                                     │
│ BotSpec/BotSpec                 /workspace/shared/specs/BotSpec.yaml           │
│ BotSpec id/BotSpec id           QIKI-DODECA-01                                 │
│ RCS thrusters/RCS сопла         16 (clusters/кластеры: A, B, C, D)             │
│ F_max (N)                       min=220.0 max=260.0                            │
│ Hardware profile/Профиль железа /workspace/src/qiki/services/q_core_agent/con… │
│ Actuators/Актуаторы             3                                              │
│ Sensors/Сенсоры                 13                                             │
╰────────────────────────────────────────────────────────────────────────────────╯

╭─ Output/Вывод ───────────────────────────────────────────────────────────────────╮
│ 05:32:09 info/инфо BIOS loaded/BIOS загрузился: OK/ОК                          │
│ 05:32:16 info/инфо System online/Система в сети                                 │
│ 10:45:57 info/инфо command/команда> screen profile                              │
╰──────────────────────────────────────────────────────────────────────────────────╯
```
