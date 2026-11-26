-- =====================================================
-- Day 5: Load the full shortage history (2017 to 2026) from S3
-- =====================================================

USE ROLE ACCOUNTADMIN;
USE WAREHOUSE DEV_WH;

-- Step 1: Check that Snowflake can see the new file in S3
LIST @DRUG_DB.RAW.S3_RAW_STAGE;

-- Step 2: Create a new table with the same columns as the original SHORTAGE table
CREATE OR REPLACE TABLE DRUG_DB.RAW.SHORTAGE_FULL LIKE DRUG_DB.RAW.SHORTAGE;

-- Step 3: Load the cleaned full history from S3
COPY INTO DRUG_DB.RAW.SHORTAGE_FULL
FROM @DRUG_DB.RAW.S3_RAW_STAGE
PATTERN = '.*shortage_full_clean[.]csv';

-- Step 4: Check the row count (expected: 25719)
SELECT COUNT(*) FROM DRUG_DB.RAW.SHORTAGE_FULL;

-- Step 5: Check the date range and status mix
SELECT STATUS, COUNT(*) AS N, MIN(DATE_CREATED) AS FIRST_REPORT, MAX(DATE_CREATED) AS LAST_REPORT
FROM DRUG_DB.RAW.SHORTAGE_FULL
GROUP BY STATUS
ORDER BY N DESC;