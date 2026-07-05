"""Бортовой каталог модулей — единый загрузчик для policy и консоли (ADR-0019 §1).

Правила:
- чтение per-request (никто не владеет устаревшей копией);
- fail-closed: нечитаемый файл -> CATALOG_UNAVAILABLE; кривая запись, дубликат
  module_id, неизвестный module_class, отрицательный quantity -> CATALOG_INVALID;
- display_name_ru — только UI-слой; evidence/audit несут module_id и коды.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

CATALOG_UNAVAILABLE = "CATALOG_UNAVAILABLE"
CATALOG_INVALID = "CATALOG_INVALID"

_ENV_PATH = "QIKI_MODULE_CATALOG_PATH"
_DEFAULT_CANDIDATES = (
    "config/modules/catalog.json",
    "/workspace/config/modules/catalog.json",
)
_REQUIRED_FIELDS = ("module_id", "module_class", "provided_capabilities", "display_name_ru", "quantity")


@dataclass(frozen=True, slots=True)
class CatalogEntry:
    """Паспорт-шаблон без mount_point (гнездо подставляется при установке)."""

    module_id: str
    module_class: str
    provided_capabilities: tuple[str, ...]
    display_name_ru: str
    quantity: int
    passport_damaged: bool = False


@dataclass(frozen=True, slots=True)
class CatalogResult:
    entries: tuple[CatalogEntry, ...]
    error_code: str | None = None
    error_detail: str = ""

    @property
    def ok(self) -> bool:
        return self.error_code is None


def resolve_catalog_path() -> Path | None:
    env_path = os.getenv(_ENV_PATH, "").strip()
    candidates = (env_path,) + _DEFAULT_CANDIDATES if env_path else _DEFAULT_CANDIDATES
    for candidate in candidates:
        path = Path(candidate)
        if path.is_file():
            return path
    return None


def load_module_catalog(
    path: str | os.PathLike[str] | None = None,
    *,
    known_classes: Iterable[str] | None = None,
) -> CatalogResult:
    """Прочитать каталог per-request. Никогда не бросает — fail-closed кодами."""
    resolved = Path(path) if path is not None else resolve_catalog_path()
    if resolved is None or not resolved.is_file():
        return CatalogResult((), CATALOG_UNAVAILABLE, "catalog file not found")
    try:
        raw = json.loads(resolved.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - fail-closed по любому сбою чтения/парса
        return CatalogResult((), CATALOG_UNAVAILABLE, f"unreadable catalog: {exc}")

    modules = raw.get("modules") if isinstance(raw, dict) else None
    if not isinstance(modules, list) or not modules:
        return CatalogResult((), CATALOG_INVALID, "modules list missing or empty")

    classes = set(known_classes) if known_classes is not None else None
    entries: list[CatalogEntry] = []
    seen_ids: set[str] = set()
    for index, record in enumerate(modules):
        if not isinstance(record, dict):
            return CatalogResult((), CATALOG_INVALID, f"record #{index} is not an object")
        missing = [field for field in _REQUIRED_FIELDS if field not in record]
        if missing:
            return CatalogResult((), CATALOG_INVALID, f"record #{index} missing {missing}")
        module_id = str(record["module_id"]).strip()
        module_class = str(record["module_class"]).strip()
        quantity = record["quantity"]
        capabilities = record["provided_capabilities"]
        if not module_id or module_id in seen_ids:
            return CatalogResult((), CATALOG_INVALID, f"duplicate or empty module_id at #{index}")
        if classes is not None and module_class not in classes:
            return CatalogResult((), CATALOG_INVALID, f"unknown module_class '{module_class}' at #{index}")
        if not isinstance(quantity, int) or isinstance(quantity, bool) or quantity < 0:
            return CatalogResult((), CATALOG_INVALID, f"bad quantity at #{index}")
        if not isinstance(capabilities, list) or any(not isinstance(item, str) for item in capabilities):
            return CatalogResult((), CATALOG_INVALID, f"bad provided_capabilities at #{index}")
        seen_ids.add(module_id)
        entries.append(
            CatalogEntry(
                module_id=module_id,
                module_class=module_class,
                provided_capabilities=tuple(capabilities),
                display_name_ru=str(record["display_name_ru"]).strip(),
                quantity=quantity,
                passport_damaged=bool(record.get("passport_damaged", False)),
            )
        )
    return CatalogResult(tuple(entries))
