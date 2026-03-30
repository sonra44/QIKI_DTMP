# ARTIFACT: ORION V F1 quick-actions runtime proof

Статус: pass
Дата: 2026-03-05
Область: `ORION V` cockpit `F1` quick-actions

## Цель

Закрыть остаточный риск после deep audit:
- доказать не только unit/headless-логикой, но и живым runtime-путём, что новый блок быстрых действий `F1` реально работает;
- подтвердить читаемость коротких labels;
- подтвердить корректный переход `F1 -> F2`;
- подтвердить QIKI confirm/cancel path без создания нового обходного контура.

## Среда

- стек: `docker-compose.phase1.yml` + `docker-compose.operator.yml`
- сервисы:
  - `operator-console`
  - `qiki-dev`
  - `q-sim-service`
  - `q-bios-service`
- режим доказательства: live `Textual run_test` против поднятого Docker-стека
- размер geometry proof: `160x48`

## Команды воспроизведения

```bash
docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml ps \
  operator-console qiki-dev q-sim-service q-bios-service

docker compose -f docker-compose.phase1.yml exec -T qiki-dev \
  ruff check tools/orion_v_f1_quick_actions_smoke.py

bash scripts/prove_orion_v_f1_quick_actions.sh
```

## Что делает proof

`tools/orion_v_f1_quick_actions_smoke.py`:
1. Подключает `OrionVApp` к живому NATS/Phase1 stack.
2. Ждёт реальную телеметрию `power`, `comms`, `docking`.
3. Проверяет, что `F1` body содержит строку `Быстрые переходы/Quick actions`.
4. Считывает реальные labels кнопок:
   - `Энергия/Power`
   - `Стыковка/Docking`
   - `Связь/Comms`
5. Проверяет, что без pending-action QIKI-кнопки компактны:
   - `QIKI: нет действия/No action`
6. Кликает по `Стыковка/Docking` и доказывает переход:
   - `current_level=f2`
   - `selected_system_module_slug=docking`
7. Возвращается на `F1`.
8. Инжектирует валидный QIKI response для pending undock action.
9. Проверяет, что labels остаются короткими:
   - `QIKI подтвердить/Confirm`
   - `QIKI отменить/Cancel`
10. Проверяет, что подробность вынесена в body:
   - `Подготовлено/Prepared: Подтвердить отстыковку`
11. Кликает `Cancel` и подтверждает итог:
   - `FINAL_QIKI_STATUS=not_sent`

## Фактический результат

Вывод smoke:

```text
OK: orion_v_f1_quick_actions_smoke
POWER_BUTTON=Энергия/Power OK -> F2
DOCKING_BUTTON=Стыковка/Docking OK -> F2
COMMS_BUTTON=Связь/Comms WARN -> F2
QIKI_CONFIRM_READY=QIKI: нет действия/No action
BODY_HAS_PREPARED=1
FINAL_LEVEL=f1
FINAL_SELECTED_MODULE=docking
FINAL_QIKI_STATUS=not_sent
```

## Что этим доказано

1. Новый блок `F1 quick-actions` реально видит live telemetry и выставляет живые labels.
2. Отдельный переход `Стыковка/Docking` действительно работает и ведёт в правильный detail-screen.
3. QIKI-кнопки остаются короткими в geometry `160x48`.
4. Подробность pending action не перегружает label и вынесена в body.
5. Cancel path использует уже существующий безопасный путь и не создаёт mouse-only ветку.

## Итог

Остаточный риск из `ARTIFACT_20260305_orion_v_clickable_deep_audit.md` закрыт.

Теперь clickable-аудит `F1` имеет:
- unit evidence,
- headless geometry evidence,
- live runtime proof.
