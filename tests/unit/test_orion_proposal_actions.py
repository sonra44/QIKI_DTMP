import asyncio
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from qiki.services.operator_console.main_orion import OrionApp, SelectionContext


@pytest.mark.asyncio
async def test_accept_selected_proposal_publishes_intent() -> None:
    app = OrionApp()
    # Avoid Textual screen stack errors in unit tests.
    app._screen_stack.append(MagicMock(focused=None))  # type: ignore[attr-defined]

    app.active_screen = "qiki"
    app._selection_by_app["qiki"] = SelectionContext(
        app_id="qiki",
        key="p-001",
        kind="proposal",
        source="qiki",
        created_at_epoch=time.time(),
        payload={},
        ids=("p-001",),
    )

    app._publish_qiki_intent = AsyncMock()  # type: ignore[method-assign]
    app.push_screen = lambda _screen, cb=None: cb(True) if cb else None  # type: ignore[method-assign]

    app.action_accept_selected_proposal()
    await asyncio.sleep(0)

    app._publish_qiki_intent.assert_awaited_once_with("proposal.accept id=p-001")  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_reject_selected_proposal_publishes_intent() -> None:
    app = OrionApp()
    app._screen_stack.append(MagicMock(focused=None))  # type: ignore[attr-defined]

    app.active_screen = "qiki"
    app._selection_by_app["qiki"] = SelectionContext(
        app_id="qiki",
        key="p-001",
        kind="proposal",
        source="qiki",
        created_at_epoch=time.time(),
        payload={},
        ids=("p-001",),
    )

    app._publish_qiki_intent = AsyncMock()  # type: ignore[method-assign]
    app.push_screen = lambda _screen, cb=None: cb(True) if cb else None  # type: ignore[method-assign]

    app.action_reject_selected_proposal()
    await asyncio.sleep(0)

    app._publish_qiki_intent.assert_awaited_once_with("proposal.reject id=p-001")  # type: ignore[attr-defined]
