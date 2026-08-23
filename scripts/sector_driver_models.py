"""Declarative sector driver registries for the Company Intelligence graphs.

These are qualitative research hypotheses only.  They intentionally contain no
company observations, forecasts, probabilities, or other numeric assumptions.
"""
from __future__ import annotations

from copy import deepcopy


def _edge(source: str, target: str, statement_line: str, unit: str) -> dict[str, str]:
    return {
        "from": source,
        "to": target,
        "statement_line": statement_line,
        "unit": unit,
        "basis": "declarative_assumption",
    }


SECTOR_MODELS: dict[str, dict] = {
    "BANKS": {
        "sector": "BANKS",
        "drivers": ["policy_rate", "deposit_cost", "loan_growth", "credit_cost", "fee_income", "capital_ratio"],
        "edges": [
            _edge("policy_rate", "net_interest_margin", "net_interest_income", "pct_points"),
            _edge("deposit_cost", "net_interest_margin", "net_interest_income", "pct_points"),
            _edge("loan_growth", "net_interest_income", "net_interest_income", "pct"),
            _edge("credit_cost", "profit_after_tax", "provisions", "pkr"),
            _edge("fee_income", "profit_after_tax", "non_interest_income", "pkr"),
            _edge("capital_ratio", "valuation", "equity_value", "pct"),
            _edge("profit_after_tax", "eps", "eps", "pkr_per_share"),
            _edge("eps", "valuation", "equity_value", "pkr_per_share"),
        ],
    },
    "CEMENT": {
        "sector": "CEMENT",
        "drivers": ["dispatch_volume", "realized_price", "coal_cost", "power_cost", "clinker_capacity", "export_price"],
        "edges": [
            _edge("dispatch_volume", "revenue", "revenue", "pct"),
            _edge("realized_price", "revenue", "revenue", "pkr_per_tonne"),
            _edge("coal_cost", "ebitda", "cost_of_sales", "pkr_per_tonne"),
            _edge("power_cost", "ebitda", "cost_of_sales", "pkr_per_tonne"),
            _edge("clinker_capacity", "revenue", "capacity", "tonnes"),
            _edge("export_price", "revenue", "revenue", "pkr_per_tonne"),
            _edge("ebitda", "fcf", "operating_cash_flow", "pkr"),
            _edge("fcf", "valuation", "enterprise_value", "pkr"),
        ],
    },
    "E&P": {
        "sector": "E&P",
        "drivers": ["oil_price", "gas_price", "production_volume", "decline_rate", "lifting_cost", "exploration_success"],
        "edges": [
            _edge("oil_price", "revenue", "revenue", "usd_per_bbl"),
            _edge("gas_price", "revenue", "revenue", "pkr_per_mmbtu"),
            _edge("production_volume", "revenue", "revenue", "boe_per_day"),
            _edge("decline_rate", "production_volume", "production", "pct"),
            _edge("lifting_cost", "ebitda", "cost_of_sales", "usd_per_boe"),
            _edge("exploration_success", "reserves", "reserves", "boe"),
            _edge("ebitda", "fcf", "operating_cash_flow", "pkr"),
            _edge("fcf", "valuation", "enterprise_value", "pkr"),
        ],
    },
    "REFINERY": {
        "sector": "REFINERY",
        "drivers": ["crude_supply", "refinery_margin", "refinery_throughput", "plant_availability", "product_mix", "inventory_position"],
        "edges": [
            _edge("crude_supply", "cost_of_sales", "cost_of_sales", "usd_per_bbl"),
            _edge("refinery_margin", "gross_profit", "gross_profit", "usd_per_bbl"),
            _edge("refinery_throughput", "revenue", "revenue", "barrels_per_day"),
            _edge("plant_availability", "refinery_throughput", "production", "pct"),
            _edge("product_mix", "revenue", "revenue", "pct"),
            _edge("inventory_position", "working_capital", "inventory", "pkr"),
            _edge("gross_profit", "ebitda", "gross_profit", "pkr"),
            _edge("ebitda", "fcf", "operating_cash_flow", "pkr"),
        ],
    },
    "FERTILIZER": {
        "sector": "FERTILIZER",
        "drivers": ["gas_supply", "fertilizer_price", "production_volume", "fertilizer_capacity", "input_cost", "working_capital"],
        "edges": [
            _edge("gas_supply", "cost_of_sales", "cost_of_sales", "pkr_per_mmbtu"),
            _edge("fertilizer_price", "revenue", "revenue", "pkr_per_tonne"),
            _edge("production_volume", "revenue", "revenue", "tonnes"),
            _edge("fertilizer_capacity", "production_volume", "capacity", "tonnes"),
            _edge("input_cost", "cost_of_sales", "cost_of_sales", "pkr"),
            _edge("working_capital", "fcf", "working_capital", "pkr"),
            _edge("revenue", "ebitda", "gross_profit", "pkr"),
            _edge("ebitda", "fcf", "operating_cash_flow", "pkr"),
        ],
    },
    "AUTO_ASSEMBLER": {
        "sector": "AUTO_ASSEMBLER",
        "drivers": ["auto_assembly_capacity", "sales_volume", "realized_price", "localization_rate", "import_cost", "model_mix"],
        "edges": [
            _edge("auto_assembly_capacity", "sales_volume", "capacity", "units"),
            _edge("sales_volume", "revenue", "revenue", "units"),
            _edge("realized_price", "revenue", "revenue", "pkr_per_unit"),
            _edge("localization_rate", "cost_of_sales", "cost_of_sales", "pct"),
            _edge("import_cost", "cost_of_sales", "cost_of_sales", "pkr"),
            _edge("model_mix", "gross_profit", "gross_profit", "pct"),
            _edge("gross_profit", "ebitda", "gross_profit", "pkr"),
            _edge("ebitda", "fcf", "operating_cash_flow", "pkr"),
        ],
    },
    "POWER": {
        "sector": "POWER",
        "drivers": ["generation_volume", "tariff", "fuel_cost", "generation_capacity", "plant_availability", "circular_debt"],
        "edges": [
            _edge("generation_volume", "revenue", "revenue", "mwh"),
            _edge("tariff", "revenue", "revenue", "pkr_per_kwh"),
            _edge("fuel_cost", "cost_of_sales", "cost_of_sales", "pkr_per_mwh"),
            _edge("generation_capacity", "generation_volume", "capacity", "mwh"),
            _edge("plant_availability", "generation_volume", "production", "pct"),
            _edge("circular_debt", "working_capital", "working_capital", "pkr"),
            _edge("revenue", "ebitda", "gross_profit", "pkr"),
            _edge("ebitda", "fcf", "operating_cash_flow", "pkr"),
        ],
    },
    "OMC": {
        "sector": "OMC",
        "drivers": ["product_price", "sales_volume", "import_parity", "storage_capacity", "exchange_rate", "marketing_margin"],
        "edges": [
            _edge("product_price", "revenue", "revenue", "pkr_per_litre"),
            _edge("sales_volume", "revenue", "revenue", "litres"),
            _edge("import_parity", "cost_of_sales", "cost_of_sales", "pkr_per_litre"),
            _edge("storage_capacity", "working_capital", "inventory", "litres"),
            _edge("exchange_rate", "cost_of_sales", "cost_of_sales", "pkr_per_usd"),
            _edge("marketing_margin", "gross_profit", "gross_profit", "pkr_per_litre"),
            _edge("gross_profit", "ebitda", "gross_profit", "pkr"),
            _edge("ebitda", "fcf", "operating_cash_flow", "pkr"),
        ],
    },
    "HOLDING_COMPANY": {
        "sector": "HOLDING_COMPANY",
        "drivers": ["subsidiary_value", "associate_earnings", "holding_discount", "capital_allocation", "portfolio_value", "dividend_income"],
        "edges": [
            _edge("subsidiary_value", "profit_after_tax", "profit_after_tax", "pkr"),
            _edge("associate_earnings", "profit_after_tax", "profit_after_tax", "pkr"),
            _edge("holding_discount", "valuation", "equity_value", "pct"),
            _edge("capital_allocation", "portfolio_value", "equity_value", "pkr"),
            _edge("portfolio_value", "valuation", "equity_value", "pkr"),
            _edge("dividend_income", "fcf", "cash_dividends", "pkr"),
            _edge("profit_after_tax", "eps", "eps", "pkr_per_share"),
            _edge("eps", "valuation", "equity_value", "pkr_per_share"),
        ],
    },
}


SECTOR_LABELS = {
    "Commercial Banks": "BANKS",
    "Cement": "CEMENT",
    "Oil & Gas Exploration Companies": "E&P",
    "Refinery": "REFINERY",
    "Fertilizer": "FERTILIZER",
    "Automobile Assembler": "AUTO_ASSEMBLER",
    "Power Generation & Distribution": "POWER",
    "Oil & Gas Marketing Companies": "OMC",
}

COMPANY_OVERRIDES = {"ENGROH": "HOLDING_COMPANY"}


def model_for_company(symbol: str, exchange_sector: str | None) -> dict | None:
    """Return a defensive copy of the model selected for one company."""
    canonical = COMPANY_OVERRIDES.get(str(symbol).upper()) or SECTOR_LABELS.get(exchange_sector or "")
    model = SECTOR_MODELS.get(canonical)
    return deepcopy(model) if model else None
