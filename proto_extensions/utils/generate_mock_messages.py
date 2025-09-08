import json
import os
from google.protobuf.json_format import MessageToDict
from generated import sensor_raw_in_pb2, actuator_raw_out_pb2, proposal_pb2

MOCK_DIR = "proto_extensions/mocks"


def write_mock(filename, message):
    path = os.path.join(MOCK_DIR, filename)
    with open(path, "w") as f:
        json.dump(MessageToDict(message), f, indent=2)
    print(f"✔ Mock saved: {path}")


def gen_sensor_mock():
    reading = sensor_raw_in_pb2.SensorReading(
        sensor_id="sim_lidar_front", sensor_type=1, scalar_data=3.14
    )
    write_mock("sensor_reading.mock.json", reading)


def gen_actuator_mock():
    command = actuator_raw_out_pb2.ActuatorCommand(
        actuator_id="motor_1", command_type="MOVE_FORWARD", confidence=0.8
    )
    write_mock("actuator_command.mock.json", command)


def gen_proposal_mock():
    proposal = proposal_pb2.Proposal(
        proposal_id=proposal_pb2.UUID(value="uuid-1234"),
        source_module_id="neural_engine",
        priority=5,
        justification="Obstacle detected",
        proposed_actions=[
            actuator_raw_out_pb2.ActuatorCommand(
                actuator_id=actuator_raw_out_pb2.UUID(value="motor_1"),
                command_type="STOP",
            )
        ],
    )
    write_mock("proposal.mock.json", proposal)


if __name__ == "__main__":
    os.makedirs(MOCK_DIR, exist_ok=True)
    gen_sensor_mock()
    gen_actuator_mock()
    gen_proposal_mock()
