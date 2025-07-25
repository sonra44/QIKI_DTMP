# Дизайн: BIOS (Basic Input/Output System)

## 1. Обзор
Этот документ описывает компонент BIOS, низкоуровневую "прошивку" для QIKI платформы. В архитектуре Digital Twin, BIOS выполняет ту же роль, что и в PC: он инициализирует и тестирует "оборудование" (`bot_physical_specs`) и передает управление высокоуровневой логике (`Q-Core Agent`).

**Архитектурное решение:** BIOS реализуется как отдельный, легковесный микросервис `q-bios-service` для изоляции и независимого тестирования.

## 2. Последовательность Загрузки (Boot Sequence)
1.  **[0.00s] Подача Питания:** `q-bios-service` запускается.
2.  **[0.01s] Чтение Спецификаций:** BIOS читает `bot_physical_specs.json` для получения списка оборудования и его контрактов.
3.  **[0.02s] Начало POST (Power-On Self-Test):** BIOS начинает опрос каждого "порта", указанного в спецификации.
4.  **[0.02s - 0.20s] Процесс POST:** Для каждого компонента выполняется базовый тест (например, проверка ответа, запрос статуса).
5.  **[0.21s] Формирование Отчета:** BIOS генерирует `bios_status.json` с результатами POST.
6.  **[0.22s] Проверка Статуса:**
    *   **Если `status: "ready"`:** BIOS публикует сообщение `hardware_ready` и завершает свою активную фазу, переходя в режим ожидания диагностических запросов.
    *   **Если `status: "error"`:** BIOS публикует сообщение `hardware_error` с кодами ошибок и переходит в режим диагностики.

## 3. Спецификация API
BIOS предоставляет gRPC или простой HTTP API для взаимодействия.

- `get_bios_status() -> bios_status.json`: Возвращает полный отчет о состоянии оборудования.
- `get_component_status(component_id: str) -> component_status_json`: Возвращает статус конкретного компонента.
- `read_port(port_id: str, params: dict) -> PortData`: Читает данные с указанного порта.
- `write_port(port_id: str, command: dict) -> Status`: Отправляет команду на указанный порт.
- `soft_reboot(component_id: str) -> Status`: Инициирует перезагрузку одного компонента.
- `hot_reload_config() -> Status`: Перечитывает `bot_physical_specs.json` для обновления конфигурации портов.

## 4. Модели Данных

**1. `bios_status.json`:**
```json
{
  "boot_time_utc": "2025-07-21T19:30:00Z",
  "hardware_profile_hash": "sha256:bd1c10a...e4c1",
  "status": "ready", // ready | error
  "components": {
    "motor_left": "ok",
    "lidar_front": "ok",
    "imu_main": "warning: high_drift"
  }
}
```

**2. Контракт Порта (из `bot_physical_specs.json`):**
```json
{
  "port_id": "lidar_front",
  "type": "lidar",
  "protocol": "sim_bus", // sim_bus | i2c | etc.
  "params": {
    "range_m": 100,
    "fov_deg": 180
  }
}
```

## 5. Логирование и Коды Ошибок

**Формат лога (`bios.log`):**
```
[0.01s] BIOS started
[0.02s] Reading hardware profile: sha256:bd1c10a...e4c1
[0.05s] POST: Probing port motor_left... OK
[0.06s] POST: Probing port lidar_front... OK
[0.07s] POST: Probing port imu_main... ERROR (Code: 0x02)
[0.08s] POST complete. STATUS: ERROR
```

**Коды Ошибок (Beep-коды):**
| Код    | Значение                  |
|--------|---------------------------|
| 0x01   | Компонент не найден       |
| 0x02   | Нестабильные показания    |
| 0x03   | Таймаут ответа            |
| 0xF0   | Критический сбой загрузки |

## 6. Анти-паттерны
- **Сложная логика в BIOS:** BIOS не должен содержать никакой бизнес-логики или FSM. Его задача — только инициализация и предоставление доступа.
- **Прямой доступ в обход BIOS:** `Q-Core Agent` никогда не должен пытаться получить доступ к симулятору или железу напрямую.

## 7. Открытые Вопросы
1.  Какой протокол выбрать для API (gRPC или HTTP)? Для MVP предлагается простой HTTP.
2.  Как реализовать `hardware_adapter` для работы с реальным железом в будущем?