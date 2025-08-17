# QIKI Digital Twin Microservices Platform (QIKI_DTMP)

## 1. Обзор Проекта

Этот репозиторий содержит исходный код и проектную документацию для платформы QIKI_DTMP.
Проект разрабатывается в соответствии с принципами, изложенными в `docs/NEW_QIKI_PLATFORM_DESIGN.md`.

---

## 2. Компоненты Системы

Ниже представлен список ключевых компонентов системы, сгенерированный автоматически на основе их дизайн-документов.



---


## 3. Protocol Buffers Контракты

Система использует Protocol Buffers для типобезопасного взаимодействия между микросервисами:


### 3.1. common_types
- **Пакет:** `qiki.common`
- **Messages:** 2, **Enums:** 3, **Services:** 0  
- **Файл:** [protos/common_types.proto](protos/common_types.proto)

### 3.2. sensor_raw_in
- **Пакет:** `qiki.sensors`
- **Messages:** 1, **Enums:** 0, **Services:** 0  
- **Файл:** [protos/sensor_raw_in.proto](protos/sensor_raw_in.proto)

### 3.3. actuator_raw_out
- **Пакет:** `qiki.actuators`
- **Messages:** 1, **Enums:** 1, **Services:** 0  
- **Файл:** [protos/actuator_raw_out.proto](protos/actuator_raw_out.proto)

### 3.4. proposal
- **Пакет:** `qiki.mind`
- **Messages:** 1, **Enums:** 2, **Services:** 0  
- **Файл:** [protos/proposal.proto](protos/proposal.proto)

### 3.5. bios_status
- **Пакет:** `qiki.bios`
- **Messages:** 2, **Enums:** 3, **Services:** 0  
- **Файл:** [protos/bios_status.proto](protos/bios_status.proto)

### 3.6. fsm_state
- **Пакет:** `qiki.fsm`
- **Messages:** 2, **Enums:** 2, **Services:** 0  
- **Файл:** [protos/fsm_state.proto](protos/fsm_state.proto)


---


## 4. Быстрый Старт

```bash
# Запуск демо системы
./scripts/run_qiki_demo.sh

# Или раздельно:
python services/q_sim_service/main.py &
python services/q_core_agent/main.py --mock
```

## 5. Инструменты Разработки

- **qiki-docgen** - генерация документации и protobuf контрактов
- **Protocol Buffers** - типобезопасные контракты между сервисами
- **Automated testing** - интеграционные тесты системы