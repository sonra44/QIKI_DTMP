# Testing Guide for QIKI Operator Console

This document provides comprehensive instructions for testing the QIKI Operator Console.

## Overview

The QIKI Operator Console includes several types of tests:
- Unit tests for gRPC clients (`test_grpc_clients.py`)
- Unit tests for i18n functionality (`test_i18n.py`) 
- UI component tests (`test_ui_components.py`)
- Integration tests (via conftest.py fixtures)

## Test Structure

```
tests/
├── conftest.py              # Shared fixtures and configuration
├── test_grpc_clients.py     # Tests for QSimGrpcClient and QAgentGrpcClient
├── test_i18n.py            # Tests for internationalization
├── test_ui_components.py   # Tests for Textual UI components
├── test_metrics_client.py  # Tests for metrics collection
├── test_metrics_panel.py   # Tests for metrics panel UI
└── test_status_bar.py      # Tests for status bar component
```

## Prerequisites

### Local Development
- Python 3.12+
- pytest and testing dependencies installed
- Virtual environment activated

### Docker Environment  
- Docker installed
- Docker image built with tests included

## Running Tests

### Local Testing

1. **Install test dependencies**:
   ```bash
   cd src/qiki/services/operator_console
   pip install -r requirements.txt
   ```

2. **Run all tests**:
   ```bash
   python -m pytest tests/ -v
   ```

3. **Run specific test modules**:
   ```bash
   # gRPC client tests
   python -m pytest tests/test_grpc_clients.py -v
   
   # i18n tests  
   python -m pytest tests/test_i18n.py -v
   
   # UI component tests (may have limitations due to Textual framework)
   python -m pytest tests/test_ui_components.py -v
   ```

4. **Run tests with coverage**:
   ```bash
   python -m pytest tests/ --cov=. --cov-report=html
   ```

5. **Run specific test cases**:
   ```bash
   # Test specific client
   python -m pytest tests/test_grpc_clients.py::TestQSimGrpcClient -v
   
   # Test specific method
   python -m pytest tests/test_grpc_clients.py::TestQSimGrpcClient::test_client_initialization -v
   ```

### Docker Testing

1. **Build Docker image** (from project root):
   ```bash
   docker build -t qiki-operator-console src/qiki/services/operator_console/
   ```

2. **Run tests in Docker container**:
   ```bash
   # Run all tests
   docker run --rm qiki-operator-console python -m pytest tests/ -v
   
   # Run with coverage
   docker run --rm qiki-operator-console python -m pytest tests/ --cov=. --cov-report=term
   
   # Run specific test module
   docker run --rm qiki-operator-console python -m pytest tests/test_grpc_clients.py -v
   ```

3. **Interactive testing session**:
   ```bash
   docker run -it --rm qiki-operator-console /bin/bash
   # Inside container:
   python -m pytest tests/ -v
   ```

## Test Configuration

### pytest.ini
The project includes a `pytest.ini` file with the following configuration:
- Test discovery patterns
- Asyncio mode settings  
- Coverage settings
- Output formatting

### conftest.py
Shared fixtures for testing include:
- `mock_metrics_client`: Pre-configured metrics client with sample data
- `mock_simulation_client`: Mock QSimGrpcClient with default responses
- `mock_chat_client`: Mock QAgentGrpcClient with default responses
- `mock_nats_client`: Mock NATS client for message testing
- `sample_i18n`: Pre-configured i18n instances for different languages

## Writing Tests

### Test Structure Guidelines

1. **Use descriptive test names**:
   ```python
   def test_client_connects_successfully_with_valid_host_and_port(self):
       # Test implementation
   ```

2. **Follow AAA pattern** (Arrange, Act, Assert):
   ```python
   def test_send_command_returns_success_when_connected(self):
       # Arrange
       client.connected = True
       
       # Act  
       result = await client.send_command("start")
       
       # Assert
       assert result["success"] is True
   ```

3. **Use fixtures for setup**:
   ```python
   @pytest.fixture
   def client(self):
       return QSimGrpcClient("localhost", 50051)
   ```

### Mocking Guidelines

1. **Mock external dependencies**:
   ```python
   with patch('clients.grpc_client.aio.insecure_channel') as mock_channel:
       # Test implementation
   ```

2. **Use AsyncMock for async methods**:
   ```python
   mock_client = AsyncMock()
   mock_client.connect.return_value = True
   ```

3. **Configure mock return values**:
   ```python
   mock_client.send_command.return_value = {
       "success": True,
       "message": "Command executed"
   }
   ```

## Known Testing Limitations

### Textual UI Components
- UI component tests have limitations due to Textual framework requirements
- Components need an active app context to function properly
- Some tests may fail with `NoActiveAppError` 
- Consider integration testing with full app context for UI components

### gRPC Clients
- Tests use mocks since actual gRPC services may not be available
- Integration tests require running gRPC services
- Proto stub generation not included in current test setup

### Async Testing
- All async tests use `@pytest.mark.asyncio` decorator
- Event loop fixture configured in conftest.py
- Some async operations may need additional setup

## Continuous Integration

### Running Tests in CI/CD

Example GitHub Actions workflow:
```yaml
- name: Run tests
  run: |
    cd src/qiki/services/operator_console
    python -m pytest tests/ -v --cov=. --cov-report=xml
```

Example Docker-based CI:
```yaml
- name: Test in Docker
  run: |
    docker build -t test-image src/qiki/services/operator_console/
    docker run --rm test-image python -m pytest tests/ -v
```

## Coverage Goals

- Target: 80% code coverage minimum
- Focus areas: gRPC clients, i18n functionality, core business logic
- UI components may have lower coverage due to testing limitations

## Test Data and Fixtures

### Sample Data
- Metrics data: CPU, memory, disk, network samples
- gRPC responses: Success/failure scenarios
- i18n translations: English and Russian test strings
- Track data: Radar track samples for NATS testing

### Environment Variables for Testing
```bash
# Optional: Override service endpoints for integration tests
export QSIM_GRPC_HOST=localhost
export QSIM_GRPC_PORT=50051
export AGENT_GRPC_HOST=localhost  
export AGENT_GRPC_PORT=50052
export NATS_URL=nats://localhost:4222
```

## Troubleshooting

### Common Issues

1. **Import errors**: Ensure PYTHONPATH includes project directories
2. **Async errors**: Check event loop configuration in conftest.py
3. **Mock setup failures**: Verify mock objects match actual API signatures
4. **Coverage issues**: Check that all test modules are being discovered

### Debug Mode
```bash
# Run with verbose output and no capture
python -m pytest tests/ -v -s

# Run with pdb on failures
python -m pytest tests/ --pdb

# Run with detailed traceback
python -m pytest tests/ --tb=long
```

## Performance Testing

### Load Testing (Future Enhancement)
- Consider adding performance tests for gRPC clients
- Test concurrent connections and message throughput
- Monitor resource usage during extended operations

### Memory Testing
```bash
# Run with memory profiling
python -m pytest tests/ --memray

# Check for memory leaks in long-running tests
```

## Maintenance

### Regular Test Updates
- Update mocks when API signatures change
- Refresh test data periodically
- Review and update coverage targets
- Keep dependency versions current in requirements.txt

### Test Review Process
- Code reviews should include test coverage analysis
- New features require corresponding test cases
- Bug fixes should include regression tests
- Regular cleanup of obsolete test code