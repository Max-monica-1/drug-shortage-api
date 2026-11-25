"""Drug Shortage API built with FastAPI."""
from fastapi import Depends, FastAPI, Query
from snowflake.connector import DictCursor

from app.db import get_connection

app = FastAPI(
    title="Drug Shortage API",
    description="Serves Canadian drug shortage data from Snowflake.",
    version="0.1.0",
)


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
        FROM SHORTAGE
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