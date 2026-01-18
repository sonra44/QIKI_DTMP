
Цель: зафиксировать **регламентное** ТЗ для виртуализации Comms/XPDR (транспондер/радиосвязь) в проекте **QIKI_DTMP** так, чтобы:
- соблюсти **no‑mocks policy** (в UI только реальные данные симуляции или честное `N/A/—`);
- не создавать **дубли** и “вторые источники правды”;
- не добавлять `*_v2.*` и новые subject’ы/контракты.

ТЗ написано так, чтобы его можно было показать стороннему инженеру/модели без доступа к репозиторию.

---

## 0) Контекст (не обсуждается)

1) Проект — **симуляция / Digital Twin**. “Железо” бота виртуальное.  
2) “Реальные данные” в рамках проекта — это **simulation‑truth** (детерминированная модель), а **не** метрики VPS/контейнера.  
3) **Запрещено**:
   - добавлять `*_v2.*` (например, `comms_v2`, `xpdr_v2` и т.п.);
   - заводить второй `bot_config`/`bot_spec`/`comms_spec` как параллельную линию правды.
4) **Разрешено**:
   - расширять `src/qiki/services/q_core_agent/config/bot_config.json`;
   - расширять `qiki.telemetry` новыми top-level ключами (в `TelemetrySnapshotModel` разрешены `extra`);
   - использовать существующий канал управления `qiki.commands.control` (без новых `.proto`).

---

## 1) Каноничные артефакты (источник правды)

- Runtime профиль железа: `src/qiki/services/q_core_agent/config/bot_config.json`
- Политика no-mocks для UI: `docs/operator_console/REAL_DATA_MATRIX.md`
- Интенция/архитектура: `docs/design/hardware_and_physics/bot_source_of_truth.md` (Comms Plane)

---

## 2) Проблема, которую решаем

Сейчас в системе есть “кусочки” XPDR/транспондера (влияние на радар и как нагрузка на Power Plane), но:
- у оператора нет прозрачного статуса: **режим / активен ли / разрешён ли по питанию / какой ID**;
- нет безопасного runtime‑контроля режима (без правки env и перезапуска);
- UI не должен показывать “0/OK” без доказанного источника.

---

## 3) Scope (MVP)

### 3.1 Телеметрия (qiki.telemetry)

Добавить top-level блок `comms` в payload телеметрии (TelemetrySnapshot v1, `extra`):

```json
{
  "comms": {
    "enabled": true,
    "xpdr": {
      "mode": "ON|OFF|SILENT|SPOOF",
      "active": true,
      "allowed": true,
      "id": "ALLY-ABC123|SPOOF-DEF456|null"
    }
  }
}
```

Правила no-mocks:
- если `comms` отсутствует → UI показывает `N/A/—`;
- если `enabled=false` → `xpdr.*` может быть `null`/`N/A` (не рисуем “0”);
- `xpdr.allowed` **производная** от Power Plane (нельзя плодить вторую истину про “можно/нельзя по питанию”).

### 3.2 Управление (qiki.commands.control)

Добавить симуляционную команду (без новых `.proto`):
- `sim.xpdr.mode` с параметром `mode` ∈ `{ON, OFF, SILENT, SPOOF}`

Принципы:
- невалидный `mode` → команда отклоняется (`False` / событие ошибки по текущему механизму).
- режим `SPOOF` должен иметь **стабильный spoof-id в рамках сессии**, чтобы UI не “мигал”.

### 3.3 ORION UI (Operator Console)

Без добавления новых hotkey (F10 занято под Exit):
- показывать XPDR блок в `Diagnostics / Диагностика`:
  - `Comms enabled/Связь вкл`
  - `XPDR mode/Режим XPDR`
  - `XPDR allowed/XPDR разрешён`
  - `XPDR active/XPDR активен`
  - `XPDR id/ID XPDR`

Команда в CLI:
- `xpdr.mode <on|off|silent|spoof>` → публикует `sim.xpdr.mode`.

---

## 4) Параметры в bot_config.json (без дублей)

Добавить `hardware_profile.comms_plane`:

```json
{
  "hardware_profile": {
    "comms_plane": {
      "enabled": true,
      "xpdr_mode_init": "ON"
    }
  }
}
```

---

## 5) Критерии приёмки (DoD)

Задача выполнена, если:
1) В `qiki.telemetry` присутствует `comms.xpdr.*` и значения меняются от `sim.xpdr.mode`.
2) ORION показывает эти поля в `Diagnostics` и не падает при отсутствии `comms` (честный `N/A/—`).
3) Есть unit‑тесты:
   - `q_sim_service`: наличие `comms` в payload, смена mode, стабильность spoof-id;
   - `operator_console`: парсер `xpdr.mode ...` (валид/невалид).
4) Не добавлены `*_v2.*`, не создано вторых источников правды.

