#!/usr/bin/env python3
"""Connected dispatch / industrial drying / GPU NPV reconciliation.

Industrial drying booster electricity is included in hourly electricity demand. It is not
simultaneously credited as free curtailed electricity or as grid export. Profitability is
recomputed using the new 25-year electricity cost path and matched gas-comparator GPU
cash flows (not a proportional premium). Site heat is unchanged with fixed IT load.
"""
from pathlib import Path
import sys,json,csv
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parent
RC=ROOT.parent
sys.path[:0]=[str(ROOT),str(RC),str(RC/'MODEL_CORE'),str(RC/'LARGE_TURBINE_STUDY')]
import reoptimize_grid as opt
import industrial_drying as dry
import profit_community_model as pcm
import storage_fuel_sweetspot as sf
from model_8mw_10mw import build_inputs

def make_booster():
    temperatures=pcm.load_temps()
    heat,served,months,_=dry.base_heat(temperatures)
    # All physically supplied dryer boosters pay an explicit opportunity cost.
    # No boosted-load schedule is tied to fictitious curtailment after energy has been exported.
    dry.PRICE['schedule_boost_to_curtailment']=False
    dry.PRICE['electricity_cad_mwh']=json.loads((ROOT/'reoptimized_grid_case.json').read_text())['selected_case']['total_CAD_MWh']
    rows,remaining,el=dry.run_drying(heat,months,np.zeros(len(months)),dry.MARKETS)
    booster=np.zeros(len(months))
    for r in rows:
        booster+=r['hourly']*r['boost_share']/(dry.PRICE['booster_cop']-r['boost_share'])
    assert np.isclose(booster.sum()/(len(months)/8760)/1e6,el['el_twh'])
    np.save(ROOT/'dryer_booster_hourly_MWh.npy',booster.reshape(-1,8760))
    ec=dry.economics(rows,el)
    ny=len(months)/8760
    loop=(served['homes']+served['digester']+served['aqua'])/ny/1e6 + sum(r['loop_heat_twh'] for r in rows)
    recover=pcm.IT_TWH*pcm.PARAM['heat']['recoverable_heat_share_it']
    heat_summary={'thermal_use_twh_per_year':loop,'thermal_utilization_pct':loop/recover*100,
       'drying_heat_twh_per_year':ec['heat_twh'],'drying_electric_booster_twh_per_year':el['el_twh'],
       'drying_capex_CAD_bn':ec['capex_bn'],'drying_margin_CAD_m_yr':ec['margin_m_cad_mean'],
       'dryer_water_removed_mt_per_year':ec['water_mt'], 'remaining_rejection_twh_per_year':sum(x.sum() for x in remaining.values())/ny/1e6,
       'dryers_assumed_contracts':len(rows),'emissions_fossil_drying_displaced_t':ec['ghg_reduction_t'],
       'electricity_no_free_curtail_claim':True}
    (ROOT/'heat_reconciled.json').write_text(json.dumps(heat_summary,indent=2)+'\n')
    pd.DataFrame([{k:v for k,v in r.items() if k not in ['hourly']} for r in rows]).to_csv(ROOT/'drying_hourly_reconciled_markets.csv',index=False)
    return booster.reshape(-1,8760),heat_summary,ec

def run():
    booster,heats,ec=make_booster()
    d=json.loads((ROOT/'reoptimized_grid_case.json').read_text());
    groups,W,S,H,L,_=build_inputs('SANY_SI19580_8MW',.4)
    a,b=opt.make_prices(groups,S,'hourly_scarcity')
    x=np.asarray([d['wind_capacity_GW_by_site'][k] for k in d['wind_capacity_GW_by_site']]+[d['solar_GW'],d['battery_GWh']])
    pre=opt.evaluate_all(x,W,S,H,L,a,b,np.zeros_like(L))
    post=opt.evaluate_all(x,W,S,H,L,a,b,booster)
    _,pstat=opt.cost_x(x,post)
    delta=post.mean(axis=0)-pre.mean(axis=0)
    # The price of booster generation is already reflected in grid transactions/fuel.
    # Pooled cost is per COMPUTING MWh; drying revenue is reported in a separate account.
    # HVO and import production emissions are allocated to all loads; avoided drying fuel is not an atmospheric removal.
    base_em=json.loads((RC/'NETWORK_LOAD_FLOW_N_MINUS_1/grid_connected_base_case.json').read_text())
    old_grid_em=base_em['emissions_100g_grid_Mt_CO2e_per_year']
    r_old=json.loads((RC/'LARGE_TURBINE_STUDY/OUTPUT/SANY_SI19580_8MW_optimization.json').read_text())['candidate']
    old_w=sum(r_old['wind_gw_by_site'].values());old_s=r_old['solar_gw'];old_b=r_old['battery_gwh']
    # Explicit LCA changes in gross generated wind+solar; no credit for exports.
    # Approx. applied wind 11 g/kWh, solar 35 g/kWh; IT-related embodied hardware stays fixed.
    mean_wcf=np.mean([np.mean([np.mean(g['windcf'][i]) for g in groups]) for i in range(5)])
    wind_gwh=float(np.mean(np.array([x[:5]@W[i] for i in range(len(groups))]).sum(axis=1)))/1000
    solar_gwh=float(np.mean(np.array([x[5]*S[i] for i in range(len(groups))]).sum(axis=1)))/1000
    original_groups,OW,OS,OH,OL,_=build_inputs('SANY_SI19580_8MW',.4)
    oldcap=np.asarray([r_old['wind_gw_by_site'][k] for k in r_old['wind_gw_by_site']]+[old_s,old_b])
    old_wind_gwh=float(np.mean([oldcap[:5]@OW[i] for i in range(len(groups))],axis=0).sum())/1000
    old_solar_gwh=float(np.mean([oldcap[5]*OS[i] for i in range(len(groups))],axis=0).sum())/1000
    # Use prior embodied renewable inputs and dispatch-related combustion from the saved connected case.
    # Carry over fixed other sources (hardware, B100) and adjust scaled material flows.
    old_hvo=base_em['annual_mean_HVO_ML'];old_imp=base_em['annual_mean_grid_purchases_TWh']
    old_battery=old_b
    hvo_delta=(post[:,0].mean()-old_hvo)*1e6*36.51*25/1e12
    grid_delta=(post[:,3].mean()-old_imp)*0.100 # Mt per TWh at 100g/kWh
    wind_delta=(wind_gwh-old_wind_gwh)*11/1e6 # Mt: GWh x 1e6 kWh/GWh x g/kWh / 1e12 g/Mt
    solar_delta=(solar_gwh-old_solar_gwh)*35/1e6
    batt_delta=(x[6]-old_battery)*1e6*70/15/1e9
    base_other=float(old_grid_em)+hvo_delta+grid_delta+wind_delta+solar_delta+batt_delta
    # SCR N2O baseline proportional engine-energy sensitivity; report coefficient uncertainty separately
    engine_new=(post[:,0].mean()-old_hvo)*1e6/opt.HVO_L_PER_MWH/1000
    engine_original=old_hvo*1e6/opt.HVO_L_PER_MWH/1000
    scr_adjust=base_em['revised_SCR_N2O_emissions_Mt'] * (engine_new/max(engine_original,1e-9))
    base_other+=scr_adjust
    emissions={str(ci):float(base_other+(ci-100)*post[:,3].mean()/1000) for ci in [20,100,250]}
    # GPU NPV model: full model against identical compute capex and utilisation, varying cost path only.
    gas_paths=pcm.gas_paths()
    gas_cost_path=np.asarray([q['cad_mwh'] for q in gas_paths['central_4_rising_3pct|tier_output_based']['path']])
    # Build 25-year cost path using the exact per-year wind and solar financing and cost model.
    stats={'hvo_ml_mean':float(post[:,0].mean()),'hvo_ml_max':float(post[:,0].max()),'gas_gwh_max':float(post[:,1].max()),
        'unserved_gwh_max':float(post[:,2].max()),'load_twh':pcm.LOAD_TWH,'gen_twh':0.,'curtail_twh':float(post[:,5].mean())}
    fin=sf.cost_25y(float(x[:5].sum()),float(x[5]),float(x[6]),stats,opt.HVO_MAX)
    trade_yr=float(post[:,6].mean()-post[:,7].mean())
    new_path=np.array([(q+trade_yr)*1000/pcm.LOAD_TWH for q in fin['annual_path_bn']])
    wind_extension_bn=.1*float(x[:5].sum())*sf.P['capex_wind_bn_gw']
    new_path[20]+=wind_extension_bn*1000/pcm.LOAD_TWH
    # fuel/emissions may include industrial drying; GPU electricity cost conservatively includes it, while
    # associated dryer heat-service profit stays outside NPV. No speculative label valuation inserted.
    products=list(pcm.PARAM['compute']['products']); rows=[]
    for prod in products:
        for tier in ['spot (conservative)','market on-demand']:
            for decline in [0,.15]:
                n0=pcm.gpu_npv(prod,tier,0.,new_path,community_net_bn=0.,community_capex_bn=0.,decline=decline,label_share=.5)
                n1=pcm.gpu_npv(prod,tier,1.,new_path,community_net_bn=0.,community_capex_bn=0.,decline=decline,label_share=.5)
                ng=pcm.gpu_npv(prod,tier,0.,gas_cost_path,community_net_bn=0.,community_capex_bn=0.,decline=decline,label_share=.5)
                premium=(ng['npv_bn']-n0['npv_bn'])/(n1['npv_bn']-n0['npv_bn'])
                rows.append(dict(product=prod,tier=tier,generation_price_decline=decline,label_share=.5,
                                 breakeven_USD_per_labelled_GPU_hour=premium,baseline_DG_NPV_bn=n0['npv_bn'],
                                 gas_NPV_bn=ng['npv_bn'],DG_NPV_at_USD1_label_bn=n1['npv_bn']))
    gp=pd.DataFrame(rows);gp.to_csv(ROOT/'gpu_npv_breakeven_reoptimized.csv',index=False,float_format='%.7f')
    res={'optimized_design_prior_to_dryer_load':d['selected_case'],
         'dryer_booster_incremental_load_TWh':float(booster.mean()*8760/1e6),
         'after_drying':pstat,
         'increment_vs_no_drying':{'HVO_ML':float(delta[0]),'grid_import_TWh':float(delta[3]),'grid_export_TWh':float(delta[4]),
                  'curtailed_TWh':float(delta[5]),'import_cost_CAD_bn':float(delta[6]),'export_receipts_CAD_bn':float(delta[7])},
         'heat':heats,'emissions_mt_approx_by_grid_intensity':emissions,
         'emissions_disclosure':'Screening life-cycle ledger under WTW factors; separate 2010–2025 weather, not measured lifetime emissions.',
         'gpu_model':'25-year explicit gpu_npv(), same GPU purchase and usage, new annual power-cost path; community finances excluded symmetrically.',
         'gpu_economics':rows,'limitations':['Ridge wind proxy sites; no measured wind farm layouts','Grid prices are hourly scenarios, not observed wholesale prices',
                       'No demonstrated 2.5GW import/3GW export agreement','No passing utility AC N-1 design','Industrial drying customers not contracted']}
    (ROOT/'integrated_grid_heat_gpu.json').write_text(json.dumps(res,indent=2)+'\n')
    print('HEAT',heats)
    print('ENERGY pre',d['selected_case'])
    print('ENERGY post',pstat)
    print('EMISSIONS',emissions)
    print('GPU',gp.to_string(index=False))
    return res

if __name__=='__main__':run()
