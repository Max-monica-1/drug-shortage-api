"""Endpoint that forecasts how soon a drug shortage will be resolved."""
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.predictor import predict

router = APIRouter(tags=["forecast"])

Reason = Literal[
    "Delay in shipping of the drug.",
    "Demand increase for the drug.",
    "Disruption of the manufacture of the drug.",
    "Other (Please describe in comments)",
    "Requirements related to complying with good manufacturing practices.",
    "Shortage of an active ingredient.",
    "Shortage of an inactive ingredient or component.",
]


class ShortageInput(BaseModel):
    """What is known about a shortage on the day it is reported."""

    reason: Reason
    atc_group: str = Field(
        "UNKNOWN", pattern=r"^([A-Z]|UNKNOWN)$",
        description="First letter of the ATC code, e.g. 'C' for cardiovascular",
    )
    dosage_form: str = Field("TABLET", description="e.g. TABLET, SOLUTION, CAPSULE")
    company_name: str = Field("UNKNOWN", description="Company that reported the shortage")
    company_prior_reports: int | None = Field(None, ge=0, description="Earlier shortage reports by this company")
    ingredient_prior_reports: int | None = Field(None, ge=0, description="Earlier shortage reports for this ingredient")
    concurrent_shortages: int | None = Field(None, ge=0, description="Other products of the same ingredient in shortage now")
    same_strength_products_on_market: int | None = Field(None, ge=0)
    other_companies_same_ingredient: int | None = Field(None, ge=0)
    product_age_years: float | None = Field(None, ge=0, le=100)

    model_config = {
        "json_schema_extra": {
            "example": {
                "reason": "Shortage of an active ingredient.",
                "atc_group": "C",
                "dosage_form": "TABLET",
                "company_name": "APOTEX INC",
                "concurrent_shortages": 3,
            }
        }
    }


class ShortageForecast(BaseModel):
    resolved_within_30_days: float
    resolved_within_90_days: float
    resolved_within_180_days: float
    predicted_median_days: int | None
    risk_level: Literal["low", "medium", "high"]
    model: str


@router.post("/predict", response_model=ShortageForecast)
def forecast_shortage(shortage: ShortageInput):
    """Estimate the chance that a shortage is resolved within 30, 90 and 180 days.

    Optional counts can be left empty; the model then uses typical values.
    Upper-case names are expected, as in the shortage database.
    """
    features = {
        "REASON": shortage.reason,
        "ATC_GROUP": shortage.atc_group,
        "MAIN_DOSAGE_FORM": shortage.dosage_form.upper(),
        "COMPANY_NAME": shortage.company_name.upper(),
        "COMPANY_PRIOR_REPORTS": shortage.company_prior_reports,
        "ING_PRIOR_REPORTS": shortage.ingredient_prior_reports,
        "CONCURRENT_SHORTAGES": shortage.concurrent_shortages,
        "N_SAME_STRENGTH_ON_MARKET": shortage.same_strength_products_on_market,
        "N_COMPANIES_SAME_INGREDIENT": shortage.other_companies_same_ingredient,
        "PRODUCT_AGE_YEARS": shortage.product_age_years,
    }
    return predict(features)
