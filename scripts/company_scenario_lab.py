"""Pure, deterministic company scenario and reverse-expectations formulas.

All assumptions are explicit caller inputs; this module never chooses a case.
"""
from __future__ import annotations

import math
from typing import Mapping, Any

FORBIDDEN_TERMS = ("forecast", "fair value", "target", "advice")


def _finite(value: Any) -> float:
    if isinstance(value, bool):
        raise ValueError("boolean is not numeric")
    value = float(value)
    if not math.isfinite(value):
        raise ValueError("value must be finite")
    return value


def _check_pct(name: str, value: Any, low: float, high: float) -> float:
    value = _finite(value)
    if value < low or value > high:
        raise ValueError(f"{name} outside bounds [{low}, {high}]")
    return value


def forward_scenario(baseline: Mapping[str, Any], revenue_growth_pct: Any,
                     net_margin_pct: Any, exit_pe: Any) -> dict[str, float]:
    """Apply explicit growth, margin and exit multiple assumptions.

    Deliberately mirrored in ci-app/app.js for the owner-side
    interactive calculator; check_company_scenario_lab_ui.mjs locks the browser
    formulas and bounds to this canonical implementation.
    """
    revenue = _finite(baseline["revenue"])
    shares = _finite(baseline["shares_out"])
    price = _finite(baseline["latest_price"])
    if revenue <= 0 or shares <= 0 or price <= 0:
        raise ValueError("baseline operands must be positive")
    growth = _check_pct("revenue_growth_pct", revenue_growth_pct, -99.999999, 1000.0)
    margin = _check_pct("net_margin_pct", net_margin_pct, 0.000001, 100.0)
    pe = _check_pct("exit_pe", exit_pe, 0.000001, 200.0)
    scenario_revenue = revenue * (1.0 + growth / 100.0)
    scenario_net_income = scenario_revenue * margin / 100.0
    scenario_eps = scenario_net_income / shares
    implied_price = scenario_eps * pe
    return {
        "revenue_growth_pct": growth,
        "net_margin_pct": margin,
        "exit_pe": pe,
        "scenario_revenue": scenario_revenue,
        "scenario_net_income": scenario_net_income,
        "scenario_eps": scenario_eps,
        "multiple_implied_price": implied_price,
        "price_delta": implied_price - price,
        "price_delta_pct": (implied_price / price - 1.0) * 100.0,
    }


def reverse_expectations(baseline: Mapping[str, Any], exit_pe: Any,
                         net_margin_pct: Any) -> dict[str, float]:
    """Solve revenue/profit/EPS required for a supplied multiple at spot price."""
    revenue = _finite(baseline["revenue"])
    shares = _finite(baseline["shares_out"])
    price = _finite(baseline["latest_price"])
    if revenue <= 0 or shares <= 0 or price <= 0:
        raise ValueError("baseline operands must be positive")
    pe = _check_pct("exit_pe", exit_pe, 0.000001, 200.0)
    margin = _check_pct("net_margin_pct", net_margin_pct, 0.000001, 100.0)
    required_eps = price / pe
    required_net_income = required_eps * shares
    required_revenue = required_net_income / (margin / 100.0)
    return {
        "exit_pe": pe,
        "net_margin_pct": margin,
        "required_eps": required_eps,
        "required_net_income": required_net_income,
        "required_revenue": required_revenue,
        "required_revenue_growth_pct": (required_revenue / revenue - 1.0) * 100.0,
    }


def market_expectations_gap(baseline: Mapping[str, Any], revenue_growth_pct: Any,
                            net_margin_pct: Any, exit_pe: Any) -> dict[str, float]:
    """Compare caller growth to the reverse-solved growth implied by spot price."""
    scenario = forward_scenario(baseline, revenue_growth_pct, net_margin_pct, exit_pe)
    reverse = reverse_expectations(baseline, exit_pe, net_margin_pct)
    return {
        "revenue_growth_pct": scenario["revenue_growth_pct"],
        "net_margin_pct": scenario["net_margin_pct"],
        "exit_pe": scenario["exit_pe"],
        "required_revenue_growth_pct": reverse["required_revenue_growth_pct"],
        "expectations_gap_pct": reverse["required_revenue_growth_pct"] - scenario["revenue_growth_pct"],
    }


def parse_scaled(value: Any) -> float:
    """Parse numbers carrying B/M/K suffixes (case-insensitive)."""
    if isinstance(value, (int, float)):
        return _finite(value)
    text = str(value).strip().replace(",", "")
    if not text or text.lower() in {"n/a", "na", "-", "null"}:
        raise ValueError("missing numeric value")
    scale = 1.0
    suffix = text[-1].upper()
    if suffix in {"T", "B", "M", "K"}:
        scale = {"T": 1e12, "B": 1e9, "M": 1e6, "K": 1e3}[suffix]
        text = text[:-1].strip()
    return _finite(float(text) * scale)
