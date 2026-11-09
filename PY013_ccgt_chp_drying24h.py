#!/usr/bin/env python3
"""Reproducible 16-year CCGT cogeneration + continuous drying service screen.

The CCGT's residual heat is available ONLY in hours when its units generate.
Low-grade IT loop surplus (from prior independently calculated heat ledger)
is allocated to *additional* 24-hour-capable drying contracts. Temperature-lift
and fan electricity are explicitly added to the hourly dispatch before grid
imports/exports and HVO consumption are recalculated. No gas turbine electricity
or heat is double counted; no unconfirmed offtake is claimed as a sale.

Prices and equipment costs are screening assumptions; 2026 FortisBC Rate 3 and
Rate 5 *variable charges* are used as external gas heat benchmarks.
"""
from pathlib import Path
import math, json
import numpy as np
import pandas as pd
from model_combined_cycle import calc_engine_hourly, UNIT_MW, CCGT_CYCLE_FACTOR, CCGT_MIN_LOADING, ENGINE_EFF, MJ_L_HVO

ROOT=Path(__file__).resolve().parent
OUTPUT=ROOT/'CHP_CONTINUOUS_DRYING'
OUTPUT.mkdir(exist_ok=True)
FRAME=pd.read_csv(ROOT/'hourly_input_reoptimized.csv.gz')
N=8760
assert len(FRAME)==16*N
HEAT=json.loads((ROOT/'heat_reconciled.json').read_text())
# Existing recoverable IT-loop heat still rejected AFTER prior 2.955-TWh drying and
# greenhouse/aquaculture/homes allocations. We cannot consume this twice.
IT_UNUSED_MWH_PER_HOUR=HEAT['remaining_rejection_twh_per_year']*1e6/N
CHP_MW=360
CHP_CYCLE=.985
HVO_PRICE=1.80
ANNUITY=.085/(1-(1.085)**(-25))
GAS_FORTIS_RATE5_GJ=1.352+1.602+1.660 # variable $/GJ, excludes fixed demand charge
GAS_FORTIS_RATE3_GJ=5.377+2.268+1.660
GAS_BOILER_EFF=.82
BASE_COST_CAD_MWH=191.50207750263417
COMPUTING_ANNUAL_MWH=36.00486e6

def steam_plant_hour(hvo_mw):
    """Same discrete 2x180 MW thermal fuel / electric logic as model_combined_cycle.py.
    No high-grade steam extraction is assumed to be free. Only residual heat is screened.
    """
    nfull=np.minimum(np.floor(hvo_mw/UNIT_MW),2).astype(int)
    rem=np.maximum(0,hvo_mw-nfull*UNIT_MW)
    ispartial=(nfull<2)&(rem>=UNIT_MW*CCGT_MIN_LOADING)
    ppart=np.where(ispartial,rem,0)
    pel=nfull*UNIT_MW+ppart
    frac=ppart/UNIT_MW
    effpart=.53+(.60-.53)*(frac-.40)/(.60)
    fuel=nfull*UNIT_MW/(.60*CHP_CYCLE)+np.where(ispartial,ppart/(effpart*CHP_CYCLE),0)
    return pel,fuel,np.maximum(fuel-pel,0)

def simulate_year(group, additional_el_mw):
    ld=group['facility_load_MW'].to_numpy()
    generation=group['generation_MW'].to_numpy()
    current_boost=group['drying_booster_load_MW'].to_numpy()
    h,b,imp,ex=calc_engine_hourly(generation,ld,current_boost+additional_el_mw,int(group['year'].iloc[0]))
    return h,b,imp,ex

def economically_compare(q_th_mwh,net_new_electricity_cad,service_MW,upgrade_share,
                         delivery_fee_cad_mwh,gas_rate_gj):
    # Matching dryer CAPEX + common handling occur in both routes; only relative thermal
    # services differ. Dryer buildings C$600/kWth, heat connections C$200/kWth,
    # HP booster C$350/kWth of upgraded duty, boiler C$150/kWth.
    dry_capex=service_MW*1000*600
    local_capex=service_MW*1000*200
    hp_capex=service_MW*upgrade_share*1000*350
    gas_boiler_capex=service_MW*1000*150
    # Total dryer annual cash cost: owned dryer + heat connection + HP booster.
    system_fixed=(dry_capex+local_capex+hp_capex)*ANNUITY + 0.04*dry_capex+0.03*local_capex+0.02*hp_capex
    # 5 CAD/MWh common drying operations (labor / logistics / milling not priced).
    system_total=system_fixed + 5*q_th_mwh + net_new_electricity_cad
    gas_fuel_per_mwh=gas_rate_gj*3.6/GAS_BOILER_EFF
    gas_fixed=(dry_capex+gas_boiler_capex)*ANNUITY+0.04*dry_capex+0.02*gas_boiler_capex
    gas_total=gas_fixed+(5+gas_fuel_per_mwh)*q_th_mwh
    return {'system_unit_cost_cad_mwh_th':system_total/q_th_mwh,
        'gas_unit_cost_cad_mwh_th':gas_total/q_th_mwh,
        'cost_difference_cad_mwh_th':(gas_total-system_total)/q_th_mwh,
        'unit_cost_at_25cad_tariff_margin_cad_mwh':25-system_total/q_th_mwh,
        'breakeven_service_tariff_cad_mwh_th':system_total/q_th_mwh,
        'annual_profit_at_25cad_tariff_cad_m':(25*q_th_mwh-system_total)/1e6,
        'annual_profit_at_35cad_tariff_cad_m':(35*q_th_mwh-system_total)/1e6,
        'annual_profit_at_45cad_tariff_cad_m':(45*q_th_mwh-system_total)/1e6,
        'gas_fuel_only_cad_mwh_th':gas_fuel_per_mwh}

def main():
    df=FRAME
    years=[]; ccgt_hour=[]; base_by_year={}
    for yr,g in df.groupby('year',sort=True):
        h,b,imp,ex=simulate_year(g,np.zeros(N))
        cc,fuel,resid=steam_plant_hour(h)
        base_by_year[int(yr)]={'hvo':h,'b100':b,'imp':imp,'ex':ex,'price_in':g.import_price_CAD_MWh.to_numpy(),
            'price_out':g.export_price_CAD_MWh.to_numpy(),'cc':cc,'cc_fuel':fuel,'residual':resid}
        years.append(int(yr))
        ccgt_hour.append((cc.sum(),fuel.sum(),resid.sum()))
    ccgt_hour=np.asarray(ccgt_hour)
    # Cross-check that 16-year CCGT electric output and fuel match the archived model.
    v=pd.read_csv(ROOT/'CCGT_BIOMETHANE_HVO/combined_cycle_options_16yr.csv')
    q=v[(v.ccgt_MW==360)&(v.efficiency_case=='screening') & (v.case=='HVO_only') &
        (np.isclose(v.biomethane_thermal_share,.25))].iloc[0]
    assert abs(ccgt_hour[:,0].mean()/1000-q.ccgt_electric_GWh)<1e-4
    assert abs(ccgt_hour[:,1].mean()/1000-q.CCGT_fuel_thermal_GWh)<1e-4
    # Simultaneous low-temperature heat uses for on-site greenhouse/aquaculture;
    # heat recovery fractions and local heat demand are *assumed*, not site-verified.
    chp=[]; annual_chp=[]
    for mode,recovery_fraction,local_mw in [('limited',.30,40),('central',.50,100),('high_match',.65,180)]:
        for yr in years:
            z=base_by_year[yr]
            recovered=np.minimum(z['residual']*recovery_fraction,local_mw)
            useful_th=recovered.sum()
            fuel_th=z['cc_fuel'].sum()
            el=z['cc'].sum()
            annual_chp.append({'year':yr,'case':mode,'ccgt_electric_GWh':el/1000,
                'fuel_input_GWh_LHV':fuel_th/1000,'post_steam_residual_GWh':z['residual'].sum()/1000,
                'matched_direct_heat_GWh':useful_th/1000,'electrical_efficiency_pct':100*el/fuel_th,
                'total_chp_efficiency_pct':100*(el+useful_th)/fuel_th,
                'heat_outlet_suitability':'low-grade greenhouse/aquaculture only; temperature/exergy unverified'})
        d=pd.DataFrame([a for a in annual_chp if a['case']==mode])
        qth=d.matched_direct_heat_GWh.mean()*1000
        # $0-20/MWhth heat sales are sensitivity only; no heat contracts secured.
        exchanger_capex=local_mw*1000*400
        annual_fixed=exchanger_capex*ANNUITY+exchanger_capex*.025
        pumping_cost=3.0*qth
        chp.append({'case':mode,'recoverable_fraction_of_post_steam_residual':recovery_fraction,
            'co_located_heat_demand_cap_MWth':local_mw,'annual_useful_heat_GWh':qth/1000,
            'electric_efficiency_pct':100*ccgt_hour[:,0].mean()/ccgt_hour[:,1].mean(),
            'combined_electric_plus_thermal_efficiency_pct':d.total_chp_efficiency_pct.mean(),
            'net_annual_margins_mCAD_at_heat_tariff_10':(10*qth-annual_fixed-pumping_cost)/1e6,
            'net_annual_margins_mCAD_at_heat_tariff_20':(20*qth-annual_fixed-pumping_cost)/1e6,
            'break_even_heat_tariff_cad_mwhth':(annual_fixed+pumping_cost)/qth})
    pd.DataFrame(chp).to_csv(OUTPUT/'chp_heat_recovery_scenarios.csv',index=False,float_format='%.7f')
    pd.DataFrame(annual_chp).to_csv(OUTPUT/'chp_annual_16year.csv',index=False,float_format='%.7f')
    # High-grade saturated/process steam extraction screen. Steam extraction from
    # the HRSG/steam turbine lowers electric output; the displaced electricity is
    # re-supplied using the same grid/HVO dispatch and is NOT granted free.
    # This differs from low-temperature heat recovery after the steam cycle.
    steam_cases=[]
    for steam_penalty in [.08,.12,.16]:
        annual=[]
        for yr,g in df.groupby('year',sort=True):
            z=base_by_year[int(yr)]
            # Limit extraction to 60 MWth while there is a running CCGT block,
            # and to 0.4 MWth per MWe being produced as a thermal feasibility screen.
            steam_th=np.minimum(60.,.40*z['cc'])
            make_up_el=steam_penalty*steam_th
            h,b,im,ex=simulate_year(g,make_up_el)
            incremental_cash=((im-z['imp'])*z['price_in']-(ex-z['ex'])*z['price_out']).sum()+\
                (h-z['hvo']).sum()*3600/(ENGINE_EFF*MJ_L_HVO)*HVO_PRICE
            annual.append({'year':yr,'useful_steam_GWh':steam_th.sum()/1000,
                'replacement_electricity_GWh':make_up_el.sum()/1000,
                'electricity_replacement_cash_CAD_M':incremental_cash/1e6})
        sub=pd.DataFrame(annual)
        q_steam=sub.useful_steam_GWh.mean()*1000
        # Steam extraction HX, steam distribution and traps, 25-yr levelised.
        steam_capex_CAD=60*1000*400
        annual_stress=sub.electricity_replacement_cash_CAD_M.mean()*1e6
        steam_network_cost=(steam_capex_CAD*ANNUITY+steam_capex_CAD*.03)+3*q_steam
        total=(steam_network_cost+annual_stress)/q_steam
        steam_cases.append({'electric_penalty_MWhe_per_MWhth':steam_penalty,
            'steam_demand_cap_MWth':60,'annual_useful_steam_GWh':q_steam/1000,
            'annual_replacement_electricity_GWh':sub.replacement_electricity_GWh.mean(),
            'all_in_heat_price_to_break_even_CAD_MWhth':total,
            'net_margin_at_35_CAD_m_yr':(35*q_steam-steam_network_cost-annual_stress)/1e6,
            'net_margin_at_50_CAD_m_yr':(50*q_steam-steam_network_cost-annual_stress)/1e6})
    pd.DataFrame(steam_cases).to_csv(OUTPUT/'steam_extraction_electric_penalty_screen.csv',index=False,float_format='%.7f')
    # 24-hour-capable new drying service, beyond 2.95-TWh/yr *existing* dryer model.
    # Temporal demand is 24-hour whenever contracted. Availability of process materials
    # is screened with weekly service uptime 75%, 95% or 100% (no inventory model).
    results=[]; selected_annual=[]
    for cap in [50,150,300]:
      for uptime in [.75,.95,1.0]:
       weekly=(np.arange(N)%168)<int(round(uptime*168))
       useful_q=cap*weekly.astype(float)
       for direct_fraction in [.25,.50,.75,1.0]:
        for cop in [2.5]:
          elec_add=useful_q*(1-direct_fraction)/cop+useful_q*.02 # fan/pump explicitly grid-dispatched
          source_heat=useful_q-elec_add+useful_q*.02 # fans do not count as thermal source
          assert source_heat.max() < IT_UNUSED_MWH_PER_HOUR
          year_rows=[]
          for yr,g in df.groupby('year',sort=True):
              v0=base_by_year[int(yr)];h,b,im,ex=simulate_year(g,elec_add)
              # opportunity-cost exact increment: 2026-forward scenarios inherit 2010-25 weather and prices
              price_in=v0['price_in'];price_out=v0['price_out']
              incremental_energy_CAD=((im-v0['imp'])*price_in-(ex-v0['ex'])*price_out).sum()
              incremental_fuel_CAD=(h-v0['hvo']).sum()*3600/(ENGINE_EFF*MJ_L_HVO)*HVO_PRICE
              q_mwh=useful_q.sum()
              year_rows.append({'year':int(yr),'annual_service_heat_MWh':q_mwh,
                'electricity_for_heat_pump_and_fans_MWh':elec_add.sum(),
                'additional_HVO_ML':(h-v0['hvo']).sum()*3600/(ENGINE_EFF*MJ_L_HVO)/1e6,
                'additional_grid_import_GWh':(im-v0['imp']).sum()/1000,
                'lost_exports_GWh':(v0['ex']-ex).sum()/1000,
                'additional_electricity_fuel_cash_CAD':incremental_energy_CAD+incremental_fuel_CAD})
          q_mwh=year_rows[0]['annual_service_heat_MWh'];d=pd.DataFrame(year_rows)
          incremental_cost=d.additional_electricity_fuel_cash_CAD.mean()
          for gas_name,rate in [('Fortis_Rate5_large_variable_only',GAS_FORTIS_RATE5_GJ),
                                ('Fortis_Rate3_commercial_variable_only',GAS_FORTIS_RATE3_GJ)]:
              costs=economically_compare(q_mwh,incremental_cost,cap,1-direct_fraction,25.,rate)
              results.append({'contract_capacity_MWth':cap,'service_uptime':uptime,
                  'low_temperature_direct_share':direct_fraction,'heat_pump_COP':cop,
                  'reference_gas_tariff':gas_name,'annual_delivery_GWh_th':q_mwh/1000,
                  'annual_heat_source_draw_GWh_th':source_heat.sum()/1000,
                  'annual_extra_electricity_GWh':elec_add.sum()/1000,
                  'mean_incr_grid_import_GWh':d.additional_grid_import_GWh.mean(),
                  'mean_foregone_export_GWh':d.lost_exports_GWh.mean(),
                  'mean_extra_HVO_ML':d.additional_HVO_ML.mean(),
                  'electricity_and_fuel_cost_per_heat_MWh_CAD':incremental_cost/q_mwh,
                  **costs})
          if cap==150 and uptime==.95 and direct_fraction==.75:
              selected_annual.extend(year_rows)
    pd.DataFrame(results).to_csv(OUTPUT/'continuous_drying_sensitivity.csv',index=False,float_format='%.7f')
    pd.DataFrame(selected_annual).to_csv(OUTPUT/'continuous_drying_annual_replay.csv',index=False,float_format='%.7f')
    central=pd.DataFrame(results)
    central=central[(central.contract_capacity_MWth==150)&(central.service_uptime==.95)&
                    (central.low_temperature_direct_share==.75)]
    rate5=central[central.reference_gas_tariff=='Fortis_Rate5_large_variable_only'].iloc[0]
    assert len(selected_annual)==16
    report={'method':'16x8760 hourly redispatch of the grid-connected 732 x 8 MW portfolio; 24-hour-capable drying added to existing 2.955-TWh/y heat contracts',
      'ccgt_MW':360,'ccgt_biomethane_share_of_fuel_input':.25,
      'ccgt_electrical_efficiency_percent':float(100*ccgt_hour[:,0].mean()/ccgt_hour[:,1].mean()),
      'ccgt_scenarios':chp,'high_temperature_steam_extraction':steam_cases,'baseline_utility_model_cost_CAD_MWh':BASE_COST_CAD_MWH,
      'continuous_dryer_central':rate5.to_dict(),
      'existing_heat_utilization_TWh_per_yr':HEAT['thermal_use_twh_per_year'],
      'existing_dryer_thermal_TWh_per_yr':HEAT['drying_heat_twh_per_year'],
      'unused_IT_heat_TWh_per_yr':HEAT['remaining_rejection_twh_per_year'],
      'heat_grade':'CCGT post-steam residual for 35–65 C greenhouse/aquaculture, IT return for direct low-temperature drying with electric heat pump for higher grade; no steam extraction credited for free',
      'site_level_allocation_not_established':True,'uncontracted_continuous_material_supply':True,
      'incremental_heat_pump_electricity_in_hourly_dispatch':True,
      'gas_rates':'FortisBC 2026 Rate 5/3 published variable charges, excluding fixed demand and taxes',
      'limits':['Thermal outlet temperatures and project siting assumed','Additional 150MW steady low-temperature IT heat sink is a deployment screen, not buyer commitments','COP=2.5 illustrative','Gas Rate 5 excludes demand charges; process capital and handling simplifications','Hourly power prices modeled, not observed or contracted','The CCGT heat may be elsewhere from proposed aquaculture/greenhouse sinks; no piping feasibility','Existing IT reject heat is treated as uniform hourly availability from annual model']}
    (OUTPUT/'CHP_CONTINUOUS_DRYING_RESULTS.json').write_text(json.dumps(report,indent=2)+'\n')
    (OUTPUT/'METHODS.md').write_text('''# CCGT cogeneration and continuous drying methods

Run: `python RESEARCH_CODE/GRID_CONNECTED_REOPT/ccgt_chp_drying24h.py` from repository root. Requires numpy, pandas and numba.

Existing 2.955 TWh/year drying and its 0.246 TWh electric boosters are already in the archived hourly load. Additional 50/150/300 MWth 24-hour capable contracts are tested at 75/95/100% operational duty. IT heat is allocated only from the previously rejected remainder, with 25/50/75/100% direct low-temperature use; the rest requires a COP 2.5 heat pump. Fan/pump load is 2% of thermal delivered and the electrical load is rerun through the 16-year grid/HVO dispatch, including forfeited exports.

360 MW CCGT is simulated from the same 2x180 MW block dispatch; heat is recovered only in hours units operate, never assumed baseload. Low-grade residual heat is capped by co-located greenhouse/aquaculture demand at 40/100/180 MWth and recovered 30/50/65%; no steam extraction beyond the steam cycle is credited for free. CHP total useful-energy efficiency = (net electric + matched useful heat)/thermal fuel LHV, not net electric efficiency.

Pricing from FortisBC business Rate 5 and Rate 3 published July 2026 variable components (C$4.614 and C$9.305 per GJ) with 82% burner/boiler efficiency. Fixed tariff demand charges, taxes, process transport, feedstock purchase, product handling, exact plant quotes and contracts are NOT included.

Sources: https://www.epa.gov/chp/methods-calculating-chp-efficiency ; https://www.fortisbc.com/accounts/billing-rates/natural-gas-rates/business-rates ; https://www.ornl.gov/publication/district-heating-utilizing-waste-heat-data-center-high-temperature-heat-pumps
''')
    print('CCGT CHP SUMMARY')
    print(pd.DataFrame(chp).round(3).to_string(index=False))
    print('STEAM EXTRACTION WITH ELECTRIC PENALTY')
    print(pd.DataFrame(steam_cases).round(3).to_string(index=False))
    print('DRYING 150 MW / 95%')
    print(pd.DataFrame(results).query('contract_capacity_MWth==150 and service_uptime==0.95')[['low_temperature_direct_share','reference_gas_tariff','system_unit_cost_cad_mwh_th','gas_unit_cost_cad_mwh_th','annual_profit_at_25cad_tariff_cad_m','annual_profit_at_35cad_tariff_cad_m']].round(3).to_string(index=False))
    print('ALL CHECKS PASSED')

if __name__=='__main__':main()
