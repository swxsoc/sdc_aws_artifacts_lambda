# AGENTS.md

This file helps AI coding agents understand the repository structure, build/test conventions, and key architecture decisions for the **Space Weather SOC (SWSOC) AWS Lambda Artifact Processing Function**.

## Project Overview

This is an AWS Lambda function that processes Space Weather Science Operations Center files to generate artifacts (Slack notifications and Timestream logs). The function:
- Accepts S3 event notifications via SNS
- Downloads science files from S3 buckets
- Parses file metadata to identify instruments and data types
- Generates Slack notifications and Timestream database entries
- Integrates with the `swxsoc` library for AWS operations and configuration management
- Operates in **DEVELOPMENT** mode (limited logging/notifications) or **PRODUCTION** mode (full artifacts)

See [README.rst](README.rst) for detailed documentation and local testing instructions.

## Essential Commands

### Testing
```bash
# Run all tests with coverage
pytest --pyargs lambda_function/tests --cov=lambda_function/src --cov-report=html

# Build Docker container for local Lambda testing
cd lambda_function && docker build --build-arg BASE_IMAGE=public.ecr.aws/w5r9l1c8/padre-swsoc-docker-lambda-base:latest -t swxsoc_sdc_aws_artifacts_lambda:latest .

# Run Lambda locally
docker run -p 9000:8080 \
  -v ~/lambda_function/tests/test_data:/test_data \
  -e SDC_AWS_FILE_PATH=/test_data/hermes_EEA_l0_2023042-000000_v0.bin \
  swxsoc_sdc_aws_artifacts_lambda:latest

# Test Lambda function with curl (from separate terminal)
curl -XPOST "http://localhost:9000/2015-03-31/functions/function/invocations" \
  -d @lambda_function/tests/test_data/test_eea_event.json
```

## Project Structure

```
lambda_function/
├── src/
│   ├── lambda.py                   # Handler entry point for Lambda
│   └── process_artifacts/
│       ├── __init__.py
│       └── process_artifacts.py    # ArtifactProcessor class and handle_event() logic
├── tests/
│   ├── conftest.py                 # Shared pytest fixtures (default_test_mission)
│   ├── test_process_artifacts.py   # Main test suite
│   └── test_data/
│       └── test_eea_event.json     # Sample SNS/S3 event payload
├── Dockerfile                      # Lambda container image
└── requirements.txt                # Production dependencies

lambda_function/src/process_artifacts/process_artifacts.py imports from swxsoc:
  - S3 operations (get_science_file, parse_file_key, etc.)
  - Config utilities (get_instrument_bucket, TSD_REGION)
  - Slack notifications (get_slack_client, send_pipeline_notification)
  - Timestream logging (create_timestream_client_session, log_to_timestream)
  - Utility functions (parse_science_filename)
  - Logging (log)
```

## Key Technical Details

**Python Version**: 3.12 (must match AWS Lambda runtime)

**Environment Variables**:
- `LAMBDA_ENVIRONMENT` (default: `"DEVELOPMENT"`): Controls artifact generation behavior
  - `"DEVELOPMENT"`: Minimal processing and notifications
  - `"PRODUCTION"`: Full artifact generation
- `SWXSOC_MISSION` (default: `"hermes"` in tests): Configures mission-specific behavior (set automatically in test fixtures)
- `SDC_AWS_FILE_PATH` (optional): Local file path when testing with Docker
- `USE_INSTRUMENT_TEST_DATA` (optional): Uses instrument package test data instead of specific file

**Dependencies**:
- `swxsoc` (from git main branch): Core library for S3, Slack, Timestream, config, logging
- `moto==5.0.15`: Mocks AWS services (S3, Secrets Manager, etc.) in tests
- `psycopg2-binary==2.9.7`: PostgreSQL adapter
- `pytest`, `pytest-astropy`, `pytest-cov`: Testing framework
- `ruff`: Code linting

**Linting**: Uses Ruff with specific ignores defined in [ruff.toml](ruff.toml) for:
- `EXE002`: Executable file without shebang (expected in container)
- `BLE001`, `TRY201`, `RUF028`, `SIM115`: Specific code style exceptions

## Architecture & Key Concepts

### Event Flow
1. **S3 Event Trigger**: File uploaded to S3 bucket
2. **SNS Notification**: S3 sends SNS message to Lambda
3. **Lambda Handler**: `handler()` in `lambda.py` receives event and context
4. **Event Parsing**: `handle_event()` extracts S3 bucket and file key from nested SNS/S3 message
5. **ArtifactProcessor**: Instantiated with S3 bucket, file key, and environment
6. **File Processing**: 
   - Parses file key and science filename
   - Downloads file from S3
   - Generates Slack and Timestream artifacts via `swxsoc` library

### ArtifactProcessor Class
- **Constructor**: Takes `s3_bucket`, `file_key`, `environment`, optional `dry_run`
- **Main Method**: `_process_artifacts()` orchestrates the artifact generation workflow
- **Helper Methods**: `_generate_slack_artifacts()` and others for specific artifact types
- **Error Handling**: Exceptions caught in `handle_event()` return HTTP 500 response

### Response Format
```json
{
  "statusCode": 200 or 500,
  "body": "JSON-serialized message string"
}
```

## Testing Conventions

- **Fixtures**: `conftest.py` provides:
  - `default_test_mission`: Auto-applied fixture that sets `SWXSOC_MISSION=hermes` for all tests
  - `use_mission`: Fixture for tests needing a specific mission configuration
  
- **Mocking**: AWS services mocked with `moto`:
  ```python
  from moto import mock_aws as moto_mock_aws
  
  @moto_mock_aws
  def test_something():
      # S3, Secrets Manager, etc. are mocked
  ```

- **Test Data**: Sample SNS events in `lambda_function/tests/test_data/`
  - Structure: SNS message wrapping S3 event with bucket name and file key

- **Environment**: Tests run with Python 3.12 to match Lambda runtime

## CI/CD Workflows

See [.github/workflows/](/.github/workflows/) for workflow definitions:
- **testing.yml**: Runs on PR, `workflow_dispatch`, and daily schedule; runs tests with coverage
- Coverage reports uploaded to Codecov
- Codestyle workflow (linting) via Ruff

## Common Development Tasks

| Task | Command/Approach |
|------|------------------|
| Run tests | `pytest --pyargs lambda_function/tests --cov=lambda_function/src --cov-report=html` |
| Build Lambda image | `cd lambda_function && docker build --build-arg BASE_IMAGE=... -t swxsoc_sdc_aws_artifacts_lambda:latest .` |
| Test locally | See "Testing Locally" in README.rst |
| Add new test | Place in `lambda_function/tests/test_*.py`; conftest fixtures auto-apply |
| Modify core logic | Edit `lambda_function/src/process_artifacts/process_artifacts.py` |
| Update dependencies | Edit `lambda_function/requirements.txt` (prod) or `requirements.dev.txt` (dev) |
| Check code style | `ruff check lambda_function/` (or let CI handle it) |

## Deployment

The function is deployed as a container image stored in AWS ECR:
- **Production**: Built from latest GitHub release
- **Development/Testing**: Built from latest commit on `main` branch
- **Base Image**: `padre-swsoc-docker-lambda-base:latest` (mission-specific)

## Key Decisions & Patterns

1. **SNS-wrapped S3 events**: Lambda receives S3 events via SNS notifications (not direct S3 triggers), which allows for more flexible event routing and fan-out.

2. **Environment-based behavior**: The `LAMBDA_ENVIRONMENT` variable controls production vs. development artifact generation (logging, Slack notifications, Timestream entries).

3. **Centralized swxsoc library**: All AWS service interactions (S3, Slack, Timestream, config) and mission-specific logic are abstracted via `swxsoc`, making this function focus on artifact orchestration.

4. **Comprehensive test coverage**: Tests use `moto` to mock AWS services, enabling testing without AWS credentials or infrastructure.

5. **Docker for local testing**: Enables testing the exact Lambda runtime environment (Python 3.12 + swxsoc deps) locally before deployment.

6. **Mission configuration**: The `SWXSOC_MISSION` env var (set to `"hermes"` by default in tests via `conftest.py`) determines instrument-specific behavior and bucket mappings via `swxsoc`.

## Common Patterns & Gotchas

- **Test Fixtures Auto-Apply**: The `default_test_mission` fixture in `conftest.py` applies to ALL tests automatically (`autouse=True`). Tests override it by setting `SWXSOC_MISSION` explicitly or using the `use_mission` fixture.

- **Event Structure**: S3 events arrive wrapped in an SNS message. The handler must parse `event["Records"][0]["Sns"]["Message"]` first, then extract S3 bucket/key.

- **Logging**: Use `from swxsoc import log` (not Python's standard `logging`). Log calls accept dictionaries:
  ```python
  log.error({"status": "ERROR", "message": e})
  ```

- **Error Responses**: Always return a dict with `statusCode` (int) and `body` (string, JSON-serialized).

## Questions or Issues?

- For Lambda-specific questions, refer to [README.rst](README.rst)
- For swxsoc library details, see the [swxsoc repository](https://github.com/swxsoc/swxsoc)
- For CI/CD, check [.github/workflows/](/.github/workflows/)
- For test patterns, review [conftest.py](lambda_function/tests/conftest.py) and [test_process_artifacts.py](lambda_function/tests/test_process_artifacts.py)
