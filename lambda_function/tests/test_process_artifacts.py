import pytest
import json
import os
from unittest.mock import patch, MagicMock
from pathlib import Path
from moto import mock_s3, mock_secretsmanager

os.environ["SDC_AWS_CONFIG_FILE_PATH"] = "lambda_function/src/config.yaml"

# Import the module to be tested
from src.process_artifacts.process_artifacts import handle_event, ArtifactProcessor

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


# Mock boto3 S3 and Secrets Manager services
@mock_s3
@mock_secretsmanager
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
@mock_s3
def test_handle_event_success():
    setup_mocks()
    response = handle_event(TEST_EVENT, None)
    assert response == {"statusCode": 200, "body": "Artifacts Processed Successfully"}


# Tests for ArtifactProcessor class
@patch("src.process_artifacts.process_artifacts.ArtifactProcessor._process_artifacts")
@mock_s3
def test_artifact_processor_initialization(mock_process_artifacts):
    setup_mocks()
    processor = ArtifactProcessor(TEST_S3_BUCKET, TEST_FILE_KEY, TEST_ENVIRONMENT)
    assert processor is not None
    assert processor.instrument_bucket_name == TEST_S3_BUCKET
    assert processor.file_key == TEST_FILE_KEY
    assert processor.environment == TEST_ENVIRONMENT
    mock_process_artifacts.assert_called_once()
