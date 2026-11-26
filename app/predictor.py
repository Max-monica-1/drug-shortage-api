"""Load the survival model and predict how soon a shortage will be resolved."""
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

MODEL_FILE = Path(__file__).resolve().parent.parent / "models" / "survival_model.joblib"
PREDICTION_DAYS = [30, 90, 180]
LOG_COLUMNS = ["COMPANY_PRIOR_REPORTS", "ING_PRIOR_REPORTS", "CONCURRENT_SHORTAGES"]

# Load once when the API starts, not on every request
_bundle = joblib.load(MODEL_FILE)
_model = _bundle["model"]


def _design_matrix(features: dict) -> pd.DataFrame:
    """Prepare one shortage exactly the way the training data was prepared."""
    categorical = _bundle["categorical"]
    numeric = _bundle["numeric"]
    X = pd.DataFrame([features])[categorical + numeric]

    for col in categorical:
        X[col] = X[col].fillna("UNKNOWN")
        X[col] = X[col].where(X[col].isin(_bundle["common_values"][col]), "OTHER")

    X[numeric] = X[numeric].astype(float).fillna(pd.Series(_bundle["numeric_medians"]))
    X["PRODUCT_AGE_YEARS"] = X["PRODUCT_AGE_YEARS"].clip(0, 60)
    for col in LOG_COLUMNS:
        X[col] = np.log1p(X[col])

    X = pd.get_dummies(X, columns=categorical, dtype=float)
    return X.reindex(columns=_bundle["columns"], fill_value=0)


def _risk_level(prob_by_90: float) -> str:
    """Turn the 90-day probability into a simple level, using the training quintiles."""
    edges = _bundle["risk_band_edges"]  # 20th, 40th, 60th and 80th percentiles
    if prob_by_90 < edges[1]:
        return "high"    # among the 40% slowest to resolve
    if prob_by_90 < edges[3]:
        return "medium"
    return "low"         # among the 20% fastest to resolve


def predict(features: dict) -> dict:
    """Return the chance of resolution by 30, 90 and 180 days, and a risk level."""
    X = _design_matrix(features)
    survival = _model.predict_survival_function(X, times=PREDICTION_DAYS)
    resolved = {day: float(1 - survival.loc[day].iloc[0]) for day in PREDICTION_DAYS}
    median_days = float(np.asarray(_model.predict_median(X)).ravel()[0])

    return {
        "resolved_within_30_days": round(resolved[30], 3),
        "resolved_within_90_days": round(resolved[90], 3),
        "resolved_within_180_days": round(resolved[180], 3),
        "predicted_median_days": None if np.isinf(median_days) else round(median_days),
        "risk_level": _risk_level(resolved[90]),
        "model": _bundle.get("trained_on", "Cox proportional hazards model"),
    }
