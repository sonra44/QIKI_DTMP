# Отчёт по файлу `services/q_core_agent/config.yaml`

## Содержимое
```
tick_interval: 5
log_level: INFO
recovery_delay: 2
proposal_confidence_threshold: 0.6
mock_neural_proposals_enabled: False
```

## Задачи
- [ ] Проверить оптимальность `tick_interval` для рабочих нагрузок.
- [ ] Реализовать возможность динамической смены `log_level`.
- [ ] Обосновать выбранное значение `proposal_confidence_threshold`.
- [ ] Уточнить необходимость `mock_neural_proposals_enabled` и описать сценарии применения.
