#!/usr/bin/env python3
"""Reproducible incremental CCGT / upgraded-biomethane / HVO screen.

This is NOT an OEM fuel-certification study or a redesigned AC transmission plan.
The 17-site 2010-2025 pooled dispatch is reproduced and its engine energy is
reallocated to modular CCGT blocks WITHOUT assuming that certified 64% H-class
performance transfers to HVO/biomethane, partial load, or frequent startup.

Uses the exact saved hourly generation, load, booster and import/export prices.
Preserves the original battery->grid->B100->HVO dispatch priority. For the incremental
screen any B100 remains on the reciprocating engine: remaining engine load may be
served by CCGT, with legacy engine serving residual/low-load hours.
"""
from pathlib import Path
import csv,json, math
import numpy as np
import pandas as pd
from numba import njit

HERE=Path(__file__).resolve().parent
SRC=HERE/'hourly_input_reoptimized.csv.gz'
OUT=HERE/'CCGT_BIOMETHANE_HVO'
OUT.mkdir(exist_ok=True)

# Physical LHV fuel basis -- do not use HHV-based nameplate efficiency here.
MJ_L_HVO=36.51
MJ_L_FAME=33.3
MJ_NM3_CH4=35.8
ENGINE_EFF=.54
HVO_CAD_L=1.80
BIOMETHANE_CAD_GJ=20.0 # Illustrative delivered upgraded gas, not a contract
FAME_UCO_CAD_L=0.90 # Paid for raw cooking oil, assumed not an established market quote
FAME_PROC_CAD_L=0.65 # Per litre FAME, inclusive of transport/upgrading allowance
FAME_YIELD_L_L=.88
CCGT_FULL_EFF_LHV=.60 # Only full-load gas-fired units can have this efficiency as screened
CCGT_PART_EFF_LHV=.53
CCGT_CYCLE_FACTOR=.985
CCGT_MIN_LOADING=.40
UNIT_MW=180.0
CCGT_CAPEX_CAD_KW=2900.0 # Screening new construction (BC siting unpriced)
ENGINE_DISPLACED_CAD_KW=1600.0 # Assumed existing engine capital within fixed network+engines account
CCGT_FIXED_OM_PREMIUM_CAD_KW_YR=10.0
CCGT_EXTRA_VAR_OM_CAD_MWH=3.0
CCGT_START_CAD=2500.0
R=0.085
BASELINE_COST_CAD_MWH=191.50207750263417
ANNUAL_LOAD_TWH=36.00486
YEARS=25
ANN=R/(1-(1+R)**(-YEARS))

@njit(cache=True)
def calc_engine_hourly(gen,load,boost,year_idx):
    # same dispatch priority as reoptimize_grid.py
    n=len(gen);hvo=np.zeros(n,dtype=np.float64);b100=np.zeros(n,dtype=np.float64)
    grid=np.zeros(n,dtype=np.float64);exports=np.zeros(n,dtype=np.float64)
    soc=3132.9541684394684*.5;cap=3132.9541684394684;pmax=cap/8.
    b100_remaining=20e6*.90*35.4/3600*.54
    for i in range(n):
        ld=load[i]+boost[i]
        d=gen[i]-ld
        if d>=0:
            ch=min(d,pmax,max(0.,(cap-soc)/.94));soc+=ch*.94
            exports[i]=min(d-ch,3000.)
        else:
            d=-d
            dis=min(d,pmax,soc*.94);soc-=dis/.94;d-=dis
            im=min(d,2500.);grid[i]=im;d-=im
            engine=min(d,5100.)
            b=min(engine,b100_remaining);b100_remaining-=b;engine-=b;b100[i]=b
            hvo[i]=engine # original central case has no gas and no unserved
            if d>5100.+.01:raise ValueError('Unavailable backup engine power')
    return hvo,b100,grid,exports

@njit(cache=True)
def ccgt_split(engine_hvo,modules,full_eff,part_eff):
    # 180 MW discrete combined-cycle blocks. Last block must reach 40% nameplate.
    # All thermal efficiencies derated 1.5% for cycling/temperature as scenario.
    ccgt=np.zeros_like(engine_hvo);cons_mwh_fuel=0.;starts=0
    previous=0
    minoutput=UNIT_MW*CCGT_MIN_LOADING
    for i in range(len(engine_hvo)):
        required=engine_hvo[i]
        nfull=int(min(required//UNIT_MW,modules))
        rem=required-nfull*UNIT_MW
        npart=1 if nfull<modules and rem>=minoutput else 0
        count=nfull+npart
        if count>previous: starts+=count-previous
        previous=count
        power=nfull*UNIT_MW+(rem if npart else 0.)
        if power>required+1e-8:raise ValueError('Over-generation')
        ccgt[i]=power
        if power:
            cons_mwh_fuel+=nfull*UNIT_MW/(full_eff*CCGT_CYCLE_FACTOR)
            if npart:
                frac=rem/UNIT_MW
                efficiency=part_eff+(full_eff-part_eff)*(frac-CCGT_MIN_LOADING)/(1-CCGT_MIN_LOADING)
                cons_mwh_fuel+=rem/(efficiency*CCGT_CYCLE_FACTOR)
    return ccgt,cons_mwh_fuel,starts

def main():
    df=pd.read_csv(SRC)
    required={'year','hour','generation_MW','facility_load_MW','drying_booster_load_MW'}
    assert required.issubset(df.columns)
    assert len(df)==16*8760 and df.year.nunique()==16
    all_hvo=[];annual=[]; annual_hvo_l=[]; q_by_year={}
    for year,group in df.groupby('year',sort=True):
        h,b,im,ex=calc_engine_hourly(group.generation_MW.to_numpy(),group.facility_load_MW.to_numpy(),group.drying_booster_load_MW.to_numpy(),year)
        annual.append({'year':int(year),'hvo_ML':h.sum()*3600/ENGINE_EFF/MJ_L_HVO/1e6,
                       'hvo_GWh':h.sum()/1000, 'b100_GWh':b.sum()/1000,
                       'grid_import_TWh':im.sum()/1e6,'grid_export_TWh':ex.sum()/1e6,
                       'max_engine_demand_MW':h.max(),'hours_with_engine':int((h>.01).sum())})
        q_by_year[int(year)]=h
    tab=pd.DataFrame(annual)
    # Strict reproduction of the selected reference HVO and energy ledger.
    obs=pd.read_csv(HERE/'reoptimized_annual.csv')
    chk=tab.merge(obs,on='year',suffixes=('_calc','_archive'))
    assert max(abs(chk.hvo_ML_calc-chk.hvo_ML_archive))<1e-3,(chk.hvo_ML_calc-chk.hvo_ML_archive).describe()
    assert max(abs(chk.grid_import_TWh_calc-chk.grid_import_TWh_archive))<1e-5
    assert max(abs(chk.grid_export_TWh_calc-chk.grid_export_TWh_archive))<1e-5
    tab.to_csv(OUT/'reproduced_original_engine_schedule_annual.csv',index=False)
    print('REPRO baseline HVO',round(tab.hvo_ML.mean(),3),'ML/y, peak engine',round(tab.max_engine_demand_MW.max(),1),'MW')
    # Competing new-build arrangements. 0 = no CCGT; each block a 180 MW 2x1-like plant.
    # Prices are transparent hypotheses; biomethane procurement is unproven.
    rows=[]; peryear=[]
    for blocks in [0,2,4,8,16,28]:
      for eff_case,eff_full,eff_part in [('conservative',.56,.49),('screening',.60,.53),('nameplate_upper',.64,.56)]:
        if blocks==0 and eff_case!='screening':continue
        for gas_share in ([0.] if blocks==0 else [0.,.10,.25]):
          for fname,fame_frac in [('HVO_only',0.),('B05_engine',.05),('B20_engine_conditional',.20)]:
            # FAME applies ONLY to OEM-authorized conventional engines, not to CCGT.
            c_e=0.;c_f=0.;c_st=0;c_eng=0.;m_hvo=0.;m_fame=0.;m_biogas=0.;m_water_m3=0.
            last_eng=0
            for yr,h in q_by_year.items():
                cc,ein,starts=ccgt_split(h,blocks,eff_full,eff_part)
                engine_energy=h.sum()-cc.sum()
                cc_hvo_mwh=ein*(1-gas_share)
                cc_gas_mwh=ein*gas_share
                eng_fuel_mwh=engine_energy/ENGINE_EFF
                fame_fuel_mwh=eng_fuel_mwh*fame_frac
                engine_hvo_fuel_mwh=eng_fuel_mwh*(1-fame_frac)
                # Liquid fuel and gas fuel are measured on thermal LHV basis.
                hvol=(cc_hvo_mwh+engine_hvo_fuel_mwh)*3600/MJ_L_HVO
                famel=fame_fuel_mwh*3600/MJ_L_FAME
                gasnm3=cc_gas_mwh*3600/MJ_NM3_CH4
                _c_f=hvol*HVO_CAD_L+famel*(FAME_UCO_CAD_L/FAME_YIELD_L_L+FAME_PROC_CAD_L)+cc_gas_mwh*3.6*BIOMETHANE_CAD_GJ
                _c_o=cc.sum()*CCGT_EXTRA_VAR_OM_CAD_MWH+starts*CCGT_START_CAD
                # One part of leftover fuel thermal becomes heat to be rejected; no credit to IT heat.
                thermal_reject_mwh=max(ein-cc.sum(),0.)
                # illustrative condenser load 45% of net residual energy, ΔT=5K, ρ water~1000 kg/m3
                condenser_mwh=.45*thermal_reject_mwh
                water_m3=condenser_mwh*3600/(4.186*5.)
                peryear.append({'year':yr,'ccgt_blocks':blocks,'ccgt_MW':blocks*UNIT_MW,'efficiency_case':eff_case,
                  'biomethane_thermal_share':gas_share,'legacy_engine_fame_share':fame_frac,
                  'ccgt_electric_GWh':cc.sum()/1000.,'legacy_engine_electric_GWh':engine_energy/1000.,
                  'HVO_ML':hvol/1e6,'FAME_ML':famel/1e6,'paid_UCO_ML':famel/FAME_YIELD_L_L/1e6,
                  'biomethane_million_Nm3':gasnm3/1e6,'CCGT_fuel_thermal_GWh':ein/1000.,
                  'CCGT_reject_thermal_GWh':thermal_reject_mwh/1000.,'condenser_screen_million_m3':water_m3/1e6,
                  'CCGT_starts':starts,'fuel_cost_CAD_M':_c_f/1e6,'CCGT_extra_var_om_CAD_M':_c_o/1e6})
            choices=[r for r in peryear if r['ccgt_blocks']==blocks and r['efficiency_case']==eff_case and r['biomethane_thermal_share']==gas_share and r['legacy_engine_fame_share']==fame_frac]
            assert len(choices)==16
            avg={k:float(np.mean([r[k] for r in choices])) for k in ['ccgt_electric_GWh','legacy_engine_electric_GWh','HVO_ML','FAME_ML','paid_UCO_ML','biomethane_million_Nm3','CCGT_fuel_thermal_GWh','CCGT_reject_thermal_GWh','condenser_screen_million_m3','CCGT_starts','fuel_cost_CAD_M','CCGT_extra_var_om_CAD_M']}
            increment_capex=(CCGT_CAPEX_CAD_KW-ENGINE_DISPLACED_CAD_KW)*blocks*UNIT_MW*1000.
            incremental_fom=CCGT_FIXED_OM_PREMIUM_CAD_KW_YR*blocks*UNIT_MW*1000.
            ref_hvo_cost=tab.hvo_ML.mean()*1e6*HVO_CAD_L
            annual_delta=avg['fuel_cost_CAD_M']*1e6-ref_hvo_cost+avg['CCGT_extra_var_om_CAD_M']*1e6+increment_capex*ANN+incremental_fom
            # Annual cashflow delta is levelised across baseline annual campus load.
            new_c=BASELINE_COST_CAD_MWH+annual_delta/(ANNUAL_LOAD_TWH*1e6)
            rows.append({'ccgt_blocks':blocks,'ccgt_MW':blocks*UNIT_MW,'efficiency_case':eff_case,'biomethane_thermal_share':gas_share,
               'legacy_engine_fame_share':fame_frac,'case':fname,**avg,
               'net_incremental_capex_CAD_bn':increment_capex/1e9,
               'levelised_total_CAD_MWh':new_c,'delta_CAD_MWh':annual_delta/(ANNUAL_LOAD_TWH*1e6)})
    result=pd.DataFrame(rows)
    result.to_csv(OUT/'combined_cycle_options_16yr.csv',index=False,float_format='%.8f')
    pd.DataFrame(peryear).to_csv(OUT/'combined_cycle_annual_replay.csv',index=False,float_format='%.8f')
    # explicitly bound FAME possible supply and costs; no invented site-specific oil quantity.
    result['liquid_fuel_thermal_GWh']=(result.HVO_ML*1e6*MJ_L_HVO +result.FAME_ML*1e6*MJ_L_FAME)/3.6e6
    selected=result[(result.ccgt_MW.isin([0,360,720,1440])) & (result.efficiency_case=='screening') & (result.case=='HVO_only') & (result.biomethane_thermal_share.isin([0,.10]))].copy()
    selected.to_csv(OUT/'ccgt_main_comparison.csv',index=False,float_format='%.7f')
    base=result[(result.ccgt_MW==0)&(result.case=='HVO_only')].iloc[0]
    assert abs(base.HVO_ML-tab.hvo_ML.mean())<.001
    assert abs(base.levelised_total_CAD_MWh-BASELINE_COST_CAD_MWH)<1e-6
    # Analytical water requirement for condenser: flow @ 5K, not discharge authorization.
    res={'source':'Hourly 16-year redispatch of archived selected wind/solar/battery build; includes drying booster',
    'baseline':{'HVO_ML_yr':float(tab.hvo_ML.mean()),'HVO_cost_CAD_M_yr':float(ref_hvo_cost/1e6), 'LCOE_CAD_MWh':BASELINE_COST_CAD_MWH,
                'original_engine_efficiency_LHV':ENGINE_EFF,'back_up_output_GWh_yr':float(tab.hvo_GWh.mean())},
    'method':'Discrete 180-MW modular CCGT operating for residual engine HVO load; legacy engine covers small/peak demands; dispatch priority unchanged',
    'assumptions':{'CCGT_gas_rated_net_efficiency_full_load_LHV':CCGT_FULL_EFF_LHV,
                   'CCGT_full_load_screen_thermal_efficiency_after_cycle_factor':CCGT_FULL_EFF_LHV*CCGT_CYCLE_FACTOR,
                   'CCGT_part_load_minimum':CCGT_MIN_LOADING,'cycle_factor':CCGT_CYCLE_FACTOR,
                   'HVO_price_CAD_per_litre':HVO_CAD_L,'upgraded_biomethane_CAD_per_GJ_LHV':BIOMETHANE_CAD_GJ,
                   'used_cooking_oil_purchase_CAD_per_litre_raw':FAME_UCO_CAD_L,
                   'FAME_processing_and_logistics_CAD_per_litre_finished':FAME_PROC_CAD_L,
                   'FAME_volume_yield':FAME_YIELD_L_L,
                   'FAME_allowed_only_in_separately_certified_reciprocating_engines':True,
                   'displaced_engine_capex_CAD_per_kW_assumed':ENGINE_DISPLACED_CAD_KW,
                   'ccgt_capex_CAD_per_kW_assumed':CCGT_CAPEX_CAD_KW,
                   'incremental_ccgt_capex_excludes_actual_transmission_water_permits':True,
                   'river_water_withdrawal_not_automatic':True,
                   'condenser_fraction_of_CC_residual_heat':.45,'once_through_temperature_rise_K':5.,
                   'high_64pct_case_not_verified_for_HVO_gas_or_cycling':True},
    'sources':['Siemens Energy: Combined Cycle Power Plants','Siemens Energy: Sustainable Alternative Fuels','Siemens Energy: SGT-800','IEA AMF: FAME Compatibility','US DOE NETL 2025 CCGT performance baseline'],
    'caveat':'No fuel blending/OEM approval, biomass purchase agreement, freshwater permit, reactive delivery, steam-cycle siting or verified heat contract established.'}
    (OUT/'combined_cycle_assumptions_and_results.json').write_text(json.dumps(res,indent=2))
    # Delivered fuel price and upstream-carbon intensity screens (no contracts assumed).
    r360=result[(result.ccgt_MW==360)&(result.efficiency_case=='screening')&(result.biomethane_thermal_share==.25)&(result.legacy_engine_fame_share==0)].iloc[0]
    r360_fame=result[(result.ccgt_MW==360)&(result.efficiency_case=='screening')&(result.biomethane_thermal_share==.25)&(result.legacy_engine_fame_share==.20)].iloc[0]
    sensitivity=[]
    for gasprice in [12,15,20,25,30,40]:
      for raw_oil in [.30,.60,.90,1.20]:
        for case,rr in [('CCGT360_25pct_RNG_HVO',r360),('CCGT360_25pct_RNG_B20_on_engines',r360_fame)]:
          delta=(rr.biomethane_million_Nm3*1e6*MJ_NM3_CH4/1000.*(gasprice-BIOMETHANE_CAD_GJ)
                  +rr.paid_UCO_ML*1e6*(raw_oil-FAME_UCO_CAD_L))
          sensitivity.append({'variant':case,'biomethane_CAD_GJ':gasprice,'raw_UCO_price_CAD_L':raw_oil,
                             'HVO_ML':rr.HVO_ML,'biomethane_million_Nm3':rr.biomethane_million_Nm3,
                             'raw_UCO_ML':rr.paid_UCO_ML,'cost_CAD_MWh':rr.levelised_total_CAD_MWh+delta/(ANNUAL_LOAD_TWH*1e6)})
    pd.DataFrame(sensitivity).to_csv(OUT/'fuel_price_paid_oil_sensitivity.csv',index=False,float_format='%.6f')
    upstream=[]
    for case,rr in [('engine_existing',base),('CCGT360_HVO_only',result[(result.ccgt_MW==360)&(result.efficiency_case=='screening')&(result.biomethane_thermal_share==0)&(result.legacy_engine_fame_share==0)].iloc[0]),('CCGT360_biomethane25',r360),('CCGT360_biomethane25_B20engines',r360_fame)]:
      a=rr.HVO_ML*1e6*MJ_L_HVO*25/1e12
      b=rr.biomethane_million_Nm3*1e6*MJ_NM3_CH4*15/1e12
      c=rr.FAME_ML*1e6*MJ_L_FAME*35/1e12
      upstream.append(dict(scenario=case,HVO_upstream_illustrative_MtCO2e=a,biomethane_upstream_illustrative_MtCO2e=b,FAME_upstream_illustrative_MtCO2e=c,sum_illustrative_MtCO2e=a+b+c))
    pd.DataFrame(upstream).to_csv(OUT/'fuel_carbon_intensity_sensitivity.csv',index=False,float_format='%.8f')

    print(selected[['ccgt_MW','biomethane_thermal_share','HVO_ML','biomethane_million_Nm3','levelised_total_CAD_MWh','ccgt_electric_GWh']].round(2).to_string(index=False))

if __name__=='__main__':main()
