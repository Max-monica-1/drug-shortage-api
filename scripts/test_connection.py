"""Test the connection to Snowflake using key-pair authentication."""
import os

import pandas as pd
import snowflake.connector
from dotenv import load_dotenv

# Load connection settings from the .env file
load_dotenv()

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
    cur = conn.cursor()

    # Check who we are connected as
    cur.execute("SELECT CURRENT_USER(), CURRENT_ROLE()")
    print("Connected as:", cur.fetchone())

    # Run a query and load the result into a pandas DataFrame
    cur.execute(
        """
        SELECT STATUS, COUNT(*) AS N
        FROM SHORTAGE
        GROUP BY STATUS
        ORDER BY N DESC
        """
    )
    columns = [col[0] for col in cur.description]
    df = pd.DataFrame(cur.fetchall(), columns=columns)
    print(df)
finally:
    conn.close()