"""Deterministic normalization of analyst forecasts."""


def normalize_forecast(raw, price):
    if not isinstance(raw, dict) or not isinstance(price, (int, float)):
        return {"status": "UNKNOWN", "missing": []}

    targets = raw.get("price_targets")
    estimates = raw.get("estimates")
    result = {"status": "PARTIAL", "missing": []}

    if isinstance(raw.get("analyst_rating"), str) and raw["analyst_rating"]:
        result["analyst_rating"] = raw["analyst_rating"]
    else:
        result["missing"].append("analyst_rating")

    if isinstance(targets, dict):
        average = targets.get("average")
        upside = targets.get("upside_pct")
        if isinstance(average, (int, float)):
            result["target_average"] = average
        else:
            result["missing"].append("target_average")
        if isinstance(upside, (int, float)):
            result["target_upside_pct"] = upside
        else:
            result["missing"].append("target_upside_pct")
    else:
        result["missing"].extend(["target_average", "target_upside_pct"])

    eps = estimates.get("eps_next_quarter") if isinstance(estimates, dict) else None
    if isinstance(eps, (int, float)):
        result["eps_estimate"] = eps
    else:
        result["missing"].append("eps_estimate")

    if not result["missing"]:
        result["status"] = "PASS"
    return result
