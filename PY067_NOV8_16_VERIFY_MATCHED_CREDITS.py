#!/usr/bin/env python3
"""Recompute the Version 16 symmetry ledger from Version 14 aggregate outputs.
No restricted hourly inputs required; this validates arithmetic only, not dispatch inputs.
"""
import csv,sys,pathlib,math
base=pathlib.Path(__file__).resolve().parent
inp=base/'NOV8_14_COUPLED_DISPATCH_CARBON_HEAT_SCENARIOS_AGGREGATE.csv'
out=base/'NOV8_16_MATCHED_COMMUNITY_EMISSIONS.csv'
with inp.open(newline='',encoding='utf-8') as f: inputs=list(csv.DictReader(f))
with out.open(newline='',encoding='utf-8') as f: rows=list(csv.DictReader(f))
keys={'Digital Gardens':'DG_gross_partial_Mt_y',
'Wonder Valley: no CCS + CH4':'WV_CCGT_no_CCS_direct_plus_methane_Mt_y',
'Wonder Valley: 90% CCS + CH4':'WV_CCGT_90pct_CCS_direct_plus_methane_Mt_y',
'Wonder Valley: 95% CCS + CH4':'WV_CCGT_95pct_CCS_direct_plus_methane_Mt_y'}
assert len(rows)==4*len(inputs),(len(rows),len(inputs))
for src in inputs:
 subset=[r for r in rows if r['heat_case']==src['heat_case'] and r['stress_case']==src['stress_case']]
 assert len(subset)==4
 credit=float(src['conditional_avoided_total_Mt_y'])
 for r in subset:
  gross=float(src[keys[r['project_scenario']]])
  for k,expected in [('gross_partial_MtCO2e_y',gross),('matched_conditional_avoided_fossil_MtCO2e_y',credit),('conditional_partial_net_MtCO2e_y',gross-credit)]:
   assert math.isclose(float(r[k]),expected,abs_tol=1e-8,rel_tol=0), (src['heat_case'],k)
  assert math.isclose(float(r['gross_partial_MtCO2e_y'])-float(r['matched_conditional_avoided_fossil_MtCO2e_y']),float(r['conditional_partial_net_MtCO2e_y']),abs_tol=2e-8)
for case in ['full_service','limited_plant','half_connected','no_network']:
 subset=[r for r in rows if r['heat_case']==case and r['stress_case']=='central']
 assert len({r['matched_conditional_avoided_fossil_MtCO2e_y'] for r in subset})==1
print(f'PASS: {len(rows)} symmetric-credits rows across {len(inputs)} source scenarios; 4 cases each')
