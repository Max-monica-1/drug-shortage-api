"""Tests for the survival model and the /predict endpoint (no cloud access needed)."""
from app.predictor import predict

ACTIVE_INGREDIENT = {
    "reason": "Shortage of an active ingredient.",
    "atc_group": "C",
    "dosage_form": "TABLET",
    "company_name": "APOTEX INC",
    "concurrent_shortages": 3,
}


def test_predict_returns_probabilities(client):
    response = client.post("/predict", json=ACTIVE_INGREDIENT)
    assert response.status_code == 200
    body = response.json()
    for key in ["resolved_within_30_days", "resolved_within_90_days", "resolved_within_180_days"]:
        assert 0 <= body[key] <= 1
    assert body["risk_level"] in {"low", "medium", "high"}


def test_probabilities_increase_over_time(client):
    body = client.post("/predict", json=ACTIVE_INGREDIENT).json()
    assert (
        body["resolved_within_30_days"]
        <= body["resolved_within_90_days"]
        <= body["resolved_within_180_days"]
    )


def test_shipping_delays_resolve_faster_than_ingredient_shortages(client):
    shipping = {**ACTIVE_INGREDIENT, "reason": "Delay in shipping of the drug."}
    slow = client.post("/predict", json=ACTIVE_INGREDIENT).json()
    fast = client.post("/predict", json=shipping).json()
    assert fast["resolved_within_90_days"] > slow["resolved_within_90_days"]


def test_unknown_company_and_missing_counts_still_work():
    result = predict({
        "REASON": "Demand increase for the drug.",
        "ATC_GROUP": "N",
        "MAIN_DOSAGE_FORM": "TABLET",
        "COMPANY_NAME": "A COMPANY THE MODEL HAS NEVER SEEN",
        "COMPANY_PRIOR_REPORTS": None,
        "ING_PRIOR_REPORTS": None,
        "CONCURRENT_SHORTAGES": None,
        "N_SAME_STRENGTH_ON_MARKET": None,
        "N_COMPANIES_SAME_INGREDIENT": None,
        "PRODUCT_AGE_YEARS": None,
    })
    assert 0 <= result["resolved_within_90_days"] <= 1


def test_invalid_input_is_rejected(client):
    assert client.post("/predict", json={"reason": "Not a real reason"}).status_code == 422
    bad_count = {**ACTIVE_INGREDIENT, "concurrent_shortages": -1}
    assert client.post("/predict", json=bad_count).status_code == 422
