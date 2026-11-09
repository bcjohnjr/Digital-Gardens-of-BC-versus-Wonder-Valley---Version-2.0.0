#!/usr/bin/env python3
"""NOV8_08 hypothetical network independent fixed-dispatch AC and DC-contingency screens.

Important: THIS IS NOT REAL BC HYDRO NETWORK SECURITY, NERC TPL, or AC OPF.
The N0 and stratified contingency calculations solve nonlinear PQ power flow.
The full 16y x 93 DC N1 is an approximate thermal sensitivity, not full AC/N1.
"""
import sys,os,time,json,argparse
from pathlib import Path
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
import numpy as np, pandas as pd
from scipy.sparse.csgraph import connected_components
from scipy.sparse import csr_matrix
from evidence_model import load_inputs
ROOT=Path(__file__).resolve().parents[1];R=ROOT/'results';G=ROOT/'baseline/RESEARCH_CODE/GRID_CONNECTED_REOPT/N1_QSUPPORT_loss_aware'
AP=argparse.ArgumentParser();AP.add_argument('--hours',type=int,default=140160);AP.add_argument('--sample',type=int,default=160);AP.add_argument('--block',type=int,default=512);AP.add_argument('--full-ac-n1',action='store_true');AP.add_argument('--max-contingencies',type=int,default=93); args=AP.parse_args()
t0=time.time(); inp,years,ptdf,rating=load_inputs()
fit=json.loads((R/'fit_results.json').read_text());c=np.asarray(json.loads((R/'NOV8_08_rounded_robust_summary.json').read_text())['integer8MW_portfolio'],float)
H=pd.read_csv(R/'NOV8_08_rounded_robust_central_hourly.csv.gz');n=min(args.hours,len(H)); H=H.iloc[:n].copy();print('n',n,flush=True)
B=pd.read_csv(G/'assumed_buses.csv');L=pd.read_csv(G/'assumed_branches.csv')
bi={name:k for k,name in enumerate(B.bus)}; nb=len(B);nl=len(L)
assert nb==37 and nl==93 and len(H)>0
an=np.array([bi[a] for a in L.a]);bn=np.array([bi[b] for b in L.b]);y=1/(L.r_pu.to_numpy()+1j*L.x_pu.to_numpy());rates=L.rating_mva.to_numpy(float)
w=np.moveaxis(inp['W'],1,2).reshape(-1,5)[:n]*c[:5]
renew=H[['wind_MW','solar_MW','hydro_MW']].sum(axis=1).to_numpy();fraction=np.clip(1-H.curtail_MW.to_numpy()/np.maximum(renew,1e-9),0,1)
wind=w*fraction[:,None]
local=(H.solar_MW.to_numpy()+H.hydro_MW.to_numpy())*fraction + H.discharge_MW.to_numpy()-H.charge_MW.to_numpy()+H.B100_MW.to_numpy()+H.HVO_MW.to_numpy()-H.load_MW.to_numpy()+H.unserved_MW.to_numpy()
loads=[bi[x] for x in B.bus if x.startswith('L_')];ws=[bi['W_'+x] for x in json.loads((ROOT/'baseline/RESEARCH_CODE/GRID_CONNECTED_REOPT/reoptimized_grid_case.json').read_text())['wind_capacity_GW_by_site']]
assert len(loads)==17 and len(ws)==5
p=np.zeros((n,nb),np.float64);q=np.zeros((n,nb),np.float64)
p[:,loads]=local[:,None]/17;p[:,ws]=wind
q[:,loads]=-H.load_MW.to_numpy()[:,None]*.04/17
spec=(p+1j*q)/1000
bal=np.max(np.abs(p.sum(axis=1)-(H.network_loss_MW.to_numpy()-H.import_MW.to_numpy()+H.export_MW.to_numpy())))
assert bal<1e-4, ('nodal account mismatch',bal)

def ac(out,indices,block):
 Y=np.zeros((nb,nb),complex)
 for k in range(nl):
  if k==out: continue
  a,b=an[k],bn[k];yy=y[k];Y[a,a]+=yy;Y[b,b]+=yy;Y[a,b]-=yy;Y[b,a]-=yy
 try:Z=np.linalg.inv(Y[1:,1:])
 except np.linalg.LinAlgError:return None
 f=-Z@Y[1:,0];active=np.arange(nl)!=out
 ia=an[active];ja=bn[active];yy=y[active];rr=rates[active]
 m=len(indices);data={k:np.zeros(m) for k in ['converged','min_voltage_pu','max_voltage_pu','max_line_loading_pct','grid_import_MW','grid_export_MW','ac_losses_MW','max_mismatch_pu']}
 for st in range(0,m,block):
  ix=indices[st:st+block];a=spec[ix,1:];N=len(a)
  v=np.ones((N,nb),complex);v[:,1:]=f[None,:]+np.conj(a)@Z.T
  valid=np.ones(N,bool)
  for k in range(50):
   # treat divergence or zero-voltage as non-convergence, not as a feasible bus
   with np.errstate(divide='ignore',invalid='ignore',over='ignore'):
    new=f[None,:]+np.conj(a/v[:,1:])@Z.T
   step=np.nanmax(np.abs(new-v[:,1:]),axis=1)
   v[:,1:]=.7*new+.3*v[:,1:]
   if np.nanmax(step)<3e-9:break
  I=(v[:,1:]@Y[1:,1:].T)+Y[1:,0][None,:]
  err=np.nanmax(np.abs(v[:,1:]*np.conj(I)-a),axis=1)
  conv=(err<1e-6)&np.isfinite(err)&np.all(np.isfinite(v),axis=1)
  vmag=np.abs(v[:,1:]);vmin=np.nanmin(vmag,axis=1);vmax=np.nanmax(vmag,axis=1)
  power_slack=v[:,0]*np.conj(Y[0,0]*v[:,0]+v[:,1:]@Y[0,1:])*1000
  vi=v[:,ia];vj=v[:,ja]
  s1=vi*np.conj((vi-vj)*yy[None,:])*1000
  s2=vj*np.conj((vj-vi)*yy[None,:])*1000
  loading=100*np.nanmax(np.maximum(np.abs(s1),np.abs(s2))/rr[None,:],axis=1)
  losses=(s1.real+s2.real).sum(axis=1)
  slices=slice(st,st+N)
  for k,val in [('converged',conv),('min_voltage_pu',vmin),('max_voltage_pu',vmax),('max_line_loading_pct',loading),('grid_import_MW',np.maximum(0,power_slack.real)),('grid_export_MW',np.maximum(0,-power_slack.real)),('ac_losses_MW',losses),('max_mismatch_pu',err)]:data[k][slices]=val
 return data

# DC N-1 branch-line outage distribution factors (LODF): DC analytical, not AC.
A=np.zeros((nl,nb));A[np.arange(nl),an]=1;A[np.arange(nl),bn]=-1
b=(A.T*(1/L.x_pu.to_numpy()))@A
Z=np.linalg.inv(b[1:,1:])
fr=(A[:,1:]@Z@A[:,1:].T)/L.x_pu.to_numpy()[:,None]
den=1-np.diag(fr)
# Explicit N-1 graph connectivity test, e.g. single feeder island (LODF undefined)
island=[]
for k in range(nl):
 sel=np.arange(nl)!=k; adj=csr_matrix((np.ones(2*(nl-1)),(np.r_[an[sel],bn[sel]],np.r_[bn[sel],an[sel]])),shape=(nb,nb))
 cc,_=connected_components(adj,directed=False)
 if cc>1 or abs(den[k])<1e-8:island.append(k)
LODF=fr/den[None,:];np.fill_diagonal(LODF,-1)
flow=(wind@ptdf[:,:5].T)+(local[:,None]*ptdf[:,5])
# Compare model's vector flow N0 number with inherited result: base central max ~57%.
max_loading=np.max(np.abs(flow)/rates,axis=1)*100
nr=np.zeros(n,int);worst=np.zeros(n);outage_viol=np.zeros(nl,int);worst_out=np.zeros(nl)
for st in range(0,n,192):
 en=min(n,st+192);f=flow[st:en,:]
 # corrected flow for every outage per hour. shape chunk x line x outage
 new=f[:,:,None]+f[:,None,:]*LODF[None,:,:]
 idx=np.arange(nl);new[:,idx,idx]=0
 ld=np.max(abs(new)/rates[None,:,None],axis=1)*100
 nr[st:en]=(ld>100+1e-6).sum(axis=1);worst[st:en]=ld.max(axis=1)
 outage_viol+=(ld>100+1e-6).sum(axis=0);worst_out=np.maximum(worst_out,ld.max(axis=0))
 if st%19200==0:print('DC N1',en,'/',n,'elapsed',round(time.time()-t0,1),flush=True)
DC=pd.DataFrame({'time_utc':H.time_utc,'n0_max_DC_loading_pct':max_loading,'n1_max_DC_loading_pct':worst,'n1_outages_with_thermal_overload':nr})
DC.to_csv(R/'NOV8_09_ROBUST_fullhour_synthetic_DC_N1.csv.gz',index=False,compression='gzip')
pd.DataFrame({'line_outage':L.line,'n1_DC_thermal_overload_hours':outage_viol,'max_DC_N1_loading_pct':worst_out,'island_after_outage':np.arange(nl)[:,None].__eq__(np.asarray(island)).any(axis=1) if island else False}).to_csv(R/'NOV8_09_ROBUST_synthetic_DC_N1_per_branch.csv',index=False)
print('DC N1 done',round(time.time()-t0,1), 'island',island,flush=True)
# Full N0 nonlinear calculation. 99%+ of load changes need a higher-resolution study.
n0=ac(-1,np.arange(n),args.block)
N0=pd.DataFrame({'time_utc':H.time_utc,**n0})
N0['voltage_violation']=(N0.min_voltage_pu<.95)|(N0.max_voltage_pu>1.05)
N0['thermal_violation']=N0.max_line_loading_pct>100
N0['project_grid_cap_violation']=(N0.grid_import_MW>H.import_cap_MW+1e-3)|(N0.grid_export_MW>H.export_cap_MW+1e-3)
N0['any_failure']=(~N0.converged.astype(bool))|N0.voltage_violation|N0.thermal_violation|N0.project_grid_cap_violation
N0.to_csv(R/'NOV8_09_ROBUST_fullhour_synthetic_AC_N0.csv.gz',index=False,compression='gzip')
n0_cap_excess=np.maximum(0.,np.maximum(N0.grid_import_MW.to_numpy()-H.import_cap_MW.to_numpy(),N0.grid_export_MW.to_numpy()-H.export_cap_MW.to_numpy()))
N0_SEVERITY={'N0_cap_excess_max_MW':float(n0_cap_excess.max()),'N0_cap_excess_mean_MW':float(n0_cap_excess.mean()),
             'N0_cap_excess_p99_MW':float(np.quantile(n0_cap_excess,.99))}
for threshold in [0.001,0.1,1.,5.,10.,50.]:N0_SEVERITY['N0_cap_excess_gt_'+str(threshold).replace('.','p')+'_MW_hours']=int((n0_cap_excess>threshold).sum())
print('AC N0 done',round(time.time()-t0,1),'fails',int(N0.any_failure.sum()),'severity',N0_SEVERITY,flush=True)
# Deterministic, explicitly selected extreme and stratified hours for AC N1, NOT all 140160.
idx=set(np.linspace(0,n-1,max(1,args.sample//4),dtype=int))
for series in (max_loading, worst, H.import_MW.to_numpy(), H.export_MW.to_numpy(), H.HVO_MW.to_numpy(),H.load_MW.to_numpy(),-H.import_cap_MW.to_numpy(),N0.max_line_loading_pct.to_numpy()):
 idx.update(np.argsort(series)[-max(1,args.sample//12):].tolist())
# Every year represented among selected hours.
for year in sorted(pd.to_datetime(H.time_utc).dt.year.unique()):
 yyidx=np.flatnonzero(pd.to_datetime(H.time_utc).dt.year.to_numpy()==year)
 idx.update(yyidx[np.linspace(0,len(yyidx)-1,3,dtype=int)].tolist())
idx=np.arange(n) if args.full_ac_n1 else np.asarray(sorted(idx),int)
# Magnitude-sensitive diagnostics; mathematical cap excess is not a blackout.
cap_in=H.import_cap_MW.to_numpy()[idx]; cap_out=H.export_cap_MW.to_numpy()[idx]
THRESHOLDS_MW=[0.001,0.1,1.,5.,10.,50.]
THERMAL_THRESHOLDS_PCT=[100.,101.,105.,110.,125.]
records=[]
for k in range(min(nl,args.max_contingencies)):
 if k in island:
  records.append({'outage':L.line.iloc[k],'hours_evaluated':0,'islanding':True,'nonconverged_hours':None,'any_failure_hours':None});continue
 d=ac(k,idx,args.block)
 if d is None:
  records.append({'outage':L.line.iloc[k],'hours_evaluated':0,'islanding':True,'nonconverged_hours':None,'any_failure_hours':None});continue
 fail=(~d['converged'].astype(bool))|(d['min_voltage_pu']<.95)|(d['max_voltage_pu']>1.05)|(d['max_line_loading_pct']>100)|(d['grid_import_MW']>H.import_cap_MW.to_numpy()[idx]+1e-3)|(d['grid_export_MW']>H.export_cap_MW.to_numpy()[idx]+1e-3)
 # For each contingency retain distinct exceedance SEVERITY alongside binary flags.
 imp_excess=np.maximum(0.,d['grid_import_MW']-cap_in)
 exp_excess=np.maximum(0.,d['grid_export_MW']-cap_out)
 cap_excess=np.maximum(imp_excess,exp_excess)
 therm_excess=np.maximum(0.,d['max_line_loading_pct']-100.)
 severity={
  'max_grid_cap_excess_MW':float(np.nanmax(cap_excess)),
  'mean_grid_cap_excess_MW_over_all_hours':float(np.nanmean(cap_excess)),
  'p95_grid_cap_excess_MW_on_exceedance':float(np.quantile(cap_excess[cap_excess>0.001],.95)) if np.any(cap_excess>0.001) else 0.,
  'max_thermal_overload_percentage_points':float(np.nanmax(therm_excess)),
 }
 for threshold in THRESHOLDS_MW:severity['cap_excess_gt_'+str(threshold).replace('.','p')+'_MW']=int((cap_excess>threshold).sum())
 for threshold in THERMAL_THRESHOLDS_PCT:severity['line_loading_gt_'+str(threshold).replace('.','p')+'_pct']=int((d['max_line_loading_pct']>threshold).sum())
 records.append({'outage':L.line.iloc[k],'hours_evaluated':len(idx),'islanding':False,'nonconverged_hours':int((~d['converged'].astype(bool)).sum()),'any_failure_hours':int(fail.sum()),'voltage_fail_hours':int(((d['min_voltage_pu']<.95)|(d['max_voltage_pu']>1.05)).sum()),'thermal_fail_hours':int((d['max_line_loading_pct']>100).sum()),'grid_fail_hours':int(((d['grid_import_MW']>H.import_cap_MW.to_numpy()[idx]+1e-3)|(d['grid_export_MW']>H.export_cap_MW.to_numpy()[idx]+1e-3)).sum()),'max_line_loading_pct':float(np.nanmax(d['max_line_loading_pct'])),'min_bus_voltage_pu':float(np.nanmin(d['min_voltage_pu'])),**severity})
 if (k+1)%20==0:print('AC N1',k+1,'/',nl,'elapsed',round(time.time()-t0,1),flush=True)
AC1=pd.DataFrame(records);AC1.to_csv(R/('NOV8_09_ROBUST_synthetic_AC_N1_full.csv' if args.full_ac_n1 else 'NOV8_09_ROBUST_synthetic_AC_N1_stratified.csv'),index=False)
# Aggregate exact counters across all evaluated contingencies; categories overlap.
ac1_severity={
 'portfolio': 'ROBUST' if 'ROBUST' in __file__.upper() else 'REFERENCE',
 'scenario_hours':len(idx),'branch_outages':int(len(AC1)),
 'evaluated_solutions':int(AC1.hours_evaluated.sum()),
 'any_failure_solutions':int(AC1.any_failure_hours.fillna(0).sum()),
 'thermal_overload_solutions':int(AC1.thermal_fail_hours.fillna(0).sum()),
 'grid_cap_exceed_solutions':int(AC1.grid_fail_hours.fillna(0).sum()),
 'max_grid_cap_excess_MW':float(AC1.max_grid_cap_excess_MW.max()),
 'max_thermal_overload_percentage_points':float(AC1.max_thermal_overload_percentage_points.max()),
 'note':'Fixed-dispatch hypothetical network: violations are numerical screens; not proved real-grid disruptions.'}
for threshold in THRESHOLDS_MW:
 name='cap_excess_gt_'+str(threshold).replace('.','p')+'_MW'
 ac1_severity['N1_'+name+'_solutions']=int(AC1[name].sum())
for threshold in THERMAL_THRESHOLDS_PCT:
 name='line_loading_gt_'+str(threshold).replace('.','p')+'_pct'
 ac1_severity['N1_'+name+'_solutions']=int(AC1[name].sum())
ac1_severity.update(N0_SEVERITY)
(R/('NOV8_09_ROBUST_N1_SEVERITY.json' if 'ROBUST' in __file__.upper() else 'NOV8_09_REFERENCE_N1_SEVERITY.json')).write_text(json.dumps(ac1_severity,indent=2)+'\n')
print('SEVERITY',json.dumps(ac1_severity),flush=True)
Rsubset=N0.iloc[idx].copy();Rsubset.to_csv(R/'NOV8_09_ROBUST_synthetic_AC_N1_sample_hours.csv',index=False)
summary={'model':'synthetic 37-bus, 93-line network, not actual utility infrastructure; fixed PQ dispatch, idealized Q and slack',
 'model_hours':n,'synthetic_branches':nl,'N0_nonlin_AC_solved_hours':n,'N0_any_failure_hours':int(N0.any_failure.sum()),'N0_nonconverged_hours':int((~N0.converged.astype(bool)).sum()),'N0_voltage_failure_hours':int(N0.voltage_violation.sum()),'N0_grid_cap_failure_hours':int(N0.project_grid_cap_violation.sum()),'N0_thermal_failure_hours':int(N0.thermal_violation.sum()),
 'N0_max_grid_import_MW':float(N0.grid_import_MW.max()),'N0_max_import_excess_over_assumed_cap_MW':float(np.maximum(0,N0.grid_import_MW-H.import_cap_MW).max()),
 'N0_min_voltage_pu':float(N0.min_voltage_pu.min()),'N0_max_voltage_pu':float(N0.max_voltage_pu.max()),
 'DC_N1_all_hour_line_outages':n*nl,'DC_N1_hours_any_thermal_overload':int((nr>0).sum()),'DC_N1_max_branch_loading_pct':float(worst.max()),'DC_N1_island_outage_count':len(island),
 'AC_N1_all_hours_attempted':bool(args.full_ac_n1),'AC_N1_completed_all_93':bool(args.full_ac_n1 and len(records)==nl),'sampled_AC_N1_hours':len(idx),'sampled_AC_N1_line_outages':int((~AC1.islanding.astype(bool)).sum()),'sampled_AC_N1_solves':int(AC1.hours_evaluated.sum()),'sampled_AC_N1_any_fail_solutions':int(AC1.any_failure_hours.fillna(0).sum()),'sampled_AC_N1_nonconverged_solutions':int(AC1.nonconverged_hours.fillna(0).sum()),
 'elapsed_s':round(time.time()-t0,2), 'limits':['This is a synthetic network, not BC Hydro N-1 security.','Full AC N-1 applies ONLY to hypothetical fixed dispatch and synthetic topology.','No corrective AC redispatch, no fault/dynamic stability, transformer/VAR certificates, or physical nodal constraints.','DC N1 thermal screen is based on 1/x and fixed injections, excludes voltage and reactive power.','PQ reactive load 4% of modeled active load is an assumed idealized compensation.']}
(R/('NOV8_09_ROBUST_synthetic_AC_DC_security_summary_full.json' if args.full_ac_n1 else 'NOV8_09_ROBUST_synthetic_AC_DC_security_summary.json')).write_text(json.dumps(summary,indent=2))
print(json.dumps(summary,indent=2),flush=True)
