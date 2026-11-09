#!/usr/bin/env python3
"""BC grid-connected 8MW wind/solar/battery re-optimisation, capacity and time-varying-price screening.

The 16-year electricity series is original 2010–2025 ERA5 and GWA-corrected SANY 8MW
engineering power curves. Hourly price SERIES ARE SCENARIOS, NOT OBSERVED BC HOURLY
PRICES or a BC Hydro buy/sell tariff. Buyer must secure import/export agreements.
This is a pooled 17-node dispatch upper bound: nodal AC constraints applied separately.
"""
from pathlib import Path
import sys,json,csv,time, argparse
import numpy as np,pandas as pd
from numba import njit
from scipy.optimize import differential_evolution

HERE=Path(__file__).resolve().parent
RC=HERE.parent
sys.path[:0]=[str(RC),str(RC/'MODEL_CORE'),str(RC/'LARGE_TURBINE_STUDY')]
from model_8mw_10mw import build_inputs,TURBINES
from dispatch_reference import B100_MWh,HVO_L_PER_MWH
import storage_fuel_sweetspot as sf

HVO_MAX=sf.P['supply_cap_ml']-sf.P['farm_hvo_ml']
IMP_MW=2500.; EXP_MW=3000.; ENG_MW=5100.
FIXED_NETWORK_CAD_BN=sf.P['capex_network_engines_bn']

@njit(cache=True)
def dispatch_one(gen, load, battery_gwh, import_cap, export_cap, hvo_max_ml, import_px, export_px, boost=None):
    # battery->grid->B100->HVO->emergency gas; annual inventories reset each year.
    soc=battery_gwh*1000*.5;cap=battery_gwh*1000; pmax=min(cap/8.,12000.)
    b100=B100_MWh; hvo=hvo_max_ml*1e6/HVO_L_PER_MWH
    hvo_mwh=0.;gas_mwh=0.;unserved=0.;grid_imp=0.;grid_exp=0.;curtail=0.
    imp_dollars=0.;exp_dollars=0.;import_hours=0.;export_hours=0.
    for i in range(len(gen)):
        ld=load[i] + (boost[i] if boost is not None else 0.)
        d=gen[i]-ld
        if d>=0:
            ch=min(d,pmax,max(0.,(cap-soc)/.94));soc+=ch*.94
            rem=d-ch
            ex=min(rem,export_cap)
            grid_exp+=ex;curtail+=rem-ex;exp_dollars+=ex*export_px[i]
            if ex>1e-6:export_hours+=1
        else:
            d=-d
            dis=min(d,pmax,soc*.94);soc-=dis/.94;d-=dis
            im=min(d,import_cap);d-=im;grid_imp+=im;imp_dollars+=im*import_px[i]
            if im>1e-6:import_hours+=1
            eng=min(d,ENG_MW);d-=eng
            b=min(eng,b100);eng-=b;b100-=b
            h=min(eng,hvo);eng-=h;hvo-=h;hvo_mwh+=h
            gas_mwh+=eng
            unserved+=d
    return (hvo_mwh*HVO_L_PER_MWH/1e6,gas_mwh/1000.,unserved/1000.,grid_imp/1e6,grid_exp/1e6,
            curtail/1e6,imp_dollars/1e9,exp_dollars/1e9,import_hours,export_hours)

@njit(cache=True)
def evaluate_all(cap,W,S,H,L,IP,EP,boost):
    n=len(H); out=np.empty((n,10),dtype=np.float64)
    for y in range(n):
        gen=cap[0]*W[y,0,:]+cap[1]*W[y,1,:]+cap[2]*W[y,2,:]+cap[3]*W[y,3,:]+cap[4]*W[y,4,:]+cap[5]*S[y,:]+H[y,:]
        out[y,:]=np.asarray(dispatch_one(gen,L[y],cap[6],IMP_MW,EXP_MW,HVO_MAX,IP[y],EP[y],boost[y]))
    return out

def make_prices(groups,S,profile='hourly_scarcity'):
    # This profile is a parametrised hourly stress case; NOT market observation.
    # Anchored at annual arithmetic averages 125 and 50 CAD/MWh, respectively.
    ip=[];xp=[];lookup=[]
    for yi,g in enumerate(groups):
        times=pd.date_range(f"{g['year']}-01-01",f"{g['year']+1}-01-01",freq='h',inclusive='left',tz='UTC')
        times=times[~((times.month==2)&(times.day==29))]
        assert len(times)==8760
        mo=np.asarray(times.month);hr=np.asarray(times.hour)
        winter=np.isin(mo,[11,12,1,2,3]).astype(float)
        evening=np.isin(hr,[16,17,18,19,20]).astype(float)
        sunny=np.asarray(S[yi])/max(float(S[yi].max()),1.0)
        if profile=='flat':
            im=np.full(len(hr),125.);ex=np.full(len(hr),50.)
        elif profile=='hourly_scarcity':
            im=125*(1+.25*(winter-winter.mean())+.2*(evening-evening.mean())-.12*(sunny-sunny.mean()))
            ex=50*(1+.18*(winter-winter.mean())+.15*(evening-evening.mean())-.45*(sunny-sunny.mean()))
            im=np.maximum(im,10.);ex=np.maximum(ex,0.)
        elif profile=='weak_export':
            im=125*(1+.25*(winter-winter.mean())+.2*(evening-evening.mean())-.12*(sunny-sunny.mean()))
            ex=25*(1+.18*(winter-winter.mean())+.15*(evening-evening.mean())-.45*(sunny-sunny.mean()))
            im=np.maximum(im,10.);ex=np.maximum(ex,0.)
        elif profile=='high_import':
            im=175*(1+.25*(winter-winter.mean())+.2*(evening-evening.mean())-.12*(sunny-sunny.mean()))
            ex=35*(1+.18*(winter-winter.mean())+.15*(evening-evening.mean())-.45*(sunny-sunny.mean()))
            im=np.maximum(im,10.);ex=np.maximum(ex,0.)
        else:raise ValueError(profile)
        ip.append(im);xp.append(ex)
    return np.asarray(ip),np.asarray(xp)

def cost_x(cap,out,include_life=True):
    means=out.mean(axis=0)
    stats={'hvo_ml_mean':float(means[0]),'hvo_ml_max':float(out[:,0].max()),'gas_gwh_max':float(out[:,1].max()),
        'unserved_gwh_max':float(out[:,2].max()),'load_twh':36.00486,'gen_twh':0.,'curtail_twh':float(means[5])}
    fin=sf.cost_25y(float(cap[:5].sum()),float(cap[5]),float(cap[6]),stats,HVO_MAX)
    trading=(means[6]-means[7])*1e9/(stats['load_twh']*1e6)
    annuity=sum(1/(1+sf.P['finance_rate'])**yr for yr in range(1,26))
    # Explicit year-21 blade/tower inspection + illustrative life extension cost, not a certification.
    extension=0.10*float(cap[:5].sum())*sf.P['capex_wind_bn_gw']*1e9 / (1+sf.P['finance_rate'])**21 / (annuity*stats['load_twh']*1e6) if include_life else 0.
    total=float(fin['lcoe_25y_cad_mwh'])+trading+extension
    return total,dict(generation_cost_CAD_MWh=float(fin['lcoe_25y_cad_mwh']),trading_cost_CAD_MWh=float(trading),
            wind_extension_CAD_MWh=float(extension),total_CAD_MWh=total,
            hvo_ml_mean=stats['hvo_ml_mean'],hvo_ml_max=stats['hvo_ml_max'],max_gas_gwh=stats['gas_gwh_max'],max_unserved_gwh=stats['unserved_gwh_max'],
            import_twh=float(means[3]),export_twh=float(means[4]),curtail_twh=float(means[5]),
            import_revenue_bn=float(means[6]),export_revenue_bn=float(means[7]),capex_bn=float(fin['capex_bn']))

def run(args):
    t=time.monotonic()
    groups,W,S,H,L,sites=build_inputs('SANY_SI19580_8MW',.4)
    # Source matrices convention: W and S already expressed as MWh/hour per GW.
    W=np.asarray(W);S=np.asarray(S);H=np.asarray(H);L=np.asarray(L)
    print('SHAPES',W.shape,S.shape,H.shape,L.shape,flush=True)
    ip,ep=make_prices(groups,S,args.price)
    # Under --boost-load optimize generation, storage and fuel for the same drying booster schedule used in the LCA.
    zeros=np.load(HERE/'dryer_booster_hourly_MWh.npy') if args.boost_load else np.zeros_like(L)
    assert zeros.shape==L.shape
    old=json.loads((RC/'LARGE_TURBINE_STUDY/OUTPUT/SANY_SI19580_8MW_optimization.json').read_text())['candidate']
    oldcap=np.asarray([old['wind_gw_by_site'][x] for x in old['wind_gw_by_site']]+[old['solar_gw'],old['battery_gwh']],float)
    oldout=evaluate_all(oldcap,W,S,H,L,ip,ep,zeros)
    _,oldst=cost_x(oldcap,oldout)
    bounds=[(0.,2.) if j!=2 else (0.,.2) for j in range(5)]+[(2.,35.),(3.,70.)]
    # check sites index equals PICK: Pennask, Mabel, Nicola, Cache, Highland Valley
    count=[0]
    def objective(x):
        count[0]+=1
        o=evaluate_all(np.asarray(x),W,S,H,L,ip,ep,zeros)
        price,stat=cost_x(x,o)
        # large constraint penalties for emergency gas and unmet load; no invented fully dispatchable supply
        return price+20*o[:,1].max()+150*o[:,2].max()
    print('OLD',oldst,'HVO cap',HVO_MAX,flush=True)
    result=differential_evolution(objective,bounds,seed=args.seed,popsize=args.popsize,maxiter=args.iter,
             updating='immediate',polish=False,workers=1,tol=0.006,disp=True)
    winner=np.asarray(result.x)
    result0=evaluate_all(winner,W,S,H,L,ip,ep,zeros)
    _,winst=cost_x(winner,result0)
    # independent deterministic nearby coordinate search; select best feasible candidate
    samples=[(winner,result0,winst,'optimizer')]
    for delta in [-0.05,0.05]:
        for j in range(7):
            x=winner.copy();x[j]=np.clip(x[j]*(1+delta),bounds[j][0],bounds[j][1]);o=evaluate_all(x,W,S,H,L,ip,ep,zeros)
            _,st=cost_x(x,o);samples.append((x,o,st,f'neighbor_{j}_{delta:+.2f}'))
    feasible=[i for i in samples if i[2]['max_gas_gwh']<0.001 and i[2]['max_unserved_gwh']<0.001]
    if feasible:win=min(feasible,key=lambda q:q[2]['total_CAD_MWh'])
    else:win=min(samples,key=lambda q:q[2]['total_CAD_MWh']+20*q[2]['max_gas_gwh']+150*q[2]['max_unserved_gwh'])
    winner, result0,winst,how=win
    # Convert continuous site decisions into whole 8-MW turbine counts, re-run all 16 years.
    discrete=winner.copy();discrete[:5]=np.round(discrete[:5]/0.008)*0.008
    dout=evaluate_all(discrete,W,S,H,L,ip,ep,zeros)
    _,dst=cost_x(discrete,dout)
    if dst['max_gas_gwh']<0.001 and dst['max_unserved_gwh']<0.001:
        winner,result0,winst,how=discrete,dout,dst,how+'; whole_8MW_turbines'
    # run sensitivities at fixed portfolio so risk is readable
    stress={}
    for profile in ['flat','hourly_scarcity','weak_export','high_import']:
        a,b=make_prices(groups,S,profile)
        out=evaluate_all(winner,W,S,H,L,a,b,zeros)
        _,s=cost_x(winner,out)
        stress[profile]=s
    summary={'data_source':'ERA5 2010–2025 + GWA 100m means; not verified site winds','prices':'PARAMETRIC HOURLY PRICE SCENARIOS, NOT OBSERVED MARKET DATA',
        'location':'Five 100-m site/proxy coordinates; 17-node network assumed pooled for optimisation',
        'reference_case_cost':oldst,'wind_capacity_GW_by_site':{v:float(winner[j]) for j,v in enumerate(old['wind_gw_by_site'])},
        'wind_GW_total':float(winner[:5].sum()),'solar_GW':float(winner[5]),'battery_GWh':float(winner[6]),'fuel_limit_ML':HVO_MAX,
        'selected_case':winst,'selected_by':how,'sensitivity_at_fixed_build':stress, 'drying_booster_in_objective':bool(args.boost_load),
        'search_metadata':{'iterations':args.iter,'popsize':args.popsize,'seed':args.seed,'evaluations':count[0],'success':bool(result.success),
                           'message':str(result.message),'seconds':time.monotonic()-t},
        'limitations':['Not a global optimum','Grid transactions are not awarded','No hourly BC Hydro or Mid-C settled prices provided','No nodal OPF','Wind speeds from ERA5/GWA proxies','HVO supplies and prices uncontracted','Network losses and terminal constraints need validation']}
    HERE.mkdir(exist_ok=True)
    (HERE/'reoptimized_grid_case.json').write_text(json.dumps(summary,indent=2)+'\n')
    pd.DataFrame([dict(year=groups[i]['year'],hvo_ML=result0[i,0],emergency_gas_GWh=result0[i,1],unserved_GWh=result0[i,2],
         grid_import_TWh=result0[i,3],grid_export_TWh=result0[i,4],curtail_TWh=result0[i,5],grid_purchase_CAD_bn=result0[i,6],
         export_receipts_CAD_bn=result0[i,7]) for i in range(len(groups))]).to_csv(HERE/'reoptimized_annual.csv',index=False)
    # store compact hourly primary case ledger for drying integration; record supply, load, prior exit. 
    rows=[]
    for yi,g in enumerate(groups):
        gen=winner[:5]@W[yi]+winner[5]*S[yi]+H[yi]
        p=gen-L[yi]
        rows.append(pd.DataFrame({'year':g['year'],'hour':np.arange(8760), 'generation_MW':gen,'facility_load_MW':L[yi], 'drying_booster_load_MW':zeros[yi],
                                  'import_price_CAD_MWh':ip[yi],'export_price_CAD_MWh':ep[yi]}))
    pd.concat(rows,ignore_index=True).to_csv(HERE/'hourly_input_reoptimized.csv.gz',index=False,compression='gzip')
    print('RESULT',json.dumps({'selected':winst,'windGW':summary['wind_GW_total'],'solarGW':summary['solar_GW'],'batteryGWh':summary['battery_GWh'],'search':summary['search_metadata']},indent=2),flush=True)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--iter',type=int,default=18);ap.add_argument('--popsize',type=int,default=6);
    ap.add_argument('--seed',type=int,default=1901);ap.add_argument('--boost-load',action='store_true');ap.add_argument('--price',choices=['flat','hourly_scarcity','weak_export','high_import'],default='hourly_scarcity');run(ap.parse_args())
