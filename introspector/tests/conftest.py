from __future__ import annotations

from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for candidate in (SRC, ROOT):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from project_introspector import scan_project
from project_introspector.llm import OpenAICompatibleEnrichmentClient, OpenAICompatibleSettings
from project_introspector.models import ModuleFact


@pytest.fixture(scope="session")
def policy_client() -> OpenAICompatibleEnrichmentClient:
    return OpenAICompatibleEnrichmentClient(
        OpenAICompatibleSettings(
            api_key="test-key",
            base_url="https://example.invalid/v1",
            default_model="test-model",
        )
    )


@pytest.fixture(scope="session")
def introspector_modules() -> dict[str, ModuleFact]:
    return {
        module.module_path: module
        for module in scan_project(ROOT / "src", project_name="introspector").modules
    }
