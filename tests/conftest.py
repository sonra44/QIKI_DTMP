from __future__ import annotations

import pytest


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Automatically mark tests under tests/integration as `integration`.

    Keeps `pytest -m 'not integration'` reliable even if a file misses a decorator.
    """

    for item in items:
        if "tests/integration" in str(getattr(item, "fspath", "")):
            item.add_marker(pytest.mark.integration)

