#!/usr/bin/env python3
"""Auditable incremental screening emission + HVO fuel cost ledger.

Boundary is ONLY the already-modeled fixed installed renewable/storage hardware,
imported grid electricity, HVO WTW factor and proportional older SCR/N2O factor.
NOT a cradle-to-grave project LCA. No physical 13%-rating upgrades are designed.
"""
import json
from pathlib import Path
import pandas as pd
HERE=Path(__file__).resolve().parent
F=HERE.parent
G=F.parent
R=G.parent
prior=json.loads((G/'integrated_grid_heat_gpu.json').read_text())
loss=json.loads((F/'full_16yr_loss_results.json').read_text())['scenario_mean_results']['nominal_i2r']
old=json.loads((R/'NETWORK_LOAD_FLOW_N_MINUS_1/grid_connected_base_case.json').read_text())
prevent=pd.read_csv(HERE/'PREEMPTIVE/preemptive_annual_fuel_check.csv')
wind=pd.read_csv(HERE/'ADVERSE_WIND_10PCT/wind10_annual_fuel_check.csv')
# Explicit inputs held constant throughout; historical-wind sensitivity is a
# diesel-substitution experiment, not a separate cradle-to-grave manufacturing LCA.
PCT=25.0; HVO_LHV=36.51; HVO_CAD_L=1.80; ELECTRICITY_MWh=36.00486e6
HVO_MT_PER_ML=PCT*HVO_LHV/1e6
SCR_MT_PER_ML=old['revised_SCR_N2O_emissions_Mt']/old['annual_mean_HVO_ML']
old_hvo=prior['after_drying']['hvo_ml_mean']
old_grid=prior['after_drying']['import_twh']
base_em={int(k):v for k,v in prior['emissions_mt_approx_by_grid_intensity'].items()}
# Demonstrate the old constant term, including wind/solar, fixed amortized hardware,
# B100 and any other components previously included; do not claim independent
# extraction of each component. An unchanged term excludes new line material.
fixed_other={int(k):v-old_hvo*(HVO_MT_PER_ML+SCR_MT_PER_ML)-old_grid*k/1000 for k,v in base_em.items()}
rows=[]
for scenario,extra in [('pooled_zero_loss',0),('intact_i2r_loss',0),('hypothetical_preventive_13pct',prevent.additional_HVO_ML.mean()),('wind_minus10_full_hvo_substitution',wind.additional_HVO_ML.mean())]:
 hvo=old_hvo if scenario=='pooled_zero_loss' else loss['HVO_ML']+extra
 gtwh=old_grid if scenario=='pooled_zero_loss' else loss['grid_import_TWh']
 cost=(prior['after_drying']['total_CAD_MWh'] if scenario=='pooled_zero_loss' else loss['loss_aware_cost_before_reactive_capex_CAD_MWh']+extra*1e6*HVO_CAD_L/ELECTRICITY_MWh)
 for factor in [20,100,250]:
  # Carbon total = fixed prior non-variable accounting + HVO upstream + scaled
  # SCR N2O sensitivity + imported-grid lifecycle, with NO export credit.
  mt=fixed_other[factor] + hvo*HVO_MT_PER_ML + hvo*SCR_MT_PER_ML + gtwh*factor/1000
  rows.append(dict(scenario=scenario,grid_CI_gCO2e_kWh=factor,import_TWh_yr=gtwh,HVO_ML_yr=hvo,HVO_WTW_Mt_yr=hvo*HVO_MT_PER_ML,SCR_N2O_scaled_Mt_yr=hvo*SCR_MT_PER_ML,other_modelled_constant_Mt_yr=fixed_other[factor],grid_lifecycle_Mt_yr=gtwh*factor/1000,total_scope_limited_Mt_yr=mt,electricity_cost_CAD_MWh_fuel_only=cost,construction_O_and_M_not_priced=True))
df=pd.DataFrame(rows)
df.to_csv(HERE/'EMISSIONS_AND_FUEL_RECONCILIATION.csv',index=False,float_format='%.10f')
summ=dict(method='Fixed asset, output-derived incremental lifecycle-factor accounting. Prior fixed-asset remainder carried forward; HVO WTW and proportional SCR N2O scaled, grid imports recalculated. No reinforcements, fuel transport geography, gas-side updates, OEM testing or standalone comprehensive LCIA.',old_reference_emissions_at_100=base_em[100],prior_hvo_ML_yr=old_hvo,prior_import_TWh_yr=old_grid,loss_hvo_ML_yr=loss['HVO_ML'],loss_import_TWh_yr=loss['grid_import_TWh'],HVO_factor_gCO2e_MJ=PCT,HVO_LHV_MJ_L=HVO_LHV,HVO_price_CAD_L=HVO_CAD_L,old_scr_scaled_from_Mt=old['revised_SCR_N2O_emissions_Mt'],old_scr_scaled_from_HVO_ML=old['annual_mean_HVO_ML'],electricity_service_TWh_yr=ELECTRICITY_MWh/1e6,central_at_100={r.scenario:float(r.total_scope_limited_Mt_yr) for r in df.itertuples() if r.grid_CI_gCO2e_kWh==100},cost_CAD_MWh={r.scenario:float(r.electricity_cost_CAD_MWh_fuel_only) for r in df.itertuples() if r.grid_CI_gCO2e_kWh==100},fuel_ML_yr={r.scenario:float(r.HVO_ML_yr) for r in df.itertuples() if r.grid_CI_gCO2e_kWh==100},unquantified=['Embodied carbon of enlarged collector conductors, towers and transformers','Battery/engine degradation from new operating profile','Revised fuel production/delivery sourcing including ILUC','Protection, dynamic stability, grid connection and electricity-price impacts','Wind project siting and true observed production','Actual SCR N2O control and permit measurements'])
(HERE/'EMISSIONS_AND_FUEL_RECONCILIATION.json').write_text(json.dumps(summ,indent=2)+'\n')
# Assert source consistency instead of hiding discrepancy with headline figures.
assert abs(summ['central_at_100']['pooled_zero_loss']-base_em[100])<1e-9
assert 2.088<summ['central_at_100']['intact_i2r_loss']<2.09
assert 2.089<summ['central_at_100']['hypothetical_preventive_13pct']<2.092
assert 2.39<summ['central_at_100']['wind_minus10_full_hvo_substitution']<2.4
assert max(wind.total_HVO_ML)<float(json.loads((G/'reoptimized_grid_case.json').read_text())['fuel_limit_ML'])
assert (wind.fuel_margin_ML>0).all()
print('PASS scoped emissions and cost reconciliation',summ['central_at_100'],summ['cost_CAD_MWh'])
