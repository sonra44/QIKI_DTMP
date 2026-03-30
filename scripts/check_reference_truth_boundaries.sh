#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

required_files=(
  ".codex/imp/RE_QIKI_Runtime_Evidence_Notes.md"
  ".codex/imp/RE_QIKI_Maturity_Matrix.md"
  ".codex/imp/RE_QIKI_Risks_and_Unresolved_Zones.md"
)

required_markers=(
  "REFERENCE ONLY / NOT CURRENT STATUS"
  "CURRENT TRUTH OVERRIDE"
  "~/MEMORI/ACTIVE_TASKS_QIKI_DTMP.md"
  "TASKS/TASK_20260330_qiki_freshness_threshold_ownership.md"
  "TASK_OUT/final_stabilization_and_baseline.md"
)

stale_claim_patterns=(
  'main_blocker = signature_changed live path'
  'active slice = proof-stage'
  'active slice остаётся в `proof-stage`'
  'Текущий active slice:.*G3-QIKI-009'
  'signature_changed live path'
)

fail=0

for file in "${required_files[@]}"; do
  if [ ! -f "$file" ]; then
    echo "FAIL: missing required reference-layer file '$file'."
    fail=1
    continue
  fi

  for marker in "${required_markers[@]}"; do
    if ! head -n 40 "$file" | rg -q -F "$marker"; then
      echo "FAIL: '$file' is missing boundary marker '$marker' in the preamble."
      fail=1
    fi
  done

  if rg -n "${stale_claim_patterns[0]}|${stale_claim_patterns[1]}|${stale_claim_patterns[2]}|${stale_claim_patterns[3]}" "$file" >/dev/null; then
    if ! head -n 40 "$file" | rg -q -F "Historical package-state below may be stale"; then
      echo "FAIL: '$file' still contains stale-status language without an explicit historical-staleness warning."
      fail=1
    fi
  fi
done

if [ "$fail" -ne 0 ]; then
  exit 1
fi

echo "OK: reference-layer docs carry explicit current-truth boundaries."
