import sys
from pathlib import Path

# Добавляем корень проекта в sys.path, чтобы можно было импортировать контроллеры
sys.path.append(str(Path(__file__).resolve().parents[1]))

from controllers.actuator_controller import ActuatorController
from controllers.fsm_handler import FSMHandler


def test_actuator_success():
    controller = ActuatorController()
    result = controller.set_thrust(0.5)
    assert result.success
    assert result.data == {"value": 0.5}


def test_actuator_invalid_thrust():
    controller = ActuatorController()
    result = controller.set_thrust(-1)
    assert not result.success
    assert result.error_code == "INVALID_THRUST"
    assert "Thrust" in result.message

def test_actuator_thrust_above_upper_bound():
    controller = ActuatorController()
    result = controller.set_thrust(1.1)
    assert not result.success
    assert result.error_code == "INVALID_THRUST"
    assert "Thrust" in result.message


def test_fsm_transition_success():
    handler = FSMHandler()
    result = handler.transition("RUNNING")
    assert result.success
    assert handler.state == "RUNNING"


def test_fsm_invalid_state():
    handler = FSMHandler()
    result = handler.transition("UNKNOWN")
    assert not result.success
    assert result.error_code == "INVALID_STATE"
    assert "Unknown state" in result.message
