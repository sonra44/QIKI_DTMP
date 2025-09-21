from qiki.services.q_sim_service.main import QSimService
from qiki.services.q_sim_service.grpc_server import QSimGrpcServicer
from qiki.shared.config_models import QSimServiceConfig
from generated.q_sim_api_pb2 import GetRadarFrameRequest, GetRadarFrameResponse
from generated.radar.v1.radar_pb2 import RadarFrame as ProtoRadarFrame


class _DummyCtx:
    def set_code(self, *args, **kwargs):  # pragma: no cover - noop
        pass

    def set_details(self, *args, **kwargs):  # pragma: no cover - noop
        pass


def test_servicer_get_radar_frame_returns_proto():
    cfg = QSimServiceConfig(sim_tick_interval=1, sim_sensor_type=1, log_level="INFO")
    qsim = QSimService(cfg)
    servicer = QSimGrpcServicer(qsim)

    out = servicer.GetRadarFrame(GetRadarFrameRequest(), _DummyCtx())
    assert isinstance(out, GetRadarFrameResponse)
    assert out.HasField("frame")
    assert isinstance(out.frame, ProtoRadarFrame)
