"""Causal pooled capacity model with empirical grid-access stress and DC I²R loss.
This is not a utility network, AC security assessment or construction design.
"""
import bootstrap
from bootstrap import ROOT
import sys,json,time,argparse
import numpy as np,pandas as pd
from numba import njit
from scipy.optimize import differential_evolution

RC=ROOT/'baseline/RESEARCH_CODE';G=RC/'GRID_CONNECTED_REOPT'
sys.path[:0]=[str(G),str(RC),str(RC/'MODEL_CORE')]
import storage_fuel_sweetspot as sf
from dispatch_reference import B100_MWh,HVO_L_PER_MWH

HVO_CAP=sf.P['supply_cap_ml']-sf.P['farm_hvo_ml']
COL=['wind_MW','solar_MW','hydro_MW','load_MW','network_loss_MW','import_MW','export_MW','B100_MW','HVO_MW','unserved_MW','curtail_MW','charge_MW','discharge_MW','soc_MWh','import_cap_MW','export_cap_MW','loss_residual_MW','balance_residual_MW']
ANNUAL=['HVO_ML','unserved_GWh','import_TWh','export_TWh','curtail_TWh','import_cost_CAD_bn','export_revenue_CAD_bn','loss_GWh','B100_GWh','max_unserved_MW','max_loss_residual_MW','max_balance_residual_MW','max_engine_MW','load_TWh','wind_TWh','solar_TWh','hydro_TWh','end_soc_MWh']

def loss_quadratic():
 buses=pd.read_csv(G/'N1_QSUPPORT_loss_aware/assumed_buses.csv');lines=pd.read_csv(G/'N1_QSUPPORT_loss_aware/assumed_branches.csv')
 bi={n:i for i,n in enumerate(buses.bus)};ids=[i for i in range(len(buses)) if i!=bi['GRID']]
 b=np.zeros((len(buses),len(buses)));fx=np.zeros((len(lines),len(buses)))
 for k,r in enumerate(lines.itertuples()):
  i,j=bi[r.a],bi[r.b];q=1/r.x_pu;b[i,i]+=q;b[j,j]+=q;b[i,j]-=q;b[j,i]-=q;fx[k,i]=1000*q;fx[k,j]=-1000*q
 ptdf=fx[:,ids]@np.linalg.inv(b[np.ix_(ids,ids)])/1000
 base=json.loads((G/'reoptimized_grid_case.json').read_text())
 wind=np.column_stack([ptdf[:,ids.index(bi['W_'+x])] for x in base['wind_capacity_GW_by_site']])
 loc=ptdf[:,[ids.index(bi[n]) for n in bi if n.startswith('L_')]].mean(axis=1)
 v=np.column_stack([wind,loc]);q=v.T@(lines.r_pu.to_numpy()[:,None]*v)/1000
 return q,v,lines.rating_mva.to_numpy()

@njit(cache=True)
def dispatch_step(gen,load,soc,b100,hvo,cap,pmax,ic,ec,engine_cap,loss):
 ch=0.;dis=0.;im=0.;ex=0.;b=0.;h=0.;shed=0.;curt=0.
 d=gen-load-loss
 if d>=0:
  ch=min(d,pmax,max(0.,(cap-soc)/.94));ns=soc+.94*ch
  ex=min(d-ch,ec);curt=max(0.,d-ch-ex)
 else:
  d=-d;dis=min(d,pmax,max(0.,soc*.94));ns=soc-dis/.94;d-=dis
  im=min(d,ic);d-=im
  firm=min(d,engine_cap);b=min(firm,b100);h=min(firm-b,hvo);shed=max(0.,d-b-h)
 return ns,ch,dis,im,ex,b,h,shed,curt

@njit(cache=True)
def simulate(c,W,S,H,L,IP,EP,IC,EC,Q,engine_cap,wind_multiplier,record):
 ny=W.shape[0];nt=W.shape[2];annual=np.zeros((ny,18));hourly=np.zeros((ny*nt if record else 1,18))
 cap=c[6]*1000.;pmax=min(cap/8.,12000.);soc=0.
 max_balance=0.;max_loss=0.
 for y in range(ny):
  bleft=B100_MWh;hleft=HVO_CAP*1e6/HVO_L_PER_MWH
  for t in range(nt):
   wind=np.empty(5);ws=0.
   for i in range(5):wind[i]=c[i]*W[y,i,t]*wind_multiplier;ws+=wind[i]
   sol=c[5]*S[y,t];hyd=H[y,t];load=L[y,t];gen=ws+sol+hyd
   aq=0.;bq=0.
   for i in range(5):
    bq+=2*wind[i]*Q[i,5]
    for j in range(5):aq+=wind[i]*Q[i,j]*wind[j]
   loss=0.
   for it in range(30):
    ns,ch,dis,im,ex,b,h,shed,curt=dispatch_step(gen,load,soc,bleft,hleft,cap,pmax,IC[y,t],EC[y,t],engine_cap,loss)
    frac=max(0.,1.-curt/max(gen,1e-12));local=(sol+hyd)*frac+dis-ch+b+h-load+shed
    est=max(0.,aq*frac*frac+bq*frac*local+Q[5,5]*local*local)
    if abs(est-loss)<1e-7 or it==29:break
    loss=est
   residual=abs(est-loss)
   balance=abs(gen-curt+im+b+h+dis+shed-load-ch-ex-loss)
   soc=ns;bleft=max(0.,bleft-b);hleft=max(0.,hleft-h)
   annual[y,0]+=h*HVO_L_PER_MWH/1e6;annual[y,1]+=shed/1000
   annual[y,2]+=im/1e6;annual[y,3]+=ex/1e6;annual[y,4]+=curt/1e6
   annual[y,5]+=im*IP[y,t]/1e9;annual[y,6]+=ex*EP[y,t]/1e9
   annual[y,7]+=loss/1000;annual[y,8]+=b/1000
   annual[y,9]=max(annual[y,9],shed);annual[y,10]=max(annual[y,10],residual);annual[y,11]=max(annual[y,11],balance)
   annual[y,12]=max(annual[y,12],b+h);annual[y,13]+=load/1e6
   annual[y,14]+=ws/1e6;annual[y,15]+=sol/1e6;annual[y,16]+=hyd/1e6;annual[y,17]=soc
   if record:
    row=y*nt+t
    hourly[row,0]=ws;hourly[row,1]=sol;hourly[row,2]=hyd;hourly[row,3]=load;hourly[row,4]=loss
    hourly[row,5]=im;hourly[row,6]=ex;hourly[row,7]=b;hourly[row,8]=h;hourly[row,9]=shed
    hourly[row,10]=curt;hourly[row,11]=ch;hourly[row,12]=dis;hourly[row,13]=soc
    hourly[row,14]=IC[y,t];hourly[row,15]=EC[y,t];hourly[row,16]=residual;hourly[row,17]=balance
 return annual,hourly

def price(c,a):
 # Tank capacity is fixed ex ante to the full assumed annual fuel allowance.
 st={'hvo_ml_mean':float(a[:,0].mean()),'hvo_ml_max':HVO_CAP,'load_twh':36.00486}
 fin=sf.cost_25y(float(c[:5].sum()),float(c[5]),float(c[6]),st,HVO_CAP)
 trading=(a[:,5].mean()-a[:,6].mean())*1e9/(36.00486e6)
 annuity=sum(1/(1+sf.P['finance_rate'])**yr for yr in range(1,26))
 ext=.1*c[:5].sum()*sf.P['capex_wind_bn_gw']*1e9/(1+sf.P['finance_rate'])**21/(annuity*36.00486e6)
 return float(fin['lcoe_25y_cad_mwh']+trading+ext)

def load_inputs():
 z=np.load(ROOT/'inputs/model_inputs.npz');grid=np.load(ROOT/'inputs/grid_access.npz')
 q,v,ratings=loss_quadratic()
 return dict(W=z['W'],S=z['S'],H=z['H'],L=z['L']+z['boost'],IP=z['ip'],EP=z['ep'],IC=2500*grid['import_factor'],EC=3000*grid['export_factor'],Q=q),z['years'],v,ratings

def run_case(c,inp,engine=5100.,wind=1.,record=False):
 return simulate(np.asarray(c,float),*(np.ascontiguousarray(inp[k]) for k in ['W','S','H','L','IP','EP','IC','EC','Q']),float(engine),float(wind),record)

def fit(inp,old,maxiter,popsize,seed):
 training={k:(v[:10] if k!='Q' else v) for k,v in inp.items()}
 count=0;t0=time.monotonic();history=[]
 def objective(c):
  nonlocal count
  count+=1;a,_=run_case(c,training)
  return price(c,a)+500*a[:,1].max()+10*a[:,9].max()
 def progress(x,convergence):
  score=objective(x);history.append({'generation':len(history)+1,'score':score,'elapsed_s':time.monotonic()-t0,'capacities':x.tolist()})
  print(f'Seed {seed} generation {len(history)} objective {score:.4f} elapsed {time.monotonic()-t0:.1f}s',flush=True)
 bounds=[(0,2),(0,2),(0,.2),(0,2),(0,2),(2,35),(3,70)]
 res=differential_evolution(objective,bounds,seed=seed,maxiter=maxiter,popsize=popsize,tol=.002,polish=False,workers=1,callback=progress,x0=old)
 # Integerize conservatively and compare adjacent feasible alternatives on training only.
 candidates=[res.x.copy(),old.copy()];candidates[0][:5]=np.ceil(candidates[0][:5]/.008)*.008
 center=candidates[0].copy()
 for j in range(7):
  for direction in [-1,1]:
   c=center.copy();c[j]=np.clip(c[j]+direction*(.008 if j<5 else .05*c[j]),*bounds[j]);candidates.append(c)
 ranked=[]
 for c in candidates:
  a,_=run_case(c,training);ranked.append((objective(c),c,price(c,a),float(a[:,1].max())))
 score,c,cost,shed=min(ranked,key=lambda x:x[0])
 meta={'seed':seed,'iterations':int(res.nit),'evaluations':count,'optimizer_success':bool(res.success),'message':str(res.message),'seconds':time.monotonic()-t0,'selected_training_cost':cost,'selected_max_training_unserved_GWh':shed,'score':score,'capacities':c.tolist(),'history':history}
 return c,meta

def summary(c,a,years,label):
 rows=[]
 for name,mask in [('training',years<=2019),('held_out',years>=2020),('all',years>0)]:
  b=a[mask];row={'scenario':label,'period':name,'first_year':int(years[mask][0]),'last_year':int(years[mask][-1]),'wind_GW':float(c[:5].sum()),'solar_GW':float(c[5]),'battery_GWh':float(c[6]),'cost_CAD_MWh':price(c,b),'mean_HVO_ML':float(b[:,0].mean()),'max_HVO_ML':float(b[:,0].max()),'mean_import_TWh':float(b[:,2].mean()),'mean_export_TWh':float(b[:,3].mean()),'mean_loss_GWh':float(b[:,7].mean()),'total_unserved_GWh':float(b[:,1].sum()),'max_unserved_MW':float(b[:,9].max()),'mean_curtail_TWh':float(b[:,4].mean()),'max_engine_MW':float(b[:,12].max()),'gross_HVO_upstream_Mt':float(b[:,0].mean()*36.51*25/1e6),'gross_grid_at100g_Mt':float(b[:,2].mean()*.1),'note':'Cost per original 36.00486 TWh facility denominator; only comparable where no unserved load. Inherited prices/capex; no new AC security cost.'}
  rows.append(row)
 return rows

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--iter',type=int,default=55);ap.add_argument('--popsize',type=int,default=8);ap.add_argument('--reuse-fit',action='store_true');args=ap.parse_args()
 inp,years,v,ratings=load_inputs();base=json.loads((G/'reoptimized_grid_case.json').read_text());old=np.array(list(base['wind_capacity_GW_by_site'].values())+[base['solar_GW'],base['battery_GWh']])
 if args.reuse_fit:
  fitdata=json.loads((ROOT/'results/fit_results.json').read_text());selected=np.array(fitdata['selected_capacities'])
 else:
  fits=[]
  for seed in [8121,8122]:
   c,m=fit(inp,old,args.iter,args.popsize,seed);fits.append(m)
   (ROOT/'results/fit_progress.json').write_text(json.dumps(fits,indent=2)+'\n')
  winner=min(fits,key=lambda m:m['score']);selected=np.array(winner['capacities']);fitdata={'training_years':list(range(2010,2020)),'held_out_years':list(range(2020,2026)),'selected_capacities':selected.tolist(),'fits':fits,'selection':'lowest penalized training score only; no held-out selection'}
  (ROOT/'results/fit_results.json').write_text(json.dumps(fitdata,indent=2)+'\n')
 print('FROZEN CAPACITIES',selected.tolist(),flush=True)
 scenarios=[('old_build_constant_access',old,1.,1.,5100.,0),('old_build_observed_shape',old,1.,1.,5100.,None),('new_build_observed_shape',selected,1.,1.,5100.,None),('new_build_wind_minus10pct',selected,1.,.9,5100.,None),('new_build_half_access',selected,.5,1.,5100.,None),('new_build_local160MW',selected,1.,1.,2720.,None),('new_build_clock_minus1h',selected,1.,1.,5100.,-1),('new_build_clock_plus1h',selected,1.,1.,5100.,1)]
 scenarios += [('new_build_missing_TTC_previous',selected,1.,1.,5100.,None),('new_build_local160MW_gapfilled',selected,1.,1.,2720.,None)]
 allsummary=[];allannual=[];checks={}
 for label,c,access,wind,engine,shift in scenarios:
  this=dict(inp);this['IC']=inp['IC']*access;this['EC']=inp['EC']*access
  if label in ['new_build_missing_TTC_previous','new_build_local160MW_gapfilled']:
   missing=np.load(ROOT/'inputs/grid_access.npz')
   for key,flag in [('IC','import_missing'),('EC','export_missing')]:
    series=pd.Series(this[key].ravel()).mask(missing[flag].ravel()>0)
    this[key]=series.ffill(limit=24).fillna(0).to_numpy().reshape(this[key].shape)
  if shift==0:this['IC']=np.full_like(inp['IC'],2500.);this['EC']=np.full_like(inp['EC'],3000.)
  elif shift is not None:
   for k in ['IC','EC']:
    flat=this[k].ravel();a=np.zeros_like(flat)
    if shift>0:a[shift:]=flat[:-shift]
    else:a[:shift]=flat[-shift:]
    this[k]=a.reshape(this[k].shape)
  annual,hourly=run_case(c,this,engine,wind,True);allsummary.extend(summary(c,annual,years,label))
  df=pd.DataFrame(annual,columns=ANNUAL);df.insert(0,'year',years);df.insert(0,'scenario',label);allannual.append(df)
  times=[]
  for y in years:
   idx=pd.date_range(f'{y}-01-01',f'{y+1}-01-01',freq='h',inclusive='left');times.extend(idx[~((idx.month==2)&(idx.day==29))])
  hd=pd.DataFrame(hourly,columns=COL);hd.insert(0,'time_utc',times)
  hd.to_csv(ROOT/'results'/f'{label}_hourly.csv.gz',index=False,compression='gzip',float_format='%.8f')
  # Independent vectorized ledger audits, including no free SOC reset at Jan 1.
  previous=np.r_[0.,hd.soc_MWh.to_numpy()[:-1]]
  soc_error=np.max(np.abs(hd.soc_MWh-previous-.94*hd.charge_MW+hd.discharge_MW/.94))
  balance=hd.wind_MW+hd.solar_MW+hd.hydro_MW-hd.curtail_MW+hd.import_MW+hd.B100_MW+hd.HVO_MW+hd.discharge_MW+hd.unserved_MW-hd.load_MW-hd.charge_MW-hd.export_MW-hd.network_loss_MW
  check={'max_balance_error_MW':float(np.max(np.abs(balance))),'max_SOC_error_MWh':float(soc_error),'min_SOC_MWh':float(hd.soc_MWh.min()),'max_SOC_MWh':float(hd.soc_MWh.max()),'max_loss_fixedpoint_error_MW':float(hd.loss_residual_MW.max()),'max_import_cap_excess_MW':float(np.maximum(hd.import_MW-hd.import_cap_MW,0).max()),'max_export_cap_excess_MW':float(np.maximum(hd.export_MW-hd.export_cap_MW,0).max()),'max_HVO_ML':float(annual[:,0].max()),'max_B100_GWh':float(annual[:,8].max())}
  assert check['max_balance_error_MW']<1e-6 and soc_error<1e-6
  assert hd.soc_MWh.min()>-1e-6 and hd.soc_MWh.max()<=c[6]*1000+1e-6
  assert hd.loss_residual_MW.max()<1e-5 and check['max_HVO_ML']<=HVO_CAP+1e-6
  assert check['max_import_cap_excess_MW']<1e-6 and check['max_export_cap_excess_MW']<1e-6
  assert (hd.B100_MW+hd.HVO_MW).max()<=engine+1e-6
  checks[label]=check
  # Intact synthetic DC loading only; no reuse of old AC/N-1 certificates.
  if label=='new_build_observed_shape':
   w=np.moveaxis(inp['W'],1,2).reshape(-1,5)*c[:5];sol=hd.solar_MW.to_numpy();hyd=hd.hydro_MW.to_numpy()
   frac=1-hd.curtail_MW.to_numpy()/np.maximum(hd.wind_MW+hd.solar_MW+hd.hydro_MW,1e-12)
   local=(sol+hyd)*frac+hd.discharge_MW-hd.charge_MW+hd.B100_MW+hd.HVO_MW-hd.load_MW+hd.unserved_MW
   flows=(w*frac.to_numpy()[:,None])@v[:,:5].T+local.to_numpy()[:,None]*v[:,5]
   loading=np.max(np.abs(flows)/ratings,axis=1)*100
   checks[label]['max_intact_DC_branch_loading_pct']=float(loading.max());checks[label]['intact_DC_over100_hours']=int((loading>100+1e-7).sum())
  print(label,allsummary[-1],flush=True)
 pd.DataFrame(allsummary).to_csv(ROOT/'results/scenario_summary.csv',index=False)
 pd.concat(allannual,ignore_index=True).to_csv(ROOT/'results/scenario_annual.csv',index=False)
 (ROOT/'results/model_validation.json').write_text(json.dumps(checks,indent=2)+'\n')
 print('MODEL COMPLETE',flush=True)

if __name__=='__main__':main()
