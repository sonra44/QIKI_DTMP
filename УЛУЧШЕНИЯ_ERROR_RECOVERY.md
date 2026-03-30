# Улучшения Error Recovery и Graceful Degradation

## Текущее Состояние
✅ **Хорошо реализовано:**
- SIGINT/SIGTERM graceful shutdown
- BIOS fail → SAFE_MODE переход
- FSM error state recovery
- Timeout в тестах

## Рекомендуемые Улучшения

### 1. Retry Механизмы
**Текущий код:**
```python
# В actuator_raw_out.proto уже есть:
int32 retry_count = 13;
int32 timeout_ms = 11;
```

**Реализовать в коде:**
```python
async def send_actuator_command_with_retry(command, max_retries=3):
    for attempt in range(max_retries):
        try:
            return await send_actuator_command(command)
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            await asyncio.sleep(0.5 * (2 ** attempt))  # Exponential backoff
```

### 2. Circuit Breaker Pattern
```python
class CircuitBreaker:
    def __init__(self, failure_threshold=5, timeout=30):
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.last_failure_time = None
        self.state = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN
```

### 3. Health Monitoring Improvements
**Добавить к BiosStatusReport:**
```python
# Расширить health_score логику:
- CPU usage monitoring
- Memory usage tracking  
- Network connectivity checks
- Disk space monitoring
```

### 4. Fallback Data Providers
```python
class FallbackDataProvider(IDataProvider):
    def __init__(self, primary_provider, fallback_provider):
        self.primary = primary_provider
        self.fallback = fallback_provider
        self.using_fallback = False
    
    def get_sensor_data(self):
        try:
            if not self.using_fallback:
                return self.primary.get_sensor_data()
        except Exception:
            self.using_fallback = True
        
        return self.fallback.get_sensor_data()
```

### 5. Error State Persistence
```python
# Сохранение состояния ошибки для recovery:
class ErrorStateManager:
    def save_error_state(self, error_context):
        # Записать в файл/БД для восстановления после перезапуска
        pass
    
    def restore_error_state(self):
        # Восстановить состояние после перезапуска
        pass
```

### 6. Progressive Degradation
```python
class DegradationLevels:
    NORMAL = 0      # Все системы работают
    LIMITED = 1     # Отключены не критичные функции  
    ESSENTIAL = 2   # Только жизненно важные системы
    EMERGENCY = 3   # Минимальный набор для безопасности
```

## Приоритеты Реализации

### Высокий приоритет:
1. **Actuator command retry** - уже есть поля в protobuf
2. **Health monitoring expansion** - улучшить health_score логику
3. **Fallback data providers** - простая реализация

### Средний приоритет:
4. **Circuit breaker** - для внешних зависимостей
5. **Error state persistence** - для recovery после рестартов

### Низкий приоритет:
6. **Progressive degradation** - сложная логика, нужна для критичных систем

## Статус
✅ Базовый error recovery работает
🔧 Рекомендуется реализовать retry механизмы и health monitoring
⚠️ Не критично для текущей функциональности