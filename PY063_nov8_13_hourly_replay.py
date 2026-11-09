#!/usr/bin/env python3
"""16x8760 coupled energy-demand screen for Digital Gardens vs. Wonder Valley.
Preserves original dispatch engine exactly; modifies demand only. Weather-derived monthly heat
shape is an *assumption*, not a measured local heat contract. 29 February deliberately omitted.
"""
from pathlib import Path
import sys, json, math
import numpy as np, pandas as pd
HERE=Path(__file__).resolve().parent
SRC=HERE.parents[1]  # package's 02_PRIVATE_RESEARCH
sys.path.insert(0,str(SRC/'code'))
from evidence_model import load_inputs,run_case,ANNUAL,COL,price,HVO_CAP
from storage_fuel_sweetspot import P
OUT=HERE/'results';OUT.mkdir(parents=True,exist_ok=True)
source_meta=json.loads((SRC/'comparative_analysis/NOV8_12/NOV8_12_metrics.json').read_text())
Q=float(source_meta['Q_delivery_target_TWh_y']);RAS=float(source_meta['RAS_case_electricity_TWh_y']);AUX=float(source_meta['extra_HP_RAS_electricity_TWh_y'])
raw=pd.read_csv(SRC/'inputs/weather_qc_hourly.csv.gz',usecols=['time_utc','temperature_C'])
raw['time_utc']=pd.to_datetime(raw.time_utc,utc=True,errors='coerce')
raw=raw[raw.temperature_C.between(-60,50)]
raw['year']=raw.time_utc.dt.year;raw['month']=raw.time_utc.dt.month
monthly=raw.groupby(['year','month']).temperature_C.mean().unstack()
# Missing weather-site months are replaced only by calendar-month climatology from the same archive.
monthly=monthly.reindex(range(2010,2026));monthly=monthly.fillna(monthly.mean()).fillna(monthly.stack().mean())
# The heat model's disaggregated components (TWh useful delivered per 8760h year)
thermal={'residential':2.459735,'aquaculture':4.770790,'digester':0.056215,
         'industrial_drying_net':Q-2.459735-4.770790-0.056215}
assert abs(sum(thermal.values())-Q)<1e-9
# 25% residential base hot water, 75% weather-shaped space heat; 70% aqua uniform,
# 30% seasonal; constant digesters and industrial drying (not measured contract).
shape_assumptions={'residential_constant_fraction':0.25,'aquaculture_constant_fraction':0.70,
                   'degree_day_reference_C':18.0,'heat_pump_COP':3.5,'distribution_loss':0.10,
                   'RAS_electricity_TWh_yr':RAS,'weather':'pooled station monthly temperatures (imperfect proxy)',
                   'thermal_source':'archived heat node totals, NOT customer metering','seasonal_drying_profile':'flat, sensitivity only'}

def datetimes(y):
 t=pd.date_range(f'{y}-01-01',f'{y+1}-01-01',freq='h',inclusive='left',tz='UTC')
 return t[~((t.month==2)&(t.day==29))]

def allocate_year(temps,idx,seasonal=True):
 mo=idx.month.to_numpy();factors=np.maximum(18-temps.loc[mo].to_numpy(),1)
 factors=factors/factors.sum();flat=np.ones(len(idx))/len(idx)
 def blend(k):return flat*k+factors*(1-k) if seasonal else flat
 profiles={}
 for name,total in thermal.items():
  if name=='residential':frac=shape_assumptions['residential_constant_fraction']
  elif name=='aquaculture':frac=shape_assumptions['aquaculture_constant_fraction']
  else:frac=1
  profiles[name]=total*blend(frac)
 delivered=sum(profiles.values()) # 8760 TWh per hour
 hp=delivered/(.9*3.5)*1e6;ras=np.full(8760,RAS*1e6/8760)
 return hp,ras,delivered*1e6,profiles

inp,years,_,_=load_inputs()
base=json.loads((SRC/'baseline/RESEARCH_CODE/GRID_CONNECTED_REOPT/reoptimized_grid_case.json').read_text())
ref=np.array(list(base['wind_capacity_GW_by_site'].values())+[base['solar_GW'],base['battery_GWh']])
robj=json.loads((SRC/'results/NOV8_08_rounded_robust_summary.json').read_text());rob=np.array(robj['integer8MW_portfolio'])
# The engine receives W etc unchanged; augmented demand = facility + existing dryer booster + HP + RAS.
HP=[];RA=[];TH=[];res_heat=[];months=[]
for y in years:
 idx=datetimes(int(y));hp,ras,deliv,profiles=allocate_year(monthly.loc[y],idx,True)
 HP.append(hp);RA.append(ras);TH.append(deliv);res_heat.append(profiles['residential']*1e6)
 months.extend(idx.strftime('%Y-%m').tolist())
HP=np.stack(HP);RA=np.stack(RA);TH=np.stack(TH);RHEAT=np.stack(res_heat)
assert np.allclose(HP.sum(axis=1)/1e6,Q/(.9*3.5))
assert np.allclose(RA.sum(axis=1)/1e6,RAS)
assert np.allclose((HP+RA).sum(axis=1)/1e6,AUX)
shape_assumptions.update({'annual_heat_service_TWh':Q,'annual_HP_TWh':float(HP.sum(axis=1).mean()/1e6),
 'incremental_annual_MWh':float((HP+RA).sum(axis=1).mean()),
 'seasonal_aux_peak_MW':float((HP+RA).max()),'base_load_TWh_per_year':float(inp['L'].sum(axis=1).mean()/1e6),
 'revised_load_TWh_per_year':float((inp['L']+HP+RA).sum(axis=1).mean()/1e6),'years':years.tolist()})
(OUT/'assumptions.json').write_text(json.dumps(shape_assumptions,indent=2)+'\n')
profile=pd.DataFrame({'year':np.repeat(years,8760),'month':months,'hp_MW':HP.ravel(),'ras_MW':RA.ravel(),
 'useful_heat_demand_MWh':TH.ravel(),'residential_heat_demand_MWh':RHEAT.ravel()})
profile['original_load_MW']=inp['L'].ravel();profile['augmented_load_MW']=profile.original_load_MW+profile.hp_MW+profile.ras_MW
profile.to_csv(OUT/'NOV8_13_HOURLY_NEW_COMMUNITY_LOAD_2010_2025.csv.gz',index=False,compression='gzip')
# Dispatch cases for reference/robust, central/joint adverse, and flat-shape sensitivity.
summary=[];annual_out=[];ledgers=[]
base_profiles={}
for portfolio,c in [('reference',ref),('enlarged',rob)]:
 for case,wind,access,engine,seasonal in [('central',1.0,1.0,5100,True),('wind_minus10',.9,1.,5100,True),
                                          ('half_access',1.,.5,5100,True),('firm_160MW_site',1.,1.,2720,True),
                                          ('combined_adverse',.9,.5,2720,True),('central_flat_load',1.,1.,5100,False)]:
  extra=HP+RA if seasonal else np.full(HP.shape,AUX*1e6/8760)
  scenario_input=dict(inp,L=inp['L']+extra,IC=inp['IC']*access,EC=inp['EC']*access)
  aa,hh=run_case(c,scenario_input,engine=engine,wind=wind,record=True)
  annual=pd.DataFrame(aa,columns=ANNUAL);annual['year']=years;annual['portfolio']=portfolio;annual['case']=case
  annual_out.append(annual)
  base_case=case=='central';fmt={'portfolio':portfolio,'scenario':case,'annual_extra_demand_TWh':float(extra.sum(axis=1).mean()/1e6),
       'annual_total_load_TWh':float(aa[:,13].mean()),'unserved_GWh_16yr':float(aa[:,1].sum()),
       'unserved_hours_16yr':int((hh[:,9]>1e-7).sum()),'max_unserved_MW':float(aa[:,9].max()),
       'max_HVO_ML_year':float(aa[:,0].max()),'mean_HVO_ML_year':float(aa[:,0].mean()),
       'mean_import_TWh_year':float(aa[:,2].mean()),'mean_export_TWh_year':float(aa[:,3].mean()),
       'mean_curtail_TWh_year':float(aa[:,4].mean()),'mean_B100_GWh_year':float(aa[:,8].mean()),
       'mean_import_net_trade_CAD_bn_year':float((aa[:,5]-aa[:,6]).mean()),
       'mean_total_load_unserved_pct':float(100*aa[:,1].sum()/(aa[:,13].sum()*1e3)),
       'conditional_cost_CAD_MWh_old_denominator':(float(price(c,aa)) if aa[:,1].sum()<1e-6 else None)}
  summary.append(fmt)
  if base_case:
   pd.DataFrame(hh,columns=COL).assign(year=np.repeat(years,8760)).to_csv(OUT/f'NOV8_13_{portfolio}_CENTRAL_AUGMENTED_DISPATCH_hourly.csv.gz',index=False,compression='gzip')
  print('RESULT',json.dumps(fmt),flush=True)
# recompute a bounded partial emissions change to old portfolio without inventing new full LCA factors
olds=pd.read_csv(SRC/'results/scenario_annual.csv')
refold=olds[olds.scenario.eq('new_build_observed_shape')]
robold=pd.read_csv(SRC/'results/NOV8_08_rounded_robust_central_annual.csv')
lcap=pd.read_csv(SRC/'audit/NOV8_08_BOUNDED_LCA_PROXY_MEAN.csv').set_index('portfolio')
for portfolio,old,lcidx in [('reference',refold,'baseline'),('enlarged',robold,'robust_integer')]:
 now=next(x for x in summary if x['portfolio']==portfolio and x['scenario']=='central')
 old_import=float(old.import_TWh.mean());old_hvo=float(old.HVO_ML.mean());old_b100=float(old.B100_GWh.mean())
 gross=float(lcap.loc[lcidx,'partial_proxy_MtCO2e'])
 grid_inc=(now['mean_import_TWh_year']-old_import)*0.1
 hvo_inc=(now['mean_HVO_ML_year']-old_hvo)*.00091275 # Mt per ML; 36.51 MJ/L*25 g/MJ
 b100_inc=(now['mean_B100_GWh_year']-old_b100)*.0002
 adjusted=gross+grid_inc+hvo_inc+b100_inc
 condition_credit=float(source_meta['DG_community_credit_legacy_Mt_y'])
 output={'portfolio':portfolio,'archived_incomplete_gross_MtCO2e_y':gross,'grid_delta_MtCO2e_y':grid_inc,
  'HVO_delta_MtCO2e_y':hvo_inc,'B100_delta_MtCO2e_y':b100_inc,
  'updated_incomplete_gross_MtCO2e_y':adjusted,'conditional_heat_and_drying_avoidance_MtCO2_y':condition_credit,
  'updated_conditional_incomplete_net_MtCO2e_y':adjusted-condition_credit,
  'fuel_cost_change_CAD_m_y':(now['mean_HVO_ML_year']-old_hvo)*1.8,
  'electricity_net_trade_change_CAD_m_y':(now['mean_import_net_trade_CAD_bn_year']-float((old.import_cost_CAD_bn-old.export_revenue_CAD_bn).mean()))*1e3,
  'cost_exclusions':'New heat-pump, RAS, greenhouses, piping, capital, network access, staff, fish feed and site-specific market prices not costed.'}
 ledgers.append(output)
(OUT/'NOV8_13_HOURLY_DISPATCH_SCENARIO_SUMMARY.csv').write_text(pd.DataFrame(summary).to_csv(index=False))
pd.concat(annual_out,ignore_index=True).to_csv(OUT/'NOV8_13_HOURLY_DISPATCH_ANNUAL.csv',index=False)
pd.DataFrame(ledgers).to_csv(OUT/'NOV8_13_PARTIAL_EMISSIONS_DISPATCH_DELTA.csv',index=False)
(OUT/'NOV8_13_MODEL_RESULTS.json').write_text(json.dumps({'summary':summary,'partial_emissions':ledgers,'assumptions':shape_assumptions},indent=2)+'\n')
assert len(summary)==12
assert abs(summary[0]['annual_extra_demand_TWh']-AUX)<1e-8
print('SUCCESS 12 model runs, 16 years x 8760 hours each. Engineering feasibility NOT certified.',flush=True)
