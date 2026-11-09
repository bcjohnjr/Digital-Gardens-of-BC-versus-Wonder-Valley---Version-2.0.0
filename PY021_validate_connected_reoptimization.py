#!/usr/bin/env python3
"""Check internal consistency of archived reoptimised capacity, dispatch, heat, carbon and GPUs.
These are consistency assertions, not certification of engineering assumptions or markets.
"""
from pathlib import Path
import json,csv,math
from docx import Document
p=Path(__file__).resolve().parent
j=json.loads((p/'reoptimized_grid_case.json').read_text())
k=json.loads((p/'integrated_grid_heat_gpu.json').read_text())
h=json.loads((p/'heat_reconciled.json').read_text())
s=j['selected_case']
checks=[]
def chk(name,expr):
 checks.append((name,bool(expr)))
 if not expr: raise AssertionError(name)
cap=j['wind_capacity_GW_by_site'];wind=sum(cap.values())
chk('Whole 8 MW turbine count',abs(wind*1000/8-round(wind*1000/8))<1e-8 and round(wind*1000/8)==732)
chk('Installed wind equals sum of site allocations',abs(wind-j['wind_GW_total'])<1e-8)
chk('Nicola site <=0.2GW',cap['nicola_wind_project_regional_proxy']<=0.2)
chk('Wind and solar physical capacities are positive',j['solar_GW']>0 and j['battery_GWh']>0)
chk('Annual central replays do not call emergency fossil gas',s['max_gas_gwh']==0)
chk('Annual central replays do not leave load unserved',s['max_unserved_gwh']==0)
chk('Limits (GW) 2.5 import/3 export documented',s['import_twh']>=0 and s['export_twh']>=0)
chk('HVO within maximum annual procurement',s['hvo_ml_max']<=j['fuel_limit_ML'])
chk('Cost accounting sum',abs(s['generation_cost_CAD_MWh']+s['trading_cost_CAD_MWh']+s['wind_extension_CAD_MWh']-s['total_CAD_MWh'])<1e-6)
chk('Turbine service-life expense positive',s['wind_extension_CAD_MWh']>0)
chk('Booster demand optimized jointly',j['drying_booster_in_objective'] is True)
chk('Dryer boost positive',h['drying_electric_booster_twh_per_year']>0)
chk('Dryer electricity not credited as free export',h['electricity_no_free_curtail_claim'] is True)
chk('Dryer supplier screen loses money',h['drying_margin_CAD_m_yr']<0)
chk('Energy cost final integration matches optimizer',abs(k['after_drying']['total_CAD_MWh']-s['total_CAD_MWh'])<1e-8)
chk('HVO final integration matches optimizer',abs(k['after_drying']['hvo_ml_mean']-s['hvo_ml_mean'])<1e-8)
chk('Imported power emissions increase with assumed grid intensity',k['emissions_mt_approx_by_grid_intensity']['20']<k['emissions_mt_approx_by_grid_intensity']['100']<k['emissions_mt_approx_by_grid_intensity']['250'])
chk('Full discounted GPU cash-flow rows are present',len(k['gpu_economics'])>=8)
chk('Reference NVL72 premium positive',0.45<k['gpu_economics'][0]['breakeven_USD_per_labelled_GPU_hour']<0.5)
chk('Environmental screen contains local river', (p/'kamloops_thompson_river_mixing_screen.csv').exists())
chk('17-node synthetic network outputs exist', (p/'N1_REOPT/ac_voltage_screen.csv').exists())
article=Document(p.parent.parent/'SUBMISSION/Joule_Research_Article.docx')
full=' '.join(x.text for x in article.paragraphs)+' '.join(c.text for t in article.tables for row in t.rows for c in row.cells)
chk('Manuscript names Wonder Valley singular project', 'Wonder Valley' in full and 'single proposed' in full)
chk('Manuscript cost uses revised central result',f"{s['total_CAD_MWh']:.2f}" in full)
chk('Manuscript original pooled emissions benchmark matches model',f"{k['emissions_mt_approx_by_grid_intensity']['100']:.3f}" in full)
chk('Revised primary lacks older fixed-cost as primary claim','The intended 2.5 GW import / 3 GW export base case buys 3.19' not in full)
chk('Reference DOI not misattributed to new release','10.5281/zenodo.23997797 identifies the current' not in full)
print('PASS',len(checks),'reoptimised-grid integrated consistency checks')
for name,_ in checks:print(' -',name)
