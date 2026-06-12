"""
This Module contains the ArtifactProcessor class that will distinguish
the appropriate HERMES intrument library to use when processing
the artifacts for science files based off which bucket the file is located in.
"""

import json
import os
from typing import Any

import botocore
from sdc_aws_utils.aws import (
    create_timestream_client_session,
    get_science_file,
    log_to_timestream,
    parse_file_key,
)
from sdc_aws_utils.config import TSD_REGION, get_instrument_bucket
from sdc_aws_utils.config import parser as science_filename_parser
from sdc_aws_utils.logging import configure_logger, log
from sdc_aws_utils.slack import (
    SlackApiError,
    get_slack_client,
    send_pipeline_notification,
)

# Configure logger
configure_logger()


def handle_event(event: dict[str, Any], context: Any) -> dict[str, int | str]:
    """
    Process a Lambda event and dispatch file artifact processing work.

    Parameters
    ----------
    event : dict[str, Any]
        Triggering AWS Lambda event. Supports S3 ``Records`` events and empty
        events that trigger a full incoming-bucket scan and sorting of all files.
    context : Any
        AWS Lambda context object (accepted for compatibility).

    Returns
    -------
    dict[str, int | str]
        Response dictionary containing ``statusCode`` and serialized ``body``.
    """

    try:
        environment = os.getenv("LAMBDA_ENVIRONMENT", "DEVELOPMENT")

        # Check if SNS or S3 event
        records = json.loads(event["Records"][0]["Sns"]["Message"])["Records"]

        # Parse message from SNS Notification
        for s3_event in records:
            # Extract needed information from event
            s3_bucket = s3_event["s3"]["bucket"]["name"]
            file_key = s3_event["s3"]["object"]["key"]

            ArtifactProcessor(
                s3_bucket=s3_bucket, file_key=file_key, environment=environment
            )

            return {"statusCode": 200, "body": "Artifacts Processed Successfully"}

    except Exception as e:
        log.error({"status": "ERROR", "message": e})

        return {
            "statusCode": 500,
            "body": json.dumps(f"Error Processing Artifacts: {e}"),
        }


class ArtifactProcessor:
    """
    Dispatch artifact generation for a science file to the appropriate
    instrument library based on its source S3 bucket.

    Parameters
    ----------
    s3_bucket : str
        Name of the S3 bucket the file is located in.
    file_key : str
        Key (object name) of the S3 object being processed.
    environment : str
        Environment the ArtifactProcessor is running in
        (e.g. ``"DEVELOPMENT"`` or ``"PRODUCTION"``).
    dry_run : str, optional
        Truthy value indicates a dry run in which side effects are skipped.
        Defaults to ``None``.
    """

    def __init__(
        self,
        s3_bucket: str,
        file_key: str,
        environment: str,
        dry_run: str | None = None,
    ) -> None:
        # Initialize Class Variables
        self.instrument_bucket_name = s3_bucket

        self.file_key = file_key

        # Variable that determines environment
        self.environment = environment

        # Variable that determines if ArtifactProcessor performs a Dry Run
        self.dry_run = dry_run

        # Process File
        self._process_artifacts()

    def _process_artifacts(self) -> None:
        """
        Main entry point for the ArtifactProcessor.

        Parses the file key, downloads the science file, and generates
        Slack and Timestream artifacts for it.

        Returns
        -------
        None
        """
        log.debug(
            {
                "status": "DEBUG",
                "message": "Generating Artifacts",
                "instrument_bucket_name": self.instrument_bucket_name,
                "file_key": self.file_key,
                "environment": self.environment,
                "dry_run": self.dry_run,
            }
        )

        # Parse file key to needed information
        parsed_file_key = parse_file_key(self.file_key)

        # Parse the science file name
        science_file = science_filename_parser(parsed_file_key)
        this_instr = science_file["instrument"]
        destination_bucket = get_instrument_bucket(this_instr, self.environment)

        # Download file from S3 or get local file path
        _ = get_science_file(
            self.instrument_bucket_name,
            self.file_key,
            parsed_file_key,
            self.dry_run,
        )

        # Generate Slack Artifacts
        self._generate_slack_artifacts(
            parsed_file_key,
        )

        # Generate Timestream Artifacts
        self._generate_timestream_artifacts(
            self.file_key,
            parsed_file_key,
            destination_bucket,
            self.environment,
        )

    @staticmethod
    def _generate_slack_artifacts(
        filename_path: str,
    ) -> None:
        """
        Send Slack notifications for the file processing pipeline.

        Handles errors raised by the Slack API so that failures do not
        interrupt processing of subsequent artifacts.

        Parameters
        ----------
        filename_path : str
            Pathname of the new file to announce in Slack.

        Returns
        -------
        None
        """
        try:
            # Initialize the slack client
            slack_client = get_slack_client(
                slack_token=os.getenv("SDC_AWS_SLACK_TOKEN")
            )

            # Initialize the slack channel
            slack_channel = os.getenv("SDC_AWS_SLACK_CHANNEL")

            # Send Slack Notification
            if slack_client and slack_channel:
                send_pipeline_notification(
                    slack_client=slack_client,
                    slack_channel=slack_channel,
                    path=filename_path,
                    alert_type="processed",
                )

        except SlackApiError as e:
            error_code = int(e.response["Error"]["Code"])
            if error_code == 404:
                log.error(
                    {
                        "status": "ERROR",
                        "message": "Slack Token is invalid",
                    }
                )

        except Exception as e:
            log.error(
                {
                    "status": "ERROR",
                    "message": f"Error when initializing slack client: {e}",
                }
            )

    @staticmethod
    def _generate_timestream_artifacts(
        file_key: str,
        new_file_key: str,
        destination_bucket: str,
        environment: str,
    ) -> None:
        """
        Log file processing events to Amazon Timestream.

        Initializes the Timestream client and records a ``PUT`` action
        for the processed file.

        Parameters
        ----------
        file_key : str
            Key of the original file.
        new_file_key : str
            Key of the processed file.
        destination_bucket : str
            Name of the S3 bucket where the processed file is stored.
        environment : str
            Current running environment.

        Returns
        -------
        None
        """
        try:
            # Initialize Timestream Client
            timestream_client = create_timestream_client_session(TSD_REGION)

            if timestream_client:
                # Log to timeseries database
                log_to_timestream(
                    timestream_client=timestream_client,
                    action_type="PUT",
                    file_key=file_key,
                    new_file_key=new_file_key,
                    source_bucket=destination_bucket,
                    destination_bucket=destination_bucket,
                    environment=environment,
                )

        except botocore.exceptions.ClientError:
            log.error(
                {
                    "status": "ERROR",
                    "message": "Timestream Client could not be initialized",
                }
            )
