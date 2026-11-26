"""Clean the raw shortage export from Health Product Shortages Canada.

Input:  data/shortage_full_raw.csv  (export from healthproductshortages.ca)
Output: data/shortage_full_clean.csv

Run from the project root:
    python scripts/clean_shortages.py
"""
from pathlib import Path

import pandas as pd

RAW_FILE = Path("data") / "shortage_full_raw.csv"
CLEAN_FILE = Path("data") / "shortage_full_clean.csv"

# Map the export's long column names to short, SQL-friendly names
COLUMN_NAMES = {
    "Report ID": "REPORT_ID",
    "Drug Identification Number": "DIN",
    "Report Type": "REPORT_TYPE",
    "Brand name": "BRAND_NAME",
    "Company Name": "COMPANY_NAME",
    "Common or Proper name": "COMMON_NAME",
    "Ingredients": "INGREDIENTS",
    "Strength(s)": "STRENGTH",
    "Packaging size": "PACKAGING_SIZE",
    "Route of administration": "ROUTE",
    "Shortage status": "STATUS",
    "Dosage form(s)": "DOSAGE_FORM",
    "Anatomical Therapeutical Chemical (ATC) Code": "ATC_CODE",
    "Anatomical Therapeutical Chemical (ATC) description": "ATC_DESCRIPTION",
    "Anticipated start date": "ANTICIPATED_START_DATE",
    "Actual start date": "ACTUAL_START_DATE",
    "Estimated end date": "ESTIMATED_END_DATE",
    "Actual end date": "ACTUAL_END_DATE",
    "Reason": "REASON",
    "Date Created": "DATE_CREATED",
    "Date Updated": "DATE_UPDATED",
    "Tier 3": "TIER_3",
}

DATE_COLUMNS = [
    "ANTICIPATED_START_DATE", "ACTUAL_START_DATE", "ESTIMATED_END_DATE",
    "ACTUAL_END_DATE", "DATE_CREATED", "DATE_UPDATED",
]


def normalize_company(name: pd.Series) -> pd.Series:
    """Uppercase, drop punctuation and extra spaces, so spelling variants match."""
    return (
        name.str.upper()
        .str.replace(r"[^A-Z0-9 ]", " ", regex=True)
        .str.replace(r"\s+", " ", regex=True)
        .str.strip()
    )


def normalize_ingredients(ingredients: pd.Series) -> pd.Series:
    """Uppercase and sort the ingredient list, so 'B; A' and 'a; b' become 'A; B'."""
    def clean_one(value):
        if pd.isna(value):
            return value
        parts = sorted({part.strip().upper() for part in value.split(";") if part.strip()})
        return "; ".join(parts)

    return ingredients.map(clean_one)


def main():
    # The first line of the export is a disclaimer, the real header is on line 2
    df = pd.read_csv(RAW_FILE, skiprows=1, dtype=str, encoding="utf-8-sig")
    df = df.rename(columns=COLUMN_NAMES)
    print(f"Raw rows: {len(df)}")

    # Clean text: remove line breaks, stray backslashes and surrounding spaces
    text_columns = [col for col in df.columns if col not in DATE_COLUMNS]
    for col in text_columns:
        df[col] = (
            df[col].str.replace(r"[\r\n]+", " ", regex=True)
            .str.replace("\\", "", regex=False)
            .str.strip()
        )

    # Standardize names that are used to group and count records
    df["COMPANY_NAME"] = normalize_company(df["COMPANY_NAME"])
    df["INGREDIENTS"] = normalize_ingredients(df["INGREDIENTS"])
    for col in ["ROUTE", "DOSAGE_FORM"]:
        df[col] = df[col].str.upper()

    # Convert date columns; invalid dates become empty (NaT)
    for col in DATE_COLUMNS:
        df[col] = pd.to_datetime(df[col], errors="coerce")

    # Dates before 1900 are typos (for example year 0017 or 0001): treat them as missing
    for col in DATE_COLUMNS:
        bad = df[col] < "1900-01-01"
        if bad.any():
            print(f"Cleared {bad.sum()} impossible dates in {col}")
            df.loc[bad, col] = pd.NaT

    # Remove exact duplicate reports
    before = len(df)
    df = df.drop_duplicates(subset="REPORT_ID")
    print(f"Removed {before - len(df)} duplicate report IDs")

    # The same product (DIN) with the same start date is the same shortage
    # reported more than once: keep the most recently updated report
    has_start = df["ACTUAL_START_DATE"].notna()
    before = len(df)
    dated = (
        df[has_start]
        .sort_values("DATE_UPDATED")
        .drop_duplicates(subset=["DIN", "ACTUAL_START_DATE"], keep="last")
    )
    df = pd.concat([dated, df[~has_start]], ignore_index=True)
    print(f"Removed {before - len(df)} repeated reports of the same DIN and start date")

    # Remove records where the shortage ends before it starts (data entry errors)
    bad_dates = df["ACTUAL_END_DATE"] < df["ACTUAL_START_DATE"]
    df = df[~bad_dates]
    print(f"Removed {bad_dates.sum()} records with end date before start date")

    df = df.sort_values("REPORT_ID", key=lambda s: s.astype(int)).reset_index(drop=True)
    df.to_csv(CLEAN_FILE, index=False, date_format="%Y-%m-%d")
    print(f"Clean rows: {len(df)}  ->  saved to {CLEAN_FILE}")


if __name__ == "__main__":
    main()
