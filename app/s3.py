"""AWS S3 helper for the API."""
import os

import boto3
import pandas as pd
from dotenv import load_dotenv

# Load AWS settings from the .env file (boto3 reads the keys from environment variables)
load_dotenv()

s3 = boto3.client("s3")
PREFIX = "raw/"


def _bucket() -> str:
    """Read the bucket name when it is needed, so the app can start without it (e.g. in tests)."""
    return os.environ["S3_BUCKET"]


def list_files():
    """List CSV files in the raw/ folder of the bucket."""
    response = s3.list_objects_v2(Bucket=_bucket(), Prefix=PREFIX)
    return [
        {
            "name": obj["Key"].removeprefix(PREFIX),
            "size_bytes": obj["Size"],
            "last_modified": obj["LastModified"],
        }
        for obj in response.get("Contents", [])
        if not obj["Key"].endswith("/")  # skip the folder placeholder
    ]


def preview_file(name: str, rows: int):
    """Read the first rows of a CSV file in raw/ and return them as records."""
    obj = s3.get_object(Bucket=_bucket(), Key=PREFIX + name)
    df = pd.read_csv(obj["Body"], nrows=rows, dtype=str)
    # Replace NaN with None so the result can be returned as JSON
    df = df.astype(object).where(df.notna(), None)
    return df.to_dict(orient="records")
