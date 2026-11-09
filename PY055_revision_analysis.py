#!/usr/bin/env python3
"""Post-process already simulated hourly and annual portfolios without refitting.
These are bounded stress/partial carbon accounting screens, NOT AC/N-1 or LCA.
"""
from pathlib import Path
import json, math
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1]
R=ROOT/'results';F=ROOT/'figures'
F.mkdir(exist_ok=True)
A=pd.read_csv(R/'scenario_annual.csv')
S=pd.read_csv(R/'scenario_summary.csv')
FITS=json.loads((R/'fit_results.json').read_text())
C=FITS['selected_capacities']
central=A[A.scenario=='new_build_observed_shape'].copy()
assert len(central)==16
Scentral=S[(S.scenario=='new_build_observed_shape')&(S.period=='all')].iloc[0]
# Assumptions copied from bundled research model. Units shown in output, not new observations.
DEFAULT={'wind_lifecycle_g_per_kWh':11.0, 'solar_lifecycle_g_per_kWh':35.0,
         'battery_embodied_kg_per_kWh':70., 'battery_amortisation_years':15.,
         'HVO_wtw_g_per_MJ':25., 'HVO_LHV_MJ_per_L':36.51,
         'B100_wtw_g_per_MJ':30., 'B100_engine_efficiency':0.54,
         'grid_intensity_g_per_kWh':100.}

def ledger(df, grid=100., hvo_ci=25.):
    out=df[['scenario','year']].copy()
    out['wind_proxy_MtCO2e']=df.wind_TWh * DEFAULT['wind_lifecycle_g_per_kWh']/1000
    out['solar_proxy_MtCO2e']=df.solar_TWh * DEFAULT['solar_lifecycle_g_per_kWh']/1000
    out['battery_amortised_proxy_MtCO2e']=float(C[6])*1e6*DEFAULT['battery_embodied_kg_per_kWh']/DEFAULT['battery_amortisation_years']/1e9
    out['HVO_wtw_proxy_MtCO2e']=df.HVO_ML*DEFAULT['HVO_LHV_MJ_per_L']*hvo_ci/1e6
    out['B100_wtw_proxy_MtCO2e']=df.B100_GWh*3.6/DEFAULT['B100_engine_efficiency']*DEFAULT['B100_wtw_g_per_MJ']/1e6
    out['grid_import_proxy_MtCO2e']=df.import_TWh*grid/1000
    components=[c for c in out if c.endswith('_MtCO2e')]
    out['partial_ledger_MtCO2e']=out[components].sum(axis=1)
    out['assumed_grid_g_per_kWh']=grid;out['assumed_HVO_g_per_MJ']=hvo_ci
    return out

combinations=[]
for grid in [15,100,250]:
 for hci in [15,25,35]:
  d=ledger(central,grid,hci)
  d.to_csv(R/f'emissions_annual_grid{grid}_hvo{hci}.csv',index=False)
  r={'grid_g_kWh':grid,'HVO_g_MJ':hci,'mean_partial_MtCO2e_per_year':d.partial_ledger_MtCO2e.mean(),
     'min_partial_MtCO2e_year':d.partial_ledger_MtCO2e.min(),'max_partial_MtCO2e_year':d.partial_ledger_MtCO2e.max()}
  for col in [c for c in d if c.endswith('_MtCO2e') and c!='partial_ledger_MtCO2e']:
   r['mean_'+col]=d[col].mean()
  combinations.append(r)
pd.DataFrame(combinations).to_csv(R/'NOV8_emissions_partial_proxy_sensitivities.csv',index=False,float_format='%.8f')

# Report true annual / full-chronology stress burden from existing stored hourly runs.
stress=[]
for label in A.scenario.unique():
    h=pd.read_csv(R/f'{label}_hourly.csv.gz',usecols=['unserved_MW','HVO_MW','import_MW','import_cap_MW'])
    bad=h.unserved_MW.to_numpy()>1e-6
    ix=np.flatnonzero(bad)
    if len(ix):
        cuts=np.where(np.diff(ix)>1)[0]
        starts=np.r_[0,cuts+1]
        ends=np.r_[cuts,len(ix)-1]
        runs=ix[ends]-ix[starts]+1
        longest=int(runs.max());events=len(runs)
    else:longest=events=0
    annual=A[A.scenario==label];assert len(annual)==16
    assert abs(h.unserved_MW.sum()/1000-annual.unserved_GWh.sum())<.02, label
    stress.append({'scenario':label, 'unserved_total_GWh':annual.unserved_GWh.sum(),
       'unserved_hours':len(ix),'unserved_events':events,'longest_contiguous_unserved_hours':longest,
       'peak_unserved_MW':h.unserved_MW.max(),'worst_year_unserved_GWh':annual.unserved_GWh.max(),
       'worst_year_unserved_year':int(annual.loc[annual.unserved_GWh.idxmax(),'year']),
       'worst_year_HVO_ML':annual.HVO_ML.max(),
       'available_HVO_margin_ML':976.4516-annual.HVO_ML.max()})
pd.DataFrame(stress).to_csv(R/'NOV8_hourly_stress_diagnostics.csv',index=False,float_format='%.6f')

# All dollar sensitivities calculated as frozen-dispatch accounting increments, NOT price forecasts.
load=36.00486;hvo=float(central.HVO_ML.mean());ic=float(central.import_cost_CAD_bn.mean());rev=float(central.export_revenue_CAD_bn.mean());
annuity=sum((1.06)**-n for n in range(1,26))
renew_capex=2.6*sum(C[:5])+1.35*C[5]
per_bn=1000/(load*annuity)
costscreens=[
 {'shock':'HVO price +20%','delta_CAD_MWh':hvo*1.8*.20/load,'boundary':'Annual average fuel spend, frozen dispatch and supply'},
 {'shock':'HVO price -20%','delta_CAD_MWh':-hvo*1.8*.20/load,'boundary':'Annual average fuel spend, frozen dispatch and supply'},
 {'shock':'Gross import purchase costs +30%','delta_CAD_MWh':ic*1000*.30/load,'boundary':'Excludes dispatch response; export revenue unchanged'},
 {'shock':'Gross import purchase costs -30%','delta_CAD_MWh':-ic*1000*.30/load,'boundary':'Excludes dispatch response; export revenue unchanged'},
 {'shock':'Gross export revenue falls 50%','delta_CAD_MWh':rev*1000*.50/load,'boundary':'Excludes dispatch response'},
 {'shock':'Wind + solar capex +20%','delta_CAD_MWh':renew_capex*.2*per_bn,'boundary':'Fixed build, initial capex annuitised over assumed 25-year horizon'},
 {'shock':'Additional unspecified capex C$1 bn','delta_CAD_MWh':per_bn,'boundary':'Unit exposure only: no engineering estimate or feasibility sign-off'},
]
for x in costscreens:x['screen_cost_CAD_MWh']=float(Scentral.cost_CAD_MWh)+x['delta_CAD_MWh']
pd.DataFrame(costscreens).to_csv(R/'NOV8_frozen_dispatch_cost_sensitivities.csv',index=False,float_format='%.6f')

# A precise reserve thought experiment, not an inventory contract or reliable re-dispatch.
cap=976.4516;peak=float(central.HVO_ML.max())
reserve={'worst_year':int(central.loc[central.HVO_ML.idxmax(),'year']),
 'worst_year_HVO_ML':peak,'assumed_annual_cap_ML':cap,'margin_ML':cap-peak,
 'margin_percent_of_cap':100*(cap-peak)/cap,
 'fuel_ceiling_for_10_percent_headroom_above_peak_ML':peak*1.10,
 'additional_volume_over_assumed_cap_ML':max(0,peak*1.10-cap),
 'method':'The 10% headroom is an arithmetic sensitivity of the central case, not a contracted supply or revised dispatch.'}
(R/'NOV8_fuel_reserve_screen.json').write_text(json.dumps(reserve,indent=2)+'\n')

# Graphs. No implied confidence intervals.
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'axes.spines.top':False,'axes.spines.right':False,'figure.dpi':180})
fig, ax=plt.subplots(figsize=(9.4,4.8))
d=pd.DataFrame(combinations)
for ci,marker in [(15,'o'),(25,'s'),(35,'^')]:
 x=d[d.HVO_g_MJ==ci]
 ax.plot(x.grid_g_kWh,x.mean_partial_MtCO2e_per_year,marker=marker,linewidth=2,label=f'HVO {ci} g CO2e/MJ')
ax.set_xlabel('Assumed grid electricity factor (g CO₂e/kWh)')
ax.set_ylabel('Partial lifecycle-proxy emissions (Mt CO₂e/year)')
ax.set_title('Recomputed 2010–2025 partial carbon ledger: sensitivity, not a system LCA')
ax.grid(alpha=.20);ax.legend(frameon=False,fontsize=8)
fig.text(.08,.03,'Includes assumed wind, solar, battery, HVO, B100 and grid components; omits hydro and other lifecycle sources.',fontsize=7.4)
fig.subplots_adjust(bottom=.19,top=.87,left=.10,right=.97)
fig.savefig(F/'Figure_4_partial_emissions_sensitivity.png',dpi=220);plt.close(fig)

view=pd.DataFrame(stress)
order=['new_build_observed_shape','new_build_wind_minus10pct','new_build_local160MW','new_build_clock_minus1h','new_build_half_access']
labels=['Central','Wind -10%','160 MW/site','Clock -1 h','Access halved']
subset=view.set_index('scenario').loc[order]
fig,ax=plt.subplots(figsize=(9.4,4.8))
y=np.arange(len(order)); vals=subset.unserved_total_GWh.values
ax.barh(y, vals, color=['#347e84','#ad7552','#ad7552','#ad7552','#ae4949'])
ax.set_yticks(y,labels);ax.invert_yaxis();ax.set_xlim(0,max(vals)*1.18+30)
for i,v in enumerate(vals):ax.text(v+max(vals)*.02+10,i,f'{v:,.1f} GWh',va='center',fontsize=9)
ax.set_xlabel('Unserved energy over 140,160 modelled hours (GWh)')
ax.set_title('Fixed-capacity adequacy failure under stressed assumptions')
ax.grid(axis='x',alpha=.18)
fig.text(.09,.035,'Not outage predictions: hypothetical unmet load in an energy-balance model, not an AC/N−1 security study.',fontsize=7.7)
fig.subplots_adjust(left=.23,right=.95,bottom=.20,top=.86)
fig.savefig(F/'Figure_5_stress_adequacy.png',dpi=220);plt.close(fig)

# QA checks (strong enough to catch accidental stale baseline selection).
base=d[(d.grid_g_kWh==100)&(d.HVO_g_MJ==25)].iloc[0]
assert 1.5 < base.mean_partial_MtCO2e_per_year < 3.5,base
assert float(view.set_index('scenario').loc['new_build_observed_shape','unserved_total_GWh'])<1e-8
assert float(view.set_index('scenario').loc['new_build_half_access','unserved_total_GWh'])>30000
summary={'ledger_boundary':'partial proxy, not project lifecycle inventory',
 'mean_partial_MtCO2e_year_grid100_HVO25':float(base.mean_partial_MtCO2e_per_year),
 'annual_generation_and_fuel_source':'results/scenario_annual.csv; scenario=new_build_observed_shape',
 'carbon_assumptions':DEFAULT,
 'stress_analyses_on_frozen_build':len(stress),'reserve':reserve,
 'cost_base_CAD_MWh':float(Scentral.cost_CAD_MWh),'price_increment_per_CAD_1bn_initial_capex_CAD_MWh':per_bn,
 'tests':'Annual sums agree with the underlying saved hourly scenario files to 0.02 GWh; no refitting or new AC claim'}
(R/'NOV8_revision_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))
print('STRESSES\n',pd.DataFrame(stress).to_string(index=False))
