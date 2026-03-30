#!/usr/bin/env bash
set -euo pipefail

base_ref="${QUALITY_GATE_BASE_REF:-origin/main}"
max_main_orion_commits="${ANTILOOP_MAX_MAIN_ORION_COMMITS:-5}"
strict="${ANTILOOP_STRICT:-1}"
pr_body_file="${ANTILOOP_PR_BODY_FILE:-}"

if ! git rev-parse --verify "${base_ref}" >/dev/null 2>&1; then
  if git rev-parse --verify "origin/main" >/dev/null 2>&1; then
    base_ref="origin/main"
  else
    base_ref="master"
  fi
fi

changed_files="$(
  {
    git diff --name-only "${base_ref}...HEAD" 2>/dev/null || true
    git diff --name-only
    git diff --name-only --cached
    git ls-files --others --exclude-standard
  } | awk 'NF' | sort -u
)"

if [[ -z "${changed_files}" ]]; then
  echo "[anti-loop] No changed files; skipping anti-loop checks"
  exit 0
fi

has_product_change=0
has_operator_change=0
dossier_candidates=()

while IFS= read -r path; do
  [[ -z "${path}" ]] && continue
  if [[ "${path}" == src/* || "${path}" == config/* || "${path}" == schemas/* || "${path}" == docker-compose*.yml ]]; then
    has_product_change=1
  fi
  if [[ "${path}" == src/qiki/services/operator_console/* ]]; then
    has_operator_change=1
  fi
  if [[ "${path}" == TASKS/TASK_*.md ]]; then
    dossier_candidates+=("${path}")
  fi
done <<< "${changed_files}"

if [[ "${has_product_change}" -eq 0 ]]; then
  echo "[anti-loop] No product-surface changes; gate passed"
  exit 0
fi

if [[ "${#dossier_candidates[@]}" -eq 0 ]]; then
  echo "[anti-loop] FAIL: product changes detected but no changed TASK dossier (TASKS/TASK_*.md)" >&2
  exit 2
fi

required_sections=(
  "## Operator Scenario (visible outcome)"
  "## Reproduction Command"
  "## Before / After"
  "## Impact Metric"
)

dossier_ok=0
for dossier in "${dossier_candidates[@]}"; do
  [[ -f "${dossier}" ]] || continue
  missing=0
  for section in "${required_sections[@]}"; do
    if ! rg -n -F -- "${section}" "${dossier}" >/dev/null; then
      missing=1
      break
    fi
  done
  if [[ "${missing}" -eq 0 ]]; then
    dossier_ok=1
    echo "[anti-loop] Dossier check passed: ${dossier}"
    break
  fi
done

if [[ "${dossier_ok}" -eq 0 ]]; then
  echo "[anti-loop] FAIL: no changed dossier has all required anti-loop sections" >&2
  printf '[anti-loop] Required sections:\n' >&2
  for section in "${required_sections[@]}"; do
    printf '  - %s\n' "${section}" >&2
  done
  exit 2
fi

if [[ -n "${pr_body_file}" && -f "${pr_body_file}" ]]; then
  pr_required=(
    "## Visible Delta for Operator"
    "## Before / After Command Transcript"
    "## Impact Metric"
  )
  for section in "${pr_required[@]}"; do
    if ! rg -n -F -- "${section}" "${pr_body_file}" >/dev/null; then
      echo "[anti-loop] FAIL: PR body missing section: ${section}" >&2
      exit 2
    fi
  done
fi

if [[ "${has_operator_change}" -eq 1 ]]; then
  main_orion_commits="$(
    git log --oneline "${base_ref}...HEAD" -- src/qiki/services/operator_console/main_orion.py \
      | wc -l | tr -d ' '
  )"
  if [[ "${main_orion_commits}" -gt "${max_main_orion_commits}" ]]; then
    msg="[anti-loop] main_orion churn above threshold (${main_orion_commits} > ${max_main_orion_commits})"
    if [[ "${strict}" -eq 1 ]]; then
      echo "[anti-loop] FAIL: ${msg}" >&2
      exit 2
    fi
    echo "[anti-loop] WARN: ${msg}" >&2
  fi
fi

echo "[anti-loop] OK"
