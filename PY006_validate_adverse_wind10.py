#!/usr/bin/env python3
"""Saved-output reproducibility checks; does NOT independently re-solve all AC states."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
p=Path(__file__).resolve().parent
s=[]
for key,fol,pref in [('unmitigated','ADVERSE_WIND_10PCT','wind10'),('export_rule','ADVERSE_WIND_10PCT_EXPORT_CAPPED','wind10_export')]:
 q=p/fol; js=json.loads((q/(pref+'_summary.json')).read_text()); a=pd.read_csv(q/(pref+'_contingency_summary.csv')); h=pd.read_csv(q/(pref+'_hourly_worstcase.csv.gz')); fuel=pd.read_csv(q/(pref+'_annual_fuel_check.csv')); reserve=pd.read_csv(q/(pref+'_hourly_reserve.csv.gz'))
 assert js['complete_140160x93_branch_sweep'] and js['nonlinear_power_flow_cases_evaluated']==13175040
 assert js['n0_and_n1_cases']==94 and len(a)==94 and len(h)==len(reserve)==140160
 assert int(a.any_failure_hours.sum())==js['total_failed_ac_cases']
 assert js['n0_failed_hours']==int(a.iloc[0].any_failure_hours)
 assert js['hours_with_any_n1_failure']==int((h.n1_failed_solutions>0).sum())
 assert int(a.thermal_failure_hours.sum())==int(a.voltage_failure_hours.sum())==int(a.nonconverged_hours.sum())==0
 assert len(fuel)==16 and (fuel.fuel_margin_ML>0).all()
 assert abs(fuel.additional_HVO_ML.mean()-js['additional_hvo_ML_per_year_including_preventive'])<1e-6
 assert abs(fuel.total_HVO_ML.max()-js['maximum_total_hvo_ML_per_year'])<1e-6
 assert np.max(reserve.added_local_HVO_MWh)<17*160
 assert 'hour' not in fuel.columns
 s.append(js)
 assert (a.maximum_grid_import_MW<=2500.001).all()
assert s[0]['total_failed_ac_cases']==10794 and s[0]['hours_with_any_n1_failure']==115
assert s[0]['max_grid_export_MW']>3000
assert s[1]['total_failed_ac_cases']==0 and s[1]['hours_with_any_n1_failure']==0
assert s[1]['max_grid_export_MW']<=3000.001 and s[1]['max_grid_import_MW']<=2500.001
assert s[1]['export_cutback_hours']==116
print('PASS saved-output adverse-wind cases: 13,175,040 AC evaluations each; unmitigated=115 hours; export rule=0. NOT utility-grade proof.')
