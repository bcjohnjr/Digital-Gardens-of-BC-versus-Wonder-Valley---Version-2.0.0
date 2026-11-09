from evidence_model import load_inputs,run_case,price,summary,COL,ANNUAL
from pathlib import Path
import json,pandas as pd,numpy as np
ROOT=Path(__file__).resolve().parents[1];R=ROOT/'results'
s=json.loads((R/'NOV8_08_robust_DE_summary.json').read_text())
x=min([z for z in s['solutions'] if z['type']=='8MW_roundup'],key=lambda x:x['score']);c=np.array(x['capacities'])
inp,years,v,r=load_inputs();rows=[]
for name,access,wind,engine in [('central',1,1,5100),('wind_minus10',1,.9,5100),('half_access',.5,1,5100),('local_160mw',1,1,2720),('joint_adverse',.5,.9,2720)]:
 ii=dict(inp,IC=inp['IC']*access,EC=inp['EC']*access)
 a,h=run_case(c,ii,engine=engine,wind=wind,record=True)
 times=[]
 for year in years:
  idx=pd.date_range(f'{year}-01-01',f'{year+1}-01-01',freq='h',inclusive='left');times.extend(idx[~((idx.month==2)&(idx.day==29))])
 hd=pd.DataFrame(h,columns=COL);hd.insert(0,'time_utc',times)
 if name=='central':hd.to_csv(R/'NOV8_08_rounded_robust_central_hourly.csv.gz',index=False,compression='gzip',float_format='%.8f')
 ad=pd.DataFrame(a,columns=ANNUAL);ad.insert(0,'year',years);ad.insert(0,'scenario',name);ad.to_csv(R/f'NOV8_08_rounded_robust_{name}_annual.csv',index=False)
 rows.append({'scenario':name,'unserved_GWh':float(a[:,1].sum()),'unserved_hours':int((h[:,9]>1e-6).sum()),'mean_HVO_ML_y':float(a[:,0].mean()),'peak_HVO_ML_y':float(a[:,0].max()),'mean_import_TWh_y':float(a[:,2].mean()),'conditional_cost_CAD_MWh_ONLY_IF_fully_served':(float(price(c,a)) if float(a[:,1].sum())<=1e-6 else None)})
assert all(x['unserved_GWh']<1e-5 for x in rows[:3]),rows
out={'integer8MW_portfolio':c.tolist(),'wind_GW':float(c[:5].sum()),'turbine_count':int(np.rint(c[:5].sum()*1000/8)), 'solar_GW':float(c[5]), 'battery_GWh':float(c[6]),'training_selected_from':'2010–2019 only', 'results':rows,'cost_scope':'No physical grid upgrades, fuel contracting, siting, AC/N1, construction safety or market access fees','interpretation':'Exploratory robust to separate stresses in the pooled model only; joint stress remains unmet'}
(R/'NOV8_08_rounded_robust_summary.json').write_text(json.dumps(out,indent=2)+'\n')
pd.DataFrame(rows).to_csv(R/'NOV8_08_rounded_robust_scenario_summary.csv',index=False)
print(json.dumps(out,indent=2))
