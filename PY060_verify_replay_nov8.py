#!/usr/bin/env python3
"""Independent arithmetic comparisons of fresh replay outputs versus archived NOV8_07 snapshot.
Does not imply independent source-data collection or independently implemented power system physics.
"""
import hashlib,io,json,zipfile,gzip,argparse
from pathlib import Path
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parents[1];R=ROOT/'results';AP=argparse.ArgumentParser();AP.add_argument('--reference',default=str(ROOT.parent/'NOV8_07_COMPLETE_PRIVATE_RESEARCH.zip')); Z=AP.parse_args().reference
z=zipfile.ZipFile(Z); names=set(z.namelist()); out={'reference_archive':Path(Z).name,'replayed_model_executable':'code/evidence_model.py --reuse-fit','scenarios':{},'missing_reference_files':[]}
for n in ['scenario_annual.csv','scenario_summary.csv']:
 a=pd.read_csv(R/n)
 rf='results/'+n
 if rf not in names:
  out['missing_reference_files'].append(rf);continue
 b=pd.read_csv(io.BytesIO(z.read(rf)))
 assert len(a)==len(b) and list(a.columns)==list(b.columns)
 numerical=a.select_dtypes(include='number').columns
 dif={col:float(np.nanmax(np.abs(a[col].to_numpy(float)-b[col].to_numpy(float)))) for col in numerical}
 out['scenarios'][n]={'records':len(a),'max_absolute_differences':dif,'max_numeric_difference':max(dif.values())}
 assert max(dif.values())<1e-5,(n,dif)
for scenario in pd.read_csv(R/'scenario_annual.csv').scenario.unique():
 cur=pd.read_csv(R/f'{scenario}_hourly.csv.gz')
 archived='results/'+scenario+'_hourly.csv.gz'
 if archived not in names:out['missing_reference_files'].append(archived);continue
 b=pd.read_csv(io.BytesIO(gzip.decompress(z.read(archived))))
 numeric=cur.select_dtypes(include='number').columns
 assert len(cur)==140160 and len(b)==140160 and list(cur.columns)==list(b.columns)
 maxdiff=max(float(np.nanmax(abs(cur[col]-b[col]))) for col in numeric)
 maxflow=abs((cur.wind_MW+cur.solar_MW+cur.hydro_MW+cur.import_MW+cur.B100_MW+cur.HVO_MW+cur.discharge_MW+cur.unserved_MW-cur.curtail_MW-cur.load_MW-cur.charge_MW-cur.export_MW-cur.network_loss_MW)).max()
 assert maxdiff<1e-5 and maxflow<1e-5,(scenario,maxdiff,maxflow)
 out['scenarios'][scenario]={'hourly_records':len(cur),'max_abs_numeric_difference_from_NOV8_07':maxdiff,'max_abs_independent_energy_balance_residual_MW':float(maxflow)}
 (R/'NOV8_08_replay_ledger_verification.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out,indent=2))
