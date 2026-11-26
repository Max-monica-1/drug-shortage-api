"""Build the modeling table: one row per shortage report with all features.

Inputs:  data/shortage_full_clean.csv  (from clean_shortages.py)
         data/dpd_products.csv         (from build_dpd_products.py)
Output:  data/model_table.csv

Every feature is calculated as of the shortage's reference date (its start
date), using only information that was available on that day.

Run from the project root:
    python scripts/build_model_table.py
"""
from pathlib import Path

import pandas as pd

SHORTAGE_FILE = Path("data") / "shortage_full_clean.csv"
DPD_FILE = Path("data") / "dpd_products.csv"
OUTPUT_FILE = Path("data") / "model_table.csv"

LONG_SHORTAGE_DAYS = 90


def load_data():
    shortages = pd.read_csv(SHORTAGE_FILE, dtype=str)
    for col in ["ANTICIPATED_START_DATE", "ACTUAL_START_DATE", "ACTUAL_END_DATE",
                "DATE_CREATED", "DATE_UPDATED"]:
        shortages[col] = pd.to_datetime(shortages[col])

    products = pd.read_csv(DPD_FILE, dtype=str)
    for col in ["MARKET_START", "MARKET_END"]:
        products[col] = pd.to_datetime(products[col])
    return shortages, products


def add_basic_features(df):
    """Target, reference date and simple features taken from the report itself."""
    # Reference date: when the shortage started (or was expected to start)
    df["REF_DATE"] = (
        df["ACTUAL_START_DATE"]
        .fillna(df["ANTICIPATED_START_DATE"])
        .fillna(df["DATE_CREATED"])
    )

    # Target for resolved shortages
    df["DURATION_DAYS"] = (df["ACTUAL_END_DATE"] - df["ACTUAL_START_DATE"]).dt.days
    df["LONG_SHORTAGE"] = (df["DURATION_DAYS"] > LONG_SHORTAGE_DAYS).astype("Int64")
    df.loc[df["DURATION_DAYS"].isna(), "LONG_SHORTAGE"] = pd.NA

    df["ATC_GROUP"] = df["ATC_CODE"].str[0].fillna("UNKNOWN")
    df["MAIN_ROUTE"] = df["ROUTE"].str.split(";").str[0].str.strip().fillna("UNKNOWN")
    df["MAIN_DOSAGE_FORM"] = df["DOSAGE_FORM"].str.split(";").str[0].str.strip().fillna("UNKNOWN")
    df["REASON"] = df["REASON"].fillna("UNKNOWN")
    df["REPORTED_IN_ADVANCE"] = df["ANTICIPATED_START_DATE"].notna().astype(int)
    df["START_MONTH"] = df["REF_DATE"].dt.month
    return df


def add_history_features(df):
    """Counts of earlier reports, using only reports created before this one."""
    history = df.sort_values(["DATE_CREATED", "REPORT_ID"]).copy()
    history["ING_PRIOR_REPORTS"] = history.groupby("INGREDIENTS").cumcount()
    history["COMPANY_PRIOR_REPORTS"] = history.groupby("COMPANY_NAME").cumcount()
    cols = ["REPORT_ID", "ING_PRIOR_REPORTS", "COMPANY_PRIOR_REPORTS"]
    return df.merge(history[cols], on="REPORT_ID", how="left")


def add_concurrent_shortages(df, group_col):
    """Other shortages of the same ingredient that were active on the reference date."""
    left = df[["REPORT_ID", group_col, "REF_DATE"]].dropna(subset=[group_col])
    right = df[["REPORT_ID", group_col, "ACTUAL_START_DATE", "ACTUAL_END_DATE"]].rename(
        columns={"REPORT_ID": "OTHER_ID"}
    )
    pairs = left.merge(right, on=group_col)
    active = pairs[
        (pairs["OTHER_ID"] != pairs["REPORT_ID"])
        & (pairs["ACTUAL_START_DATE"] <= pairs["REF_DATE"])
        & (pairs["ACTUAL_END_DATE"].isna() | (pairs["ACTUAL_END_DATE"] > pairs["REF_DATE"]))
    ]
    counts = active.groupby("REPORT_ID").size().rename("CONCURRENT_SHORTAGES")
    return df.merge(counts, on="REPORT_ID", how="left")


def add_dpd_features(df, products):
    """Market features from the Drug Product Database, as of the reference date."""
    # Link each shortage to its product in DPD through the DIN
    own = products.drop_duplicates("DIN")[["DIN", "AI_GROUP", "AI_GROUP_NO", "MARKET_START"]]
    own = own.rename(columns={"MARKET_START": "OWN_MARKET_START"})
    df = df.merge(own, on="DIN", how="left")
    df["IN_DPD"] = df["AI_GROUP"].notna().astype(int)
    df["PRODUCT_AGE_YEARS"] = (
        (df["REF_DATE"] - df["OWN_MARKET_START"]).dt.days / 365.25
    ).round(1)

    # Pair each shortage with every product that has the same active ingredient(s)
    matched = df[df["IN_DPD"] == 1][["REPORT_ID", "DIN", "AI_GROUP", "AI_GROUP_NO", "REF_DATE"]]
    others = products[["DIN", "AI_GROUP", "AI_GROUP_NO", "COMPANY_NAME",
                       "MARKET_START", "MARKET_END"]].rename(
        columns={"DIN": "OTHER_DIN", "AI_GROUP_NO": "OTHER_AI_GROUP_NO",
                 "COMPANY_NAME": "OTHER_COMPANY"}
    )
    pairs = matched.merge(others, on="AI_GROUP")

    # Keep other products that were on the market on the reference date
    on_market = pairs[
        (pairs["OTHER_DIN"] != pairs["DIN"])
        & (pairs["MARKET_START"] <= pairs["REF_DATE"])
        & (pairs["MARKET_END"].isna() | (pairs["MARKET_END"] > pairs["REF_DATE"]))
    ]
    same_strength = on_market[on_market["OTHER_AI_GROUP_NO"] == on_market["AI_GROUP_NO"]]

    features = pd.DataFrame({
        "N_SAME_INGREDIENT_ON_MARKET": on_market.groupby("REPORT_ID").size(),
        "N_SAME_STRENGTH_ON_MARKET": same_strength.groupby("REPORT_ID").size(),
        "N_COMPANIES_SAME_INGREDIENT": on_market.groupby("REPORT_ID")["OTHER_COMPANY"].nunique(),
    })
    df = df.merge(features, on="REPORT_ID", how="left")

    # Matched products with no alternatives on the market get 0, not missing
    for col in features.columns:
        df.loc[df["IN_DPD"] == 1, col] = df.loc[df["IN_DPD"] == 1, col].fillna(0)
    return df


def main():
    shortages, products = load_data()
    print(f"Shortage reports: {len(shortages)}, DPD products: {len(products)}")

    df = add_basic_features(shortages)
    df = add_history_features(df)
    df = add_dpd_features(df, products)
    # Use the DPD ingredient group when available, otherwise the ingredient text
    df["INGREDIENT_KEY"] = df["AI_GROUP"].fillna(df["INGREDIENTS"])
    df = add_concurrent_shortages(df, "INGREDIENT_KEY")

    count_cols = ["ING_PRIOR_REPORTS", "COMPANY_PRIOR_REPORTS", "CONCURRENT_SHORTAGES"]
    df[count_cols] = df[count_cols].fillna(0).astype(int)

    print(f"Matched to DPD by DIN: {df['IN_DPD'].mean():.1%}")
    print(f"Resolved with a known duration: {df['LONG_SHORTAGE'].notna().sum()}")
    df.to_csv(OUTPUT_FILE, index=False, date_format="%Y-%m-%d")
    print(f"Saved {len(df)} rows and {df.shape[1]} columns to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
