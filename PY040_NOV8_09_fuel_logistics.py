#!/usr/bin/env python3
"""Monthly/rolling fuel-withdrawal and illustrative delivery-stock screens, NOT a supply contract.
Uses chronological hourly fuel use that the existing dispatch generated before inventory constraints.
Run from any directory. Writes results next to this code's parent research folder.
"""
import json, numpy as np,pandas as pd
from pathlib import Path
R=Path(__file__).resolve().parents[1]/'results'
HVO_LHV_MJ_PER_L=36.51;NET_EFF=0.54
L_PER_MWH=3600/(HVO_LHV_MJ_PER_L*NET_EFF)
ASSUMED_HVO_CAP_ML_YEAR=976.4516
cases={
 'reference_central':'new_build_observed_shape_hourly.csv.gz',
 'robust_central':'NOV8_08_rounded_robust_central_hourly.csv.gz'}
annual=[]; windows=[]; month=[]
for name,fn in cases.items():
 H=pd.read_csv(R/fn,usecols=['time_utc','HVO_MW','load_MW','unserved_MW'])
 dates=pd.to_datetime(H.time_utc,utc=True)
 H['date']=dates;H['year']=dates.dt.year;H['month']=dates.dt.month
 H['HVO_ML']=H.HVO_MW*L_PER_MWH/1e6
 for year,df in H.groupby('year',sort=True):
  cons=df.HVO_ML.to_numpy(); T=len(cons)
  assert T==8760
  uniform=np.full(T,ASSUMED_HVO_CAP_ML_YEAR/T)
  cum=np.cumsum(cons-uniform)
  opening_if_uniform=float(max(0,cum.max()))
  max_tank_if_uniform=float((opening_if_uniform-cum).max())
  loss10=max(0,cons.sum()-ASSUMED_HVO_CAP_ML_YEAR*.9)
  annual.append({'portfolio':name,'year':year,'HVO_consumed_ML':cons.sum(),'annual_ceiling_ML':ASSUMED_HVO_CAP_ML_YEAR,
    'annual_headroom_ML':ASSUMED_HVO_CAP_ML_YEAR-cons.sum(),
    'annual_arithmetic_shortfall_under_10pct_less_procurement_ML':loss10,
    'minimum_start_inventory_ML_with_inflexible_uniform_deliveries':opening_if_uniform,
    'largest_tank_fill_ML_under_fixed_uniform_full_ceiling_deliveries':max_tank_if_uniform,
    'fixed_uniform_deliveries_note':'Full annual ceiling delivered at constant hourly rate; unused supply accumulates and no offtake/disposal assumed. This is NOT realistic procurement.'})
  for days in (7,14,30):
   series=pd.Series(cons).rolling(days*24,min_periods=days*24).sum()
   j=int(series.idxmax());win=float(series.iloc[j])
   windows.append({'portfolio':name,'year':year,'disruption_days':days,'max_HVO_consumption_with_no_deliveries_ML':win,
     'ending_hour_offset':j,'minimum_just_before_disruption_stock_ML':win,
     'interpretation':'Perfectly timed worst-window inventory lower bound assuming zero resupply and frozen dispatch, no competing fuel uses.'})
  for m,g in df.groupby('month',sort=True): month.append({'portfolio':name,'year':year,'month':m,'HVO_consumed_ML':g.HVO_ML.sum()})
A=pd.DataFrame(annual);W=pd.DataFrame(windows);M=pd.DataFrame(month)
# independent reconciliation to saved annual summaries
ref=pd.read_csv(R/'scenario_annual.csv');ref=ref[ref.scenario=='new_build_observed_shape']
rob=pd.read_csv(R/'NOV8_08_rounded_robust_central_annual.csv')
for name,src in [('reference_central',ref),('robust_central',rob)]:
 aa=A[A.portfolio==name].sort_values('year');bb=src.sort_values('year')
 assert list(aa.year)==list(bb.year)
 assert max(abs(aa.HVO_consumed_ML.to_numpy()-bb.HVO_ML.to_numpy()))<1e-6,(name,max(abs(aa.HVO_consumed_ML.to_numpy()-bb.HVO_ML.to_numpy())))
A.to_csv(R/'NOV8_09_fuel_delivery_annual_diagnostics.csv',index=False,float_format='%.8f')
W.to_csv(R/'NOV8_09_fuel_disruption_rolling_windows.csv',index=False,float_format='%.8f')
M.to_csv(R/'NOV8_09_fuel_monthly_demand.csv',index=False,float_format='%.8f')
summary={'method':'Frozen dispatch fuel-draw postprocessing only: annual resetting retained in source model; does not model realistic delivery schedules, fleet size, transport, tanks, contracts or re-dispatch',
 'HVO_litres_per_MWh':L_PER_MWH,'assumed_annual_cap_ML':ASSUMED_HVO_CAP_ML_YEAR,
 'cases':{}}
for name in cases:
 d=A[A.portfolio==name]; ww=W[W.portfolio==name]
 summary['cases'][name]={
  'peak_annual_consumption_ML':round(float(d.HVO_consumed_ML.max()),6),
  'peak_year':int(d.loc[d.HVO_consumed_ML.idxmax(),'year']),
  'lowest_annual_headroom_ML':round(float(d.annual_headroom_ML.min()),6),
  'max_uniform_delivery_opening_inventory_ML':round(float(d.minimum_start_inventory_ML_with_inflexible_uniform_deliveries.max()),6),
  'max_annual_volume_shortfall_at_10pct_less_procurement_ML':round(float(d.annual_arithmetic_shortfall_under_10pct_less_procurement_ML.max()),6),
  'max_7day_no_delivery_draw_ML':round(float(ww[ww.disruption_days==7].max_HVO_consumption_with_no_deliveries_ML.max()),6),
  'max_14day_no_delivery_draw_ML':round(float(ww[ww.disruption_days==14].max_HVO_consumption_with_no_deliveries_ML.max()),6),
  'max_30day_no_delivery_draw_ML':round(float(ww[ww.disruption_days==30].max_HVO_consumption_with_no_deliveries_ML.max()),6),
 }
(R/'NOV8_09_fuel_logistics_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))
