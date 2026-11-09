#!/usr/bin/env python3
"""Exploratory robust multi-scenario optimization: train on 2010–19, evaluate held-out 2020–25.
Not a real network/security or land siting optimization; no AC or manufacturing constraints.
"""
import json,time,sys
from pathlib import Path
import numpy as np,pandas as pd
from scipy.optimize import differential_evolution
from evidence_model import load_inputs,run_case,price,HVO_CAP
ROOT=Path(__file__).resolve().parents[1];R=ROOT/'results';R.mkdir(exist_ok=True)
inp,years,_,_=load_inputs(); fit=json.loads((R/'fit_results.json').read_text()); base=np.array(fit['selected_capacities'])
train={k:(v[:10] if k!='Q' else v) for k,v in inp.items()}
held={k:(v[10:] if k!='Q' else v) for k,v in inp.items()}
HVO_HEADROOM=HVO_CAP*.9
stress=[('central',1.,1.,5100.),('wind_minus10',1.,.9,5100.),('access_half',.5,1.,5100.)]

def evaluate(c,inp,with_joint=False):
 rows=[]
 scenarios=stress+([('wind_minus10_access_half_engine2720',.5,.9,2720.)] if with_joint else [])
 for name,access,wind,eng in scenarios:
  ii=dict(inp);ii['IC']=inp['IC']*access;ii['EC']=inp['EC']*access
  a,_=run_case(c,ii,engine=eng,wind=wind,record=False)
  rows.append({'scenario':name,'unserved_GWh':float(a[:,1].sum()),'peak_HVO_ML_y':float(a[:,0].max()),'cost_CAD_MWh_IF_served':float(price(c,a)),'mean_HVO_ML_y':float(a[:,0].mean()),'mean_import_TWh_y':float(a[:,2].mean())})
 return rows
counter=0; start=time.time();hist=[]
def objective(c):
 global counter
 counter+=1
 rows=evaluate(c,train)
 p=max(r['unserved_GWh'] for r in rows)
 f=max(0.,max(r['peak_HVO_ML_y'] for r in rows)-HVO_HEADROOM)
 score=max(r['cost_CAD_MWh_IF_served'] for r in rows)+1.e3*p+1.e2*f
 return score
bounds=[(0.,2),(0.,2),(0.,.2),(0.,2),(0.,2),(2.,35.),(3.,70.)]
selected=[]
for seed in [681,682]:
 result=differential_evolution(objective,bounds,seed=seed,maxiter=28,popsize=6,tol=.005,polish=False,x0=base,workers=1)
 cand=np.asarray(result.x)
 # rounded wind turbine counts can alter results! round UP to 8MW and evaluate rounded separately
 rounded=cand.copy();rounded[:5]=np.ceil(cand[:5]/.008)*.008
 rounded[:5]=np.minimum(rounded[:5],[2,2,.2,2,2])
 for typ,c in [('continuous',cand),('8MW_roundup',rounded)]:
  r=evaluate(c,train);selected.append({'seed':seed,'type':typ,'capacities':c.tolist(),'score':float(objective(c)),'training':r})
 print('seed',seed,'elapsed',round(time.time()-start,1),'evaluations',counter,'score',result.fun,'cap',cand.tolist(),flush=True)
# Select by only training scores; no held-out leakage.
champ=min(selected,key=lambda r:r['score'])
rows=[]
for kind,c in [('frozen',base),('robust_training_candidate',np.array(champ['capacities']))]:
 for label,ip in [('training_2010_2019',train),('heldout_2020_2025',held),('full_2010_2025',inp)]:
  for s in evaluate(c,ip,with_joint=True): rows.append({'portfolio':kind,'period':label,'wind_GW':float(c[:5].sum()),'solar_GW':float(c[5]),'battery_GWh':float(c[6]),'capacity_vector':json.dumps(c.tolist()),**s})
DF=pd.DataFrame(rows);DF.loc[DF.unserved_GWh>1e-6,'cost_CAD_MWh_IF_served']=np.nan;DF.to_csv(R/'NOV8_08_robust_DE_comparison.csv',index=False)
summary={'type':'exploratory differential evolution fixed static capacity multi-scenario screen (not construction feasibility)',
 'selection_from':'2010-2019 training periods only','validation':'2020-2025 held-out with respect to these new capacity choices, but not to original underlying weather calibration',
 'training_stresses':[r[0] for r in stress], 'joint_stress_heldout_only':True,
 'site_wind_max_GW':[2,2,.2,2,2], 'solar_max_GW':35,'battery_max_GWh':70,
 'fuel_limit_ML_y':HVO_CAP,'minimum_supply_headroom_fraction_for_training_stresses':.1,
 'engine_limits':['5100 MW central/wind/access independent','2720 MW only joint sensitivity, not training'],
 'seeds':[681,682],'solutions':selected,'selected':champ,
 'elapsed_s':round(time.time()-start,2),'calls':counter,
 'cautions':['Numerical optimization searches a nonconvex engineering proxy, no global certificate','Source availability/fuel costs/land/siting/AC/N1/unmodelled firm-generation constraints are not optimized','Maximum 2 GW/site wind and 35 GW solar/70 GWh battery are assumed mathematical bounds','Cost applies only when full demand served and does not include grid-upgrade charges','No genuinely independent wind resource prediction.']}
(R/'NOV8_08_robust_DE_summary.json').write_text(json.dumps(summary,indent=2))
print('selected',json.dumps(champ,indent=2),flush=True)
print(DF.to_string(index=False),flush=True)
