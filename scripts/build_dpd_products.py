"""Build a product table from Health Canada's Drug Product Database (DPD).

Input:  data/dpd/marketed/, data/dpd/cancelled/, data/dpd/dormant/
        (unzipped allfiles.zip, allfiles_ia.zip and allfiles_dr.zip)
Output: data/dpd_products.csv  (one row per human drug product)

For each product we keep the active-ingredient group, the company, and the
dates it entered and left the market. These dates let us count how many
alternative products were on the market on the day a shortage started,
without using information from the future.

Run from the project root:
    python scripts/build_dpd_products.py
"""
from pathlib import Path

import pandas as pd

DPD_DIR = Path("data") / "dpd"
OUTPUT_FILE = Path("data") / "dpd_products.csv"

# Each folder holds the same files; cancelled and dormant files have a suffix
FOLDERS = {"marketed": "", "cancelled": "_ia", "dormant": "_dr"}

# The DPD extract files have no header row; these names follow the DPD read-me
DRUG_COLUMNS = [
    "DRUG_CODE", "PRODUCT_CATEGORIZATION", "CLASS", "DIN", "BRAND_NAME",
    "DESCRIPTOR", "PEDIATRIC_FLAG", "ACCESSION_NUMBER", "NUMBER_OF_AIS",
    "LAST_UPDATE_DATE", "AI_GROUP_NO", "CLASS_F", "BRAND_NAME_F", "DESCRIPTOR_F",
]
STATUS_COLUMNS = [
    "DRUG_CODE", "CURRENT_STATUS_FLAG", "STATUS", "HISTORY_DATE",
    "STATUS_F", "LOT_NUMBER", "EXPIRATION_DATE",
]
COMP_COLUMNS = [
    "DRUG_CODE", "MFR_CODE", "COMPANY_CODE", "COMPANY_NAME", "COMPANY_TYPE",
    "ADDRESS_MAILING_FLAG", "ADDRESS_BILLING_FLAG", "ADDRESS_NOTIFICATION_FLAG",
    "ADDRESS_OTHER", "SUITE_NUMBER", "STREET_NAME", "CITY_NAME", "PROVINCE",
    "COUNTRY", "POSTAL_CODE", "POST_OFFICE_BOX", "PROVINCE_F", "COUNTRY_F",
]

# Statuses that mean the product has left the market
OFF_MARKET = {"DORMANT", "CANCELLED POST MARKET", "CANCELLED (UNRETURNED ANNUAL)"}


def read_dpd(folder: str, name: str, columns: list) -> pd.DataFrame:
    """Read one DPD file (no header) from a folder, if the folder exists."""
    path = DPD_DIR / folder / f"{name}{FOLDERS[folder]}.txt"
    if not path.exists():
        print(f"  skipped (not found): {path}")
        return pd.DataFrame(columns=columns)
    df = pd.read_csv(path, header=None, dtype=str, encoding="utf-8")
    df = df.iloc[:, : len(columns)]
    df.columns = columns[: df.shape[1]]
    return df


def main():
    drugs, statuses, companies = [], [], []
    for folder in FOLDERS:
        print(f"Reading {folder} products")
        drugs.append(read_dpd(folder, "drug", DRUG_COLUMNS))
        statuses.append(read_dpd(folder, "status", STATUS_COLUMNS))
        companies.append(read_dpd(folder, "comp", COMP_COLUMNS))

    drug = pd.concat(drugs, ignore_index=True).drop_duplicates("DRUG_CODE")
    status = pd.concat(statuses, ignore_index=True)
    comp = pd.concat(companies, ignore_index=True).drop_duplicates("DRUG_CODE")

    # Keep human drugs only (no veterinary, disinfectant or radiopharmaceutical)
    drug = drug[drug["CLASS"] == "Human"]

    status["HISTORY_DATE"] = pd.to_datetime(
        status["HISTORY_DATE"], format="%d-%b-%Y", errors="coerce"
    )

    # Market entry: the first date the product was marketed
    market_start = (
        status[status["STATUS"] == "MARKETED"]
        .groupby("DRUG_CODE")["HISTORY_DATE"].min()
        .rename("MARKET_START")
    )

    # Market exit: the date of the current status, if that status is off-market
    current = status[status["CURRENT_STATUS_FLAG"] == "Y"]
    market_end = (
        current[current["STATUS"].isin(OFF_MARKET)]
        .groupby("DRUG_CODE")["HISTORY_DATE"].max()
        .rename("MARKET_END")
    )

    products = (
        drug[["DRUG_CODE", "DIN", "BRAND_NAME", "AI_GROUP_NO", "NUMBER_OF_AIS"]]
        .merge(comp[["DRUG_CODE", "COMPANY_NAME"]], on="DRUG_CODE", how="left")
        .merge(market_start, on="DRUG_CODE", how="left")
        .merge(market_end, on="DRUG_CODE", how="left")
    )

    # Products that were never marketed cannot be alternatives during a shortage
    before = len(products)
    products = products[products["MARKET_START"].notna()]
    print(f"Removed {before - len(products)} products that were never marketed")

    # The first 7 digits of AI_GROUP_NO identify the active ingredient(s);
    # all 10 digits also include the strength
    products["AI_GROUP"] = products["AI_GROUP_NO"].str[:7]

    # Same company-name cleaning as in clean_shortages.py, so names can be matched
    products["COMPANY_NAME"] = (
        products["COMPANY_NAME"].str.upper()
        .str.replace(r"[^A-Z0-9 ]", " ", regex=True)
        .str.replace(r"\s+", " ", regex=True)
        .str.strip()
    )

    products.to_csv(OUTPUT_FILE, index=False, date_format="%Y-%m-%d")
    print(f"Saved {len(products)} human drug products to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()