#!/usr/bin/env python3
"""Small, deterministic post-selection joint-stress screen, not a new optimisation certificate."""
import os,json,time
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
from pathlib import Path
import numpy as np,pandas as pd,sys
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'code'))
from evidence_model import load_inputs,run_case,price,HVO_CAP
out=root/'results'
base=np.array(json.loads((out/'NOV8_08_rounded_robust_summary.json').read_text())['integer8MW_portfolio'])
inp,years,_,_=load_inputs()
train={k:(v[:10] if k!='Q' else v) for k,v in inp.items()}
held={k:(v[10:] if k!='Q' else v) for k,v in inp.items()}
rows=[]
options=[]
for solar in [base[5],22.,27.,35.]:
 for batt in [base[6],35.,50.,70.]:
  c=base.copy();c[5]=solar;c[6]=batt
  options.append((f'pv{solar:.2f}_batt{batt:.2f}',c))
# A separate feasible mathematical upper bound for permitted wind-site capacity
c=base.copy();c[:5]=[2,2,.2,2,2];options.append(('wind_site_upper_bound',c))
print('n',len(options),flush=True)
t0=time.time()
for j,(name,c) in enumerate(options):
 for part,ip in [('train_2010_2019',train),('heldout_2020_2025',held)]:
  for test,grid,wind,engine in [('central',1.,1.,5100.),('combined_adverse',.5,.9,2720.)]:
   d=dict(ip);d['IC']=ip['IC']*grid;d['EC']=ip['EC']*grid
   a,_=run_case(c,d,engine=engine,wind=wind,record=False)
   shed=float(a[:,1].sum());fuel=float(a[:,0].max())
   rows.append({'candidate':name,'period':part,'test':test,'wind_GW':float(sum(c[:5])),'solar_GW':float(c[5]),'battery_GWh':float(c[6]),'unserved_GWh':shed,
                'peak_annual_HVO_ML':fuel,'fuel_headroom_ML':float(HVO_CAP-fuel),'cost_CAD_MWh_if_served':price(c,a) if shed<1e-6 else np.nan})
 print(j+1,name,'elapsed',round(time.time()-t0,1),flush=True)
D=pd.DataFrame(rows);D.to_csv(out/'NOV8_09_joint_stress_capacity_sensitivity.csv',index=False,float_format='%.8f')
summary={'status':'scenario screen only, not globally optimal or physically secure', 'options':len(options),
         'min_train_joint_unserved_GWh':float(D[(D.period=='train_2010_2019')&(D.test=='combined_adverse')].unserved_GWh.min()),
         'min_heldout_joint_unserved_GWh':float(D[(D.period=='heldout_2020_2025')&(D.test=='combined_adverse')].unserved_GWh.min()),
         'combined_zero_train_candidates':D[(D.period=='train_2010_2019')&(D.test=='combined_adverse')&(D.unserved_GWh<1e-6)].candidate.tolist(),
         'combined_zero_heldout_candidates':D[(D.period=='heldout_2020_2025')&(D.test=='combined_adverse')&(D.unserved_GWh<1e-6)].candidate.tolist(),
         'fixed_assumptions':'Wind site capacities frozen at rounded robust candidate except one separate upper-bound case; fuel ceiling and delivery reset from source model; synthetic grid shape; no AC/security or extra procurement.',
         'elapsed_s':round(time.time()-t0,2)}
(out/'NOV8_09_joint_stress_capacity_sensitivity_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2),flush=True)
