"""Drug Shortage API built with FastAPI."""
from typing import Literal

from botocore.exceptions import ClientError
from fastapi import Depends, FastAPI, HTTPException, Path, Query
from snowflake.connector import DictCursor

from app import s3
from app.db import get_connection
from app.predict_api import router as predict_router

app = FastAPI(
    title="Drug Shortage API",
    description="Serves Canadian drug shortage data from Snowflake and AWS S3.",
    version="0.1.0",
)
app.include_router(predict_router)

@app.get("/")
def root():
    """Health check endpoint."""
    return {"status": "ok", "message": "Drug Shortage API is running"}


@app.get("/shortages")
def list_shortages(
    drug: str | None = Query(None, description="Search brand name or ingredient"),
    status: str | None = Query(None, description="e.g. 'Actual shortage', 'Resolved'"),
    limit: int = Query(20, ge=1, le=100, description="Max rows to return"),
    conn=Depends(get_connection),
):
    """Return shortage reports, optionally filtered by drug and status."""
    sql = """
        SELECT REPORT_ID, DIN, BRAND_NAME, COMPANY_NAME, INGREDIENTS,
               STATUS, ACTUAL_START_DATE, ACTUAL_END_DATE, REASON
        FROM SHORTAGE_FULL
        WHERE 1 = 1
    """
    params = {}

    # Add filters only when they are provided (parameterized to prevent SQL injection)
    if drug:
        sql += " AND (BRAND_NAME ILIKE %(drug)s OR INGREDIENTS ILIKE %(drug)s)"
        params["drug"] = f"%{drug}%"
    if status:
        sql += " AND STATUS = %(status)s"
        params["status"] = status

    sql += " ORDER BY DATE_UPDATED DESC LIMIT %(limit)s"
    params["limit"] = limit

    cur = conn.cursor(DictCursor)
    cur.execute(sql, params)
    rows = cur.fetchall()

    # Return lowercase keys, which is the usual JSON style
    return [{key.lower(): value for key, value in row.items()} for row in rows]


# Columns that can be used for grouping (whitelist to keep the SQL safe)
STATS_COLUMNS = {
    "status": "STATUS",
    "reason": "REASON",
    "company": "COMPANY_NAME",
}


@app.get("/shortages/stats")
def shortage_stats(
    by: Literal["status", "reason", "company"] = Query(
        "status", description="Group shortage reports by this field"
    ),
    conn=Depends(get_connection),
):
    """Count shortage reports grouped by status, reason or company."""
    column = STATS_COLUMNS[by]
    sql = f"""
        SELECT {column} AS CATEGORY,
               COUNT(*) AS N,
               ROUND(COUNT(*) * 100 / SUM(COUNT(*)) OVER (), 1) AS PCT
        FROM SHORTAGE_FULL
        GROUP BY {column}
        ORDER BY N DESC
        LIMIT 20
    """
    cur = conn.cursor(DictCursor)
    cur.execute(sql)
    rows = cur.fetchall()
    return [{key.lower(): value for key, value in row.items()} for row in rows]

@app.get("/files")
def list_raw_files():
    """List raw data files stored in S3."""
    return s3.list_files()


@app.get("/files/{name}")
def preview_raw_file(
    name: str = Path(
        ..., pattern=r"^[\w.-]+\.csv$", description="CSV file name, e.g. shortage_clean.csv"
    ),
    rows: int = Query(5, ge=1, le=50, description="Number of rows to preview"),
):
    """Preview the first rows of a raw CSV file in S3."""
    try:
        return s3.preview_file(name, rows)
    except ClientError as error:
        code = error.response["Error"]["Code"]
        if code in ("NoSuchKey", "404", "AccessDenied", "403"):
            raise HTTPException(status_code=404, detail=f"File '{name}' not found")
        raise