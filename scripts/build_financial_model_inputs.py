"""Build model-ready historical inputs from v2 statement facts only."""
from __future__ import annotations
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from psx_data import STATE, load_json, save_json
from forecast_contract import qualified_financial_fact_source, selected_model_version

OUT = STATE / 'company_intel' / 'financial_model_inputs.json'
LINES = ('revenue','profit_after_tax_attributable','basic_eps','gross_profit','operating_profit')
def _num(f):
    if not isinstance(f,dict): return None
    value=f.get('normalized_value')
    return value if isinstance(value,(int,float)) and not isinstance(value,bool) else None
def _operands(*facts):
    return [{'fact_id':f.get('fact_id'),'source_url':f.get('source_url'),'period_end':f.get('period_end')} for f in facts]
def build():
    profiles=load_json(STATE/'company_profiles.json',{}); pilot=(profiles.get('pilot') or {}).get('symbols') or []; series=load_json(STATE/'company_financial_series.json',{}).get('tickers') or {}; sectors=load_json(STATE/'sectors.json',{}).get('tickers') or {}; out={}
    for sym in sorted(pilot):
        exchange_sector=(sectors.get(sym) or {}).get('sector')
        if not exchange_sector:
            exchange_sector=(profiles.get('companies') or {}).get(sym,{}).get('sector')
        model=selected_model_version(sym,exchange_sector); facts=[f for f in (series.get(sym,{}).get('facts') or []) if qualified_financial_fact_source(f) and f.get('readiness')=='model_loadable' and f.get('line') in LINES]
        groups={}
        for f in facts:
            key=(f.get('line'),f.get('period_end'),f.get('consolidation'),f.get('currency'),f.get('unit'),f.get('unit_multiplier'),f.get('statement_type'))
            groups.setdefault(key,[]).append(f)
        annual={line:sorted([sorted(vals,key=lambda f: str(f.get('fact_id') or ''))[0] for k,vals in groups.items() if k[0]==line and vals and vals[0].get('duration_months')==12 and len({_num(f) for f in vals})==1], key=lambda f: str(f.get('period_end') or '')) for line in LINES}
        core=('revenue','profit_after_tax_attributable','basic_eps')
        # EPS is per-share and must not be forced to share the monetary scale
        # of revenue/PAT.  Require common consolidation/currency/statement
        # family, while revenue and PAT additionally share unit/multiplier.
        common_context=set.intersection(*({(f.get('consolidation'),f.get('currency'),f.get('statement_type')) for f in annual.get(x,[])} for x in core)) if all(annual.get(x) for x in core) else set()
        monetary_basis={(f.get('consolidation'),f.get('currency'),f.get('statement_type'),f.get('unit'),f.get('unit_multiplier')) for f in annual.get('revenue',[])} & {(f.get('consolidation'),f.get('currency'),f.get('statement_type'),f.get('unit'),f.get('unit_multiplier')) for f in annual.get('profit_after_tax_attributable',[])}
        valid_context={(c,cur,st) for c,cur,st in common_context if any(m[0]==c and m[1]==cur and m[2]==st for m in monetary_basis)}
        valid_eps={(f.get('consolidation'),f.get('currency'),f.get('statement_type')) for f in annual.get('basic_eps',[]) if f.get('unit_multiplier') == 1 and ('share' in str(f.get('unit') or '').lower() or str(f.get('line')) == 'basic_eps')}
        common_context &= valid_eps
        monetary_pairs={(f.get('period_end'),f.get('consolidation'),f.get('currency'),f.get('statement_type'),f.get('unit'),f.get('unit_multiplier')) for f in annual.get('revenue',[])} & {(f.get('period_end'),f.get('consolidation'),f.get('currency'),f.get('statement_type'),f.get('unit'),f.get('unit_multiplier')) for f in annual.get('profit_after_tax_attributable',[])}
        monetary_periods={p[0] for p in monetary_pairs if (p[1],p[2],p[3]) in common_context}
        periods=set.intersection(*(set(f.get('period_end') for f in annual.get(x,[]) if (f.get('consolidation'),f.get('currency'),f.get('statement_type')) in common_context and (x=='basic_eps' or f.get('period_end') in monetary_periods)) for x in core)) if common_context else set()
        ready=bool(model and len(periods)>=3)
        status='ready' if ready else ('unsupported_sector_model' if not model else 'partial')
        out[sym]={'symbol':sym,'model_version':model,'status':status,'observations':{k:sorted(v,key=lambda x:x.get('period_end') or '') for k,v in annual.items()},'derived':{},'downstream_status':{'forecast':'blocked_not_implemented','valuation':'blocked_not_implemented','market_expectations':'blocked_not_implemented','scenario_lab':'blocked_not_implemented'},'quality_flags':[] if ready else ['insufficient_three_year_consolidated_v2_history']}
        for line, vals in annual.items():
            for prev,cur in zip(vals,vals[1:]):
                pv,cv=_num(prev),_num(cur)
                if pv not in (None,0) and cv is not None: out[sym]['derived'].setdefault(line+'_growth_pct',[]).append({'period_end':cur.get('period_end'),'value':(cv/pv-1)*100,'availability':max(prev.get('available_on') or '',cur.get('available_on') or ''),'formula_version':'financial_model_inputs_v1','source_fact_ids':[prev.get('fact_id'),cur.get('fact_id')],'operand_provenance':_operands(prev,cur)})
        for metric, numerator, denominator in (('gross_margin_pct','gross_profit','revenue'),('operating_margin_pct','operating_profit','revenue'),('pat_margin_pct','profit_after_tax_attributable','revenue')):
            by_period={f.get('period_end'):f for f in annual.get(numerator,[])}
            for f in annual.get(denominator,[]):
                n=by_period.get(f.get('period_end'))
                nv,dv=_num(n),_num(f)
                if n and dv not in (None,0) and nv is not None: out[sym]['derived'].setdefault(metric,[]).append({'period_end':f.get('period_end'),'value':nv/dv*100,'availability':max(n.get('available_on') or '',f.get('available_on') or ''),'formula_version':'financial_model_inputs_v1','source_fact_ids':[n.get('fact_id'),f.get('fact_id')],'operand_provenance':_operands(n,f)})
    result={'schema_version':1,'pilot_symbols':sorted(pilot),'companies':out,'source':'state/company_financial_series.json','model_registry_source':'scripts/sector_driver_models.py'}; save_json(OUT,result); print(f'financial_model_inputs: {len(out)} companies'); return result
if __name__=='__main__': build()
