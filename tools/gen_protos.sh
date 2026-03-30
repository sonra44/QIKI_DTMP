#!/usr/bin/env bash
set -euo pipefail

# Generate Python stubs from .proto using grpcio-tools (no system protoc required)
# Usage: from repo root or QIKI_DTMP/: bash QIKI_DTMP/tools/gen_protos.sh

ROOT_DIR=$(cd "$(dirname "$0")/.." && pwd)

PYTHON=${PYTHON:-python3}
PROTOC="$PYTHON -m grpc_tools.protoc"

INCLUDES=(
  "-I${ROOT_DIR}/protos"
  "-I${ROOT_DIR}"
)

OUT_PY="--python_out=${ROOT_DIR}/generated"
OUT_GRPC="--grpc_python_out=${ROOT_DIR}/generated"

# Generate core protos
$PROTOC "${INCLUDES[@]}" $OUT_PY ${ROOT_DIR}/protos/common_types.proto
$PROTOC "${INCLUDES[@]}" $OUT_PY ${ROOT_DIR}/protos/sensor_raw_in.proto
$PROTOC "${INCLUDES[@]}" $OUT_PY ${ROOT_DIR}/protos/actuator_raw_out.proto
$PROTOC "${INCLUDES[@]}" $OUT_PY ${ROOT_DIR}/protos/bios_status.proto
$PROTOC "${INCLUDES[@]}" $OUT_PY ${ROOT_DIR}/protos/fsm_state.proto
$PROTOC "${INCLUDES[@]}" $OUT_PY ${ROOT_DIR}/protos/proposal.proto

# gRPC service stubs
$PROTOC "${INCLUDES[@]}" $OUT_PY $OUT_GRPC ${ROOT_DIR}/protos/q_sim_api.proto

# Radar v1
$PROTOC "${INCLUDES[@]}" $OUT_PY ${ROOT_DIR}/protos/radar/v1/radar.proto

echo "Protobuf stubs generated into ${ROOT_DIR}/generated"
