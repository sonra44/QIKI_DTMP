"""M4: конверт v2 — схема-валидация, диспатч версий, сквозной request_id."""

from __future__ import annotations

import time
from uuid import uuid4

import pytest
from pydantic import ValidationError

from qiki.shared.models.qiki_chat import QikiChatInput, QikiChatRequestV1, QikiChatResponseV1, QikiMode
from qiki.shared.models.qiki_chat_v2 import (
    AuthContext,
    DecisionPreview,
    EvidenceContext,
    EvidenceSourceType,
    QikiChatRequestV2,
    QikiChatResponseV2,
    ResponseEvidence,
    RuntimeClaimStatus,
    parse_chat_request,
    parse_chat_response,
    upgrade_response_to_v2,
)


def _v1_request() -> QikiChatRequestV1:
    return QikiChatRequestV1(
        request_id=uuid4(),
        ts_epoch_ms=int(time.time() * 1000),
        mode_hint=QikiMode.FACTORY,
        input=QikiChatInput(text="доложи состояние"),
    )


def _v2_request() -> QikiChatRequestV2:
    return QikiChatRequestV2(
        request_id=uuid4(),
        ts_epoch_ms=int(time.time() * 1000),
        mode_hint=QikiMode.FACTORY,
        input=QikiChatInput(text="доложи состояние"),
        auth_context=AuthContext(
            subject="operator_console.orion_v",
            session="sess-1",
            scopes=["qiki.intents.publish"],
            token_id="tk_abc123",
        ),
        evidence_context=EvidenceContext(sensor_trust="degraded", source="orion_v"),
        command_intent_class="observation",
    )


def test_v2_request_roundtrip_schema():
    req = _v2_request()
    payload = req.model_dump(mode="json")
    parsed = parse_chat_request(payload)
    assert isinstance(parsed, QikiChatRequestV2)
    assert parsed.request_id == req.request_id  # сквозной request_id
    assert parsed.auth_context is not None and parsed.auth_context.token_id == "tk_abc123"
    assert parsed.evidence_context.sensor_trust == "degraded"


def test_dispatch_v1_payload_returns_v1():
    payload = _v1_request().model_dump(mode="json")
    parsed = parse_chat_request(payload)
    assert type(parsed) is QikiChatRequestV1
    assert parsed.version == 1


def test_v1_parser_rejects_v2_payload_by_design():
    """extra=forbid у v1 — осознанно: v2 не должен маскироваться под v1."""
    payload = _v2_request().model_dump(mode="json")
    with pytest.raises(ValidationError):
        QikiChatRequestV1.model_validate(payload)


def test_upgrade_response_preserves_request_id_and_content():
    v1_resp = QikiChatResponseV1(
        request_id=uuid4(),
        ok=True,
        mode=QikiMode.FACTORY,
        reply=None,
        proposals=[],
    )
    evidence = ResponseEvidence(
        source_type=EvidenceSourceType.DERIVED,
        source_id="q_core_intents",
        trust_status="trusted",
        freshness="unknown",
        runtime_claim_status=RuntimeClaimStatus.CANDIDATE_ONLY,
    )
    v2 = upgrade_response_to_v2(v1_resp, evidence=evidence,
                                decision_preview=DecisionPreview(validation_layers=["trust"], next_step="q confirm"))
    assert v2.version == 2
    assert v2.request_id == v1_resp.request_id  # сквозной request_id
    assert v2.ok is True
    assert v2.evidence.runtime_claim_status is RuntimeClaimStatus.CANDIDATE_ONLY
    # v2-ответ парсится диспатчем:
    parsed = parse_chat_response(v2.model_dump(mode="json"))
    assert isinstance(parsed, QikiChatResponseV2)
    assert parsed.evidence.source_type is EvidenceSourceType.DERIVED


def test_response_dispatch_v1_still_v1():
    v1_resp = QikiChatResponseV1(request_id=uuid4(), ok=True, mode=QikiMode.FACTORY)
    parsed = parse_chat_response(v1_resp.model_dump(mode="json"))
    assert type(parsed) is QikiChatResponseV1


def test_forbidden_enum_values_rejected():
    """ADR-0017: seed_only/provider_candidate запрещены схемой."""
    with pytest.raises(ValueError):
        RuntimeClaimStatus("seed_only")
    with pytest.raises(ValueError):
        RuntimeClaimStatus("provider_candidate")


def test_trust_vocabulary_is_canon_15_5():
    """Словарь доверия строго §15.5 (+fixture_only) — левые значения падают."""
    with pytest.raises(ValidationError):
        EvidenceContext(sensor_trust="provider_trusted")
    ok = EvidenceContext(sensor_trust="local_reconstruction")
    assert ok.sensor_trust == "local_reconstruction"


def test_provider_source_type_exists_per_adr_0017():
    assert EvidenceSourceType.PROVIDER.value == "provider"
