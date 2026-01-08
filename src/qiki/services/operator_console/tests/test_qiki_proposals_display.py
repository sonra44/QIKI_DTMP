from __future__ import annotations

import pytest

from qiki.services.operator_console.main_orion import OrionApp
from qiki.shared.models.orion_qiki_protocol import ProposalsBatchV1, ProposalV1


def test_ingest_proposals_batch_updates_store() -> None:
    app = OrionApp()
    assert app._proposals_by_key == {}

    batch = ProposalsBatchV1(
        ts=1700000000000,
        proposals=[
            ProposalV1(
                proposal_id="P1",
                title="Title 1",
                justification="Just 1",
                priority=80,
                confidence=0.7,
            ),
            ProposalV1(
                proposal_id="P2",
                title="Title 2",
                justification="Just 2",
                priority=20,
                confidence=0.5,
            ),
        ],
        metadata={"source": "test"},
    )

    app._ingest_proposals_batch(batch)
    assert "P1" in app._proposals_by_key
    assert app._proposals_by_key["P1"]["title"] == "Title 1"


@pytest.mark.asyncio
async def test_handle_proposals_data_invalid_does_not_crash() -> None:
    app = OrionApp()
    await app.handle_proposals_data({"data": {"version": 1}})
