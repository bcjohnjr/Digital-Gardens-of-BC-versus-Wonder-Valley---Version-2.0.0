import bootstrap
from bootstrap import ROOT
from pathlib import Path
import shutil,json,hashlib,sys,time
import numpy as np

source=ROOT.parent/'NOV8_Referee_Response/01_Complete_Research/RESEARCH_CODE'
target=ROOT/'baseline/RESEARCH_CODE'
if not target.exists():
 shutil.copytree(source,target,ignore=shutil.ignore_patterns('__pycache__','*.nbc','*.nbi'))
sys.path[:0]=[str(target/'LARGE_TURBINE_STUDY'),str(target/'GRID_CONNECTED_REOPT')]
from model_8mw_10mw import build_inputs
import reoptimize_grid as R
start=time.monotonic()
groups,W,S,H,L,sites=build_inputs('SANY_SI19580_8MW',.4)
boost=np.load(target/'GRID_CONNECTED_REOPT/dryer_booster_hourly_MWh.npy')
ip,ep=R.make_prices(groups,S,'hourly_scarcity')
np.savez_compressed(ROOT/'inputs/model_inputs.npz',W=W,S=S,H=H,L=L,boost=boost,ip=ip,ep=ep,years=np.array([g['year'] for g in groups]))
base=json.loads((target/'GRID_CONNECTED_REOPT/reoptimized_grid_case.json').read_text())
caps=np.array(list(base['wind_capacity_GW_by_site'].values())+[base['solar_GW'],base['battery_GWh']])
out=R.evaluate_all(caps,W,S,H,L,ip,ep,boost)
price,stats=R.cost_x(caps,out)
assert abs(price-base['selected_case']['total_CAD_MWh'])<1e-6
report={'baseline_cost_reproduced':price,'baseline_reference_cost':base['selected_case']['total_CAD_MWh'],'stats':stats,'sites':sites,'seconds':time.monotonic()-start,'scientific_source':str(source),'note':'Original model reproduced unchanged; pooled no-loss cost, not the 192.47 loss-aware screen.'}
(ROOT/'results/baseline_reproduction.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2),flush=True)
