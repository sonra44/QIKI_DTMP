# services/q_core_agent/state/tests/test_integration.py — анализ по методу «Задачи»

## Назначение файла
Интеграционные тесты взаимодействия FSMHandler и StateStore, включая проверку подписчиков и конвертации данных.

## Основные блоки задач
### 1. `TestFSMHandlerStateStoreIntegration`
- [ ] `test_basic_fsm_processing_with_store` — переход BOOTING → IDLE с записью в стора.
- [ ] `test_fsm_state_sequence` — последовательность переходов и проверка финального состояния.
- [ ] `test_version_monotonicity` — версии должны возрастать монотонно.
- [ ] `test_no_state_change_keeps_version` — отсутствие изменений не увеличивает версию.
- [ ] `test_fsm_handler_without_state_store` — работа FSMHandler без стора.

### 2. `TestStateStoreSubscriberIntegration`
- [ ] `test_subscriber_receives_fsm_updates` — подписчик получает переходы FSM.
- [ ] `test_multiple_subscribers_fsm_updates` — синхронные обновления для нескольких подписчиков.
- [ ] `test_subscriber_stream_consistency` — порядок версий в потоке обновлений.

### 3. `TestConversionIntegration`
- [ ] `test_dto_protobuf_roundtrip_with_real_fsm_data` — проверка roundtrip конвертации DTO ↔ protobuf.
- [ ] `test_json_conversion_with_fsm_history` — преобразование состояния с историей в JSON.

### 4. `TestConcurrentIntegration`
- [ ] `test_concurrent_fsm_processing` — параллельные обработчики FSM обновляют общий StateStore.

## Наблюдения и рекомендации
- Моки контекста и FSMHandler позволяют изолировать тесты от остального ядра.
- При расширении логики переходов важно обновлять сценарии последовательностей и подписчиков.
