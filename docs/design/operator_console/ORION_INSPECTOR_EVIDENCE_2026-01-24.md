# ORION Inspector Evidence (2026-01-24)

## Context

- Screen: `Power/Питание` (selection on `SoC/Заряд`)
- Source key: `power.soc_pct`
- Terminal size: 174x52 (tmux full window)
- Stack: `docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml up -d --build operator-console`

## tmux capture

```
Component/Компонент                       Status/Статус     Value/Значение            Age/Возраст  ╭─ Inspector/Инспектор ────────────────────╮
Battery level/Уровень батареи             Normal/Норма      100.0%                    0.0sec/0.0с  │                                          │
SoC/Заряд                                 Normal/Норма      100.0%                    0.0sec/0.0с  │ Summary/Сводка                           │
...
Key/Ключ        state_of_charge                                                                       │
Source keys/Кл… power.soc_pct                                                                          │
Timestamp/Время 11:43:54                                                                               │
Meaning/Смысл   power.soc_pct: SoC/Заряд                                                               │
                (percent, number)                                                                     │
Why/Зачем       Energy reserve for safe operation/Резерв энергии                                       │
                для безопасной работы                                                                  │
Actions hint/П… Check load shedding and faults; reduce loads if needed/Проверьте сброс                 │
                нагрузки и аварии; снизьте нагрузки при необходимости                                 │
Raw data (JSON)/Сырые данные (JSON)
{"attitude":{"pitch_rad":-0.00680200247…
```
