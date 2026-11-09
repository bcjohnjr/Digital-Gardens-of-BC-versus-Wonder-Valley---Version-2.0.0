#!/usr/bin/env python3
"""Audits 140160-hour output, original zero-loss control and published yearly summaries."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
P=Path(__file__).resolve().parent
j=json.loads((P/'full_16yr_loss_results.json').read_text())
a=pd.read_csv(P/'nominal_i2r_hourly_2010_2025.csv.gz')
assert j['hours']==140160 and len(a)==140160
assert a.year.nunique()==16 and set(a.year)==set(range(2010,2026))
assert all(a.groupby('year').size()==8760)
assert a.grid_import_MW.max()<=2500.000001 and a.grid_export_MW.max()<=3000.000001
assert a.grid_import_MW.min()>=0 and a.grid_export_MW.min()>=0
assert a.battery_soc_MWh.min()>=-1e-5 and a.battery_soc_MWh.max()<=3132.955
assert a.max_dc_branch_rating_pct.max()<100
assert a.uniform_local_firm_generation_MW_per_site.max()<160
assert a.emergency_gas_MWh.sum()==0 and a.unserved_MWh.sum()==0
assert a.network_loss_MWh.min()>=0
balance=a.renewables_delivered_MWh+a.battery_discharge_MW+a.grid_import_MW+a.B100_MWh+a.HVO_MWh+a.emergency_gas_MWh+a.unserved_MWh-(a.facility_and_booster_load_MWh+a.network_loss_MWh+a.battery_charge_MW+a.grid_export_MW)
assert balance.abs().max()<1e-4
assert a.loss_fixedpoint_residual_MW.max()<1e-3
assert max(abs(x) for x in j['baseline_differences'].values())<2e-6
for key in ['pooled_zero_losses','nominal_i2r','lower_i2r_075','upper_i2r_125']:
    df=pd.read_csv(P/(key+'_annual.csv'))
    assert len(df)==16
    assert abs(df.AC_approx_losses_GWh.mean()-j['scenario_mean_results'][key]['AC_approx_losses_GWh'])<1e-7
    assert abs(df.HVO_ML.mean()-j['scenario_mean_results'][key]['HVO_ML'])<1e-7
s=j['scenario_mean_results']
assert s['pooled_zero_losses']['AC_approx_losses_GWh']==0.
assert s['lower_i2r_075']['AC_approx_losses_GWh']<s['nominal_i2r']['AC_approx_losses_GWh']<s['upper_i2r_125']['AC_approx_losses_GWh']
assert s['nominal_i2r']['incremental_cost_CAD_MWh']>0
assert (P/'Figure_S15_Full_16yr_Network_Losses.png').exists()
print('PASS: 140160 hourly records; complete 16-year balance; exact pooled control; 2.5/3GW caps; zero emergency gas/unserved; site/local network screens; 0.75/1/1.25 loss sensitivity.')
