#!/usr/bin/env python3
"""Audit loss-aware winter AC N0/N-1 screens (not an operator certificate)."""
from pathlib import Path
import json, numpy as np, pandas as pd
p=Path(__file__).resolve().parent/'N1_QSUPPORT_loss_aware'
a=pd.read_csv(p/'ac_voltage_screen.csv')
s=json.loads((p/'loss_aware_accounting_audit.json').read_text())
assert len(a)==99==s['n_cases']
assert len(a['outage'].unique())==99
assert a['ac_converged'].all() and a['ac_balanced_pass'].all()
assert (a['ac_grid_slack_mw']<=2500.02).all()
assert (a['ac_voltage_violations']==0).all()
assert (a['ac_thermal_violations']==0).all()
assert (a['unserved_mw']<1e-5).all()
assert (a['ac_residual_pu']<1e-5).all()
assert (a['ac_loss_balance_residual_mw'].abs()<1e-4).all()
assert (a['ac_total_hvo_after_balance_mw'] <= 17*160+1e-5).all()
assert (a['ac_added_local_hvo_mw']>0).all()
assert abs(a['ac_loss_mw'].min()-s['active_AC_losses_mw_min'])<1e-8
assert abs(a['ac_loss_mw'].max()-s['active_AC_losses_mw_max'])<1e-8
assert abs(a['ac_grid_slack_mw'].max()-s['actual_ac_grid_slack_mw_max'])<1e-8
assert (p/'Figure_S14_AC_Loss_Aware_N1.png').exists()
print('PASS: 99 loss-aware AC N0/N−1 cases; import <=2.5 GW; 0 voltage/thermal/shortfall failures. Screening assumptions only.')
