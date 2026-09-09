========
Overview
========

.. start-badges

.. list-table::
    :stub-columns: 1

    * - build status
      - |testing| |codestyle| |coverage|

.. |testing| image:: https://github.com/swxsoc/sdc_aws_artifacts_lambda/actions/workflows/testing.yml/badge.svg
    :target: https://github.com/swxsoc/sdc_aws_artifacts_lambda/actions/workflows/testing.yml
    :alt: testing status

.. |codestyle| image:: https://github.com/swxsoc/sdc_aws_artifacts_lambda/actions/workflows/codestyle.yml/badge.svg
    :target: https://github.com/swxsoc/sdc_aws_artifacts_lambda/actions/workflows/codestyle.yml
    :alt: codestyle and linting

.. |coverage| image:: https://codecov.io/gh/swxsoc/sdc_aws_artifacts_lambda/graph/badge.svg
    :target: https://codecov.io/gh/swxsoc/sdc_aws_artifacts_lambda
    :alt: code coverage

.. end-badges

This repository defines the image to be used for the SWSOC file artifacts Lambda function container. 
This container will be built and and stored in an ECR Repo. 
The container will contain the latest release code as the production environment and the latest code on ``main`` as the development.

Deployment contract
-------------------

CodeBuild publishes only an exact current ``main`` commit or a release tag.
Pull requests, stale commits, and other branches finish without pushing an
image. The mission is derived from the CodeBuild project name. Development is
the default; ``CDK_ENVIRONMENT=PRODUCTION`` or a release tag selects
production.

When a mission base-image build starts this project, it passes a versioned
``PUBLIC_ECR_REPO`` URI and the normalized ``CDK_ENVIRONMENT``. The build
verifies that the URI belongs to the expected mission and environment and
rejects ``latest`` before using it. Direct Lambda builds fall back to the
matching mission base image's ``latest`` tag. Successful image pushes start
the mission's architecture project from its ``main`` branch with the immutable
Lambda tag.

Running Unit Tests
------------------

.. code-block:: sh

    pytest --pyargs lambda_function/tests --cov=lambda_function/src --cov-report=html

Testing Locally (Using own Test Data)
-------------------------------------

The container image can be built and run locally. You can specify the base image at runtime.
By default, the Dockerfile uses
``dev-swsoc-docker-lambda-base:latest``. Mission CodeBuild projects select
their matching base image.

.. code-block:: sh

    # Chose a Base Image for you desired mission
    export BASE_IMAGE=public.ecr.aws/w5r9l1c8/padre-swsoc-docker-lambda-base:latest
    export IMAGE_NAME=swxsoc_sdc_aws_artifacts_lambda
    export VERSION=$(date -u +"%Y%m%d%H%M%S")

    # Build the image
    docker build --no-cache --build-arg BASE_IMAGE=$BASE_IMAGE -t $IMAGE_NAME:latest lambda_function/.

    # Tag the image with a version
    docker tag $IMAGE_NAME:latest $IMAGE_NAME:$VERSION

Run the lambda container image you've built (After using your mfa script), this will start the lambda runtime environment:

.. code-block:: sh

    docker run -p 9000:8080 \
      -v ~/lambda_function/tests/test_data:/test_data \
      -e SDC_AWS_FILE_PATH=/test_data/hermes_EEA_l0_2023042-000000_v0.bin \
      artifacts_function:latest

From a **separate** terminal, make a curl request to the running lambda function:

.. code-block:: sh

    curl -XPOST "http://localhost:9000/2015-03-31/functions/function/invocations" \
      -d @lambda_function/tests/test_data/test_eea_event.json

Testing Locally (Using own Instrument Package Test Data)
--------------------------------------------------------

Run the lambda container image you've built (After using your mfa script), this will start the lambda runtime environment:

.. code-block:: sh

    docker run -p 9000:8080 \
      -v ~/lambda_function/tests/test_data:/test_data \
      -e USE_INSTRUMENT_TEST_DATA=True \
      artifacts_function:latest

From a **separate** terminal, make a curl request to the running lambda function:

.. code-block:: sh

    curl -XPOST "http://localhost:9000/2015-03-31/functions/function/invocations" \
      -d @lambda_function/tests/test_data/test_eea_event.json


Acknowledgements
----------------

The package template used by this package is based on the one developed by the
`NASA Space Weather Science Operations Center (SWxSOC) <https://swxsoc.github.io>`_ which is based on those provided by
`OpenAstronomy community <https://openastronomy.org>`_ and the `SunPy Project <https://sunpy.org/>`_.

This project makes use of the `NASA Space Weather Science Operations Center (SWxSOC) <https://swxsoc.github.io>`_.
