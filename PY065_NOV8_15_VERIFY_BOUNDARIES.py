#!/usr/bin/env python3
"""Verify aggregate emissions ledger identities. No rights-restricted hourly inputs needed."""
from pathlib import Path
import pandas as pd,json,math
p=Path(__file__).resolve().parent
x=pd.read_csv(p/'NOV8_15_EXPLICIT_CARBON_BOUNDARIES.csv');v=json.loads((p/'NOV8_15_CARBON_AUDIT.json').read_text())
row=lambda n:float(x.loc[x.category==n,'emissions_MtCO2e_y'].iloc[0])
a=sum(row(n) for n in ['Wind lifetime proxy','Solar lifetime proxy','Battery embodied proxy','Imported electricity assumed mix','HVO renewable-fuel well-to-wheel','B100 renewable-fuel well-to-wheel'])
c=row('Conditional displaced fossil home and drying'); w=row('Unabated CCGT direct fossil combustion')+row('Unabated CCGT methane at assumed 1 percent')
assert abs(a-v['dig_gross_Mt_y'])<1e-9
assert abs(a+c-v['dig_net_Mt_y'])<1e-9
assert abs(w-v['wv_direct_plus_methane_Mt_y'])<1e-9
assert abs(row('90 percent CCS direct plus methane')-(row('Unabated CCGT direct fossil combustion')*.1*1.15+row('Unabated CCGT methane at assumed 1 percent')*1.15))<1e-8
assert abs(row('95 percent CCS direct plus methane')-(row('Unabated CCGT direct fossil combustion')*.05*1.15+row('Unabated CCGT methane at assumed 1 percent')*1.15))<1e-8
assert abs((a+c)/w-v['ratio_DG_partialnet_to_WV_unabated_partial'])<1e-9
print('PASS: gross, community credit, net, unabated gas, both CCS rates, methane and ratios')
