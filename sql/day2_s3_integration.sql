-- =====================================================
-- Day 2: Load data from AWS S3 into Snowflake
-- =====================================================

USE ROLE ACCOUNTADMIN;
USE WAREHOUSE DEV_WH;

-- Step 1: Create a storage integration that assumes an IAM role in AWS
-- (no AWS credentials are stored in Snowflake)
CREATE STORAGE INTEGRATION S3_DRUG_INT
  TYPE = EXTERNAL_STAGE
  STORAGE_PROVIDER = 'S3'
  ENABLED = TRUE
  STORAGE_AWS_ROLE_ARN = 'arn:aws:iam::<AWS_ACCOUNT_ID>:role/snowflake-s3-role'
  STORAGE_ALLOWED_LOCATIONS = ('s3://monica-drug-shortage-2026/raw/');

-- Step 2: Get the Snowflake IAM user ARN and external ID
-- (used to update the trust policy of the IAM role in AWS)
DESC INTEGRATION S3_DRUG_INT;

-- Step 3: Create an external stage pointing to the raw/ folder in S3
CREATE STAGE DRUG_DB.RAW.S3_RAW_STAGE
  STORAGE_INTEGRATION = S3_DRUG_INT
  URL = 's3://monica-drug-shortage-2026/raw/'
  FILE_FORMAT = (
    TYPE = CSV
    SKIP_HEADER = 1
    FIELD_OPTIONALLY_ENCLOSED_BY = '"'
    EMPTY_FIELD_AS_NULL = TRUE
  );

-- Step 4: Test the connection by listing files in the stage
LIST @DRUG_DB.RAW.S3_RAW_STAGE;

-- Step 5: Create a new table with the same structure as the SHORTAGE table
CREATE TABLE DRUG_DB.RAW.SHORTAGE_S3 LIKE DRUG_DB.RAW.SHORTAGE;

-- Step 6: Load data from S3 through the external stage
COPY INTO DRUG_DB.RAW.SHORTAGE_S3
FROM @DRUG_DB.RAW.S3_RAW_STAGE
PATTERN = '.*shortage_clean[.]csv';

-- Step 7: Check the row count (expected: 10416)
SELECT COUNT(*) FROM DRUG_DB.RAW.SHORTAGE_S3;

-- Step 8: Run COPY INTO again to show it skips files already loaded (idempotent)
COPY INTO DRUG_DB.RAW.SHORTAGE_S3
FROM @DRUG_DB.RAW.S3_RAW_STAGE
PATTERN = '.*shortage_clean[.]csv';

-- Step 9: Compare the two tables (expected: 0 rows, meaning they are identical)
SELECT * FROM DRUG_DB.RAW.SHORTAGE_S3
MINUS
SELECT * FROM DRUG_DB.RAW.SHORTAGE;
