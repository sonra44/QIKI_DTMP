"""
Серьёзные unit тесты для DTO типов StateStore.
Проверяют immutability, создание снапшотов, переходы состояний.
"""

import pytest
import time
import uuid
from dataclasses import FrozenInstanceError

from ..types import (
    FsmSnapshotDTO,
    TransitionDTO,
    FsmState,
    TransitionStatus,
    initial_snapshot,
    create_transition,
    next_snapshot,
)


class TestFsmState:
    """Тесты enum'а FsmState"""

    def test_fsm_state_values(self):
        """Проверяем корректность значений enum"""
        assert FsmState.UNSPECIFIED == 0
        assert FsmState.BOOTING == 1
        assert FsmState.IDLE == 2
        assert FsmState.ACTIVE == 3
        assert FsmState.ERROR_STATE == 4
        assert FsmState.SHUTDOWN == 5

    def test_fsm_state_names(self):
        """Проверяем корректность имён enum"""
        assert FsmState.BOOTING.name == "BOOTING"
        assert FsmState.IDLE.name == "IDLE"
        assert FsmState.ACTIVE.name == "ACTIVE"
        assert FsmState.ERROR_STATE.name == "ERROR_STATE"


class TestTransitionDTO:
    """Тесты TransitionDTO - immutable переходы состояний"""

    def test_transition_creation(self):
        """Тест создания перехода"""
        transition = TransitionDTO(
            from_state=FsmState.BOOTING,
            to_state=FsmState.IDLE,
            trigger_event="BOOT_COMPLETE",
            status=TransitionStatus.SUCCESS,
        )

        assert transition.from_state == FsmState.BOOTING
        assert transition.to_state == FsmState.IDLE
        assert transition.trigger_event == "BOOT_COMPLETE"
        assert transition.status == TransitionStatus.SUCCESS
        assert transition.ts_mono > 0  # автоустановка времени
        assert transition.ts_wall > 0

    def test_transition_immutability(self):
        """Тест неизменяемости TransitionDTO"""
        transition = TransitionDTO(
            from_state=FsmState.IDLE, to_state=FsmState.ACTIVE, trigger_event="TEST"
        )

        # Попытка изменения должна упасть
        with pytest.raises(FrozenInstanceError):
            transition.from_state = FsmState.BOOTING

        with pytest.raises(FrozenInstanceError):
            transition.trigger_event = "MODIFIED"

    def test_transition_with_error(self):
        """Тест перехода с ошибкой"""
        transition = TransitionDTO(
            from_state=FsmState.IDLE,
            to_state=FsmState.ERROR_STATE,
            trigger_event="BIOS_ERROR",
            status=TransitionStatus.FAILED,
            error_message="BIOS check failed",
        )

        assert transition.status == TransitionStatus.FAILED
        assert transition.error_message == "BIOS check failed"

    def test_create_transition_helper(self):
        """Тест helper функции create_transition"""
        transition = create_transition(
            from_state=FsmState.ACTIVE,
            to_state=FsmState.IDLE,
            trigger="NO_PROPOSALS",
            status=TransitionStatus.SUCCESS,
            error_msg="",
        )

        assert isinstance(transition, TransitionDTO)
        assert transition.from_state == FsmState.ACTIVE
        assert transition.to_state == FsmState.IDLE
        assert transition.trigger_event == "NO_PROPOSALS"


class TestFsmSnapshotDTO:
    """Тесты FsmSnapshotDTO - основной DTO для состояния FSM"""

    def test_snapshot_creation(self):
        """Тест создания снапшота"""
        snapshot = FsmSnapshotDTO(version=1, state=FsmState.IDLE, reason="TEST_REASON")

        assert snapshot.version == 1
        assert snapshot.state == FsmState.IDLE
        assert snapshot.reason == "TEST_REASON"
        assert snapshot.ts_mono > 0  # автоустановка времени
        assert snapshot.ts_wall > 0
        assert snapshot.snapshot_id  # автогенерация UUID
        assert snapshot.fsm_instance_id

    def test_snapshot_immutability(self):
        """Тест неизменяемости FsmSnapshotDTO"""
        snapshot = FsmSnapshotDTO(version=1, state=FsmState.IDLE)

        # Попытка изменения должна упасть
        with pytest.raises(FrozenInstanceError):
            snapshot.version = 2

        with pytest.raises(FrozenInstanceError):
            snapshot.state = FsmState.ACTIVE

    def test_snapshot_with_history(self):
        """Тест снапшота с историей переходов"""
        transition1 = create_transition(
            FsmState.BOOTING, FsmState.IDLE, "BOOT_COMPLETE"
        )
        transition2 = create_transition(
            FsmState.IDLE, FsmState.ACTIVE, "PROPOSALS_RECEIVED"
        )

        snapshot = FsmSnapshotDTO(
            version=2, state=FsmState.ACTIVE, history=[transition1, transition2]
        )

        assert len(snapshot.history) == 2
        assert snapshot.history[0] == transition1
        assert snapshot.history[1] == transition2

        # История immutable
        with pytest.raises(AttributeError):
            snapshot.history.append(transition1)

    def test_snapshot_with_metadata(self):
        """Тест снапшота с метаданными"""
        context_data = {"sensor_count": "5", "proposal_count": "3"}
        state_metadata = {"debug_mode": "true", "test_run": "false"}

        snapshot = FsmSnapshotDTO(
            version=1,
            state=FsmState.ACTIVE,
            context_data=context_data,
            state_metadata=state_metadata,
        )

        assert snapshot.context_data == context_data
        assert snapshot.state_metadata == state_metadata

    def test_snapshot_defaults(self):
        """Тест значений по умолчанию"""
        snapshot = FsmSnapshotDTO(version=0, state=FsmState.BOOTING)

        assert snapshot.prev_state is None
        assert snapshot.source_module == "fsm_handler"
        assert snapshot.attempt_count == 0
        assert snapshot.history == []
        assert snapshot.context_data == {}
        assert snapshot.state_metadata == {}

    def test_snapshot_uuid_validation(self):
        """Тест генерации и валидации UUID"""
        snapshot = FsmSnapshotDTO(version=1, state=FsmState.IDLE)

        # UUID должны быть валидными
        uuid.UUID(snapshot.snapshot_id)  # не должно упасть
        uuid.UUID(snapshot.fsm_instance_id)  # не должно упасть

        # UUID должны быть уникальными
        snapshot2 = FsmSnapshotDTO(version=1, state=FsmState.IDLE)
        assert snapshot.snapshot_id != snapshot2.snapshot_id
        assert snapshot.fsm_instance_id != snapshot2.fsm_instance_id


class TestInitialSnapshot:
    """Тесты функции initial_snapshot"""

    def test_initial_snapshot_creation(self):
        """Тест создания начального снапшота"""
        snapshot = initial_snapshot()

        assert snapshot.version == 0
        assert snapshot.state == FsmState.BOOTING
        assert snapshot.prev_state is None
        assert snapshot.reason == "COLD_START"
        assert snapshot.source_module == "initial_boot"
        assert snapshot.attempt_count == 0

    def test_initial_snapshot_immutability(self):
        """Тест неизменяемости начального снапшота"""
        snapshot = initial_snapshot()

        with pytest.raises(FrozenInstanceError):
            snapshot.version = 1

        with pytest.raises(FrozenInstanceError):
            snapshot.state = FsmState.IDLE

    def test_initial_snapshot_timing(self):
        """Тест временных меток начального снапшота"""
        before = time.time()
        snapshot = initial_snapshot()
        after = time.time()

        # Времена должны быть в разумных пределах
        assert before <= snapshot.ts_wall <= after
        assert snapshot.ts_mono > 0


class TestNextSnapshot:
    """Тесты функции next_snapshot - ключевая для переходов"""

    def test_state_change_increments_version(self):
        """Тест инкремента версии при изменении состояния"""
        current = FsmSnapshotDTO(version=1, state=FsmState.BOOTING)

        next_snap = next_snapshot(
            current=current, new_state=FsmState.IDLE, reason="BOOT_COMPLETE"
        )

        assert next_snap.version == 2  # версия увеличилась
        assert next_snap.state == FsmState.IDLE
        assert next_snap.prev_state == FsmState.BOOTING
        assert next_snap.reason == "BOOT_COMPLETE"
        assert next_snap.attempt_count == 1  # попытка увеличилась

    def test_no_state_change_keeps_version(self):
        """Тест сохранения версии при отсутствии изменений"""
        current = FsmSnapshotDTO(version=5, state=FsmState.IDLE)

        next_snap = next_snapshot(
            current=current,
            new_state=FsmState.IDLE,  # то же состояние
            reason="NO_CHANGE",
        )

        assert next_snap.version == 5  # версия не изменилась
        assert next_snap.state == FsmState.IDLE
        assert next_snap.prev_state == current.prev_state  # сохранилось предыдущее
        assert next_snap.attempt_count == current.attempt_count  # не увеличилось

    def test_next_snapshot_with_transition(self):
        """Тест создания следующего снапшота с переходом"""
        current = FsmSnapshotDTO(version=2, state=FsmState.IDLE)
        transition = create_transition(
            FsmState.IDLE, FsmState.ACTIVE, "PROPOSALS_RECEIVED"
        )

        next_snap = next_snapshot(
            current=current,
            new_state=FsmState.ACTIVE,
            reason="PROPOSALS_RECEIVED",
            transition=transition,
        )

        assert len(next_snap.history) == len(current.history) + 1
        assert next_snap.history[-1] == transition  # переход добавлен в конец

    def test_next_snapshot_preserves_instance_id(self):
        """Тест сохранения instance_id между снапшотами"""
        instance_id = str(uuid.uuid4())
        current = FsmSnapshotDTO(
            version=1, state=FsmState.IDLE, fsm_instance_id=instance_id
        )

        next_snap = next_snapshot(
            current=current, new_state=FsmState.ACTIVE, reason="STATE_CHANGE"
        )

        assert next_snap.fsm_instance_id == instance_id  # сохранился
        assert next_snap.snapshot_id != current.snapshot_id  # но snapshot_id новый

    def test_next_snapshot_preserves_metadata(self):
        """Тест сохранения метаданных между снапшотами"""
        context_data = {"key1": "value1"}
        state_metadata = {"key2": "value2"}

        current = FsmSnapshotDTO(
            version=1,
            state=FsmState.IDLE,
            context_data=context_data,
            state_metadata=state_metadata,
        )

        next_snap = next_snapshot(
            current=current, new_state=FsmState.ACTIVE, reason="CHANGE"
        )

        # Метаданные скопированы (но это новые dict'ы)
        assert next_snap.context_data == context_data
        assert next_snap.state_metadata == state_metadata
        assert next_snap.context_data is not current.context_data  # новый объект
        assert next_snap.state_metadata is not current.state_metadata  # новый объект


class TestEdgeCases:
    """Тесты граничных случаев и ошибок"""

    def test_empty_strings_and_none_values(self):
        """Тест обработки пустых строк и None значений"""
        snapshot = FsmSnapshotDTO(
            version=0,
            state=FsmState.IDLE,
            reason="",  # пустая строка
            snapshot_id="",  # пустая строка -> должна автогенерироваться
            prev_state=None,  # None значение
            history=None,  # None -> должен стать []
            context_data=None,  # None -> должен стать {}
        )

        assert snapshot.reason == ""
        assert snapshot.snapshot_id  # автогенерированный UUID
        assert snapshot.prev_state is None
        assert snapshot.history == []
        assert snapshot.context_data == {}

    def test_large_history_handling(self):
        """Тест обработки большой истории переходов"""
        # Создаём большую историю переходов
        large_history = [
            create_transition(FsmState.IDLE, FsmState.ACTIVE, f"EVENT_{i}")
            for i in range(1000)
        ]

        snapshot = FsmSnapshotDTO(
            version=1000, state=FsmState.ACTIVE, history=large_history
        )

        assert len(snapshot.history) == 1000
        assert all(isinstance(t, TransitionDTO) for t in snapshot.history)

    def test_version_overflow_behavior(self):
        """Тест поведения при больших номерах версий"""
        large_version = 2**63 - 1  # максимальный int64

        snapshot = FsmSnapshotDTO(version=large_version, state=FsmState.IDLE)

        # Следующий снапшот должен обработать overflow корректно
        # (в Python int'ы не переполняются, но тестируем логику)
        next_snap = next_snapshot(
            current=snapshot, new_state=FsmState.ACTIVE, reason="TEST"
        )

        assert next_snap.version == large_version + 1

    def test_unicode_strings(self):
        """Тест обработки unicode строк"""
        unicode_reason = "Причина на русском 🚀"
        unicode_trigger = "事件_中文"

        snapshot = FsmSnapshotDTO(version=1, state=FsmState.IDLE, reason=unicode_reason)

        transition = create_transition(FsmState.IDLE, FsmState.ACTIVE, unicode_trigger)

        assert snapshot.reason == unicode_reason
        assert transition.trigger_event == unicode_trigger

        # Должно работать с next_snapshot
        next_snap = next_snapshot(
            current=snapshot,
            new_state=FsmState.ACTIVE,
            reason=unicode_reason,
            transition=transition,
        )

        assert next_snap.reason == unicode_reason
