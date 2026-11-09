#!/usr/bin/env python3
"""NOV8_12: transparent comparison ledger, source-linked and replayable.
It reads locally archived NOV8_11 metrics and robust-scenario annual CSVs.
This does NOT certify project construction, heat availability, life-cycle completeness,
or public redistribution rights.
"""
from pathlib import Path
import csv, json, math

HERE=Path(__file__).resolve().parent
PRIVATE=HERE.parents[1]  # .../02_PRIVATE_RESEARCH
OLD=HERE.parent/'NOV8_11'/'NOV8_11_verified_metrics.json'
R=PRIVATE/'results'
if not OLD.exists():
    raise FileNotFoundError(f'NOV8_11 metrics not found at {OLD}')
a=json.loads(OLD.read_text())

def write(name, rows):
    path=HERE/name
    keys=list(rows[0].keys())
    with path.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)

def r(x,n=6):return round(float(x),n)
GAS=52.91   # kg CO2/MMBtu, EIA published October 2026
C=3.412141633*GAS/1000  # Mt CO2 per TWh of gas input on HHV basis
ETA=0.57
E=a['electricity_TWh_y']
F=a['facility_TWh_y_ex_dryer_booster']
B=a['dryer_booster_TWh_y']
assert abs(E-F-B)<1e-8
IT=a['IT_TWh_y']
assert abs(F/IT-a['true_inferred_PUE_ex_dryer'])<1e-7
DG_GROSS=a['DG_ref_partial_MtCO2e_y']
DG_ENL=a['DG_enlarged_partial_MtCO2e_y']
CREDIT=a['DG_total_community_avoided_MtCO2_y_conditional']
Q=a['DG_legacy_total_heat_use_TWh_y']

rows=[]
for scope,e in [('same facility only',F),('facility plus distinct dryer booster (archived primary)',E)]:
    for typ,eta in [('CCGT 57% net HHV',0.57),('simple cycle 38% net HHV',0.38)]:
        rows.append(dict(scope=scope,case=typ,annual_electric_service_TWh=r(e),gas_fuel_TWh_HHV=r(e/eta),direct_gas_CO2_Mt=r(C*e/eta),non_electric_fuel_heat_TWh=r(e/eta-e),status='assumed technology; not a WV operating forecast'))
write('NOV8_12_fixed_gas_generation.csv',rows)

# Transparent CCS sensitivity; leakage coefficient inherited from old script (not an LCA)
LEAK_BASE=a['WV_CCGT_assumed_1pct_fossil_methane_leak_MtCO2e_y']
ccs=[]
for capture,penalty in [(0,0),(0.90,0.15),(0.95,0.15),(1.0,0.15)]:
    fuel=E/ETA*(1+penalty)
    direct=C*fuel*(1-capture)
    ch4=LEAK_BASE*(1+penalty)
    ccs.append(dict(case=f'CCGT capture {capture:.0%}',capture_fraction=capture,assumed_extra_fuel_fraction=penalty,electric_TWh=r(E),fuel_TWh_HHV=r(fuel),uncaptured_direct_CO2_Mt=r(direct),upstream_CH4_only_CO2e_Mt_if_1pct_leak=r(ch4),direct_plus_CH4_only_Mt_CO2e=r(direct+ch4),non_electric_thermodynamic_TWh=r(fuel-E),additional_upstream_nonmethane_and_embodied='excluded (unknown)',status='unbuilt hypothetical; 100% case ideal upper-bound, not bankable'))
write('NOV8_12_Wonder_Valley_CCS_and_methane.csv',ccs)

# Matched heat-quality scenario with full community service demand, not a measured heat network.
loss=0.10;cop=3.5;source_temp=35;supply_temp=55
heat_out_before_loss=Q/(1-loss)
Pel=heat_out_before_loss/cop
source_heat=heat_out_before_loss-Pel
DG_HVO=3.155
base_wv=E/ETA
heat=[]
for p,local_gross,aux_supply,extra_fuel in [('Digital Gardens reference',E+DG_HVO,'external/imported electricity (hypothetical)',0.0),('Wonder Valley 57% CCGT',base_wv,'additional same-site CCGT at 57% efficiency',Pel/ETA)]:
    if p.startswith('Digital'):
        total_input=local_gross+Pel; incremental_direct_CO2=None
    else:
        total_input=local_gross+extra_fuel; incremental_direct_CO2=C*extra_fuel
    heat.append(dict(project=p,IT_source_temperature_C_assumed=source_temp,community_supply_temperature_C_assumed=supply_temp,distribution_loss_fraction=loss,heat_pump_COP_assumed=cop,delivered_heat_TWh=r(Q),source_heat_extracted_TWh=r(source_heat),HP_electricity_additional_TWh=r(Pel),heat_before_distribution_TWh=r(heat_out_before_loss),gross_thermodynamic_input_screen_TWh=r(total_input),unrecovered_energy_screen_TWh=r(total_input-Q),additional_direct_gas_CO2_Mt_if_CCGT=r(incremental_direct_CO2) if incremental_direct_CO2 is not None else 'not modelled; grid/fuel mix uncertain',heat_source='both use same server-heat pump case; WV generation-stage waste heat excluded from recovered heat',caveat='not hourly co-optimised; gross input differs in upstream boundaries'))
write('NOV8_12_matched_heat_pump_service.csv',heat)

# Site heat sensitivity; a direct-heat counterfactual uses no HP electric energy, BUT requires suitably hot stream.
heat_modes=[]
for share_hp in [0.0,0.25,0.5,1.0]:
    delivered_hp=Q*share_hp
    hp_elec=delivered_hp/(1-loss)/cop
    direct_source=Q*(1-share_hp)/(1-loss)
    hp_source=delivered_hp/(1-loss)-hp_elec
    heat_modes.append(dict(share_low_grade_heat_assumed=share_hp,delivered_heat_TWh=r(Q),direct_temperature_suitable_source_TWh_needed=r(direct_source),heat_pump_source_TWh_needed=r(hp_source),total_source_TWh=r(direct_source+hp_source),heat_pump_electricity_TWh=r(hp_elec),caveat='direct heat needs independently confirmed source temperature and extraction penalty; zero-HP case not asserted feasible'))
write('NOV8_12_heat_quality_sensitivity.csv',heat_modes)

# Food production and electricity/fee risks
residents=a['DG_enrolled_residents'];fish_t=a['DG_seafood_t_y_proposed'];veg_t=a['DG_produce_t_y_proposed'];FCR=1.6
ras_kwhkg=9.59  # published case study, not measured on design; Aquacultural Engineering 2023
RAS_TWh=fish_t*1000*ras_kwhkg/1e9
Rfish_m3=a['DG_assumed_active_culture_volume_m3']
water1=Rfish_m3*.01*365
water5=Rfish_m3*.05*365
food=[dict(item='vegetables',planned_tonnes_y=r(veg_t,3),area_ha=r(a['DG_assumed_greenhouse_area_ha'],3),power_TWh='unknown',direct_FTE_assumed=r(a['DG_veg_fte_scenario'],1)),dict(item='seafood RAS',planned_tonnes_y=r(fish_t,3),area_ha='not estimated',power_TWh=r(RAS_TWh,6),direct_FTE_assumed=r(a['DG_aquaculture_fte_scenario'],1)),dict(item='processing/logistics',planned_tonnes_y=r(veg_t+fish_t,3),area_ha='not estimated',power_TWh='unknown',direct_FTE_assumed=r(a['DG_processing_FTE_scenario'],1))]
write('NOV8_12_community_food_energy_and_labour.csv',food)

# DG community reductions: avoid double counting and show necessary auxiliary energy.
inc=Pel+RAS_TWh
net=[]
for intensity in [0.015,0.100,0.250,0.438]:
    inc_CO2=inc*intensity # TWh * kg/kWh = Mt
    for name,gross in [('reference',DG_GROSS),('enlarged',DG_ENL)]:
        net.append(dict(DG_case=name,incremental_supply_factor_kg_per_kWh=intensity,uncoupled_partial_gross_MtCO2e=r(gross),conditional_home_avoidance_MtCO2=r(a['DG_residential_gas_avoided_MtCO2_y_conditional']),conditional_drying_avoidance_MtCO2=r(a['DG_drying_fossil_emissions_avoided_MtCO2_y_conditional']),aux_HP_electricity_TWh=r(Pel),RAS_scenario_electricity_TWh=r(RAS_TWh),hypothetical_incremental_electricity_emissions_MtCO2e=r(inc_CO2),indicative_adjusted_partial_net_MtCO2e=r(gross-CREDIT+inc_CO2),status='not hourly dispatched; excludes other agriculture, hardware, chemicals, water, methane, CCS effects'))
write('NOV8_12_DG_community_net_carbon_qualified.csv',net)

# employment capacities and explicit normalizations
IT_GW=IT/8.76
staff=[dict(case='DG data centre only, planning assumption',IT_GW_used_for_denominator=r(IT_GW,3),direct_ongoing_FTE=r(a['DG_data_centre_FTE_model'],1),FTE_per_GW_IT=r(a['DG_data_centre_FTE_model']/IT_GW,1),source='0.25 FTE/MW from inherited scenario'),dict(case='DG data centre plus proposed food network, planning assumption',IT_GW_used_for_denominator=r(IT_GW,3),direct_ongoing_FTE=r(a['DG_total_fte_scenario'],1),FTE_per_GW_IT=r(a['DG_total_fte_scenario']/IT_GW,1),source='includes 1,125 hypothetical community-food FTE'),dict(case='WV Phase 1 lower developer projection',IT_GW_used_for_denominator=1,direct_ongoing_FTE=100,FTE_per_GW_IT=100,source='projected per phase; 1 GW IT phase assumption'),dict(case='WV Phase 1 upper developer projection',IT_GW_used_for_denominator=1,direct_ongoing_FTE=150,FTE_per_GW_IT=150,source='projected per phase; not full-build workforce count')]
write('NOV8_12_jobs_by_GW_IT.csv',staff)

# Grid adequacy: magnitude of backup needed is a useful planning screen; NOT corrected AC dispatch.
with (R/'NOV8_08_rounded_robust_joint_adverse_annual.csv').open(newline='') as f: annual=list(csv.DictReader(f))
energy_GWh=sum(float(row['unserved_GWh']) for row in annual)
max_MW=max(float(row['max_unserved_MW']) for row in annual)
with (R/'NOV8_08_rounded_robust_local_160mw_annual.csv').open(newline='') as f: annual_local=list(csv.DictReader(f))
local_GWh=sum(float(row['unserved_GWh']) for row in annual_local)
backup_CC_CO2=C*(energy_GWh/1000)/ETA
required_nameplate_GW=max_MW/1000
fuel_GJ=energy_GWh*1000*3.6/ETA
rs=dict(robust_16yr_combined_stress_unserved_GWh=r(energy_GWh),robust_combined_stress_peak_unserved_MW=r(max_MW),robust_16yr_local_160MW_case_unserved_GWh=r(local_GWh),minimum_hypothetical_dispatchable_backup_nameplate_GW=r(required_nameplate_GW),backup_energy_16yr_TWh=r(energy_GWh/1000),additional_direct_CCGT_CO2_16yr_Mt=r(backup_CC_CO2),additional_direct_CCGT_CO2_average_year_Mt=r(backup_CC_CO2/16),incremental_CCGT_fuel_input_16yr_GJ=r(fuel_GJ),CCGT_fuel_spend_if_CAD6_per_GJ_over16yr_CAD_million=r(fuel_GJ*6/1e6),note='energy-only repair assuming no startup constraint; cannot certify dispatch feasibility or N-1; excludes firm capacity/connection/capex and reserve margins')
(HERE/'NOV8_12_reliability_backup_energy_only.json').write_text(json.dumps(rs,indent=2)+'\n')

# Coverage manifests: exclusions matter.
coverage=[
 ('Wonder Valley CCGT fuel combustion','computed direct fossil CO2','included'),
 ('Wonder Valley upstream methane (1% scenario)','upstream CH4 only','sensitivity, not primary'),
 ('Wonder Valley upstream non-CH4 gas supply','not modelled','excluded'),
 ('Wonder Valley generation capital and CCS plant','not modelled','excluded'),
 ('Wonder Valley CCUS energy penalty 15%','hypothetical electricity-maintaining fuel penalty','sensitivity'),
 ('Wonder Valley CO2 transport/leak/monitoring','not modelled','excluded'),
 ('Wonder Valley district heating','architect design intention','unverified; counterfactual matched heat scenario'),
 ('Digital Gardens wind, solar, storage','inherited amortized proxy factors','partial proxy'),
 ('Digital Gardens HVO/B100','inherited pathway factors','incomplete feedstock and tailpipe accounting'),
 ('Digital Gardens grid imports','inherited 100 g/kWh factor','not an hourly marginal grid factor'),
 ('Digital Gardens GPUs/data centre civil works','not modelled','excluded'),
 ('Digital Gardens heat-pump electricity','scenario explicit in this revision','not resimulated'),
 ('Digital Gardens community fossil heating displaced','legacy service counterfactual','conditional credit'),
 ('Digital Gardens drying fossil heat displaced','legacy service counterfactual','conditional credit'),
 ('Digital Gardens RAS pump/filtration electricity','literature single-species case-study scenario','not resimulated'),
 ('Digital Gardens crop inputs, fish feed and water','only screening quantities','excluded from emissions'),
 ('Both projects construction/decommissioning','not harmonized','excluded'),
 ('Both projects IT hardware, server refreshes','common IT workload but capital not modelled','excluded'),
 ('Grid/security full physical interconnection','synthetic topology','unverified')]
write('NOV8_12_boundary_gap_register.csv',[dict(category=x,status=y,accounting=z) for x,y,z in coverage])

status={'source_version':'NOV8_11_DIGITAL_GARDENS_VS_WONDER_VALLEY_COMPLETE','service_TWh_y':E,'facility_service_TWh_y':F,'drying_booster_TWh_y':B,'DG_gross_partial_Mt_y':DG_GROSS,'DG_enlarged_gross_partial_Mt_y':DG_ENL,'WV_CCGT_direct_Mt_y':C*E/ETA,'WV_CCGT_90pct_direct_Mt_y':ccs[1]['uncaptured_direct_CO2_Mt'],'WV_CCGT_95pct_direct_Mt_y':ccs[2]['uncaptured_direct_CO2_Mt'],'WV_CCGT_90pct_incl_CH4_Mt_y':ccs[1]['direct_plus_CH4_only_Mt_CO2e'],'DG_community_credit_legacy_Mt_y':CREDIT,'Q_delivery_target_TWh_y':Q,'heat_pump_aux_electricity_TWh_y':Pel,'heat_extracted_TWh_y':source_heat,'RAS_case_electricity_TWh_y':RAS_TWh,'extra_HP_RAS_electricity_TWh_y':inc,'water_1pct_daily_m3_y':water1,'water_5pct_daily_m3_y':water5,'feed_FCR1p6_t_y':fish_t*FCR,'DG_reference_illustrative_net_at100g_Mt_y':DG_GROSS-CREDIT+inc*.1,'DG_enlarged_illustrative_net_at100g_Mt_y':DG_ENL-CREDIT+inc*.1,**rs}
(HERE/'NOV8_12_metrics.json').write_text(json.dumps(status,indent=2)+'\n')
assert math.isclose(status['WV_CCGT_direct_Mt_y'],a['WV_CCGT_combustion_MtCO2_y'],rel_tol=1e-9)
assert math.isclose(status['DG_community_credit_legacy_Mt_y'],a['DG_total_community_avoided_MtCO2_y_conditional'],rel_tol=1e-9)
assert abs(Pel+source_heat-heat_out_before_loss)<1e-9
assert abs(total_input-Q-heat[-1]['unrecovered_energy_screen_TWh'])<1e-5
assert abs(energy_GWh-2944.470663858971)<1e-5
print('PASS NOV8_12 cross-check; nine generated tabular/JSON research outputs. NOT physical validation.')
print(json.dumps({k:status[k] for k in ['WV_CCGT_direct_Mt_y','WV_CCGT_90pct_incl_CH4_Mt_y','heat_pump_aux_electricity_TWh_y','RAS_case_electricity_TWh_y','extra_HP_RAS_electricity_TWh_y','DG_reference_illustrative_net_at100g_Mt_y','robust_combined_stress_peak_unserved_MW']},indent=2))
