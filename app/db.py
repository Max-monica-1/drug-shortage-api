"""Snowflake connection helper for the API."""
import os

import snowflake.connector
from dotenv import load_dotenv

# Load connection settings from the .env file
load_dotenv()


def get_connection():
    """Open a Snowflake connection for one request and close it afterwards."""
    conn = snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        authenticator="SNOWFLAKE_JWT",
        private_key_file=os.environ["SNOWFLAKE_PRIVATE_KEY_PATH"],
        role=os.environ["SNOWFLAKE_ROLE"],
        warehouse=os.environ["SNOWFLAKE_WAREHOUSE"],
        database=os.environ["SNOWFLAKE_DATABASE"],
        schema=os.environ["SNOWFLAKE_SCHEMA"],
    )
    try:
        yield conn
    finally:
        conn.close()