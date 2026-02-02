# Thermal Plane — Warn/Trip policy + Ambient floor (P0 canon)

Цель: сделать тепловую плоскость **оператор‑объяснимой** и **не‑дребезжащей** без моков.

Инварианты:
- источник правды: `q_sim_service`;
- без `v2` / без новых subject’ов: расширяем текущие поля телеметрии `thermal.nodes[]` назад‑совместимо;
- детерминизм: поведение должно быть защищено тестами.

## Source of truth (код)

- Модель и пороги: `src/qiki/services/q_sim_service/core/world_model.py` (`_thermal_step()` + thermal init).
- Тесты: `src/qiki/services/q_sim_service/tests/test_thermal_plane.py`.

## Telemetry contract (Phase1)

`thermal.nodes[]` содержит (минимум):
- `id: str`
- `temp_c: float`
- `tripped: bool`
- `warned: bool`
- `warn_c: float`
- `trip_c: float`
- `hys_c: float`

`warned` вычисляется как: `temp_c >= warn_c` и `not tripped`.

## Warn threshold policy

1) Если в узле задано `t_warn_c`, используем его напрямую.
2) Иначе, если задан `t_max_c`/`trip_c > 0`, то `warn_c = trip_c - warn_delta_c`.
3) По умолчанию `warn_delta_c = 10` (можно переопределить `thermal_plane.warn_delta_c`).

## Trip + hysteresis policy

- Trip: `temp_c >= trip_c` ⇒ `tripped=True`.
- Clear: `temp_c <= trip_c - hys_c` ⇒ `tripped=False`.

Если `trip_c > 0`, но `hys_c == 0`, это считается ошибкой профиля:
- в `power.faults` добавляется `THERMAL_PLANE_PARAM_INVALID:<node>:hys_zero`.

## Ambient floor (Euler overshoot guard)

Модель использует явный Эйлер. При больших `dt`/сильном охлаждении возможен численный “перелёт” ниже `ambient` при охлаждении **сверху**.

Политика:
- если узел был `temp_c >= ambient` и шаг дал `temp_c < ambient`, то `temp_c` клэмпится к `ambient`.
- если узел уже ниже `ambient` (начальные условия или охлаждение через связи), **клэмпа вверх нет** — узел может быть холоднее окружающей среды, но модель не должна “охлаждать его ниже ambient” через сам ambient‑терм.

## Proof / tests (must stay green)

Тесты должны доказывать:
- наличие полей warn/trip в `thermal.nodes[]`,
- `warned` выставляется до `tripped`,
- trip clear соблюдает гистерезис,
- нет overshoot ниже ambient из состояния выше ambient.

