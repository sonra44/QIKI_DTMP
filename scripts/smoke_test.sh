#!/usr/bin/env bash
# Smoke test script for QIKI-DTMP Stage 0 components

set -e  # Exit on any error

echo "🚀 Starting QIKI-DTMP Stage 0 Smoke Tests"
echo "========================================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print status
print_status() {
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}✅ $2${NC}"
    else
        echo -e "${RED}❌ $2${NC}"
        exit 1
    fi
}

# Function to print warning
print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

# Check if docker is available
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Docker is required but not installed${NC}"
    exit 1
fi

# Check if docker-compose is available
if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}docker-compose is required but not installed${NC}"
    exit 1
fi

echo "🔧 Checking project structure..."
# Check that required files exist
REQUIRED_FILES=(
    "shared/specs/BotSpec.yaml"
    "src/qiki/shared/models/bot_spec.py"
    "src/qiki/shared/events/cloudevents.py"
    "src/qiki/services/faststream_bridge/lag_monitor.py"
    "src/qiki/services/registrar/main.py"
)

for file in "${REQUIRED_FILES[@]}"; do
    if [ ! -f "$file" ]; then
        echo -e "${RED}Missing required file: $file${NC}"
        exit 1
    fi
done

echo -e "${GREEN}✅ All required files present${NC}"

# Start Phase 1 services
echo "🐳 Starting Phase 1 services..."
docker-compose -f docker-compose.phase1.yml up -d

# Wait for services to be healthy
echo "⏱  Waiting for services to be healthy..."
sleep 10

# Check if services are running
echo "🔍 Checking service status..."
SERVICES_RUNNING=true

if ! docker-compose -f docker-compose.phase1.yml ps | grep -q "qiki-nats-phase1.*Up"; then
    echo -e "${RED}NATS service is not running${NC}"
    SERVICES_RUNNING=false
fi

if ! docker-compose -f docker-compose.phase1.yml ps | grep -q "qiki-sim-phase1.*Up"; then
    echo -e "${RED}Q-Sim service is not running${NC}"
    SERVICES_RUNNING=false
fi

if ! docker-compose -f docker-compose.phase1.yml ps | grep -q "qiki-faststream-bridge-phase1.*Up"; then
    echo -e "${RED}FastStream bridge is not running${NC}"
    SERVICES_RUNNING=false
fi

if [ "$SERVICES_RUNNING" = true ]; then
    echo -e "${GREEN}✅ All core services are running${NC}"
else
    echo -e "${RED}❌ Some services failed to start${NC}"
    docker-compose -f docker-compose.phase1.yml ps
    docker-compose -f docker-compose.phase1.yml logs --tail=20
    exit 1
fi

# Run linter checks
echo "🔍 Running code style checks (ruff)..."
if docker-compose -f docker-compose.phase1.yml exec -T qiki-dev python -m ruff check --select=E,F src/qiki/shared/models/bot_spec.py src/qiki/shared/events/cloudevents.py src/qiki/services/faststream_bridge/lag_monitor.py src/qiki/services/registrar; then
    echo -e "${GREEN}✅ Code style checks passed${NC}"
else
    echo -e "${RED}❌ Code style checks failed${NC}"
    exit 1
fi

# Run mypy checks
echo "🔍 Running type checks (mypy)..."
if docker-compose -f docker-compose.phase1.yml exec -T qiki-dev python -m mypy src/qiki/shared/models/bot_spec.py src/qiki/shared/events/cloudevents.py src/qiki/services/faststream_bridge/lag_monitor.py src/qiki/services/registrar; then
    echo -e "${GREEN}✅ Type checks passed${NC}"
else
    echo -e "${RED}❌ Type checks failed${NC}"
    exit 1
fi

# Run unit tests
echo "🔍 Running unit tests..."
if docker-compose -f docker-compose.phase1.yml exec -T qiki-dev python -m pytest -v tests/shared/test_bot_spec_validator.py src/qiki/services/faststream_bridge/tests/test_metrics_lag.py src/qiki/services/faststream_bridge/tests/test_smoke_lag.py src/qiki/services/registrar/tests; then
    echo -e "${GREEN}✅ Unit tests passed${NC}"
else
    echo -e "${RED}❌ Unit tests failed${NC}"
    exit 1
fi

# Run integration tests
echo "🔍 Running integration tests..."
if docker-compose -f docker-compose.phase1.yml exec -T qiki-dev python -m pytest -v tests/integration/test_lag_monitor_smoke.py; then
    echo -e "${GREEN}✅ Integration tests passed${NC}"
else
    echo -e "${RED}❌ Integration tests failed${NC}"
    exit 1
fi

# Check that radar pipeline is working
echo "🔍 Checking radar pipeline..."
if docker-compose -f docker-compose.phase1.yml exec -T qiki-dev python -m pytest -q tests/integration/test_radar_flow.py tests/integration/test_radar_tracks_flow.py; then
    echo -e "${GREEN}✅ Radar pipeline is working${NC}"
else
    echo -e "${RED}❌ Radar pipeline tests failed${NC}"
    exit 1
fi

# Check that config generator works
echo "🔍 Testing config generator..."
if docker-compose -f docker-compose.phase1.yml exec -T qiki-dev python -c "
import sys
sys.path.insert(0, '/workspace')
from qiki.shared.config.generator import generate_bot_config_from_spec
config = generate_bot_config_from_spec()
print('Bot ID:', config.get('bot_id'))
print('Components:', len(config.get('runtime_profile', {})))
"; then
    echo -e "${GREEN}✅ Config generator works${NC}"
else
    echo -e "${RED}❌ Config generator failed${NC}"
    exit 1
fi

# Check that registrar service starts
echo "🔍 Checking registrar service..."
if docker-compose -f docker-compose.phase1.yml exec -T qiki-dev python -c "
import sys
sys.path.insert(0, '/workspace')
from qiki.services.registrar.core.service import RegistrarService
from qiki.services.registrar.core.codes import RegistrarCode
registrar = RegistrarService()
print('Registrar service created')
print('Boot OK code:', RegistrarCode.BOOT_OK)
"; then
    echo -e "${GREEN}✅ Registrar service works${NC}"
else
    echo -e "${RED}❌ Registrar service failed${NC}"
    exit 1
fi

# Clean up
echo "🧹 Cleaning up..."
docker-compose -f docker-compose.phase1.yml down

echo ""
echo -e "${GREEN}🎉 All smoke tests passed! Stage 0 implementation is working correctly.${NC}"
echo ""
echo "📋 Summary of checks:"
echo "  - ✅ Project structure verification"
echo "  - ✅ Docker services startup"
echo "  - ✅ Code style checks (ruff)"
echo "  - ✅ Type checks (mypy)"
echo "  - ✅ Unit tests"
echo "  - ✅ Integration tests"
echo "  - ✅ Radar pipeline verification"
echo "  - ✅ Config generator"
echo "  - ✅ Registrar service"