#!/usr/bin/env python3
"""Digital Gardens vs Wonder Valley: 2010-2025 complete hourly loss-aware dispatch.

Replays the fixed 5.856 GW / 4.866 GW / 3.133 GWh optimized build with
140,160 continuous *within-year* hours. Losses use the I^2 R expression on
hour-specific intact-network DC line flows (assumed nominal 1 pu voltage).
They are not 140,160 full nonlinear AC OPF solves, not chronological N-1,
and not a BC Hydro topology. A 0% loss replay is independently reconciled
with the original pooled optimizer. Scenarios 0.75, 1, 1.25 scale DC I^2R.

Battery state and annual B100/HVO inventories are rerun when losses change;
actual grid imports/exports obey 2.5/3.0 GW limits and fuel is not minted.
"""
from pathlib import Path
import json,sys
import numpy as np,pandas as pd
from numba import njit
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE=Path(__file__).resolve().parent
G=HERE.parent
RC=G.parent
sys.path[:0]=[str(RC),str(RC/'LARGE_TURBINE_STUDY'),str(RC/'MODEL_CORE'),str(G)]
from model_8mw_10mw import build_inputs
from dispatch_reference import B100_MWh,HVO_L_PER_MWH
import reoptimize_grid as R

B=json.loads((G/'reoptimized_grid_case.json').read_text())
capacities=np.asarray(list(B['wind_capacity_GW_by_site'].values()),float)
nbuses=pd.read_csv(G/'N1_QSUPPORT_loss_aware/assumed_buses.csv')
lines=pd.read_csv(G/'N1_QSUPPORT_loss_aware/assumed_branches.csv')
bi={n:i for i,n in enumerate(nbuses.bus)}
nb=len(nbuses)
Bnet=np.zeros((nb,nb),float)
Fx=np.zeros((len(lines),nb),float)
for k,e in enumerate(lines.itertuples()):
    i=bi[e.a];j=bi[e.b];q=1/float(e.x_pu)
    Bnet[i,i]+=q;Bnet[j,j]+=q;Bnet[i,j]-=q;Bnet[j,i]-=q
    Fx[k,i]=1000*q;Fx[k,j]=-1000*q
ids=np.array([i for i in range(nb) if i!=bi['GRID']])
PTDF=Fx[:,ids]@np.linalg.inv(Bnet[np.ix_(ids,ids)])/1000
windbase=np.zeros((len(lines),5))
for j,k in enumerate(B['wind_capacity_GW_by_site']):
    ix=np.where(ids==bi['W_'+k])[0][0]
    windbase[:,j]=PTDF[:,ix]
local_buses=[name for name in bi if name.startswith('L_')]
assert len(local_buses)==17
lix=[np.where(ids==bi[name])[0][0] for name in local_buses]
localbase=PTDF[:,lix].mean(axis=1)
rpu=lines.r_pu.to_numpy(float)
ratings=lines.rating_mva.to_numpy(float)

@njit(cache=True)
def step(gen,ld,soc,b100,hvo,batt_gwh,loss_mw):
    """Replay exact original battery/grid/B100/HVO priority at load + endogenous losses."""
    total=ld+loss_mw
    cap=batt_gwh*1000.; pmax=min(cap/8.,12000.)
    charge=0.;discharge=0.;imp=0.;exp=0.;b=0.;h=0.;gas=0.;shed=0.;curt=0.
    if gen>=total:
        surplus=gen-total
        charge=min(surplus,pmax,max(0.,(cap-soc)/.94))
        new_soc=soc+charge*.94
        leftover=surplus-charge
        exp=min(leftover,3000.)
        curt=leftover-exp
    else:
        deficit=total-gen
        discharge=min(deficit,pmax,soc*.94)
        new_soc=soc-discharge/.94
        deficit-=discharge
        imp=min(deficit,2500.)
        deficit-=imp
        engine=min(deficit,5100.)
        deficit-=engine
        b=min(engine,b100)
        engine-=b
        h=min(engine,hvo)
        engine-=h
        gas=engine
        shed=deficit
    return new_soc,b100-b,hvo-h,charge,discharge,imp,exp,b,h,gas,shed,curt

@njit(cache=True)
def one_year(wind,solar,hydro,load,price_imp,price_exp,windvec,localvec,rpu,ratings,batt_gwh,hvo_cap_ml,scale):
    n=len(solar);nline=len(rpu)
    # 20 columns documented in METHODS_FULL_16YR.md.
    out=np.zeros((n,20),np.float64)
    soc=batt_gwh*1000*.5;b100=B100_MWh;hvo=hvo_cap_ml*1e6/HVO_L_PER_MWH
    for t in range(n):
        gen=solar[t]+hydro[t]
        for j in range(5):gen+=wind[t,j]
        ld=load[t]
        loss=0.
        # Solve each hour to fixed point: network loss -> dispatch -> network loss.
        for it in range(6):
            ret=step(gen,ld,soc,b100,hvo,batt_gwh,loss)
            ns,nb,nh,ch,dis,imp,exp,bb,hh,gas,shed,curt=ret
            fraction=max(0.,1.-curt/max(gen,1e-9))
            local=(solar[t]+hydro[t])*fraction+dis-ch+bb+hh+gas-ld+shed
            estloss=0.;mx=0.
            for k in range(nline):
                f=localvec[k]*local
                for j in range(5):f+=windvec[k,j]*wind[t,j]*fraction
                estloss+=rpu[k]*f*f/1000.
                xx=abs(f)/ratings[k]
                if xx>mx:mx=xx
            estloss*=scale
            if abs(estloss-loss)<1e-5:
                loss=estloss;break
            loss=estloss
        ret=step(gen,ld,soc,b100,hvo,batt_gwh,loss)
        ns,nb,nh,ch,dis,imp,exp,bb,hh,gas,shed,curt=ret
        frac=max(0.,1.-curt/max(gen,1e-9))
        local=(solar[t]+hydro[t])*frac+dis-ch+bb+hh+gas-ld+shed
        finaloss=0.;mx=0.
        for k in range(nline):
            f=localvec[k]*local
            for j in range(5):f+=windvec[k,j]*wind[t,j]*frac
            finaloss+=rpu[k]*f*f/1000.
            xx=abs(f)/ratings[k]
            if xx>mx:mx=xx
        finaloss*=scale
        # After final recomputation any residual is <5e-5 MW for normal convergence.
        out[t,0]=imp;out[t,1]=exp;out[t,2]=bb;out[t,3]=hh;out[t,4]=gas
        out[t,5]=shed;out[t,6]=curt;out[t,7]=ch;out[t,8]=dis;out[t,9]=ns
        out[t,10]=finaloss;out[t,11]=mx*100
        out[t,12]=imp*price_imp[t];out[t,13]=exp*price_exp[t]
        out[t,14]=gen;out[t,15]=ld;out[t,16]=max(0,gen-curt)
        out[t,17]=abs(finaloss-loss)
        out[t,18]=(bb+hh+gas)/17 # MW per campus, uniform local dispatch assumption
        out[t,19]=max(0,imp-2500,exp-3000)
        soc=ns;b100=nb;hvo=nh
    return out

COL=['grid_import_MW','grid_export_MW','B100_MWh','HVO_MWh','emergency_gas_MWh','unserved_MWh','curtail_MWh','battery_charge_MW','battery_discharge_MW','battery_soc_MWh','network_loss_MWh','max_dc_branch_rating_pct','grid_import_CAD','export_receipts_CAD','gross_renewable_generation_MWh','facility_and_booster_load_MWh','renewables_delivered_MWh','loss_fixedpoint_residual_MW','uniform_local_firm_generation_MW_per_site','grid_cap_violation_MW']

def annual_stats(y,output):
    df=pd.DataFrame(output,columns=COL)
    return dict(year=y,AC_approx_losses_GWh=df.network_loss_MWh.sum()/1000,
                grid_import_TWh=df.grid_import_MW.sum()/1e6,
                grid_export_TWh=df.grid_export_MW.sum()/1e6,
                HVO_ML=df.HVO_MWh.sum()*HVO_L_PER_MWH/1e6,
                B100_GWh=df.B100_MWh.sum()/1000,
                emergency_gas_GWh=df.emergency_gas_MWh.sum()/1000,
                unserved_GWh=df.unserved_MWh.sum()/1000,
                curtail_GWh=df.curtail_MWh.sum()/1000,
                import_cost_CAD_bn=df.grid_import_CAD.sum()/1e9,
                export_revenue_CAD_bn=df.export_receipts_CAD.sum()/1e9,
                max_branch_loading_pct=df.max_dc_branch_rating_pct.max(),
                branch_rating_exceedance_hours=int((df.max_dc_branch_rating_pct>100).sum()),
                local_160MW_engine_violation_hours=int((df.uniform_local_firm_generation_MW_per_site>160+1e-7).sum()),
                max_grid_cap_excess_MW=df.grid_cap_violation_MW.max(),
                max_fixedpoint_residual_MW=df.loss_fixedpoint_residual_MW.max())

def run():
    groups,W,S,H,L,site=build_inputs('SANY_SI19580_8MW',.4)
    prices=pd.read_csv(G/'hourly_input_reoptimized.csv.gz')
    arr=np.asarray(prices.generation_MW).reshape(16,8760)
    booster=np.load(G/'dryer_booster_hourly_MWh.npy')
    assert booster.shape==(16,8760)
    assert np.max(np.abs(arr-(capacities[None,:,None]*W).sum(axis=1)-B['solar_GW']*S-H))<1e-5
    assert np.max(np.abs(np.asarray(prices.facility_load_MW).reshape(16,8760)-L))<1e-5
    wind=np.moveaxis(W,1,2)*capacities[None,None,:]
    solar=B['solar_GW']*S
    ip=np.asarray(prices.import_price_CAD_MWh).reshape(16,8760)
    ep=np.asarray(prices.export_price_CAD_MWh).reshape(16,8760)
    hvo_limit=R.HVO_MAX
    print('STUDY HOURS:',len(groups)*8760,'TURBINE CONFIG (GW)',capacities.sum(),flush=True)
    scenarios={'pooled_zero_losses':0.,'nominal_i2r':1.,'lower_i2r_075':.75,'upper_i2r_125':1.25}
    all_rows=[];hist=None;stat={}
    for name,fac in scenarios.items():
        records=[];hourly=[]
        for i,g in enumerate(groups):
            a=one_year(wind[i],solar[i],H[i],L[i]+booster[i],ip[i],ep[i],windbase,localbase,rpu,ratings,B['battery_GWh'],hvo_limit,fac)
            records.append(annual_stats(g['year'],a));
            if name=='nominal_i2r':
                hourly.append(pd.DataFrame({'year':g['year'],'hour':np.arange(8760),**{k:a[:,j] for j,k in enumerate(COL)}}))
        annual=pd.DataFrame(records);annual.to_csv(HERE/(name+'_annual.csv'),index=False,float_format='%.10f')
        means=annual.select_dtypes('number').mean();base={k:float(v) for k,v in means.to_dict().items()}
        base['max_branch_loading_pct']=float(annual.max_branch_loading_pct.max())
        base['branch_rating_exceedance_hours_total']=int(annual.branch_rating_exceedance_hours.sum())
        base['local_160MW_engine_violation_hours_total']=int(annual.local_160MW_engine_violation_hours.sum())
        base['max_grid_cap_excess_MW']=float(annual.max_grid_cap_excess_MW.max())
        base['max_fixedpoint_residual_MW']=float(annual.max_fixedpoint_residual_MW.max())
        stat[name]=base
        if hourly:pd.concat(hourly,ignore_index=True).to_csv(HERE/'nominal_i2r_hourly_2010_2025.csv.gz',index=False,compression='gzip',float_format='%.7f')
        print(name,{'loss_GWh':round(base['AC_approx_losses_GWh'],2),'hvo_ML':round(base['HVO_ML'],3),'import_TWh':round(base['grid_import_TWh'],4),'export_TWh':round(base['grid_export_TWh'],4),'maxbranch%':round(base['max_branch_loading_pct'],1)},flush=True)
    # Check exact no-loss reconciliation to previously-published fixed portfolio values.
    pooled=stat['pooled_zero_losses'];orig=B['selected_case']
    diffs={
      'hvo_ml_mean':pooled['HVO_ML']-orig['hvo_ml_mean'],
      'import_twh':pooled['grid_import_TWh']-orig['import_twh'],
      'export_twh':pooled['grid_export_TWh']-orig['export_twh'],
      'curtail_twh':pooled['curtail_GWh']/1000-orig['curtail_twh'],
      'import_revenue_bn':pooled['import_cost_CAD_bn']-orig['import_revenue_bn'],
      'export_revenue_bn':pooled['export_revenue_CAD_bn']-orig['export_revenue_bn']}
    print('BASELINE RECONCILIATION',diffs,flush=True)
    assert max(abs(z) for z in diffs.values())<2e-6, 'Nonzero baseline discrepancy: '+str(diffs)
    for n in ['nominal_i2r','lower_i2r_075','upper_i2r_125']:
        s=stat[n];dhvo=s['HVO_ML']-pooled['HVO_ML'];dimp=s['grid_import_TWh']-pooled['grid_import_TWh'];dexp=s['grid_export_TWh']-pooled['grid_export_TWh']
        # Delta uses existing model's HVO CAD1.80/L, time-differentiated price costs, no gas assumed.
        delta_cad=(dhvo*1e6*1.8+(s['import_cost_CAD_bn']-pooled['import_cost_CAD_bn'])*1e9-(s['export_revenue_CAD_bn']-pooled['export_revenue_CAD_bn'])*1e9)/(36.00486e6)
        s.update({'delta_HVO_ML':dhvo,'delta_grid_import_TWh':dimp,'delta_grid_export_TWh':dexp,'incremental_cost_CAD_MWh':delta_cad,
                  'loss_aware_cost_before_reactive_capex_CAD_MWh':orig['total_CAD_MWh']+delta_cad,
                  'delta_emissions_100g_MtCO2e_yr_screen':dhvo*.00091275+dimp*.1,
                  'delta_emissions_20g_MtCO2e_yr_screen':dhvo*.00091275+dimp*.02,
                  'delta_emissions_250g_MtCO2e_yr_screen':dhvo*.00091275+dimp*.25})
    final={'method':'full 140160-hour within-year chronological dispatch with synthetic-intact-network DC I²R line-loss model, fixed selected build, hourly price scenarios; static loss-aware AC N-1 independently retained',
           'hours':140160,'years':list(range(2010,2026)),'grid_import_cap_MW':2500,'grid_export_cap_MW':3000,
           'loss_definition':'sum over assumed lines of r_pu*DC_flow_MW²/1000 at nominal 1 pu voltage; 0.75x/1.25x sensitivity; not nonlinear hourly AC',
           'allocation':'equal facility load, PV, hydro, storage and engine generation across 17 site buses; wind injected at five wind collector buses; proportional renewable curtailment',
           'baseline_differences':diffs,'scenario_mean_results':stat,
           'baseline_cost_CAD_MWh':orig['total_CAD_MWh'],'cost_denominator':'36.00486 TWh/year computing and facility electricity, excludes incremental drying revenue',
           'emissions_delta_boundary':'additional HVO upstream at 25 gCO2e/MJ and grid imports at sensitivity 20/100/250 g/kWh; no grid-export credits, SCR N2O change not included',
           'limitations':['not a 140160-hour nonlinear AC OPF','not an hourly N-1 contingency study','synthetic 37-bus, 93-branch unverified grid model','no BC Hydro export purchase or transmission rights','annual fuel supply contracts unverified','no re-optimization of capacity against losses','each year initial 50% battery SoC, matching archived optimiser']}
    (HERE/'full_16yr_loss_results.json').write_text(json.dumps(final,indent=2)+'\n')
    names=['pooled_zero_losses','nominal_i2r','lower_i2r_075','upper_i2r_125']
    fig,ax=plt.subplots(figsize=(10,5.2))
    plot=[stat[i]['AC_approx_losses_GWh'] for i in names]
    ax.bar(['No losses','Nominal I²R','0.75 × I²R','1.25 × I²R'],plot,color=['#b0c4ce','#32899a','#5aa993','#cb9358'])
    ax.set_ylabel('Annual network energy loss (GWh/year)')
    ax.set_title('Digital Gardens: sixteen-year hourly network-loss replay (2010–2025)')
    ax.grid(axis='y',alpha=.2)
    for i,x in enumerate(plot):ax.text(i,x+max(plot)*.015,f'{x:,.1f}',ha='center',fontsize=9)
    fig.tight_layout();fig.savefig(HERE/'Figure_S15_Full_16yr_Network_Losses.png',dpi=180);plt.close(fig)
    print('PASS 16-YEAR CHRONOLOGY',json.dumps({'baseline_differences':diffs,'nominal_summary':stat['nominal_i2r']},indent=2),flush=True)

if __name__=='__main__':run()
