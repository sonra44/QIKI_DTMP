#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

# Get the directory of the current script
SCRIPT_DIR=$(dirname "$(readlink -f "$0")")
PROJECT_ROOT=$(dirname "$SCRIPT_DIR")

# Set PYTHONPATH to include the project root for module imports
export PYTHONPATH="$PROJECT_ROOT"

echo "Running tests..."
pytest "$PROJECT_ROOT/services/q_core_agent/tests/"

echo "Running linter (ruff)..."
q_core_agent_path="$PROJECT_ROOT/services/q_core_agent/"
ruff check "$q_core_agent_path"

echo "Checking Protobuf files..."
# This assumes protoc is in your PATH. If not, adjust the path.
# --dry_run is not a standard protoc option. We'll just check for syntax.
find "$PROJECT_ROOT/protos" -name "*.proto" -print0 | xargs -0 -n1 protoc --proto_path="$PROJECT_ROOT/protos" --descriptor_set_out=/dev/null

echo "All checks passed!"
