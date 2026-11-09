#!/usr/bin/env python3
"""Re-run source-derived connected-case wind allocation and inspect static reactive-support screens.
This is a reproducibility audit of existing assumptions, not independent site certification.
"""
from pathlib import Path
import sys,json,math
import pandas as pd,numpy as np
HERE=Path(__file__).resolve().parent;RC=HERE.parent
sys.path[:0]=[str(RC),str(RC/'MODEL_CORE'),str(RC/'LARGE_TURBINE_STUDY')]
from model_8mw_10mw import build_inputs
j=json.loads((HERE/'reoptimized_grid_case.json').read_text());c=j['wind_capacity_GW_by_site']
assert list(c)==['pennask_mountain_summit','mount_mabel_summit','nicola_wind_project_regional_proxy','cache_wind_northern_area_proxy','highland_valley_wind_project_area']
assert [round(v,3) for v in c.values()]==[1.968,1.832,0.048,1.976,0.032]
assert math.isclose(sum(c.values()),5.856,abs_tol=1e-10)
g,W,S,H,L,sites=build_inputs('SANY_SI19580_8MW',0.4)
cf_after=[float(np.mean(W[:,i,:])/1000) for i in range(5)];cf_before=[s['screened_cf'] for s in sites]
w_after=sum(v*x for v,x in zip(c.values(),cf_after))/sum(c.values());w_before=sum(v*x for v,x in zip(c.values(),cf_before))/sum(c.values())
assert abs(w_after-.33596137405)<5e-6 and abs(w_before-.35755890749)<5e-6
summary=[]
for folder in ['N1_QSUPPORT_q022','N1_QSUPPORT_q010','N1_QSUPPORT_q008','N1_QSUPPORT_q004']:
 d=pd.read_csv(HERE/folder/'ac_voltage_screen.csv');v=d[d.scenario=='connected_winter_import2500_export3000'];summary.append(dict(case=folder,points=len(v),breaches=int((v.ac_voltage_violations>0).sum()),min_pu=float(v.min_bus_vm_pu.min()),unserved_mw=float(v.unserved_mw.max()),AC_converged=int(v.ac_converged.sum())))
assert [r['points'] for r in summary]==[99]*4
assert [r['breaches'] for r in summary]==[14,2,2,0]
assert all(r['AC_converged']==99 for r in summary)
assert all(r['unserved_mw']<.001 for r in summary)
# 17 campus buses, winter ~5.1728 GW system load, Q 0.22 -> 0.04 net ratio
peak=((36.00486+.246358418)*1e6/8760)*1.25
mvar=peak*(.22-.04)
assert abs(mvar-931.110062)<.02
print(json.dumps({'selected_GW':sum(c.values()),'turbines':round(sum(c.values())/.008),'CF_after_six_percent_loss':w_after,'CF_before_loss':w_before,'reactive_MVAr_ideal':mvar,'winter_AC_99cases':summary},indent=2))
