"""Build bounded declarative driver graphs for the exact Company Intelligence pilot."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from psx_data import STATE, load_json, save_json
from sector_driver_models import SECTOR_MODELS, model_for_company

OUT = STATE / "company_intel" / "driver_graphs.json"
def build():
    profiles = load_json(STATE / "company_profiles.json", {})
    sectors = load_json(STATE / "sectors.json", {}).get("tickers") or {}
    pilot = (profiles.get("pilot") or {}).get("symbols") or []
    companies = {}
    for sym in sorted(pilot):
        sector = (sectors.get(sym) or {}).get("sector")
        model = model_for_company(sym, sector)
        companies[sym] = {
            "sector": model["sector"] if model else None,
            "drivers": model["drivers"] if model else [],
            "edges": model["edges"] if model else [],
            "quality_flags": [],
        }
    out = {
        "schema_version": 2,
        "pilot_symbols": sorted(pilot),
        "supported_sectors": list(SECTOR_MODELS),
        "companies": companies,
    }
    save_json(OUT, out)
    print(f"driver_graphs: {sum(bool(v['edges']) for v in companies.values())} modeled companies / {len(companies)} pilot")
    return out
if __name__ == "__main__": build()
