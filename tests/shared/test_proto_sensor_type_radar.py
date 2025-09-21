def test_generated_proto_has_radar_enum():
    from generated.common_types_pb2 import SensorType as ProtoSensorType

    assert hasattr(ProtoSensorType, "RADAR"), "RADAR must exist in proto enum"
    # Ensure value matches Python model enum expectation (6)
    assert ProtoSensorType.RADAR == 6

