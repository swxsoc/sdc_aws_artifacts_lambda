import json
import os
from unittest.mock import patch

from moto import mock_aws as moto_mock_aws
import pytest

from src.process_artifacts.process_artifacts import ArtifactProcessor  # noqa: E402
from src.process_artifacts.process_artifacts import handle_event  # noqa: E402; noqa: E402

# Constants for testing
TEST_S3_BUCKET = "hermes-eea"
TEST_FILE_KEY = "hermes_EEA_l0_2023042-000000_v0.bin"
TEST_ENVIRONMENT = "PRODUCTION"
TEST_EVENT = {
    "Records": [
        {
            "Sns": {
                "Message": json.dumps(
                    {
                        "Records": [
                            {
                                "s3": {
                                    "bucket": {"name": TEST_S3_BUCKET},
                                    "object": {"key": TEST_FILE_KEY},
                                }
                            }
                        ]
                    }
                )
            }
        }
    ]
}


@pytest.fixture(scope="function")
def mock_aws():
    """Mock AWS services using moto."""
    with moto_mock_aws():
        yield

# Mock boto3 S3 and Secrets Manager services
def setup_mocks():
    # Setup S3
    import boto3

    s3 = boto3.client("s3")
    s3.create_bucket(Bucket=TEST_S3_BUCKET)
    s3.put_object(Bucket=TEST_S3_BUCKET, Key=TEST_FILE_KEY, Body="Dummy file content")

    # Setup Secrets Manager
    secretsmanager = boto3.client("secretsmanager", region_name="us-east-1")
    secretsmanager.create_secret(
        Name="RDS_SECRET_ARN",
        SecretString=json.dumps(
            {
                "username": "testuser",
                "password": "testpass",
                "host": "localhost",
                "port": 5432,
                "dbname": "testdb",
            }
        ),
    )


# Tests for handle_event function
def test_handle_event_success(mock_aws):
    setup_mocks()
    response = handle_event(TEST_EVENT, None)
    assert response == {"statusCode": 200, "body": "Artifacts Processed Successfully"}


# Tests for ArtifactProcessor class
@patch("src.process_artifacts.process_artifacts.ArtifactProcessor._process_artifacts")
def test_artifact_processor_initialization(mock_process_artifacts, mock_aws):
    setup_mocks()
    processor = ArtifactProcessor(TEST_S3_BUCKET, TEST_FILE_KEY, TEST_ENVIRONMENT)
    assert processor is not None
    assert processor.instrument_bucket_name == TEST_S3_BUCKET
    assert processor.file_key == TEST_FILE_KEY
    assert processor.environment == TEST_ENVIRONMENT
    mock_process_artifacts.assert_called_once()
