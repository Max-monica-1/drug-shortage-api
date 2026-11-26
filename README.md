# Drug Shortage API

![CI](https://github.com/Max-monica-1/drug-shortage-api/actions/workflows/ci.yml/badge.svg)

An end-to-end data and machine learning project on Canadian drug shortages. Public shortage reports are cleaned and combined with Health Canada's Drug Product Database, stored in AWS S3 and Snowflake, analysed with survival models, and served through a FastAPI application that forecasts how soon a shortage is likely to be resolved.

## What it does

- Builds a reproducible pipeline from three public sources: shortage reports (2017 to 2026), the Drug Product Database, and the data stored in S3 and Snowflake.
- Estimates how long shortages last with Kaplan-Meier curves and a Cox proportional hazards model.
- Serves the data and the model through a FastAPI app, tested automatically with GitHub Actions on every pull request.

## Key findings

Based on 22,617 shortages that started between March 2017 and November 2026:

- **Half of all shortages are resolved within 61 days.** About 29% end within 30 days, 62% within 90 days and 88% within a year.
- **The reason matters most.** The median time to resolution is 35 days for shipping delays but 124 days for active ingredient shortages.
- **GMP compliance issues have the longest tail.** About 28% of them are still ongoing after a year.
- **Shortages are slower to resolve when other products with the same ingredient are also short**, which points to problems further up the supply chain.
- **The number of alternative products on the market barely changes how long a shortage lasts.** It probably matters more for patients than for the manufacturer's recovery.

| Reason | Shortages | Median days to resolution | Resolved within 90 days |
|---|---|---|---|
| Delay in shipping | 2,810 | 35 | 76% |
| Demand increase | 3,129 | 51 | 68% |
| Disruption of manufacturing | 13,990 | 66 | 60% |
| Other | 1,563 | 72 | 55% |
| GMP compliance | 643 | 91 | 49% |
| Inactive ingredient shortage | 173 | 96 | 48% |
| Active ingredient shortage | 309 | 124 | 41% |

## Architecture

```
healthproductshortages.ca (CSV export)      Drug Product Database (Health Canada)
               │                                         │
               ▼                                         ▼
     scripts/clean_shortages.py              scripts/build_dpd_products.py
               │                                         │
               └──────────────┬──────────────────────────┘
                              ▼
                 scripts/build_model_table.py  ──►  notebooks (analysis, models)
                              │                              │
                              ▼                              ▼
                   AWS S3 (raw/)                  models/survival_model.joblib
                              │ storage integration + IAM role          │
                              ▼                                          │
                   Snowflake (DRUG_DB.RAW)                               │
                              │ read-only service user, key-pair auth    │
                              ▼                                          ▼
                     FastAPI  ──►  /shortages, /shortages/stats, /files, /predict
                              ▲
                              └── GitHub Actions: ruff + pytest on every pull request
```

## Data pipeline

| Step | Script | What it does |
|---|---|---|
| Clean | `clean_shortages.py` | Standardizes company and ingredient names, removes 921 repeated reports of the same product and start date, removes 91 records that end before they start, clears impossible dates |
| Products | `build_dpd_products.py` | Combines marketed, cancelled and dormant products (43,333 human drugs) with the dates each entered and left the market |
| Features | `build_model_table.py` | Builds one row per shortage with features calculated as of the shortage start date. 99.3% of shortages match a product in the Drug Product Database |

## Modeling

### Avoiding misleading results

Three problems were found and fixed along the way:

- **Data leakage.** Every feature uses only information available on the day the shortage started. The company's latest estimated end date is excluded because it is updated during the shortage.
- **Censoring.** Ongoing shortages were first left out, which made recent shortages look shorter than they are (34% long in training vs 21% in testing). Labelling shortages that were already longer than 90 days as long fixed this (39.6% vs 38.1%). The survival models handle ongoing shortages directly.
- **Left truncation.** Mandatory reporting started in March 2017. The 548 shortages that started earlier only appear because they were still ongoing then (median 480 days vs 57 overall). They were excluded, which improved calibration.

### Survival model (used by the API)

A Cox proportional hazards model, evaluated on shortages that started from mid-2024 after training on earlier ones:

- C-index: 0.620
- When test shortages are split into five risk groups, the median time to resolution ranges from 33 days in the fastest group to 129 days in the slowest.
- Predicted and actual shares resolved within 90 days differ by at most 3.9 percentage points.

The final model was retrained on all 22,617 shortages.

### Classification models (ablation study)

Predicting whether a shortage lasts more than 90 days, ROC AUC on the most recent 20% of shortages:

| Features | Logistic regression | Gradient boosting | Random forest |
|---|---|---|---|
| A: report fields and history | 0.667 | 0.668 | 0.694 |
| B: + concurrent shortages | 0.678 | 0.672 | 0.698 |
| C: + Drug Product Database features | 0.677 | 0.695 | 0.707 |

Each feature group adds a small gain. Results stay around 0.70 because much of what decides a shortage's length, such as repair time or raw material supply, is not known when the shortage is reported. The model is most useful for ranking shortages by risk rather than predicting exact durations.

## API

| Method | Path | Source | Description |
|---|---|---|---|
| GET | `/` | – | Health check |
| GET | `/shortages` | Snowflake | Search by drug name or ingredient, filter by status |
| GET | `/shortages/stats` | Snowflake | Count shortages by status, reason or company |
| GET | `/files` | S3 | List raw data files |
| GET | `/files/{name}` | S3 | Preview the first rows of a raw CSV file |
| POST | `/predict` | Model | Chance of resolution within 30, 90 and 180 days |

Example request to `/predict`:

```json
{
  "reason": "Shortage of an active ingredient.",
  "atc_group": "C",
  "dosage_form": "TABLET",
  "company_name": "APOTEX INC",
  "concurrent_shortages": 3
}
```

Response:

```json
{
  "resolved_within_30_days": 0.184,
  "resolved_within_90_days": 0.456,
  "resolved_within_180_days": 0.639,
  "predicted_median_days": 106,
  "risk_level": "high"
}
```

With the same inputs but a shipping delay as the reason, the predicted median drops to 43 days and the risk level is low.

## Security choices

- **No passwords in code.** Snowflake uses key-pair authentication and secrets stay in a local `.env` file that Git ignores.
- **Least privilege.** The Snowflake service user can only read one schema. The AWS policies only allow reading the `raw/` folder.
- **No AWS keys in Snowflake.** Snowflake reads S3 by assuming an IAM role with an external ID.
- **Input checks.** SQL filters are parameterized, grouping columns come from a whitelist, file names must match a strict pattern, and model inputs are validated with Pydantic.

## Tests and CI

- 13 pytest tests cover the API and the model. Snowflake and S3 are replaced by fakes, so tests run without any credentials.
- The tests check, among other things, that user input never goes directly into SQL, that predicted probabilities rise over time, and that shipping delays are predicted to resolve faster than ingredient shortages.
- `ci.yml` runs on every pull request and every push to `main`. It calls a reusable workflow (`reusable-python-checks.yml`) that installs dependencies, runs ruff and runs pytest, on Python 3.10 and 3.12.

## Project structure

```
app/            FastAPI app, Snowflake and S3 helpers, survival model loader
models/         Trained Cox model
notebooks/      01 exploration, 02 classification models, 03 survival analysis
scripts/        Data pipeline and setup scripts
sql/            Snowflake and AWS setup, step by step
tests/          pytest tests
.github/        GitHub Actions workflows
```

## Running locally

1. Create a virtual environment and install the packages:
   ```
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements-dev.txt
   ```
2. Run the tests (no cloud accounts needed):
   ```
   pytest -v
   ```
3. To rebuild the data, put the shortage export in `data/shortage_full_raw.csv` and the unzipped Drug Product Database files in `data/dpd/`, then run:
   ```
   python scripts/clean_shortages.py
   python scripts/build_dpd_products.py
   python scripts/build_model_table.py
   ```
4. To connect to Snowflake and S3, run the SQL files in `sql/` in order, generate a key pair with `scripts/generate_keypair.py`, and create a `.env` file:
   ```
   SNOWFLAKE_ACCOUNT=<org>-<account>
   SNOWFLAKE_USER=API_SVC
   SNOWFLAKE_ROLE=API_READER
   SNOWFLAKE_WAREHOUSE=DEV_WH
   SNOWFLAKE_DATABASE=DRUG_DB
   SNOWFLAKE_SCHEMA=RAW
   SNOWFLAKE_PRIVATE_KEY_PATH=keys/rsa_key.p8
   AWS_ACCESS_KEY_ID=<your key>
   AWS_SECRET_ACCESS_KEY=<your secret>
   AWS_DEFAULT_REGION=us-east-2
   S3_BUCKET=<your bucket>
   ```
5. Start the API and open http://127.0.0.1:8000/docs:
   ```
   fastapi dev app/main.py
   ```

## Limitations and next steps

- The model is slightly optimistic for the slowest shortages, which may reflect drift. It should be retrained as new reports come in.
- The 0.40 threshold in the classification notebook was chosen on the test set. A separate validation set would be more rigorous.
- The classification notebook does not yet exclude shortages that started before March 2017.
- Adding US FDA shortage data could show when a shortage is part of a global supply problem.

## Data sources

- [Health Product Shortages Canada](https://healthproductshortages.ca): shortage reports submitted by drug companies
- [Drug Product Database](https://www.canada.ca/en/health-canada/services/drugs-health-products/drug-products/drug-product-database.html), Health Canada
