#!/usr/bin/env python3
"""Kamloops local receiving-water FIRST-ORDER heat-mixing screen, not thermal permit model.

Q scenarios are illustrative, not gauge statistics. Station 08LF023 (Thompson River
at Kamloops) offers actual flow observations; live 309 m3/s on 30 Oct 2026 was a
single time point, not a low-flow Q95. Source Water Survey of Canada.
"""
from pathlib import Path
import sys,json
import numpy as np,pandas as pd
HERE=Path(__file__).resolve().parent;RC=HERE.parent
sys.path.insert(0,str(RC))
import industrial_drying as dr
import profit_community_model as pcm
T=pcm.load_temps();surplus,served,months,_=dr.base_heat(T)
dr.PRICE['schedule_boost_to_curtailment']=False
rows,rem,el=dr.run_drying(surplus,months,np.zeros(len(months)),dr.MARKETS)
node='kamloops';heat=rem[node]
# P (MW) = Q(m3/s) * 4.186(MJ/(m3 K)) * deltaT(K)
rows=[]
for ptag,p in [('annual_mean',float(np.mean(heat))),('p95',float(np.percentile(heat,95))),('max',float(np.max(heat)))]:
    for q in [50,100,200,309,500]:
        for mixing in [.05,.10,.25,1.]:
            dT=p/(4.186*q*mixing)
            rows.append(dict(node=node,heat_case=ptag,rejected_heat_MW=p,flow_m3_s=q,
                    mixed_fraction=mixing,temp_rise_C=dT,flow_needed_for_1C_m3_s=p/(4.186*mixing),
                    stated_flow_data_status='illustrative; only 309 m3/s is observed 2026-10-30 snapshot'))
res=pd.DataFrame(rows)
res.to_csv(HERE/'kamloops_thompson_river_mixing_screen.csv',index=False,float_format='%.6f')
summary={'node':node,'receiving_water':'Thompson River at Kamloops','hydrometric_station':'Water Survey of Canada 08LF023',
   'observed_one_day_flow_reference':'309 m3/s at 2026-10-30 (source cited in article; not Q95)',
   'heat_rejected_twh_y':float(heat.sum()/(len(heat)/8760)/1e6),'mean_heat_MW':float(np.mean(heat)),
   'p95_heat_MW':float(np.percentile(heat,95)),'max_heat_MW':float(np.max(heat)),
   'max_full_mixing_deltaT_at_309m3s_C':float(max(heat)/(4.186*309)),
   'max_10pct_mixing_deltaT_at_309m3s_C':float(max(heat)/(4.186*309*.1)),
   'flow_to_hold_peak_deltaT_under_1C_at_10pct_mixing_m3s':float(max(heat)/(4.186*.1)),
   'conclusion':'No compliance finding: local flows, outfall placement, stratification, baseline temperatures and fish habitat needed; use dry coolers when water impacts too high.'}
(HERE/'river_mixing_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))
