#!/usr/bin/env python3
"""Exhaustive hourly fixed-dispatch *nonlinear PQ AC* N-0/N-1 screening (NOT AC OPF).

All 140,160 historical model hours x 93 branch outages plus the intact network.
Based solely on a SYNTHETIC 37-bus 93-branch topology (not a BC Hydro model).
Hourly renewable production, curtailment, battery, fuel, and grid set points are
those of the previously saved chronological (nominal I²R) dispatch. A nonlinear
AC solution is obtained for each hourly fixed injection vector; this does not
reoptimize nodal dispatch, run voltage controllers, enforce future fuel inventory
or model actual utility protection/dynamic N-1. The external slack is *not*
implicitly treated as having unlimited import rights: actual AC slack power
is explicitly checked against 2500 MW import / 3000 MW export.

Run from RESEARCH_CODE/ with:
 OPENBLAS_NUM_THREADS=1 python GRID_CONNECTED_REOPT/FULL_16YR_LOSS_AWARE/run_full_hourly_ac_n1.py
Optional --max-hours 8760 for a scientifically labeled shorter diagnostic run.
"""
import os,sys,json,time,argparse
from pathlib import Path
import numpy as np,pandas as pd
HERE=Path(__file__).resolve().parent.parent
OUT=HERE/'CORRECTIVE_SENSITIVITY'
OUT.mkdir(exist_ok=True)
G=HERE.parent; RC=G.parent
sys.path[:0]=[str(RC),str(RC/'LARGE_TURBINE_STUDY'),str(RC/'MODEL_CORE'),str(G)]
from model_8mw_10mw import build_inputs
p=argparse.ArgumentParser();p.add_argument('--max-hours',type=int,default=140160);p.add_argument('--block',type=int,default=2048);p.add_argument('--max-contingencies',type=int,default=93);args=p.parse_args()
D=json.loads((G/'reoptimized_grid_case.json').read_text()); win=list(D['wind_capacity_GW_by_site'])
cap=np.array(list(D['wind_capacity_GW_by_site'].values()),float)
ledger=pd.read_csv(HERE/'nominal_i2r_hourly_2010_2025.csv.gz')
buses=pd.read_csv(G/'N1_QSUPPORT_loss_aware/assumed_buses.csv'); lines=pd.read_csv(G/'N1_QSUPPORT_loss_aware/assumed_branches.csv')
bi={v:i for i,v in enumerate(buses.bus)};nb=len(bi); ii=np.array([bi[r.a] for r in lines.itertuples()]);jj=np.array([bi[r.b] for r in lines.itertuples()]); yy=1/(lines.r_pu.to_numpy()+1j*lines.x_pu.to_numpy()); rt=lines.rating_mva.to_numpy(float)
# Model-only conductor/terminal rating increase, no network physics altered.
upgraded=lines.line.str.contains(r'500kV_wind_collector:W_(?:pennask_mountain_summit|mount_mabel_summit|cache_wind_northern_area_proxy)',regex=True).to_numpy()
assert upgraded.sum()==6
rt[upgraded]*=1.13
assert nb==37 and len(lines)==93 and len(ledger)==140160
n=min(len(ledger),args.max_hours)
assert n>0
print('reconstructing sixteen historical wind-region vectors',flush=True)
t0=time.time(); groups,W,S,H,L,site=build_inputs('SANY_SI19580_8MW',.4)
wind=np.moveaxis(W,1,2).reshape(140160,5)*cap[None,:]
solar=np.asarray(S).reshape(-1)*D['solar_GW'];hydro=np.asarray(H).reshape(-1);wind=wind[:n];solar=solar[:n];hydro=hydro[:n];ledger=ledger.iloc[:n]
assert len(wind)==n
load=ledger.facility_and_booster_load_MWh.to_numpy(float)
solarhyd=solar+hydro
# Chronological model assumes proportional curtailment of all generation streams.
frac=np.clip(ledger.renewables_delivered_MWh.to_numpy(float)/np.maximum(1e-9,ledger.gross_renewable_generation_MWh.to_numpy(float)),0,1)
pnode=np.zeros((n,nb),dtype=np.float64);qnode=np.zeros((n,nb),dtype=np.float64)
loads=[bi[x] for x in buses.bus if x.startswith('L_')];widx=[bi['W_'+k] for k in win]
local=(solarhyd*frac +ledger.battery_discharge_MW.to_numpy(float)-ledger.battery_charge_MW.to_numpy(float)+ledger.B100_MWh.to_numpy(float)+ledger.HVO_MWh.to_numpy(float)+ledger.emergency_gas_MWh.to_numpy(float)-load+ledger.unserved_MWh.to_numpy(float))/17
pnode[:,loads]=local[:,None];qnode[:,loads]=-load[:,None]/17*.04
pnode[:,widx]=wind*frac[:,None]
spec=(pnode+1j*qnode)/1000
# Explicit conservation check for injection/settlement accounting, before actual AC losses.
ledger_net=ledger.grid_import_MW.to_numpy(float)-ledger.grid_export_MW.to_numpy(float)
expected=ledger.network_loss_MWh.to_numpy(float)-ledger_net
residual=np.abs(pnode.sum(axis=1)-expected)
assert residual.max()<0.002,('P balance inconsistency MW',residual.max())
print('reconstruction complete (s):',round(time.time()-t0,1),'max P balance error MW',residual.max(),flush=True)

def Ymatrix(out):
 Y=np.zeros((nb,nb),complex)
 for k in range(len(lines)):
  if k==out:continue
  i,j=ii[k],jj[k];y=yy[k];Y[i,i]+=y;Y[j,j]+=y;Y[i,j]-=y;Y[j,i]-=y
 return Y

# Based on fixed-point AC current-injection equations: Y_nn V_n + Y_n0 V_0 = conj(S_n/V_n).
# This is nonlinear AC power flow, NOT linear DC loss or a heuristic voltage approximation.
# V0 = 1+j0; no time-dependent transformer taps or dynamic reactive control is modeled.
# A failure to converge is a failed check, NOT an implicitly feasible hour.
worst=pd.DataFrame({'year':ledger.year.to_numpy(),'hour_of_year':ledger.hour.to_numpy(),'n1_failed_solutions':np.zeros(n,int),'n1_voltage_failure_count':np.zeros(n,int),'n1_thermal_failure_count':np.zeros(n,int),'n1_grid_limit_failure_count':np.zeros(n,int),'n1_nonconvergence_count':np.zeros(n,int),'worst_min_voltage_pu':np.full(n,np.inf),'worst_max_branch_loading_pct':np.zeros(n),'maximum_grid_import_mw':np.full(n,-np.inf),'maximum_grid_export_mw':np.zeros(n),'highest_ac_losses_mw':np.zeros(n)})
rows=[];t0=time.time();nr=min(args.max_contingencies,93)
selected=np.where(upgraded)[0].tolist()
for out in [-1]+selected:
 Y=Ymatrix(out)
 Z=np.linalg.inv(Y[1:,1:]);f=-Z@Y[1:,0]
 active=np.arange(len(lines))!=out
 # bus endpoints already contain per-unit voltage scaling
 ai=ii[active];aj=jj[active];ay=yy[active];ratings=rt[active]
 conv=np.zeros(n,bool);vmlo=np.full(n,np.nan);vmhi=np.full(n,np.nan);loading=np.full(n,np.nan);import_mw=np.full(n,np.nan);export_mw=np.full(n,np.nan);ac_losses=np.full(n,np.nan)
 maxres=0.
 for st in range(0,n,args.block):
  en=min(st+args.block,n);a=spec[st:en,1:];v=np.ones((len(a),nb),complex)
  # A first-order voltage seed accelerates nonlinear iterations, but final checks use actual AC mismatch.
  v[:,1:]=f[None,:]+np.conj(a)@Z.T
  for k in range(35):
   new=f[None,:]+np.conj(a/v[:,1:])@Z.T
   delta=np.nanmax(np.abs(new-v[:,1:]),axis=1)
   v[:,1:]=.7*new+.3*v[:,1:]
   if np.nanmax(delta)<2e-8:break
  # Enforce actual nonlinear KCL/PQ equation (not solver step-size alone).
  current=(v[:,1:]@Y[1:,1:].T)+Y[1:,0][None,:]
  mismatch=np.nanmax(np.abs(v[:,1:]*np.conj(current)-a),axis=1)
  maxres=max(maxres,float(np.nanmax(mismatch)))
  ok=np.isfinite(mismatch)&(mismatch<1e-6)&np.all(np.isfinite(v),axis=1)
  voltage=np.abs(v[:,1:]);vmlo[st:en]=np.nanmin(voltage,axis=1);vmhi[st:en]=np.nanmax(voltage,axis=1)
  # exact nonlinear AC complex power at the GRID slack and both line terminals
  slack=v[:,0]*np.conj(Y[0,0]*v[:,0]+(v[:,1:]@Y[0,1:]))*1000
  import_mw[st:en]=np.maximum(0,slack.real);export_mw[st:en]=np.maximum(0,-slack.real)
  Vi=v[:,ai];Vj=v[:,aj];Sij=Vi*np.conj((Vi-Vj)*ay[None,:])*1000; Sji=Vj*np.conj((Vj-Vi)*ay[None,:])*1000
  loading[st:en]=100*np.nanmax(np.maximum(np.abs(Sij),np.abs(Sji))/ratings[None,:],axis=1)
  ac_losses[st:en]=(Sij.real+Sji.real).sum(axis=1)
  conv[st:en]=ok
 voltfail=(vmlo<.95-1e-6)|(vmhi>1.05+1e-6)
 thermfail=loading>100+1e-4
 gridfail=(import_mw>2500.001)|(export_mw>3000.001)
 bad=~conv|voltfail|thermfail|gridfail
 worst['n1_failed_solutions']+=bad.astype(int)
 worst['n1_voltage_failure_count']+=voltfail.astype(int)
 worst['n1_thermal_failure_count']+=thermfail.astype(int)
 worst['n1_grid_limit_failure_count']+=gridfail.astype(int)
 worst['n1_nonconvergence_count']+=(~conv).astype(int)
 worst['worst_min_voltage_pu']=np.minimum(worst.worst_min_voltage_pu,vmlo)
 worst['worst_max_branch_loading_pct']=np.maximum(worst.worst_max_branch_loading_pct,loading)
 worst['maximum_grid_import_mw']=np.maximum(worst.maximum_grid_import_mw,import_mw)
 worst['maximum_grid_export_mw']=np.maximum(worst.maximum_grid_export_mw,export_mw)
 worst['highest_ac_losses_mw']=np.maximum(worst.highest_ac_losses_mw,ac_losses)
 rows.append({'contingency':'N0' if out<0 else lines.iloc[out]['line'],'hours_solved':n,'nonconverged_hours':int((~conv).sum()),'voltage_failure_hours':int(voltfail.sum()),'thermal_failure_hours':int(thermfail.sum()),'grid_limit_failure_hours':int(gridfail.sum()),'any_failure_hours':int(bad.sum()),'minimum_voltage_pu':float(np.nanmin(vmlo)),'maximum_voltage_pu':float(np.nanmax(vmhi)),'maximum_branch_loading_pct':float(np.nanmax(loading)),'maximum_grid_import_MW':float(np.nanmax(import_mw)),'maximum_grid_export_MW':float(np.nanmax(export_mw)),'mean_ac_resistive_losses_MW':float(np.nanmean(ac_losses)),'max_solver_mismatch_pu':maxres})
 if out<0:
  pd.DataFrame({'year':ledger.year.to_numpy(),'hour_of_year':ledger.hour.to_numpy(),'min_bus_voltage_pu':vmlo,'max_bus_voltage_pu':vmhi,'max_branch_loading_pct':loading,'ac_grid_import_mw':import_mw,'ac_grid_export_mw':export_mw,'ac_losses_mw':ac_losses,'converged':conv,'any_constraint_failure':bad}).to_csv(OUT/'reinforced_n0_hourly.csv.gz',index=False,compression='gzip',float_format='%.7f')
 if out%10==0 or out==-1:print('outage',out,'/',nr,'fail',int(bad.sum()),'elapsed_s',round(time.time()-t0,1),flush=True)

a=pd.DataFrame(rows);a.to_csv(OUT/'reinforced_selected_contingencies.csv',index=False)
worst.to_csv(OUT/'reinforced_seven_cases_hourly_worstcase.csv.gz',index=False,compression='gzip')
summary={'method':'nonlinear fixed-PQ balanced AC load flow for historical chronological fixed dispatch, intact + each single branch outage; not AC OPF and not a BC Hydro network','hours':n,'branch_outages_completed':nr,'n0_and_n1_cases':len(rows),'nonlinear_power_flow_cases_evaluated':n*(nr+1),'complete_140160x93_branch_sweep':False,'total_failed_ac_cases':int(a.any_failure_hours.sum()),'total_nonconverged_cases':int(a.nonconverged_hours.sum()),'n0_failed_hours':int(a.iloc[0].any_failure_hours),'hours_with_any_n1_failure':int((worst.n1_failed_solutions>0).sum()),'hourly_energy_balance_baseline_max_discrepancy_MW':float(residual.max()),'max_branch_loading_pct':float(a.maximum_branch_loading_pct.max()),'worst_min_voltage_pu':float(a.minimum_voltage_pu.min()),'max_grid_import_MW':float(a.maximum_grid_import_MW.max()),'max_grid_export_MW':float(a.maximum_grid_export_MW.max()),'mean_n0_ac_losses_MW':float(a.iloc[0].mean_ac_resistive_losses_MW),'elapsed_seconds':round(time.time()-t0,2),'notes':['No corrective redispatch or fuel inventory recalculation after N-1; failures are screens, not optimized outcomes.','All 37 buses, 93 parallel circuits, 17 campus allocation and 931 MVAr idealized Q correction are hypothetical.','The AC grid slack is independently checked against external access caps; these have not been contracted.','No PV bus generator Q limits, load-dependent losses feedback, tap controls, harmonics, fault duty or dynamic protections.']}
(OUT/'reinforced_partial_summary_DO_NOT_USE_AS_FULL_SWEEP.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2),flush=True)
