#!/usr/bin/env python3
"""Algorithmic PQ power-flow cross-check on deterministic cases using scipy.optimize.root.
Independent algorithm but same synthetic topology and same injections; NOT independent physical network validation.
"""
import json,os,sys
from pathlib import Path
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
import numpy as np,pandas as pd
from scipy.optimize import root
base=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(base/'code'))
from evidence_model import load_inputs
inp,years,_,_=load_inputs()
G=base/'baseline/RESEARCH_CODE/GRID_CONNECTED_REOPT/N1_QSUPPORT_loss_aware'
B=pd.read_csv(G/'assumed_buses.csv');L=pd.read_csv(G/'assumed_branches.csv');n=len(B)
bi={name:k for k,name in enumerate(B.bus)}
a_idx=np.array([bi[x] for x in L.a]);b_idx=np.array([bi[x] for x in L.b])
y=1/(L.r_pu.to_numpy()+1j*L.x_pu.to_numpy())
loads=[bi[x] for x in B.bus if x.startswith('L_')]
ws=[bi['W_'+x] for x in json.loads((base/'baseline/RESEARCH_CODE/GRID_CONNECTED_REOPT/reoptimized_grid_case.json').read_text())['wind_capacity_GW_by_site']]
fit=json.loads((base/'results/fit_results.json').read_text())
rob=json.loads((base/'results/NOV8_08_rounded_robust_summary.json').read_text())
portfolio={'reference':(np.array(fit['selected_capacities']),base/'results/new_build_observed_shape_hourly.csv.gz'),
 'robust':(np.array(rob['integer8MW_portfolio']),base/'results/NOV8_08_rounded_robust_central_hourly.csv.gz')}
records=[]
for title,(cap,pth) in portfolio.items():
 H=pd.read_csv(pth)
 ix=[0,10000,70000,140159]
 wind=np.moveaxis(inp['W'],1,2).reshape(-1,5)[ix]*cap[:5]
 subset=H.iloc[ix]
 renew=subset[['wind_MW','solar_MW','hydro_MW']].sum(axis=1).to_numpy()
 frac=np.clip(1-subset.curtail_MW.to_numpy()/np.maximum(renew,1e-9),0,1)
 wind*=frac[:,None]
 loc=(subset.solar_MW.to_numpy()+subset.hydro_MW.to_numpy())*frac+subset.discharge_MW.to_numpy()-subset.charge_MW.to_numpy()+subset.B100_MW.to_numpy()+subset.HVO_MW.to_numpy()-subset.load_MW.to_numpy()+subset.unserved_MW.to_numpy()
 for i,h in enumerate(ix):
  spec=np.zeros(n,complex)
  spec[loads]=loc[i]/17/1000-1j*subset.load_MW.iloc[i]*0.04/17/1000
  spec[ws]=wind[i]/1000
  for removed in [-1,0,47,92]:
   Y=np.zeros((n,n),complex)
   for e in range(len(L)):
    if e==removed: continue
    a,b=a_idx[e],b_idx[e];yy=y[e]
    Y[a,a]+=yy;Y[b,b]+=yy;Y[a,b]-=yy;Y[b,a]-=yy
   def residual(x):
    V=np.r_[1.+0j,x[:n-1]+1j*x[n-1:]]
    S=V*np.conj(Y@V)
    r=S[1:]-spec[1:]
    return np.r_[r.real,r.imag]
   # One independent scipy nonlinear root solve
   r=root(residual,np.r_[np.ones(n-1),np.zeros(n-1)],method='hybr',options={'xtol':1e-11,'maxfev':3000})
   Vroot=np.r_[1.+0j,r.x[:n-1]+1j*r.x[n-1:]]
   # Direct Z-bus implicit fixed-point power flow, original algorithmic family
   Z=np.linalg.inv(Y[1:,1:]);f=-Z@Y[1:,0]
   V=np.r_[1.+0j,f+np.conj(spec[1:])@Z.T]
   for iteration in range(200):
    V_new=f+np.conj(spec[1:]/V[1:])@Z.T
    delta=max(abs(V_new-V[1:]));V[1:]=.7*V_new+.3*V[1:]
    if delta<1e-12:break
   sroot=Vroot[0]*np.conj((Y@Vroot)[0])*1000
   sfix=V[0]*np.conj((Y@V)[0])*1000
   rec={'portfolio':title,'hour_index':h,'removed_branch':removed,'root_solver_success':bool(r.success),
        'root_max_PQ_mismatch_pu':float(max(abs(residual(r.x)))),
        'fixed_point_max_PQ_mismatch_pu':float(max(abs(residual(np.r_[V[1:].real,V[1:].imag])))),
        'maximum_bus_voltage_difference_pu':float(max(abs(Vroot-V))),
        'slack_real_power_difference_MW':float(abs(sroot.real-sfix.real)),
        'slack_real_power_MW_newton':float(sroot.real)}
   records.append(rec)
   assert rec['root_max_PQ_mismatch_pu']<1e-7 and rec['fixed_point_max_PQ_mismatch_pu']<1e-7,rec
   assert rec['maximum_bus_voltage_difference_pu']<1e-6 and rec['slack_real_power_difference_MW']<1e-3,rec
D=pd.DataFrame(records);D.to_csv(base/'results/NOV8_09_independent_nonlinear_solver_crosscheck.csv',index=False,float_format='%.12g')
summary={'n_cases':len(D),'portfolios':list(portfolio),'hours_per_portfolio':4,'contingency_outages_tested':[-1,0,47,92],
 'scipy_root_all_converged':bool(D.root_solver_success.all()),
 'max_voltage_difference_pu':float(D.maximum_bus_voltage_difference_pu.max()),
 'max_slack_difference_MW':float(D.slack_real_power_difference_MW.max()),
 'max_PQ_mismatch_pu':float(D.root_max_PQ_mismatch_pu.max()),
 'qualification':'Algorithmic comparison using different numerical solvers but identical synthetic PQ equations and assumed injections; not independent validation of the grid or plant.'}
(base/'results/NOV8_09_independent_nonlinear_solver_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))
