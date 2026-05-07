from __future__ import annotations


def test_warning_layer_dedupes_runtime_and_docstring_signal(policy_client) -> None:
    normalized = policy_client._normalize_warnings(
        [
            "No observed runtime signal for this module; analysis is based on static structure only.",
            "No observed runtime signal for this module; analysis is based on static structure only.",
            "Module has no docstring; purpose inference relies on names, imports, and symbol structure.",
            "Purpose and responsibilities were empty; module-analysis semantic signal is low.",
            "Purpose was left empty because semantic confidence was low.",
        ],
        actionable_hints=[
            "Add one real runtime flow to confirm the live path.",
            "Add a short module docstring or contract note.",
        ],
    )

    assert normalized == ["no runtime evidence", "missing module docstring", "semantic signal remains low"]


def test_warning_layer_separates_issue_signal_from_actionable_hints(policy_client) -> None:
    warning_normalized = policy_client._normalize_warnings(
        [
            "Public surface may be noisy before normalization.",
            "Cleanup suggestions need manual review.",
        ],
        actionable_hints=[
            "Keep the public surface compact and avoid helper leakage.",
            "Review cleanup candidates manually before deleting symbols.",
        ],
    )

    processing_normalized = policy_client._normalize_processing_notes(
        [
            "Reduced public_symbols to the canonical top-level public surface.",
            "Filtered cleanup_candidates to private non-runtime symbols only.",
        ]
    )

    assert warning_normalized == ["public surface may be noisy", "cleanup suggestions need manual review"]
    assert processing_normalized == [
        "public surface normalized to top-level API",
        "cleanup suggestions were narrowed",
    ]
