"""Download the raw shortage CSV from S3 into the local data/ folder."""
import os
from pathlib import Path

import boto3
from dotenv import load_dotenv

# Load AWS settings from the .env file
load_dotenv()

bucket = os.environ["S3_BUCKET"]
key = "raw/shortage_clean.csv"
target = Path("data") / "shortage_clean.csv"

# Create the data/ folder if it does not exist yet
target.parent.mkdir(exist_ok=True)

boto3.client("s3").download_file(bucket, key, str(target))
print(f"Downloaded s3://{bucket}/{key} to {target}")