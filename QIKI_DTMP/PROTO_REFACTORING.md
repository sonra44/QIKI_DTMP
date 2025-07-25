# PROTO_REFACTORING.md

##  Цель

Повысить надёжность, расширяемость и верифицируемость всех `.proto`-контрактов QIKI_DTMP. Введение строгих правил и инструментария позволит обеспечить доверие между микросервисами, снизить риск ошибок и ускорить интеграцию.

---

##  Общая Структура

###  Расположение файлов
- Все `.proto` в `protos/`
- Сгенерированные `.py` в `generated/`
- Моки и схемы — в `proto_extensions/`

###  Соглашения
- Использовать `oneof` для взаимоисключающих полей
- Все идентификаторы — `UUID` из `common_types.proto`
- Все поля времени — `google.protobuf.Timestamp`
- Все статусные поля — `enum` с префиксом (например, `ProposalStatus`)

---

##  Рефакторинг по Модулям

### 1. `common_types.proto`

| Изменение                 | Описание                                     |
|---------------------------|-----------------------------------------------|
| + `Unit.MILLISECONDS`     | Для сенсоров, таймеров                       |
| + `Unit.KELVIN`, `BAR`    | Для температуры и давления                   |
| + `ActuatorType` (enum)   | Для отделения от `SensorType`               |
| + Комментарии `Vector3`   | Указать локальные/глобальные системы        |

---

### 2. `sensor_raw_in.proto`

| Изменение                       | Описание                                      |
|--------------------------------|-----------------------------------------------|
| `oneof sensor_data`            | Для исключения конфликтов между scalar/vector/binary |
| + `is_valid`, `encoding`       | Сигналы качества                             |
| + `signal_strength`, `source_module` | Расширенная телеметрия                    |

---

### 3. `actuator_raw_out.proto`

| Изменение                | Описание                                 |
|--------------------------|-------------------------------------------|
| `enum CommandType`       | Заменяет строку `command_type`           |
| + `command_id`           | Идентификатор для трассировки            |
| + `timeout_ms`, `ack_required` | Надёжная доставка                     |

---

### 4. `bios_status.proto`

| Изменение                   | Описание                                 |
|-----------------------------|-------------------------------------------|
| `status_code → enum`        | Предотвращает произвольные значения      |
| + `uptime_sec`, `health_score` | Метрики устройства                    |

---

### 5. `fsm_state.proto`

| Изменение                          | Описание                                   |
|------------------------------------|---------------------------------------------|
| + `FSMStateEnum`, `FSMTransitionStatus` | Стандартизация переходов         |
| + `source_module`, `attempt_count` | Диагностика ошибок                         |

---

### 6. `proposal.proto`

| Изменение                     | Описание                                    |
|-------------------------------|----------------------------------------------|
| + `confidence` (float)        | Степень уверенности                         |
| + `ProposalStatus` (enum)     | Текущий статус: accepted, executed и др.    |
| + `depends_on`, `conflicts_with` | Координация сложных решений            |
| + `proposal_signature`        | Подпись для реплея, отката, верификации     |

---

##  Технический стек

- `protobuf` ≥ 3.21
- `protoc` + `grpc_tools.protoc`
- Проверка через `proto_linter.py`
- Моки генерируются `generate_mock_messages.py`

---

##  Структура `proto_extensions/`

```bash
proto_extensions/
├── mocks/
│   ├── sensor_reading.mock.json
│   └── actuator_command.mock.json
├── schemas/
│   └── ruleset.yaml
└── utils/
    └── generate_mock_messages.py
    └── proto_linter.py
```
 Примеры команд
```bash
# Компиляция .proto
make compile_proto

# Генерация моков
python proto_extensions/utils/generate_mock_messages.py

# Валидация схем
python proto_extensions/utils/proto_linter.py
```

