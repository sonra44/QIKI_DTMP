"""
Integration тесты для StateStore архитектуры.
Проверяют взаимодействие между компонентами: FSMHandler + StateStore + конвертеры.
"""

import pytest
import asyncio
import os
from unittest.mock import Mock, AsyncMock, patch

from ..store import AsyncStateStore, create_initialized_store
from ..types import (
    FsmSnapshotDTO,
    FsmState,
    initial_snapshot,
    next_snapshot,
)
from ..conv import dto_to_proto, proto_to_dto, dto_to_json_dict

# Импорт компонентов для интеграции (мокаем для изоляции от core)


class MockAgentContext:
    """Мок контекста агента для тестирования FSMHandler"""

    def __init__(self):
        self.bios_ok = True
        self.has_proposals = False
        self.fsm_state = None
        self.bios_status = None
        self.proposals = []

    def is_bios_ok(self) -> bool:
        return self.bios_ok

    def has_valid_proposals(self) -> bool:
        return self.has_proposals


class MockFSMHandler:
    """Мок FSMHandler для тестирования интеграции"""

    def __init__(self, context: MockAgentContext, state_store: AsyncStateStore = None):
        self.context = context
        self.state_store = state_store

    async def process_fsm_dto(self, current_dto: FsmSnapshotDTO) -> FsmSnapshotDTO:
        """Упрощённая логика FSM для тестов"""
        bios_ok = self.context.is_bios_ok()
        has_proposals = self.context.has_valid_proposals()

        # Простая логика переходов
        new_state = current_dto.state
        reason = "NO_CHANGE"

        if current_dto.state == FsmState.BOOTING and bios_ok:
            new_state = FsmState.IDLE
            reason = "BOOT_COMPLETE"
        elif current_dto.state == FsmState.IDLE and has_proposals:
            new_state = FsmState.ACTIVE
            reason = "PROPOSALS_RECEIVED"
        elif current_dto.state == FsmState.ACTIVE and not has_proposals:
            new_state = FsmState.IDLE
            reason = "NO_PROPOSALS"
        elif not bios_ok:
            new_state = FsmState.ERROR_STATE
            reason = "BIOS_ERROR"

        # Создаём новый снапшот
        updated_dto = next_snapshot(
            current=current_dto, new_state=new_state, reason=reason
        )

        # Записываем в StateStore
        if self.state_store:
            try:
                stored_dto = await self.state_store.set(updated_dto)
                return stored_dto
            except Exception:
                # Игнорируем проблемы StateStore, возвращаем локальный результат
                return updated_dto

        return updated_dto


@pytest.fixture
def mock_context():
    """Мок контекста агента"""
    return MockAgentContext()


@pytest.fixture
def state_store():
    """StateStore с начальным состоянием"""
    return create_initialized_store()


@pytest.fixture
def fsm_handler(mock_context, state_store):
    """FSMHandler с StateStore"""
    return MockFSMHandler(mock_context, state_store)


class TestFSMHandlerStateStoreIntegration:
    """Интеграционные тесты FSMHandler + StateStore"""

    @pytest.mark.asyncio
    async def test_basic_fsm_processing_with_store(self, fsm_handler, state_store):
        """Тест базовой обработки FSM с записью в StateStore"""
        # Получаем начальное состояние
        initial = await state_store.get()
        assert initial.state == FsmState.BOOTING

        # Обрабатываем переход BOOTING -> IDLE
        result = await fsm_handler.process_fsm_dto(initial)

        assert result.state == FsmState.IDLE
        assert result.reason == "BOOT_COMPLETE"
        assert result.version == 1  # версия увеличилась

        # Проверяем что состояние записалось в StateStore
        stored = await state_store.get()
        assert stored == result
        assert stored.state == FsmState.IDLE

    @pytest.mark.asyncio
    async def test_fsm_state_sequence(self, fsm_handler, state_store, mock_context):
        """Тест последовательности переходов FSM"""
        # 1. BOOTING -> IDLE (BIOS OK)
        initial = await state_store.get()
        mock_context.bios_ok = True
        mock_context.has_proposals = False

        result1 = await fsm_handler.process_fsm_dto(initial)
        assert result1.state == FsmState.IDLE
        assert result1.version == 1

        # 2. IDLE -> ACTIVE (proposals появились)
        mock_context.has_proposals = True

        result2 = await fsm_handler.process_fsm_dto(result1)
        assert result2.state == FsmState.ACTIVE
        assert result2.reason == "PROPOSALS_RECEIVED"
        assert result2.version == 2

        # 3. ACTIVE -> IDLE (proposals исчезли)
        mock_context.has_proposals = False

        result3 = await fsm_handler.process_fsm_dto(result2)
        assert result3.state == FsmState.IDLE
        assert result3.reason == "NO_PROPOSALS"
        assert result3.version == 3

        # 4. IDLE -> ERROR_STATE (BIOS ошибка)
        mock_context.bios_ok = False

        result4 = await fsm_handler.process_fsm_dto(result3)
        assert result4.state == FsmState.ERROR_STATE
        assert result4.reason == "BIOS_ERROR"
        assert result4.version == 4

        # Проверяем финальное состояние в StateStore
        final_stored = await state_store.get()
        assert final_stored == result4

    @pytest.mark.asyncio
    async def test_version_monotonicity(self, fsm_handler, state_store, mock_context):
        """Тест монотонности версий при множественных изменениях"""
        versions = []

        # Серия изменений состояний
        for i in range(10):
            current = await state_store.get()

            # Меняем условия для вызова переходов
            mock_context.has_proposals = i % 2 == 0

            result = await fsm_handler.process_fsm_dto(current)
            versions.append(result.version)

        # Версии должны монотонно возрастать
        assert all(versions[i] <= versions[i + 1] for i in range(len(versions) - 1))
        assert len(set(versions)) > 1  # должны быть разные версии

    @pytest.mark.asyncio
    async def test_no_state_change_keeps_version(
        self, fsm_handler, state_store, mock_context
    ):
        """Тест что отсутствие изменений не увеличивает версию"""
        # Устанавливаем стабильные условия
        mock_context.bios_ok = True
        mock_context.has_proposals = False

        # Первый переход BOOTING -> IDLE
        initial = await state_store.get()
        result1 = await fsm_handler.process_fsm_dto(initial)
        assert result1.state == FsmState.IDLE
        assert result1.version == 1

        # Повторная обработка без изменений условий
        result2 = await fsm_handler.process_fsm_dto(result1)

        # Состояние и версия не должны измениться
        assert result2.state == FsmState.IDLE
        assert result2.version == 1  # версия не увеличилась
        assert result2.reason == "NO_CHANGE"

    @pytest.mark.asyncio
    async def test_fsm_handler_without_state_store(self, mock_context):
        """Тест FSMHandler без StateStore (fallback режим)"""
        # FSMHandler без StateStore
        handler = MockFSMHandler(mock_context, state_store=None)

        initial = initial_snapshot()
        result = await handler.process_fsm_dto(initial)

        # Должно работать, но без записи в StateStore
        assert result.state == FsmState.IDLE  # переход произошёл
        assert result.version == 1


class TestStateStoreSubscriberIntegration:
    """Интеграционные тесты подписчиков StateStore"""

    @pytest.mark.asyncio
    async def test_subscriber_receives_fsm_updates(self, fsm_handler, state_store):
        """Тест что подписчики получают обновления от FSM"""
        # Подписываемся на изменения
        queue = await state_store.subscribe("fsm_test_subscriber")

        # Должно быть начальное состояние
        initial_update = await asyncio.wait_for(queue.get(), timeout=1.0)
        assert initial_update.state == FsmState.BOOTING

        # Выполняем FSM переход
        current = await state_store.get()
        await fsm_handler.process_fsm_dto(current)

        # Подписчик должен получить обновление
        update = await asyncio.wait_for(queue.get(), timeout=1.0)
        assert update.state == FsmState.IDLE
        assert update.reason == "BOOT_COMPLETE"

    @pytest.mark.asyncio
    async def test_multiple_subscribers_fsm_updates(
        self, fsm_handler, state_store, mock_context
    ):
        """Тест множественных подписчиков при FSM обновлениях"""
        # Создаём несколько подписчиков
        queues = []
        for i in range(5):
            queue = await state_store.subscribe(f"subscriber_{i}")
            queues.append(queue)

        # Очищаем начальные сообщения
        for queue in queues:
            await queue.get()  # начальное состояние

        # Выполняем серию FSM переходов
        transitions = [
            (True, False, FsmState.IDLE),  # BOOTING -> IDLE
            (True, True, FsmState.ACTIVE),  # IDLE -> ACTIVE
            (True, False, FsmState.IDLE),  # ACTIVE -> IDLE
        ]

        for bios_ok, has_proposals, expected_state in transitions:
            mock_context.bios_ok = bios_ok
            mock_context.has_proposals = has_proposals

            current = await state_store.get()
            await fsm_handler.process_fsm_dto(current)

            # Все подписчики должны получить обновление
            for i, queue in enumerate(queues):
                update = await asyncio.wait_for(queue.get(), timeout=1.0)
                assert update.state == expected_state, f"Subscriber {i} got wrong state"

    @pytest.mark.asyncio
    async def test_subscriber_stream_consistency(
        self, fsm_handler, state_store, mock_context
    ):
        """Тест согласованности потока обновлений у подписчика"""
        queue = await state_store.subscribe("consistency_test")

        # Очищаем начальное сообщение
        await queue.get()

        received_updates = []

        # Выполняем быструю серию изменений
        for i in range(20):
            mock_context.has_proposals = i % 3 == 0

            current = await state_store.get()
            await fsm_handler.process_fsm_dto(current)

            # Собираем все доступные обновления
            try:
                while True:
                    update = queue.get_nowait()
                    received_updates.append(update)
            except asyncio.QueueEmpty:
                pass

        # Должны получить все обновления в правильном порядке
        assert len(received_updates) > 0

        # Версии должны идти по возрастанию
        versions = [u.version for u in received_updates]
        assert all(versions[i] <= versions[i + 1] for i in range(len(versions) - 1))


class TestConversionIntegration:
    """Интеграционные тесты конвертации с реальными данными"""

    @pytest.mark.asyncio
    async def test_dto_protobuf_roundtrip_with_real_fsm_data(
        self, fsm_handler, state_store, mock_context
    ):
        """Тест roundtrip конвертации с реальными FSM данными"""
        # Выполняем несколько FSM переходов для накопления реальных данных
        mock_context.bios_ok = True
        mock_context.has_proposals = False

        current = await state_store.get()
        result1 = await fsm_handler.process_fsm_dto(current)  # BOOTING -> IDLE

        mock_context.has_proposals = True
        result2 = await fsm_handler.process_fsm_dto(result1)  # IDLE -> ACTIVE

        # Конвертируем в protobuf и обратно
        proto = dto_to_proto(result2)
        converted_back = proto_to_dto(proto)

        # Основные данные должны сохраниться
        assert converted_back.version == result2.version
        assert converted_back.state == result2.state
        assert converted_back.reason == result2.reason
        assert len(converted_back.history) == len(result2.history)

    @pytest.mark.asyncio
    async def test_json_conversion_with_fsm_history(
        self, fsm_handler, state_store, mock_context
    ):
        """Тест JSON конвертации с историей FSM переходов"""
        # Накапливаем историю переходов
        transitions_sequence = [
            (True, False),  # -> IDLE
            (True, True),  # -> ACTIVE
            (True, False),  # -> IDLE
            (False, False),  # -> ERROR_STATE
        ]

        for bios_ok, has_proposals in transitions_sequence:
            mock_context.bios_ok = bios_ok
            mock_context.has_proposals = has_proposals

            current = await state_store.get()
            await fsm_handler.process_fsm_dto(current)

        # Получаем финальное состояние с историей
        final_state = await state_store.get()

        # Конвертируем в JSON
        json_dict = dto_to_json_dict(final_state)

        assert json_dict["state"] == "ERROR_STATE"
        assert json_dict["history_count"] > 0
        assert "version" in json_dict
        assert "ts_mono" in json_dict
        assert "ts_wall" in json_dict

        # JSON должен быть сериализуемым
        import json

        json_str = json.dumps(json_dict)  # не должно упасть
        parsed_back = json.loads(json_str)
        assert parsed_back["state"] == "ERROR_STATE"


class TestConcurrentIntegration:
    """Интеграционные тесты конкурентного доступа между компонентами"""

    @pytest.mark.asyncio
    async def test_concurrent_fsm_processing(self, mock_context, state_store):
        """Тест конкурентной обработки FSM от нескольких handlers"""
        # Создаём несколько FSM handlers
        handlers = [MockFSMHandler(mock_context, state_store) for _ in range(5)]

        async def process_transitions(handler, handler_id):
            """Выполняет серию переходов от одного handler'а"""
            for i in range(10):
                current = await state_store.get()

                # Небольшая вариация условий
                mock_context.has_proposals = (handler_id + i) % 2 == 0

                await handler.process_fsm_dto(current)
                await asyncio.sleep(0.001)  # небольшая пауза

        # Запускаем конкурентную обработку
        tasks = [process_transitions(handler, i) for i, handler in enumerate(handlers)]
        await asyncio.gather(*tasks)

        # Проверяем финальное состояние
        final_state = await state_store.get()
        assert final_state is not None
        assert final_state.version > 0

        # Метрики должны отражать активность
        metrics = await state_store.get_metrics()
        assert metrics["total_sets"] >= 50  # минимум от всех handlers

    @pytest.mark.asyncio
    async def test_concurrent_subscribers_and_fsm(
        self, fsm_handler, state_store, mock_context
    ):
        """Тест конкурентных подписчиков во время FSM обработки"""
        # Запускаем подписчиков
        subscriber_results = []

        async def subscriber_task(subscriber_id):
            """Задача подписчика - собирает все обновления"""
            queue = await state_store.subscribe(f"concurrent_sub_{subscriber_id}")
            updates = []

            try:
                # Собираем обновления в течение времени теста
                while len(updates) < 10:  # ожидаем несколько обновлений
                    update = await asyncio.wait_for(queue.get(), timeout=2.0)
                    updates.append(update)
            except asyncio.TimeoutError:
                pass

            subscriber_results.append((subscriber_id, updates))

        async def fsm_processing_task():
            """Задача FSM - выполняет переходы"""
            for i in range(15):
                mock_context.bios_ok = i % 3 != 2  # иногда BIOS падает
                mock_context.has_proposals = i % 2 == 0

                current = await state_store.get()
                await fsm_handler.process_fsm_dto(current)
                await asyncio.sleep(0.05)

        # Запускаем всё конкурентно
        await asyncio.gather(
            subscriber_task(0),
            subscriber_task(1),
            subscriber_task(2),
            fsm_processing_task(),
        )

        # Все подписчики должны получить обновления
        assert len(subscriber_results) == 3
        for sub_id, updates in subscriber_results:
            assert len(updates) > 0, f"Subscriber {sub_id} got no updates"

            # Проверяем монотонность версий
            versions = [u.version for u in updates]
            assert all(versions[i] <= versions[i + 1] for i in range(len(versions) - 1))


class TestErrorHandlingIntegration:
    """Интеграционные тесты обработки ошибок"""

    @pytest.mark.asyncio
    async def test_state_store_failure_recovery(self, mock_context):
        """Тест восстановления при сбоях StateStore"""
        # Создаём StateStore который иногда падает
        store = AsyncStateStore()
        handler = MockFSMHandler(mock_context, store)

        # Мокаем store.set чтобы иногда падал
        original_set = store.set
        call_count = 0

        async def failing_set(snapshot):
            nonlocal call_count
            call_count += 1
            if call_count == 2:  # второй вызов падает
                raise Exception("StateStore failure simulation")
            return await original_set(snapshot)

        store.set = failing_set

        # Выполняем серию операций
        current = await store.initialize_if_empty()

        # Первая операция должна пройти
        result1 = await handler.process_fsm_dto(current)
        assert result1.state == FsmState.IDLE

        # Вторая операция упадёт в StateStore, но FSMHandler должен обработать
        mock_context.has_proposals = True
        result2 = await handler.process_fsm_dto(result1)
        assert result2.state == FsmState.ACTIVE  # переход всё равно произошёл

        # StateStore может быть в несогласованном состоянии
        stored = await store.get()
        # Может не совпадать с result2 из-за ошибки записи

    @pytest.mark.asyncio
    async def test_conversion_error_handling(self, state_store):
        """Тест обработки ошибок конвертации в интеграции"""
        # Создаём снапшот с проблемными данными
        problematic_dto = FsmSnapshotDTO(
            version=1,
            state=FsmState.IDLE,
            reason="Test" * 10000,  # очень длинная строка
            context_data={
                f"key_{i}": f"value_{i}" * 100 for i in range(1000)
            },  # много данных
        )

        await state_store.set(problematic_dto)

        # Конвертация должна работать даже с большими данными
        retrieved = await state_store.get()
        proto = dto_to_proto(retrieved)

        assert proto.current_state == dto_to_proto(problematic_dto).current_state

        # JSON конвертация должна быть безопасной
        json_dict = dto_to_json_dict(retrieved)
        assert "version" in json_dict

    @pytest.mark.asyncio
    async def test_subscriber_error_isolation(self, fsm_handler, state_store):
        """Тест изоляции ошибок подписчиков"""
        # Создаём нормального подписчика
        good_queue = await state_store.subscribe("good_subscriber")

        # Создаём "плохого" подписчика (мок который падает)
        bad_queue = Mock()
        bad_queue.put_nowait = Mock(side_effect=Exception("Subscriber error"))

        # Добавляем плохого подписчика напрямую
        async with state_store._lock:
            state_store._subscribers.append(bad_queue)
            state_store._subscriber_ids[id(bad_queue)] = "bad_subscriber"

        # Очищаем начальные сообщения у хорошего подписчика
        await good_queue.get()

        # Выполняем FSM операцию
        current = await state_store.get()
        await fsm_handler.process_fsm_dto(current)

        # Хороший подписчик должен получить обновление несмотря на плохого
        update = await asyncio.wait_for(good_queue.get(), timeout=1.0)
        assert update.state == FsmState.IDLE

        # Плохой подписчик должен быть удалён
        async with state_store._lock:
            assert bad_queue not in state_store._subscribers


class TestFeatureFlagIntegration:
    """Интеграционные тесты с feature флагами"""

    @pytest.mark.asyncio
    async def test_state_store_enable_disable(self, mock_context):
        """Тест включения/выключения StateStore через переменную окружения"""
        store = AsyncStateStore()

        # Тест с включённым StateStore
        with patch.dict(os.environ, {"QIKI_USE_STATESTORE": "true"}):
            handler = MockFSMHandler(mock_context, store)

            initial = await store.initialize_if_empty()
            result = await handler.process_fsm_dto(initial)

            # Результат должен быть записан в StateStore
            stored = await store.get()
            assert stored == result

        # Тест с отключённым StateStore
        with patch.dict(os.environ, {"QIKI_USE_STATESTORE": "false"}):
            handler_disabled = MockFSMHandler(mock_context, None)

            result_disabled = await handler_disabled.process_fsm_dto(initial)

            # StateStore не должен обновляться
            stored_after = await store.get()
            assert stored_after == stored  # не изменился

    @pytest.mark.asyncio
    async def test_graceful_degradation(self, mock_context):
        """Тест плавной деградации при проблемах с StateStore"""
        # Создаём "сломанный" StateStore
        broken_store = Mock(spec=AsyncStateStore)
        broken_store.set = AsyncMock(side_effect=Exception("Store is broken"))
        broken_store.get = AsyncMock(return_value=None)

        handler = MockFSMHandler(mock_context, broken_store)

        # Обработка должна работать даже со сломанным StateStore
        initial = initial_snapshot()
        result = await handler.process_fsm_dto(initial)

        # FSM переход должен произойти
        assert result.state == FsmState.IDLE
        assert result.reason == "BOOT_COMPLETE"

        # StateStore.set был вызван, но упал
        broken_store.set.assert_called_once()


if __name__ == "__main__":
    # Запуск интеграционных тестов
    pytest.main([__file__, "-v", "-s", "--tb=short"])
