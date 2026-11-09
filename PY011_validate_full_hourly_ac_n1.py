#!/usr/bin/env python3
"""Audit archived 16-year nonlinear AC intact + 93 branch-outage screening outputs."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
H=Path(__file__).resolve().parent
s=json.loads((H/'full_hourly_ac_n1_summary.json').read_text())
c=pd.read_csv(H/'full_hourly_ac_n1_contingency_summary.csv')
h=pd.read_csv(H/'full_hourly_ac_n1_hourly_worstcase.csv.gz')
n=pd.read_csv(H/'full_hourly_n0_nonlinear_ac.csv.gz')
assert s['complete_140160x93_branch_sweep']
assert len(c)==94 and len(h)==len(n)==140160
assert s['nonlinear_power_flow_cases_evaluated']==140160*94
assert c.hours_solved.eq(140160).all()
assert int(c.nonconverged_hours.sum())==s['total_nonconverged_cases']
assert int(c.any_failure_hours.sum())==s['total_failed_ac_cases']
assert int(c.iloc[0].any_failure_hours)==s['n0_failed_hours']
assert int((h.n1_failed_solutions>0).sum())==s['hours_with_any_n1_failure']
assert int((h.n1_failed_solutions==0).sum())+s['hours_with_any_n1_failure']==140160
assert (n.ac_grid_import_mw>=0).all() and (n.ac_grid_export_mw>=0).all()
assert np.max(np.abs(h.maximum_grid_import_mw))<=s['max_grid_import_MW']+1e-3
assert np.all(np.isfinite(n.ac_losses_mw))
assert (H/'annual_hourly_nonlinear_ac_n1_results.csv').exists()
print('PASS: 16-year 140,160-hour × 94 nonlinear AC screening outputs consistent.')
print('NOT a BC Hydro operating model, AC OPF, corrective redispatch, generator protection, or NERC compliance certification.')
