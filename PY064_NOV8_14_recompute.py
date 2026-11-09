#!/usr/bin/env python3
"""NOV8_14 targeted corrected comparison, respecting archive scope and source/data rights.
Couples capacity-limited monthly weather-proxy heat deliveries to original hourly dispatch.
Does not simulate a physically solved AC network; factual model inputs are shared with provenance; assess separately accepted access terms.
"""
from __future__ import annotations
import json,sys
from pathlib import Path
import numpy as np,pandas as pd
SCRIPT=Path(__file__).resolve()
ROOT=(SCRIPT.parents[3] if SCRIPT.parent.name=='NOV8_14' else SCRIPT.parent/'NOV8_14_DIGITAL_GARDENS_VS_WONDER_VALLEY')
SRC=ROOT/'02_PRIVATE_RESEARCH'; H=SRC/'comparative_analysis/NOV8_13'; O=SRC/'comparative_analysis/NOV8_14'; O.mkdir(exist_ok=True)
sys.path[:0]=[str(SRC/'code'),str(SRC/'baseline/RESEARCH_CODE')]
from evidence_model import load_inputs,run_case,ANNUAL
meta13=json.loads((H/'results/NOV8_13_MODEL_RESULTS.json').read_text())
metrics12=json.loads((SRC/'comparative_analysis/NOV8_12/NOV8_12_metrics.json').read_text())
results13=pd.read_csv(H/'results/NOV8_13_HOURLY_DISPATCH_SCENARIO_SUMMARY.csv')
ledger13=pd.read_csv(H/'results/NOV8_13_PARTIAL_EMISSIONS_DISPATCH_DELTA.csv')
profile=pd.read_csv(H/'results/NOV8_13_HOURLY_NEW_COMMUNITY_LOAD_2010_2025.csv.gz')
assert len(profile)==16*8760
base_load=profile.original_load_MW.to_numpy().reshape((16,8760))
assert abs(base_load.sum()/16/1e6-36.251218418153286)<1e-5
RAS_Y=float(metrics12['RAS_case_electricity_TWh_y']); Q=float(metrics12['Q_delivery_target_TWh_y'])
Y=np.tile(np.arange(2010,2026)[:,None],(1,8760))
# reconstruct individual hourly allocations of heat demand using the already published source's
# 25%/70% climatology / temperature assumptions, so credits are prorated by which SERVICE was delivered.
raw=pd.read_csv(SRC/'inputs/weather_qc_hourly.csv.gz',usecols=['time_utc','temperature_C'])
raw.time_utc=pd.to_datetime(raw.time_utc,utc=True,errors='coerce');raw=raw[raw.temperature_C.between(-60,50)]
raw['year']=raw.time_utc.dt.year;raw['month']=raw.time_utc.dt.month
monthly=raw.groupby(['year','month']).temperature_C.mean().unstack().reindex(range(2010,2026))
monthly=monthly.fillna(monthly.mean()).fillna(monthly.stack().mean())
thermal={'residential':2.459735,'aquaculture':4.770790,'digester':0.056215,'drying':Q-2.459735-4.770790-0.056215}
component={key:[] for key in thermal}
for y in range(2010,2026):
 t=pd.date_range(f'{y}-01-01',f'{y+1}-01-01',freq='h',inclusive='left',tz='UTC')
 t=t[~((t.month==2)&(t.day==29))];assert len(t)==8760
 factors=np.maximum(18-monthly.loc[y].loc[t.month].to_numpy(),1.0);factors=factors/factors.sum()
 flat=np.ones(8760)/8760
 for k,val in thermal.items():
  frac=0.25 if k=='residential' else 0.70 if k=='aquaculture' else 1.
  component[k].append(val*1e6*(flat*frac+factors*(1-frac)))
for k in component:component[k]=np.stack(component[k])
Q_hour=sum(component.values());original_heat=profile.useful_heat_demand_MWh.to_numpy().reshape((16,8760))
assert np.allclose(Q_hour,original_heat,rtol=0,atol=1e-7)
# single common-service block; for each project assume same thermal profile.
WvEFA=3.412141633*52.91/1000; gas_eff=.57; methane_factor_1pct=1.512 # calibrated NOV8_13 factor corrected below using source row
w13=pd.read_csv(H/'results/NOV8_13_WONDER_VALLEY_MATCHED_SERVICE_CCGT_CCS.csv')
ws=w13[(w13.CCS_capture==0)&w13.service_basis.str.startswith('Equal-electricity')].iloc[0]
leakage_per_TWh_fuel=float(ws.upstream_methane_only_CO2e_Mt_y_1pct_assumed/ws.fuel_TWh_HHV_y)
HVO_PER_ML=36.51*25/1e6 # Mt per ML
B100_PER_GWH=.0002
# Archive's 'central' gross is a partial factor ledger, not matched whole LCA.
robj=json.loads((SRC/'results/NOV8_08_rounded_robust_summary.json').read_text())
capacities=np.array(robj['integer8MW_portfolio'],float)
inp,years,_,_=load_inputs()
assert len(years)==16 and (years==np.arange(2010,2026)).all()
main13=results13[(results13.portfolio=='enlarged')&(results13.scenario=='central')].iloc[0]
base13=ledger13[ledger13.portfolio=='enlarged'].iloc[0]
name_cfg=[('full_service',1.0,3.0),('limited_plant',1.,1.),('half_connected',.5,2.),('no_network',0.,2.)]
summary=[];annout=[];months=[]
for name,conn,cap_mult in name_cfg:
 max_cap=Q*1e6/8760*cap_mult
 delivered=np.minimum(Q_hour*conn,max_cap)
 scale=np.divide(delivered,Q_hour,out=np.zeros_like(delivered),where=Q_hour>0)
 comp_del={k:component[k]*scale for k in thermal}
 hp=delivered/(.9*3.5)
 ras=np.full_like(hp,RAS_Y*1e6/8760) # hold RAS electric input constant; food heat shortfall not repaired
 expected_base=inp['L']
 assert np.max(np.abs(expected_base-base_load))<1e-6
 consumption=expected_base+hp+ras
 q_y=float(delivered.sum()/16/1e6)
 home_frac=float(comp_del['residential'].sum()/component['residential'].sum())
 drying_frac=float(comp_del['drying'].sum()/component['drying'].sum())
 aq_frac=float(comp_del['aquaculture'].sum()/component['aquaculture'].sum())
 heat_credit=.310656757740502*home_frac+.18603057039670576*drying_frac
 heat_home=float(comp_del['residential'].sum()/16/1e6)
 heat_aq=float(comp_del['aquaculture'].sum()/16/1e6)
 for stress,wind,access,engine in [('central',1.,1.,5100),('combined_adverse',.9,.5,2720)]:
  new_inp=dict(inp,L=consumption,IC=inp['IC']*access,EC=inp['EC']*access)
  annual,_=run_case(capacities,new_inp,engine=engine,wind=wind,record=False)
  adf=pd.DataFrame(annual,columns=ANNUAL);adf.insert(0,'year',years);adf.insert(1,'heat_case',name);adf.insert(2,'stress_case',stress);annout.append(adf)
  mean_hvo=float(annual[:,0].mean());mean_b100=float(annual[:,8].mean());mean_imp=float(annual[:,2].mean())
  mean_trade=float((annual[:,5]-annual[:,6]).mean())
  gross=float(base13.updated_incomplete_gross_MtCO2e_y+(mean_imp-float(main13.mean_import_TWh_year))*.1+(mean_hvo-float(main13.mean_HVO_ML_year))*HVO_PER_ML+(mean_b100-float(main13.mean_B100_GWh_year))*B100_PER_GWH)
  fuelcost=float((mean_hvo-float(main13.mean_HVO_ML_year))*1.8)
  tradecost=float((mean_trade-float(main13.mean_import_net_trade_CAD_bn_year))*1e3)
  E=float(consumption.sum()/16/1e6)
  wv_fuel=E/.57
  wv_direct=wv_fuel*WvEFA
  wv_leak=wv_fuel*leakage_per_TWh_fuel
  row=dict(heat_case=name,stress_case=stress,connected_customers_fraction_assumed=conn,thermal_plant_capacity_multiple_of_mean=cap_mult,
    heat_target_TWh_y=Q,delivered_heat_TWh_y=q_y,residential_delivered_TWh_y=heat_home,aquaculture_heat_delivered_TWh_y=heat_aq,
    aquaculture_heat_coverage_fraction=aq_frac,industrial_drying_heat_coverage_fraction=drying_frac,
    annual_HP_electricity_TWh_y=float(hp.sum()/16/1e6),annual_RAS_electricity_TWh_y=RAS_Y,
    annual_common_electricity_TWh_y=E,conditional_avoided_residential_Mt_y=.310656757740502*home_frac,
    conditional_avoided_drying_Mt_y=.18603057039670576*drying_frac,
    conditional_avoided_total_Mt_y=heat_credit,
    DG_gross_partial_Mt_y=gross,DG_conditional_net_partial_Mt_y=gross-heat_credit,
    DG_mean_HVO_ML_year=mean_hvo,DG_mean_import_TWh_year=mean_imp,DG_mean_export_TWh_year=float(annual[:,3].mean()),
    DG_new_cost_change_from_V13_CAD_m_y=fuelcost+tradecost,DG_unserved_GWh_16yr=float(annual[:,1].sum()),
    DG_max_unserved_MW=float(annual[:,9].max()),
    WV_CCGT_no_CCS_direct_Mt_y=wv_direct,WV_CCGT_no_CCS_1pct_CH4_Mt_y=wv_leak,
    WV_CCGT_no_CCS_direct_plus_methane_Mt_y=wv_direct+wv_leak,
    WV_CCGT_90pct_CCS_direct_plus_methane_Mt_y=(wv_fuel*1.15)*WvEFA*.1+(wv_fuel*1.15)*leakage_per_TWh_fuel,
    WV_CCGT_95pct_CCS_direct_plus_methane_Mt_y=(wv_fuel*1.15)*WvEFA*.05+(wv_fuel*1.15)*leakage_per_TWh_fuel,
    caveat='Partial emissions unequal LCA boundaries; electricity load includes assumed food/heat service at WV hypothetically; heat customer connection not verified')
  summary.append(row)
  print('RESULT',name,stress,'elec',round(E,4),'thermal',round(q_y,4),'gross',round(gross,4),'net',round(gross-heat_credit,4),'unserved GWh',round(annual[:,1].sum(),2),flush=True)
  if stress=='central':
   pd.DataFrame({'year':np.repeat(years,8760),'hour_index':np.tile(np.arange(8760),16),'load_MW':consumption.ravel(),
      'hp_MW':hp.ravel(),'ras_MW':ras.ravel(),'heat_demand_MWh':Q_hour.ravel(),
      'heat_delivered_MWh':delivered.ravel(),'home_heat_delivered_MWh':comp_del['residential'].ravel(),
      'drying_heat_delivered_MWh':comp_del['drying'].ravel(),'aq_heat_delivered_MWh':comp_del['aquaculture'].ravel()}).to_csv(O/f'NOV8_14_{name}_hourly_demand_service.csv.gz',index=False)
res=pd.DataFrame(summary);res.to_csv(O/'NOV8_14_COUPLED_DISPATCH_CARBON_HEAT_SCENARIOS.csv',index=False)
pd.concat(annout,ignore_index=True).to_csv(O/'NOV8_14_ANNUAL_DISPATCH_SCENARIOS.csv',index=False)
# Economic ledgers: only final value-added benefits not intermediate heat used in aquaculture, digesters and drying.
# Food output is still contingent on facility actually built, aquatic output scaled by aquaculture heat service
# where NO alternate aquaculture heat supply has been modelled. Additional capital costs omitted in ALL scenarios.
econ=[]
for _,r in res[res.stress_case=='central'].iterrows():
 for case,(pval,fval,wage,feed,price) in {'low':(450,3500,50000,600,6),'central':(700,6000,75000,800,10),'high':(950,8500,100000,1200,14)}.items():
  produce=115038*pval/1e6
  seafood=36245*fval*r.aquaculture_heat_coverage_fraction/1e6
  residential_heat=r.residential_delivered_TWh_y*3.6e6*price/1e6
  labour=1125*wage/1e6
  feed_cost=57992*feed*r.aquaculture_heat_coverage_fraction/1e6
  old_incremental=502.55002568914983
  delta=r.DG_new_cost_change_from_V13_CAD_m_y
  cost=old_incremental+delta+labour+feed_cost
  econ.append({'heat_case':r.heat_case,'valuation':case,'conditional_garden_produce_CAD_m_y':produce,
    'conditional_seafood_final_product_CAD_m_y':seafood,'final_household_delivered_heat_CAD_m_y':residential_heat,
    'INTERNAL_aquaculture_heat_CAD_m_y_EXCLUDED':r.aquaculture_heat_delivered_TWh_y*3.6e6*price/1e6,
    'INTERNAL_dryer_and_digester_heat_EXCLUDED':max(r.delivered_heat_TWh_y-r.residential_delivered_TWh_y-r.aquaculture_heat_delivered_TWh_y,0)*3.6e6*price/1e6,
    'corrected_conditional_final_in_kind_value_CAD_m_y':produce+seafood+residential_heat,
    'energy_delta_to_version13_CAD_m_y':delta,'energy_additional_v_original_CAD_m_y':old_incremental+delta,
    'hypothetical_labour_CAD_m_y':labour,'hypothetical_feed_CAD_m_y':feed_cost,
    'PARTIAL_cost_CAD_m_y':cost,'illustrative_FINAL_VALUE_minus_PARTIAL_COST_CAD_m_y_NOT_PROFIT':produce+seafood+residential_heat-cost,
    'limitations':'Food supply, residential connection, wages, feed, unpriced capex, fish juveniles, water, CO2 accounting and full lifecycle assumptions remain conditional; cannot infer actual cash profit.'})
pd.DataFrame(econ).to_csv(O/'NOV8_14_CORRECTED_FINAL_VS_INTERMEDIATE_COMMUNITY_ECONOMICS.csv',index=False)
# Cross-check EIA units, existing V13 reported common cases, and no double counted heat.
full=res[(res.heat_case=='full_service')&(res.stress_case=='central')].iloc[0]
assert abs(full.annual_common_electricity_TWh_y-39.77182082663497)<1e-6
assert abs(full.DG_gross_partial_Mt_y-2.016541)<1e-4
assert abs(full.WV_CCGT_no_CCS_direct_Mt_y-12.596951)<1e-4
assert abs(full.WV_CCGT_no_CCS_direct_plus_methane_Mt_y-14.109)<.01
assert (res.DG_gross_partial_Mt_y>=res.DG_conditional_net_partial_Mt_y).all()
assert np.all(res['delivered_heat_TWh_y']<=Q+1e-8)
assert np.all(res['annual_RAS_electricity_TWh_y']>0)
assert (pd.DataFrame(econ).final_household_delivered_heat_CAD_m_y < 360).all()
(O/'NOV8_14_VERIFICATION.json').write_text(json.dumps({'scenario_count':len(res),'hour_count_per_scenario':16*8760,'archive_provenance':'NOV8_13 supplied original prepared inputs','crosschecks_passed':True,'full_annual_electricity_TWh':float(full.annual_common_electricity_TWh_y),'full_WV_CC_no_ccs_direct_and_methane_Mt':float(full.WV_CCGT_no_CCS_direct_plus_methane_Mt_y),'source_rights':'private, not cleared for unrestricted release'},indent=2)+'\n')
print('ALL VERIFICATIONS PASSED',flush=True)
