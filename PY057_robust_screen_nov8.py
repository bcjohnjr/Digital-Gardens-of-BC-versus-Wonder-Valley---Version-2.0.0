"""Transparent fixed technology robust design screening, not globally optimal or physically certified.
Loads independently prepared input arrays and uses the original dispatch kernel.
"""
from pathlib import Path
import json,time,itertools
import numpy as np,pandas as pd
from evidence_model import load_inputs,run_case,price,HVO_CAP
ROOT=Path(__file__).resolve().parents[1]; out=ROOT/'results'; out.mkdir(exist_ok=True)
inp,years,v,rating=load_inputs()
fit=json.loads((out/'fit_results.json').read_text());base=np.asarray(fit['selected_capacities'])
# A priori candidate grid, nowhere asserted as a true engineering optimum.
winds={'frozen':base[:5].copy(),'higher_wind':np.array([2,2,.2,2,1.2]),'full_siting':np.array([2,2,.2,2,2.])}
# Existing model bounds: solar<=35 GW, battery<=70 GWh; larger turbines need site review.
plans=[('frozen',float(base[5]),float(base[6]))]
for name,s,b in itertools.product(winds,[12.,20.,28.,35.],[8.,24.,50.,70.]):
 plans.append((name,s,b))
# Smaller screening subset: every plan checked in 10 training years for wind -10% and grid access 50%.
train={k:(a[:10] if k!='Q' else a) for k,a in inp.items()}
rows=[];start=time.time()
for idx,(name,s,b) in enumerate(plans):
 c=np.r_[winds[name],s,b]
 scenarios=[('wind_minus10',train,5100,.9),('half_access',dict(train,IC=train['IC']*.5,EC=train['EC']*.5),5100,1.),('joint_wind_minus10_half_access',dict(train,IC=train['IC']*.5,EC=train['EC']*.5),2720,.9)]
 score=0.;metrics={};fuel=0.
 for label,ii,eng,wind in scenarios:
  a,_=run_case(c,ii,engine=eng,wind=wind,record=False)
  shed=float(a[:,1].sum());fuel=max(fuel,float(a[:,0].max()))
  metrics[label+'_GWh_2010_2019']=shed
  score=max(score,shed)
 aa,_=run_case(c,train,record=False)
 row={'plan':f'{name}_solar{s:g}_battery{b:g}','wind_GW':c[:5].sum(),'solar_GW':s,'battery_GWh':b,'cost_CAD_MWh_if_served':price(c,aa),'training_max_stress_unserved_GWh':score,'max_stress_HVO_ML_y':fuel,**metrics,'c':c.tolist()}
 rows.append(row)
 if (idx+1)%8==0: print('screen',idx+1,'of',len(plans),'elapsed',round(time.time()-start,1),'top',min(x['training_max_stress_unserved_GWh'] for x in rows),flush=True)
ranked=sorted(rows,key=lambda x:(x['training_max_stress_unserved_GWh']>1e-3, x['training_max_stress_unserved_GWh'],x['cost_CAD_MWh_if_served']))
pd.DataFrame([{k:v for k,v in x.items() if k!='c'} for x in rows]).to_csv(out/'NOV8_08_robust_candidate_training_screen.csv',index=False)
# Independently evaluate the top 8 stress-score candidates across all 16 yrs; also check a lower-cost near-feasible mix.
final=[];chosen={x['plan']:x for x in ranked[:8]};costsorted=sorted([x for x in rows if x['training_max_stress_unserved_GWh']<100],key=lambda x:x['cost_CAD_MWh_if_served'])
for x in costsorted[:3]:chosen[x['plan']]=x
for plan,x in chosen.items():
 c=np.asarray(x['c']);d=[]
 for label,access,wind,engine in [('central',1,1,5100),('wind_minus10',1,.9,5100),('half_access',.5,1,5100),('local_160mw',1,1,2720),('joint_wind_minus10_half_access_local160',.5,.9,2720)]:
  ii=dict(inp,IC=inp['IC']*access,EC=inp['EC']*access)
  a,h=run_case(c,ii,engine=engine,wind=wind,record=True)
  d.append({'plan':plan,'scenario':label,'wind_GW':c[:5].sum(),'solar_GW':c[5],'battery_GWh':c[6],
            'unserved_GWh':float(a[:,1].sum()),'unserved_hours':int((h[:,9]>1e-6).sum()),'mean_import_TWh_y':float(a[:,2].mean()),
            'max_HVO_ML_y':float(a[:,0].max()),'mean_HVO_ML_y':float(a[:,0].mean()),'max_engine_MW':float(a[:,12].max()),
            'cost_CAD_MWh_IF_FULL_SERVICE':(float(price(c,a)) if float(a[:,1].sum())<=1e-6 else float('nan')),'training_peak_stress_unserved_GWh':x['training_max_stress_unserved_GWh']})
 final+=d
 print('full',plan,'worstunserved',max(r['unserved_GWh'] for r in d),'elapsed',round(time.time()-start,1),flush=True)
df=pd.DataFrame(final);df.to_csv(out/'NOV8_08_robust_candidate_full16.csv',index=False)
summary={'status':'technology and dispatch sensitivity only, NOT global optimality or grid feasibility', 'training_candidates':len(rows),'full16_checked_plans':len(chosen), 'scenarios_for_full16':5,'elapsed_seconds':round(time.time()-start,2),'HVO_cap_ML_per_year':HVO_CAP,'best_training_plan':ranked[0]['plan'],'best_training_worst_unserved_GWh':ranked[0]['training_max_stress_unserved_GWh']}
(out/'NOV8_08_robust_screen_summary.json').write_text(json.dumps(summary,indent=2))
print(json.dumps(summary,indent=2),flush=True)
