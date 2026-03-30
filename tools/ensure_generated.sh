#!/usr/bin/env bash
set -euo pipefail

# Ensure protobuf-generated stubs exist before service startup.
# Idempotent: if required files are present, this script is a no-op.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="${QIKI_REPO_ROOT:-}"
if [[ -z "${ROOT_DIR}" ]]; then
  ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
fi

REQ1="${ROOT_DIR}/generated/q_sim_api_pb2.py"
REQ2="${ROOT_DIR}/generated/q_sim_api_pb2_grpc.py"

if [[ -f "${REQ1}" && -f "${REQ2}" ]]; then
  echo "ensure_generated: stubs present, skipping generation"
  exit 0
fi

echo "ensure_generated: stubs missing, generating via tools/gen_protos.sh"
cd "${ROOT_DIR}"
bash tools/gen_protos.sh

