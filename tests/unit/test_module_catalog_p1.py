"""P1 (ADR-0019): единый загрузчик каталога — fail-closed, и policy-доклад по отсеку."""

from __future__ import annotations

import json
from uuid import uuid4

import pytest

from qiki.services.q_core_agent.core.body_structure import KNOWN_MOUNT_CLASSES
from qiki.shared.module_catalog import (
    CATALOG_INVALID,
    CATALOG_UNAVAILABLE,
    CatalogResult,
    load_module_catalog,
)


def _valid_record(**overrides) -> dict:
    record = {
        "module_id": "m1",
        "module_class": "sensor",
        "provided_capabilities": ["cap_a"],
        "display_name_ru": "Модуль",
        "quantity": 1,
    }
    record.update(overrides)
    return record


def _write_catalog(tmp_path, modules) -> str:
    path = tmp_path / "catalog.json"
    path.write_text(json.dumps({"modules": modules}, ensure_ascii=False), encoding="utf-8")
    return str(path)


def test_real_repo_catalog_is_valid() -> None:
    result = load_module_catalog("config/modules/catalog.json", known_classes=KNOWN_MOUNT_CLASSES)
    assert result.ok, (result.error_code, result.error_detail)
    ids = [entry.module_id for entry in result.entries]
    assert len(ids) == len(set(ids)) and len(ids) >= 5
    assert any(entry.module_class == "rcs-cluster" for entry in result.entries)
    assert any(entry.passport_damaged for entry in result.entries)


def test_missing_file_fail_closed() -> None:
    result = load_module_catalog("/nonexistent/catalog.json")
    assert result.error_code == CATALOG_UNAVAILABLE and not result.entries


def test_broken_json_fail_closed(tmp_path) -> None:
    path = tmp_path / "catalog.json"
    path.write_text("{broken", encoding="utf-8")
    result = load_module_catalog(str(path))
    assert result.error_code == CATALOG_UNAVAILABLE


@pytest.mark.parametrize(
    "modules",
    [
        [],
        [_valid_record(), _valid_record()],                       # дубликат id
        [_valid_record(module_class="warp-drive")],               # неизвестный класс
        [_valid_record(quantity=-1)],                             # отрицательный остаток
        [_valid_record(quantity=True)],                           # bool вместо int
        [{k: v for k, v in _valid_record().items() if k != "quantity"}],  # нет поля
        [_valid_record(provided_capabilities="cap_a")],           # не список
    ],
)
def test_invalid_records_fail_closed(tmp_path, modules) -> None:
    result = load_module_catalog(_write_catalog(tmp_path, modules), known_classes=KNOWN_MOUNT_CLASSES)
    assert result.error_code == CATALOG_INVALID and not result.entries


def test_policy_cargo_list_reports_quantities() -> None:
    from qiki.services.q_core_agent.qiki_orion_intents_service import (
        _build_cargo_list_response,
        _is_cargo_list_command,
    )
    from qiki.shared.models.qiki_chat import QikiChatInput, QikiChatRequestV1, QikiMode

    assert _is_cargo_list_command("q: доложи отсек")
    assert _is_cargo_list_command("какие модули есть?")
    assert not _is_cargo_list_command("установи модуль")

    req = QikiChatRequestV1(request_id=uuid4(), ts_epoch_ms=0, input=QikiChatInput(text="доложи отсек"))
    resp = _build_cargo_list_response(req=req, mode=QikiMode.FACTORY)
    assert resp.proposals == []  # информация, не команда
    body_ru = resp.reply.body.ru
    assert "test_sensor_module_001" in body_ru and "остаток 2" in body_ru
    assert "rcs_cluster_module_001" in body_ru


def test_policy_cargo_list_fail_closed_no_inventions() -> None:
    from qiki.services.q_core_agent.qiki_orion_intents_service import _build_cargo_list_response
    from qiki.shared.models.qiki_chat import QikiChatInput, QikiChatRequestV1, QikiMode

    req = QikiChatRequestV1(request_id=uuid4(), ts_epoch_ms=0, input=QikiChatInput(text="доложи отсек"))
    broken = CatalogResult((), CATALOG_UNAVAILABLE, "test")
    resp = _build_cargo_list_response(req=req, mode=QikiMode.FACTORY, catalog=broken)
    assert resp.legality is not None and resp.legality.status == "deferred"
    assert resp.legality.reason_code == CATALOG_UNAVAILABLE
    assert resp.proposals == [] and CATALOG_UNAVAILABLE in resp.reply.body.ru
