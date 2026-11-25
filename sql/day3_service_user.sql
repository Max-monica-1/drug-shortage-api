-- =====================================================
-- Day 3: Read-only service user for the Python API
-- =====================================================

USE ROLE ACCOUNTADMIN;

-- Step 1: Create a read-only role
CREATE ROLE IF NOT EXISTS API_READER;
GRANT USAGE ON WAREHOUSE DEV_WH TO ROLE API_READER;
GRANT USAGE ON DATABASE DRUG_DB TO ROLE API_READER;
GRANT USAGE ON SCHEMA DRUG_DB.RAW TO ROLE API_READER;
GRANT SELECT ON ALL TABLES IN SCHEMA DRUG_DB.RAW TO ROLE API_READER;
GRANT SELECT ON FUTURE TABLES IN SCHEMA DRUG_DB.RAW TO ROLE API_READER;

-- Step 2: Create a service user that authenticates with a key pair (no password)
-- Generate the key pair with scripts/generate_keypair.py
CREATE USER IF NOT EXISTS API_SVC
  TYPE = SERVICE
  DEFAULT_ROLE = API_READER
  DEFAULT_WAREHOUSE = DEV_WH
  DEFAULT_NAMESPACE = DRUG_DB.RAW
  RSA_PUBLIC_KEY = '<YOUR_PUBLIC_KEY>';

GRANT ROLE API_READER TO USER API_SVC;

-- Step 3: Verify the public key is set (RSA_PUBLIC_KEY_FP should have a value)
DESC USER API_SVC;

-- Step 4: Get the account identifier for the Python connection
SELECT CURRENT_ORGANIZATION_NAME() || '-' || CURRENT_ACCOUNT_NAME() AS ACCOUNT_IDENTIFIER;