"""P2 (ADR-0019): парсер «установи <модуль> на <гнездо>» + полный шаблон в пломбу.

Матч — только module_id / однозначный префикс / класс (RU-синонимы policy);
display_name_ru в матче не участвует. Негативы — с кодами, без выдумок.
"""

from __future__ import annotations

from uuid import uuid4

from qiki.services.q_core_agent.qiki_orion_intents_service import _build_attach_module_response
from qiki.shared.models.qiki_chat import QikiChatInput, QikiChatRequestV1, QikiMode
from qiki.shared.module_catalog import CATALOG_UNAVAILABLE, CatalogEntry, CatalogResult


def _entry(module_id: str, module_class: str, quantity: int = 1, damaged: bool = False) -> CatalogEntry:
    return CatalogEntry(
        module_id=module_id,
        module_class=module_class,
        provided_capabilities=("cap",),
        display_name_ru="Имя (не участвует в матче)",
        quantity=quantity,
        passport_damaged=damaged,
    )


CATALOG = CatalogResult(
    (
        _entry("test_sensor_module_001", "sensor", quantity=2),
        _entry("comm_antenna_module_001", "antenna"),
        _entry("science_probe_module_001", "science"),
        _entry("rcs_cluster_module_001", "rcs-cluster"),
        _entry("salvage_sensor_damaged_001", "sensor", damaged=True),
    )
)


def _resp(text: str, catalog: CatalogResult = CATALOG):
    req = QikiChatRequestV1(request_id=uuid4(), ts_epoch_ms=0, input=QikiChatInput(text=text))
    return _build_attach_module_response(req=req, mode=QikiMode.FACTORY, catalog=catalog)


def _action(resp):
    return resp.proposals[0].proposed_actions[0]


def test_exact_id_and_mount() -> None:
    resp = _resp("установи comm_antenna_module_001 на F03")
    assert resp.legality.status == "allowed"
    action = _action(resp)
    assert action.parameters["module_id"] == "comm_antenna_module_001"
    assert action.parameters["mount"] == "F03"


def test_class_synonym_unambiguous() -> None:
    resp = _resp("установи антенну на F00")
    assert _action(resp).parameters["module_id"] == "comm_antenna_module_001"


def test_class_synonym_ambiguous_asks_for_id() -> None:
    resp = _resp("установи сенсор на F02")  # два sensor-модуля в отсеке
    assert resp.legality.status == "deferred"
    assert resp.legality.reason_code == "MODULE_AMBIGUOUS"
    assert resp.proposals == []


def test_default_module_keeps_b2_behavior() -> None:
    resp = _resp("установи модуль")
    action = _action(resp)
    assert action.parameters["module_id"] == "test_sensor_module_001"
    assert action.parameters["mount"] == "F06"


def test_unknown_mount_blocked_with_body_code() -> None:
    resp = _resp("установи антенну на F42")
    assert resp.legality.status == "blocked"
    assert resp.legality.reason_code == "MOUNT_POINT_UNKNOWN"
    assert resp.proposals == []


def test_depleted_module_blocked() -> None:
    catalog = CatalogResult((_entry("test_sensor_module_001", "sensor", quantity=0),))
    resp = _resp("установи модуль", catalog)
    assert resp.legality.reason_code == "MODULE_DEPLETED"
    assert resp.proposals == []


def test_catalog_failure_defers_attach() -> None:
    resp = _resp("установи модуль", CatalogResult((), CATALOG_UNAVAILABLE, "x"))
    assert resp.legality.status == "deferred"
    assert resp.legality.reason_code == CATALOG_UNAVAILABLE


def test_parameters_carry_full_passport_template() -> None:
    """Пломба M5 покрывает весь паспорт (ADR-0019 §2) — TOCTOU каталога закрыт."""
    params = _action(_resp("установи science_probe_module_001 на F09")).parameters
    assert params == {
        "module_id": "science_probe_module_001",
        "mount": "F09",
        "module_class": "science",
        "provided_capabilities": ["cap"],
        "quantity": 1,
        "passport_damaged": False,
    }


def test_damaged_passport_flag_travels_in_template() -> None:
    params = _action(_resp("установи salvage_sensor_damaged_001 на F01")).parameters
    assert params["passport_damaged"] is True
