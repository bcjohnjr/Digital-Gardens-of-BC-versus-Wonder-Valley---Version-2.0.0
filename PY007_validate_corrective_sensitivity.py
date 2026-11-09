#!/usr/bin/env python3
"""Independent consistency checks of the archived conditional sensitivity; does not re-solve AC."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
HERE=Path(__file__).resolve().parent; P=HERE/'PREEMPTIVE'; O=HERE.parent
orig=json.loads((O/'full_hourly_ac_n1_summary.json').read_text())
assert orig['hours_with_any_n1_failure']==101640 and orig['n0_failed_hours']==48766
base=pd.read_csv(O/'full_hourly_ac_n1_hourly_worstcase.csv.gz')
cont=pd.read_csv(O/'full_hourly_ac_n1_contingency_summary.csv')
rate=pd.read_csv(HERE/'reinforced_selected_contingencies.csv')
run=pd.read_csv(P/'preemptive_contingency_summary.csv')
w=pd.read_csv(P/'preemptive_hourly_worstcase.csv.gz')
f=pd.read_csv(P/'preemptive_annual_fuel_check.csv')
h=pd.read_csv(P/'preemptive_hourly_reserve.csv.gz')
s=json.loads((P/'preemptive_summary.json').read_text())
assert len(base)==len(w)==len(h)==140160
assert len(cont)==len(run)==94 and len(rate)==7
assert s['hours']==140160 and s['nonlinear_power_flow_cases_evaluated']==13175040
assert s['complete_140160x93_branch_sweep'] and s['total_failed_ac_cases']==0
assert int(run.any_failure_hours.sum())==0 and int(run.thermal_failure_hours.sum())==0
assert int(run.grid_limit_failure_hours.sum())==0 and int(run.voltage_failure_hours.sum())==0
assert int(run.nonconverged_hours.sum())==0
assert np.max(run.maximum_branch_loading_pct)<100.0001
assert np.max(run.maximum_grid_import_MW)<=2500.001
assert np.max(run.maximum_grid_export_MW)<=3000.001
assert (w.n1_failed_solutions==0).all()
assert np.max(np.abs(h.added_local_HVO_MWh.to_numpy()-1.025*np.maximum(0,base.maximum_grid_import_mw.to_numpy()-2499.75)))<1e-7
assert len(f)==16 and (f.fuel_margin_ML>0).all()
assert abs(f.additional_HVO_ML.mean()-1.3672600570)<1e-5
assert abs(f.total_HVO_ML.max()-611.579603298)<1e-4
assert (rate.thermal_failure_hours==0).all() and rate.maximum_branch_loading_pct.max()<100.0001
assert int(cont.thermal_failure_hours.sum())==193812
assert (cont.query('thermal_failure_hours > 0').shape[0])==6
assert ((base.maximum_grid_import_mw>2500.001)).sum()==48827
print('PASS: full 13,175,040-case preventive + assumed rating AC screen; fuel inventory and archived original comparison.')
print('Mean annual added HVO ML',round(f.additional_HVO_ML.mean(),6),'mean gross additional fuel C$/MWh',round(f.additional_HVO_ML.mean()*1e6*1.8/(36.00486e6),6))
