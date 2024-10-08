"""
This Module contains the ArtifactProcessor class that will distinguish
the appropriate HERMES intrument library to use when processing
the artifacts for science files based off which bucket the file is located in.
"""

import os
import json
from pathlib import Path

import boto3
import botocore

from itertools import combinations

import swxsoc

from sdc_aws_utils.logging import log, configure_logger
from sdc_aws_utils.config import (
    TSD_REGION,
    parser as science_filename_parser,
    get_instrument_bucket,
)
from sdc_aws_utils.aws import (
    create_timestream_client_session,
    log_to_timestream,
    get_science_file,
    parse_file_key,
)

from sdc_aws_utils.slack import (
    get_slack_client,
    send_pipeline_notification,
    SlackApiError,
)


import cdftracker

# Configure logger
configure_logger()


def handle_event(event, context) -> dict:
    """
    Handles the event passed to the lambda function to initialize the ArtifactProcessor

    :param event: Event data passed from the lambda trigger
    :type event: dict
    :param context: Lambda context
    :type context: dict
    :return: Returns a 200 (Successful) / 500 (Error) HTTP response
    :rtype: dict
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
    The ArtifactProcessor class will then determine which instrument
    library to use to process the file.

    :param s3_bucket: The name of the S3 bucket the file is located in
    :type s3_bucket: str
    :param file_key: The name of the S3 object that is being processed
    :type file_key: str
    :param environment: The environment the ArtifactProcessor is running in
    :type environment: str
    :param dry_run: Whether or not the ArtifactProcessor is performing a dry run
    :type dry_run: bool
    """

    def __init__(
        self, s3_bucket: str, file_key: str, environment: str, dry_run: str = None
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
        This method serves as the main entry point for the ArtifactProcessor class.
        It will then determine which instrument library to use to process the file.

        :return: None
        :rtype: None
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
        file_path = get_science_file(
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

        # Generate CDFTracker Artifacts
        self._generate_cdftracker_artifacts(
            science_filename_parser,
            file_path,
        )

    @staticmethod
    def _generate_slack_artifacts(
        filename_path,
    ):
        """
        Generates and sends Slack notifications for the file processing pipeline.
        Includes error handling for Slack API interactions.

        :param filename_path: The pathname of the new file.
        :type filename_path: str
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
        file_key, new_file_key, destination_bucket, environment
    ):
        """
        Logs file processing events to Amazon Timestream.
        Handles the initialization of the Timestream client
        and logs the necessary information.

        :param file_key: The key of the original file.
        :type file_key: str
        :param new_file_key: The key of the processed file.
        :type new_file_key: str
        :param destination_bucket: The name of the S3 bucket where the processed file is stored.
        :type destination_bucket: str
        :param environment: The current running environment.
        :type environment: str
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

    @staticmethod
    def _generate_cdftracker_artifacts(science_filename_parser, file_path):
        """
        Tracks processed science product in the CDF Tracker file database.
        It involves initializing the database engine, setting up database tables,
        and tracking both the original and processed files.

        :param science_filename_parser: The parser function to process file names.
        :type science_filename_parser: function
        :param file_path: The path of the original file.
        :type file_path: Path
        """
        secret_arn = os.getenv("RDS_SECRET_ARN", None)
        if secret_arn:
            try:
                # Get Database Credentials
                session = boto3.session.Session()
                client = session.client(service_name="secretsmanager")
                response = client.get_secret_value(SecretId=secret_arn)
                secret = json.loads(response["SecretString"])
                connection_string = (
                    f"postgresql://{secret['username']}:{secret['password']}@"
                    f"{secret['host']}:{secret['port']}/{secret['dbname']}"
                )

                cdftracker_config = ArtifactProcessor.get_cdftracker_config(
                    swxsoc.config
                )

                log.info(swxsoc.config)

                log.info(cdftracker_config)

                cdftracker.set_config(cdftracker_config)

                from cdftracker.database import create_engine
                from cdftracker.database.tables import create_tables
                from cdftracker.tracker import tracker

                # Initialize the database engine
                database_engine = create_engine(connection_string)

                # Setup the database tables if they do not exist
                create_tables(database_engine)

                # Set tracker to CDFTracker
                cdf_tracker = tracker.CDFTracker(
                    database_engine, science_filename_parser
                )

                if cdf_tracker:
                    # Track processed file in CDF
                    cdf_tracker.track(Path(file_path))

            except Exception as e:
                log.error(
                    {
                        "status": "ERROR",
                        "message": f"Error when initializing database engine: {e}",
                    }
                )

    @staticmethod
    def get_cdftracker_config(swxsoc_config: dict) -> dict:
        """
        Creates the CDFTracker configuration from the swxsoc configuration.

        :param config: The swxsoc configuration.
        :type config: dict
        :return: The CDFTracker configuration.
        :rtype: dict
        """
        mission_data = swxsoc_config["mission"]
        instruments = mission_data["inst_names"]

        instruments_list = [
            {
                "instrument_id": idx + 1,
                "description": (
                    f"{mission_data['inst_fullnames'][idx]} "
                    f"({mission_data['inst_targetnames'][idx]})"
                ),
                "full_name": mission_data["inst_fullnames"][idx],
                "short_name": mission_data["inst_shortnames"][idx],
            }
            for idx in range(len(instruments))
        ]

        # Generate all possible configurations of the instruments
        instrument_configurations = []
        config_id = 1
        for r in range(1, len(instruments) + 1):
            for combo in combinations(range(1, len(instruments) + 1), r):
                config = {"instrument_configuration_id": config_id}
                config.update(
                    {
                        f"instrument_{i+1}_id": combo[i] if i < len(combo) else None
                        for i in range(len(instruments))
                    }
                )
                instrument_configurations.append(config)
                config_id += 1

        cdftracker_config = {
            "mission_name": mission_data["mission_name"],
            "instruments": instruments_list,
            "instrument_configurations": instrument_configurations,
        }

        return cdftracker_config
