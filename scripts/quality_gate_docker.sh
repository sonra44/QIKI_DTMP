#!/usr/bin/env bash
set -euo pipefail

compose_files=(-f docker-compose.phase1.yml)

if [[ "${QIKI_USE_OPERATOR_COMPOSE:-0}" == "1" ]]; then
  compose_files+=(-f docker-compose.operator.yml)
fi

dc() {
  docker compose "${compose_files[@]}" "$@"
}

echo "[quality-gate] Services status (informational)"
dc ps

SCOPE="${QUALITY_GATE_SCOPE:-}"

resolve_base_ref() {
  local base_ref="${QUALITY_GATE_BASE_REF:-origin/master}"
  if git rev-parse --verify "${base_ref}" >/dev/null 2>&1; then
    echo "${base_ref}"
    return
  fi
  if git rev-parse --verify "origin/main" >/dev/null 2>&1; then
    echo "origin/main"
    return
  fi
  echo "master"
}

compute_changed_python_files() {
  local base_ref
  base_ref="$(resolve_base_ref)"

  git diff --name-only --diff-filter=ACMRT "${base_ref}...HEAD" 2>/dev/null \
    | awk '/\.(py|pyi)$/' \
    || true
}

echo "[quality-gate] Ruff (lint)"
if [[ -n "${SCOPE}" ]]; then
  echo "[quality-gate] Ruff scope: ${SCOPE}"
  dc exec -T qiki-dev ruff check ${SCOPE}
else
  mapfile -t changed_py < <(compute_changed_python_files)
  # The file list is computed from commits (base_ref...HEAD) and may include files that
  # were deleted in the working tree but not committed yet. Filter to existing paths.
  if ((${#changed_py[@]} > 0)); then
    existing_py=()
    for path in "${changed_py[@]}"; do
      if [[ -f "${path}" ]]; then
        existing_py+=("${path}")
      fi
    done
    changed_py=("${existing_py[@]}")
  fi
  if ((${#changed_py[@]} == 0)); then
    echo "[quality-gate] Ruff: no changed Python files; skipping lint"
  else
    echo "[quality-gate] Ruff scope: changed files (${#changed_py[@]})"
    dc exec -T qiki-dev ruff check "${changed_py[@]}"
  fi
fi

echo "[quality-gate] Ruff (format check)"
if [[ "${QUALITY_GATE_RUFF_FORMAT_CHECK:-0}" == "1" ]]; then
  if [[ -n "${SCOPE}" ]]; then
    dc exec -T qiki-dev ruff format --check ${SCOPE}
  else
    if ((${#changed_py[@]} == 0)); then
      echo "[quality-gate] Ruff format: no changed Python files; skipping"
    else
      dc exec -T qiki-dev ruff format --check "${changed_py[@]}"
    fi
  fi
else
  echo "[quality-gate] Ruff format check disabled (set QUALITY_GATE_RUFF_FORMAT_CHECK=1 to enable)"
fi

echo "[quality-gate] Pytest"
dc exec -T qiki-dev pytest -q ${QUALITY_GATE_PYTEST_PATHS:-}

echo "[quality-gate] Integration tests"
if [[ "${QUALITY_GATE_RUN_INTEGRATION:-0}" == "1" ]]; then
  # NOTE: integration tests are deselected by default via pytest.ini addopts.
  # This script forces the correct invocation.
  bash scripts/run_integration_tests_docker.sh ${QUALITY_GATE_INTEGRATION_PATHS:-tests/integration}
else
  echo "[quality-gate] Integration disabled (set QUALITY_GATE_RUN_INTEGRATION=1 or run scripts/run_integration_tests_docker.sh)"
fi

echo "[quality-gate] Mypy"
if [[ "${QUALITY_GATE_RUN_MYPY:-0}" == "1" ]]; then
  dc exec -T qiki-dev mypy --config-file mypy.ini ${QUALITY_GATE_MYPY_PATHS:-src}
else
  echo "[quality-gate] Mypy disabled (set QUALITY_GATE_RUN_MYPY=1 to enable)"
fi

echo "[quality-gate] OK"
