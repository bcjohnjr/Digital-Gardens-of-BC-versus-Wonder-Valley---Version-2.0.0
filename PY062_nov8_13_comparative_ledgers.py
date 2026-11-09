#!/usr/bin/env python3
"""Append reproducible comparative sensitivity ledgers; no measured WV operating data inferred."""
import json,pandas as pd,numpy as np,math
from pathlib import Path
HERE=Path(__file__).resolve().parent;R=HERE/'results'
m=json.loads((R/'NOV8_13_MODEL_RESULTS.json').read_text());s=pd.read_csv(R/'NOV8_13_HOURLY_DISPATCH_SCENARIO_SUMMARY.csv');l=pd.read_csv(R/'NOV8_13_PARTIAL_EMISSIONS_DISPATCH_DELTA.csv')
a=json.loads(((HERE.parents[1]/'comparative_analysis/NOV8_12/NOV8_12_metrics.json')).read_text())
E0=a['facility_service_TWh_y'];E1=a['service_TWh_y'];E2=m['assumptions']['revised_load_TWh_per_year']
EF=3.412141633*52.91/1000
leak0=1.378 # pre-existing assumed 1% gas methane CH4 only; inherited approximate
leak_base=1.378219 # accuracy not warranted; recompute from archive previously declared
meta=[]
for e,label in [(E0,'Common facility-only compute + PUE'),(E1,'Facility plus proposed drying-booster'),(E2,'Equal-electricity including hypothetical full DG community programme')]:
 for cc,pen in [(0,0),(.9,.15),(.95,.15)]:
  direct=EF*e/.57*(1+pen)*(1-cc)
  methane=a['WV_CCGT_90pct_incl_CH4_Mt_y']-a['WV_CCGT_90pct_direct_Mt_y']
  # Use the original NOV8_12 explicit CCS methane at 90% to calibrate; scale by fuel
  methane=methane*(e/E1)*(1+pen)/1.15
  meta.append({'service_basis':label,'electric_TWh_y':e,'WW_gas_efficiency_net_HHV':.57,'CCS_capture':cc,
               'assumed_gas_penalty':pen,'direct_combustion_CO2_Mt_y':direct,
               'upstream_methane_only_CO2e_Mt_y_1pct_assumed':methane,
               'direct_plus_methane_only_Mt_y':direct+methane,
               'fuel_TWh_HHV_y':e/.57*(1+pen),'non_electric_fuel_TWh_y':e/.57*(1+pen)-e,
               'status':'hypothetical stationary CCGT; no claim WV installed this plant/CCS; no full life cycle or customer access'})
pd.DataFrame(meta).to_csv(R/'NOV8_13_WONDER_VALLEY_MATCHED_SERVICE_CCGT_CCS.csv',index=False)
# Hourly heat capacity/seasonality screen, both projects same source-side conditions; no customer metering
p=pd.read_csv(R/'NOV8_13_HOURLY_NEW_COMMUNITY_LOAD_2010_2025.csv.gz')
heat_out=p.useful_heat_demand_MWh.to_numpy(); res=p.residential_heat_demand_MWh.to_numpy()
annual_heat=float(a['Q_delivery_target_TWh_y']);maxref=annual_heat*1e6/8760
rows=[]
for title,source in [('Digital Gardens', 'assumed 35C waste server heat'),('Wonder Valley','same 35C waste server heat; proposed district energy not measured')]:
 for nominal_cap in [.5,1,1.5,2]:
  for co_location in [.25,.5,1.]:
   # assumed fraction of heat load that is actually connected/customer-eligible,
   # separate from plant thermal throughput cap; no real geospatial heat market basis.
   delivered=np.minimum(heat_out*co_location, maxref*nominal_cap)
   res_delivered=np.minimum(res*co_location,delivered)
   useful=delivered.sum()/16/1e6
   heat_loss=useful/.9-useful
   hp_e=useful/.9/3.5
   avoided_home=a['DG_community_credit_legacy_Mt_y']*0  # independently separate residential credit
   home_credit=.310656757740502*max(0,min(1,res_delivered.sum()/max(res.sum(),1e-9)))
   # Drying avoidance prorated to co-located demand, also limited by overall heat service fraction.
   drying_credit=.18603057039670576*min(co_location, useful/annual_heat)
   rows.append({'project':title,'heat_pump_output_cap_multiple_of_avg':nominal_cap,'customer_connected_fraction_ASSUMED':co_location,
    'annual_assumed_heat_demand_TWh':annual_heat,'actual_matched_heat_TWh_y_scenario':useful,
    'unmet_heat_demand_TWh_y':annual_heat-useful,'heat_pump_electricity_TWh_y':hp_e,
    'heat_source_extracted_TWh_y':useful/.9-hp_e,'distribution_losses_TWh_y':heat_loss,
    'conditional_home_gas_avoidance_Mt_y':home_credit,'conditional_drying_avoidance_Mt_y':drying_credit,
    'assumption':'Same theoretical 35C source for both; co-location and thermal plant cap synthetic, not installed or measured'})
pd.DataFrame(rows).to_csv(R/'NOV8_13_BOTH_PROJECTS_SEASONAL_HEAT_MATCH_SENSITIVITY.csv',index=False)
# Economic scenarios illustrate food/heat in-kind vs cash service: no claiming true profitability.
food_t=115038.0;fish_t=36245.0;feed_t=fish_t*1.6;ftes=1125.;solar=2.0;employees_total=2063
eref=s[(s.portfolio=='enlarged') & (s.scenario=='central')].iloc[0];cost=l[l.portfolio=='enlarged'].iloc[0]
base_incremental=float(cost.fuel_cost_change_CAD_m_y+cost.electricity_net_trade_change_CAD_m_y)
fin=[]
for intensity in ['low','central','high']:
 unit={'low':(450,3500,50000,600,6,0),'central':(700,6000,75000,800,10,0),'high':(950,8500,100000,1200,14,0)}[intensity]
 produce_value=food_t*unit[0]/1e6;fish_value=fish_t*unit[1]/1e6
 wages=ftes*unit[2]/1e6;feed=feed_t*unit[3]/1e6
 thermal_gj=annual_heat*3.6e6
 heat_value=thermal_gj*unit[4]/1e6
 fin.append({'scenario':intensity,'produce_valued_CAD_m_y_IN_KIND_not_sales':produce_value,'seafood_valued_CAD_m_y_IN_KIND_not_sales':fish_value,
  'delivered_heat_valued_CAD_m_y_IN_KIND_not_sales':heat_value,
  'sum_in_kind_not_CASH_revenue_CAD_m_y':produce_value+fish_value+heat_value,
  'new_food_jobs_FTE':ftes,'new_food_jobs_wages_CAD_m_y':wages,'assumed_feed_t_y':feed_t,'assumed_feed_purchase_CAD_m_y':feed,
  'extra_annual_energy_cost_CAD_m_y_FROM_hourly_dispatch_robust':base_incremental,
  'sum_partial_increments_CAD_m_y':wages+feed+base_incremental,
  'partially_costed_gap_CAD_m_y_not_a_net_profit':produce_value+fish_value+heat_value-wages-feed-base_incremental,
  'EXCLUDED':'heat network, heat pump and RAS capex, greenhouse/processing capex, fish juveniles, water treatment, insurance, taxes, logistics, retail margins, financing; heat demand access and double use of heat must be checked'})
pd.DataFrame(fin).to_csv(R/'NOV8_13_COMMUNITY_SERVICES_ECONOMIC_SCREEN.csv',index=False)
# Alternative full service access vs no infrastructure: value of matched services is not an asymmetrical achieved benefit
out={'WW_matched_full_service_no_CCS_direct_Mt_y':meta[6]['direct_combustion_CO2_Mt_y'],
     'WW_matched_full_service_90CCS_direct_Mt_y':meta[7]['direct_combustion_CO2_Mt_y'],
     'WW_matched_full_service_95CCS_direct_Mt_y':meta[8]['direct_combustion_CO2_Mt_y'],
     'DG_enlarged_updated_gross_Mt_y':float(cost.updated_incomplete_gross_MtCO2e_y),
     'DG_enlarged_updated_conditional_net_Mt_y':float(cost.updated_conditional_incomplete_net_MtCO2e_y),
     'DG_enlarged_hvo_consumption_new_ML_y':float(eref.mean_HVO_ML_year),
     'DG_enlarged_extra_dispatch_cost_CAD_m_y':base_incremental,
     'DG_reference_central_hourly_unserved_GWh':float(s[(s.portfolio=='reference')&(s.scenario=='central')].iloc[0].unserved_GWh_16yr),
     'DG_enlarged_central_unserved_GWh':float(eref.unserved_GWh_16yr),
     'DG_enlarged_joint_stress_unserved_GWh':float(s[(s.portfolio=='enlarged')&(s.scenario=='combined_adverse')].iloc[0].unserved_GWh_16yr),
     'approximate_partial_cost_practices':'DG added dispatch costs from inherited 1.8 CAD/L HVO and archived hourly import/export prices; no project-wide NPV, no WV OPEX comparison.',
     'important_caution':'DG credit assumes complete local thermal connections; modeled heat connection sensitivity shows less if network not built. No equal lifecycle boundary established.'}
(R/'NOV8_13_COMPARATIVE_HIGHLIGHTS.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out,indent=2))

# Site-level theoretical thermal ledger from newly dispatched HVO/B100, not heat-recovery certification.
thermal=[]
for portfolio in ('reference','enlarged'):
 row=s[(s.portfolio==portfolio)&(s.scenario=='central')].iloc[0]
 chemical=row.mean_HVO_ML_year*1e6*36.51/3.6e9
 other=(row.mean_B100_GWh_year/1e3)*(.46/.54)
 reject=chemical*.46+other
 thermal.append(dict(portfolio=portfolio,annual_local_generator_non_electric_TWh=reject,
    heat_equivalent_facility_TWh=36.00486,
    total_site_energy_heat_equiv_TWh=36.00486+reject,
    thermal_not_extracted_by_HP_TWh=36.00486+reject-7.932533009304888,
    scope='HVO fuel LHV times 46% non-electric efficiency plus B100; DOES NOT include imports heat abroad'))
for ccs in (0,.9,.95):
 z=pd.DataFrame(meta)[(pd.DataFrame(meta).service_basis=='Equal-electricity including hypothetical full DG community programme') & (pd.DataFrame(meta).CCS_capture==ccs)].iloc[0]
 reject=z.non_electric_fuel_TWh_y
 thermal.append(dict(portfolio='Wonder Valley CCGT '+str(int(ccs*100))+'% CCS',annual_local_generator_non_electric_TWh=reject,
    heat_equivalent_facility_TWh=36.00486,
    total_site_energy_heat_equiv_TWh=36.00486+reject,
    thermal_not_extracted_by_HP_TWh=36.00486+reject-7.932533009304888,
    scope='Gas HHV minus electricity; NON-ELECTRIC energy includes CCS utility and is not all recoverable heat'))
pd.DataFrame(thermal).to_csv(R/'NOV8_13_COMPARE_SITE_THERMAL_BALANCE.csv',index=False)
