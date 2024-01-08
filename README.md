# SWSOC File Artifacts Lambda Container

| **CodeBuild Status** |![aws build status](https://codebuild.us-east-2.amazonaws.com/badges?uuid=eyJlbmNyeXB0ZWREYXRhIjoiNi9WaG5pa1V4MUpoVURjRXlWc0w5d1lKR293RWJPSGtudmUzNHljd2JWaHZaQ09TVE12UTVOMWdFdU9rMFA1QWs0eCtLTW9vblV1emNwQ01HN0hqMm9vPSIsIml2UGFyYW1ldGVyU3BlYyI6IjdUVHlYZUZsc0dCV2lnUDAiLCJtYXRlcmlhbFNldFNlcmlhbCI6MX0%3D&branch=main)|
|-|-|

### **Base Image Used For Container:** https://github.com/HERMES-SOC/docker-lambda-base 

### **Description**:
This repository is to define the image to be used for the SWSOC file artifacts Lambda function container. This container will be built and and stored in an ECR Repo. 
The container will contain the latest release code as the production environment and the latest code on master as the development. Files with the appropriate naming convention will be handled in production while files prefixed with `dev_` will be handled using the development environment.

### **Testing Locally (Using own Test Data)**:
1. Build the lambda container image (from within the lambda_function folder) you'd like to test: 
    
    `docker build -t artifacts_function:latest .`

2. Run the lambda container image you've built (After using your mfa script), this will start the lambda runtime environment:
    
    `docker run -p 9000:8080 -v /home/dbarrous/dbarrous/sdc_aws_artifacts_lambda/lambda_function/tests/test_data:/test_data -e SDC_AWS_FILE_PATH=/test_data/hermes_EEA_l0_2023042-000000_v0.bin artifacts_function:latest`

3. From a `separate` terminal, make a curl request to the running lambda function:

    `curl -XPOST "http://localhost:9000/2015-03-31/functions/function/invocations" -d @lambda_function/tests/test_data/test_eea_event.json`

### **Testing Locally (Using own Instrument Package Test Data)**:
1. Build the lambda container image (from within the lambda_function folder) you'd like to test: 
    
    `docker build -t artifacts_function:latest .`

2. Run the lambda container image you've built (After using your mfa script), this will start the lambda runtime environment:
    
    `docker run -p 9000:8080 -v /home/dbarrous/dbarrous/sdc_aws_artifacts_lambda/lambda_function/tests/test_data:/test_data -e USE_INSTRUMENT_TEST_DATA=True artifacts_function:latest`

3. From a `separate` terminal, make a curl request to the running lambda function:

    `curl -XPOST "http://localhost:9000/2015-03-31/functions/function/invocations" -d @lambda_function/tests/test_data/test_eea_event.json`
