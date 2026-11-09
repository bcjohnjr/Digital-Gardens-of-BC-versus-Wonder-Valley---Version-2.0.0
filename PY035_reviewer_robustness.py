#!/usr/bin/env python3
"""Independent release stress tests of saved 8/10 MW alternatives.

Not a wind-farm micro-siting study or AC power-flow: deratings are illustrative
system-level transfer/availability losses. Fixed portfolios; no re-optimization.
Engineering assumptions and public data limitations disclosed in output.
"""
from pathlib import Path
import json,csv,sys,copy,math
import numpy as np
BASE=Path(__file__).resolve().parent
sys.path.insert(0,str(BASE/'LARGE_TURBINE_STUDY'))
from model_8mw_10mw import build_inputs,run_case_fast
import storage_fuel_sweetspot as sf
OUT=BASE/'OUTPUT'/'REVIEWER_SENSITIVITY';OUT.mkdir(parents=True,exist_ok=True)
INPUT=BASE/'LARGE_TURBINE_STUDY'/'OUTPUT'


def pv_cost_horizon(c,horizon=25,option='none',extra_wind_fraction=.0):
    """Same disclosed financing/cost accounting as sf.cost_25y, but correct wind life.
    Treat wind-year-21 expenditure as incremental cash cost, not re-financed debt.
    20-year case excludes all cash flows from year 21 onward; losses no salvage.
    25-year extension is conditional on engineering certification and upkeep.
    25-year repower scenario charges 80% of current wind capex in year 21.
    """
    p=sf.P; r=p['finance_rate'];wf=c['wind_gw'];solar=c['solar_gw'];batt=c['battery_gwh'];st=c['stats']
    wind_capex=wf*p['capex_wind_bn_gw']
    fixedcapex=wind_capex+solar*p['capex_solar_bn_gw']+batt*p['capex_batt_bn_gwh']+p['capex_network_engines_bn']
    tanks=st['hvo_ml_max']*1e3*p['tank_cad_per_m3']/1e9
    annual_debt=(fixedcapex+tanks)*sf.crf(r,p['finance_years'])
    om=wf*p['om_wind_bn_gw']+solar*p['om_solar_bn_gw']+batt*p['om_batt_bn_gwh']+p['om_engines_bn']+tanks*p['tank_om_frac']
    fuel=st['hvo_ml_mean']*1e6*p['hvo_cad_l']/1e9+p['b100_bn']
    carry=.5*st['hvo_ml_max']*1e6*p['hvo_cad_l']*p['inventory_carry_rate']/1e9
    battery_repl=batt*p['capex_batt_bn_gwh']*p['battery_replacement_cost_fraction']
    arr=[]
    for y in range(1,horizon+1):
        annual=om+fuel+carry+(annual_debt if y<=p['finance_years'] else 0)
        if y==p['battery_life']: annual+=battery_repl
        if y==21: annual+=extra_wind_fraction*wind_capex
        arr.append(annual)
    pv=sum(x/(1+r)**i for i,x in enumerate(arr,1))
    pv_load=sum(st['load_twh']*1e6/(1+r)**i for i in range(1,horizon+1))
    return dict(horizon_years=horizon,scenario=option,year_21_wind_investment_bn=extra_wind_fraction*wind_capex,
                wind_capex_original_bn=wind_capex,lcoe_cad_per_mwh=pv*1e9/pv_load,
                delta_from_archived_25yr_cad_mwh=pv*1e9/pv_load-c['cost']['lcoe_25y_cad_mwh'])


def stat_row(model,label,x,W,S,H,L,price=1.8,meta=''):
    raw=run_case_fast(np.array(x,dtype=np.float64),W,S,H,L)
    st=dict(hvo_ml_mean=float(raw[0]),hvo_ml_max=float(raw[1]),gas_gwh_max=float(raw[2]),
            unserved_gwh_max=float(raw[3]),gen_twh=float(raw[4]),load_twh=float(raw[5]),curtail_twh=float(raw[6]))
    c=sf.cost_25y(float(sum(x[:5])),float(x[5]),float(x[6]),st,float(x[7]))
    price_delta=(price-sf.P['hvo_cad_l'])*(st['hvo_ml_mean']*1e6 + .5*st['hvo_ml_max']*1e6*sf.P['inventory_carry_rate'])
    factor=sum(1/(1+sf.P['finance_rate'])**i for i in range(1,26))
    pvden=st['load_twh']*1e6*factor
    return dict(turbine=model,scenario=label,hvo_limit_ml=x[7],hvo_price_cad_l=price,
                hvo_mean_ml=st['hvo_ml_mean'],hvo_max_ml=st['hvo_ml_max'],
                gas_worst_year_gwh=st['gas_gwh_max'],unserved_worst_year_gwh=st['unserved_gwh_max'],
                cost_cad_mwh_unpriced_emergency_gas=c['lcoe_25y_cad_mwh']+price_delta*factor/pvden,notes=meta)

rows=[];life=[]
for name in ('SANY_SI19580_8MW','SANY_SI230100_10MW'):
    d=json.loads((INPUT/(name+'_optimization.json')).read_text()); c=d['candidate']
    x=np.array(list(c['wind_gw_by_site'].values())+[c['solar_gw'],c['battery_gwh'],c['fuel_cap_ml']],dtype=float)
    # The published 25-year number assumes wind machines survive past stated 20-year design life without expense.
    for yrs,typ,f in [(20,'20yr_base_service_life',0),(25,'25yr_certified_extension_at_10pct_wind_capex',.10),(25,'25yr_certified_extension_at_20pct_wind_capex',.20),(25,'25yr_repower_at_80pct_wind_capex',.80),(25,'25yr_repower_at_100pct_wind_capex',1.0)]:
        life.append(dict(turbine=name,**pv_cost_horizon(c,yrs,typ,f)))
    _,W,S,H,L,_=build_inputs(name,cf_ceiling=.4)
    rows.append(stat_row(name,'baseline_GWA40',x,W,S,H,L,meta='Optimistic copper-plate / pooled generation; zero network bottlenecks'))
    for haircut in (.02,.05,.10):
        # Screen extra delivered renewable derating to represent losses/congestion, NOT a network flow model.
        rows.append(stat_row(name,f'pooled_renewable_deliverability_minus_{int(haircut*100)}pct',x,W*(1-haircut),S*(1-haircut),H,L,meta='Illustrative loss/curtailment imposed on renewables only; no topology or contingency validated'))
    for fuelcap in (500.,750.,900.):
        xx=x.copy();xx[7]=fuelcap
        rows.append(stat_row(name,f'fuel_available_{int(fuelcap)}ML_per_yr',xx,W,S,H,L,meta='Annual fuel ceiling; does not simulate truck or winter inventory logistics'))
    for price in (2.25,2.75,3.50):
        rows.append(stat_row(name,f'HVO_delivered_price_{price:.2f}_CAD_L',x,W,S,H,L,price=price,meta='HVO price sensitivity, same hourly dispatch; no optimization'))
    for lower in (.90,.85,.80):
        _,Ww,Sw,Hw,Lw,_=build_inputs(name,cf_ceiling=.4,wind_mean_multiplier=lower)
        rows.append(stat_row(name,f'GWA_means_{int(lower*100)}pct',x,Ww,Sw,Hw,Lw,meta='Common-mode site-mean reduction; captures correlated resource risk, not observed spatial chronology'))

# Explicit rated-wind-speed uncertainty where manufacturer language variants differ.
rated_rows=[]
for name in ('SANY_SI19580_8MW','SANY_SI230100_10MW'):
    d=json.loads((INPUT/(name+'_optimization.json')).read_text());c=d['candidate']
    x=np.array(list(c['wind_gw_by_site'].values())+[c['solar_gw'],c['battery_gwh'],c['fuel_cap_ml']],dtype=float)
    for rated in ((11.0,11.5,12.0) if '8MW' in name else (10.5,11.0,11.5,12.0)):
        _,W,S,H,L,_=build_inputs(name,cf_ceiling=.4,rated_override=rated)
        z=run_case_fast(x,W,S,H,L)
        rated_rows.append(dict(turbine=name,assumed_rated_wind_speed_ms=rated,mean_hvo_ml=float(z[0]),worst_year_hvo_ml=float(z[1]),worst_year_emergency_gas_gwh=float(z[2]),
        comment='Engineering curve and same installed portfolio, GWA site CF screen re-applied; not a manufacturer-certified hourly power curve'))
with (OUT/'rated_wind_speed_sensitivity.csv').open('w',newline='',encoding='utf8') as f:
    w=csv.DictWriter(f,fieldnames=list(rated_rows[0]));w.writeheader();w.writerows(rated_rows)

for filename,data in [('turbine_service_life_scenarios.csv',life),('fixed_portfolio_stress_tests.csv',rows)]:
    with (OUT/filename).open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
(OUT/'SENSITIVITY_README.md').write_text('''# Referee stress-test methods and limits\n\nThese scripts do not independently establish wind generation, physical grid deliverability or renewable diesel availability. They are deterministic counterfactuals on the *same fixed 8 MW and 10 MW portfolios*.\n\nTurbine-life cases compare a 20-year horizon (consistent with reported turbine design life) and 25-year horizons requiring either a hypothetical life-extension budget (10%/20% of original wind turbine capital, paid at year 21) or an illustrative repowering budget (80%/100% of original wind capital at year 21). No terminal asset salvage value is assigned. Costs use the original 6% financial discount rate, 20-year capital repayment, year-15 battery replacement, and unchanged operating outputs. Extended operation and repowering require certifications and downtime assessment.\n\nThe renewable-deliverability stress is a uniform 2%/5%/10% reduction in modeled wind/solar delivered to the pooled load. It is **not an AC/DC power flow**; there are no line coordinates, ratings, protection systems, or node injections. Hence it cannot test N-1 contingencies or establish individual data-centre reliability. The zero-gas original result must be described as an idealized unconstrained-network case.\n\nFuel volume sensitivities 500/750/900 ML per year impose annual HVO ceilings; delivery price sensitivities C$2.25/2.75/3.50 per litre change costs for the original dispatch only. Neither certifies procurement or winter inventory. GWA site mean deratings of 10%/15%/20% are common-mode statistical stresses, not spatially resolved micrositing.\n\nThe original installed turbine counts are upward rounded by site; continuously optimized MW rather than integer builds were used for annual energy and costs. Actual turbine multiples require integer replanning.\n\nTo reproduce: run `python RESEARCH_CODE/reviewer_robustness.py` from the submission archive root. Requires same numpy/scipy/numba/etc as model_8mw_10mw.py.\n''',encoding='utf8')
print('LIFE CASES')
for l in life:print(l['turbine'][-3:],l['scenario'],round(l['lcoe_cad_per_mwh'],2))
print('STRESS CASES')
for r in rows:print(r['turbine'][-3:],r['scenario'],round(r['gas_worst_year_gwh'],1),round(r['cost_cad_mwh_unpriced_emergency_gas'],2))
