# Анализ: services/q_core_agent/core/bios_handler.py

## Вход и цель
- [Факт] Проанализировать класс `BiosHandler`, обрабатывающий отчёты BIOS.

## Сбор контекста
- [Факт] Импортирует `IBiosHandler`, `logger`, `BotCore` и protobuf-сообщения `BiosStatusReport`, `DeviceStatus`, `UUID`.
- [Факт] Предполагает наличие hardware_profile в конфиге через `BotCore.get_property`.
- [Гипотеза] `IBiosHandler` определяет интерфейс с методом `process_bios_status`.

## Локализация артефакта
- [Факт] Путь: `services/q_core_agent/core/bios_handler.py`.
- [Факт] Используется в Python 3, вызывается из `QCoreAgent`.

## Фактический разбор
- [Факт] Конструктор принимает `BotCore` и логирует инициализацию.
- [Факт] `process_bios_status` копирует входной `BiosStatusReport`, проверяет устройства из `hardware_profile` и дополняет отсутствующие.
- [Факт] При отсутствии профиля выводит предупреждение и считает систему минимальной.
- [Факт] Возвращает обновлённый `BiosStatusReport` с полем `all_systems_go`.

## Роль в системе и связи
- [Факт] Сопоставляет ожидаемые устройства с фактическим отчётом BIOS.
- [Гипотеза] Результат влияет на дальнейшую инициализацию агента.

## Несоответствия и риски
- [Гипотеза] Нет обработки дубликатов `post_results`, возможны повторяющиеся статусы (Low).
- [Гипотеза] Возможен `KeyError`, если структура hardware_profile неожиданна (Med).

## Мини-патчи (safe-fix)
- [Патч] Проверять структуру `hardware_profile` перед использованием и логировать ошибки.
- [Патч] Отфильтровать дубли по `device_id` при добавлении `missing_device_status`.

## Рефактор-скетч (по желанию)
```python
class BiosHandler(IBiosHandler):
    def __init__(self, bot_core: BotCore):
        self.bot_core = bot_core
        self.log = logger

    def process_bios_status(self, report: BiosStatusReport) -> BiosStatusReport:
        updated = BiosStatusReport()
        updated.CopyFrom(report)
        expected = {d["id"] for d in self.bot_core.get_property("hardware_profile") or {}}
        seen = {ds.device_id.value for ds in report.post_results}
        for dev in expected - seen:
            updated.post_results.append(
                DeviceStatus(device_id=UUID(value=dev),
                             status=DeviceStatus.Status.NOT_FOUND,
                             status_code=DeviceStatus.StatusCode.COMPONENT_NOT_FOUND,
                             error_message="Device not reported by BIOS")
            )
        updated.all_systems_go = all(ds.status == DeviceStatus.Status.OK for ds in updated.post_results)
        return updated
```

## Примеры использования
```python
handler = BiosHandler(bot_core)
result = handler.process_bios_status(BiosStatusReport())
print(result.all_systems_go)
```

## Тест-хуки/чек-лист
- [Факт] Сценарий без hardware_profile — ожидается `all_systems_go=True` и предупреждение.
- [Факт] Отчёт с отсутствующим устройством — в `post_results` появляется статус `NOT_FOUND`.

## Вывод
- [Факт] Класс сравнивает BIOS-отчёт с конфигурацией и добавляет сведения о пропавших устройствах.
- [Патч] Нужна валидация структуры профиля и фильтрация дубликатов.
