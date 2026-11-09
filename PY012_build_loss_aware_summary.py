from pathlib import Path
import json,math,shutil
import numpy as np,pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
rc=Path(__file__).resolve().parent;root=rc.parent.parent;out=rc/'N1_QSUPPORT_loss_aware';figdir=root/'FIGURES'
d=json.loads((out/'loss_aware_summary.json').read_text())
ac=pd.read_csv(out/'ac_voltage_screen.csv')
assert len(ac)==99 and ac.ac_balanced_pass.all() and (ac.ac_grid_slack_mw<=2500.02).all()
assert (ac.ac_voltage_violations==0).all() and (ac.ac_thermal_violations==0).all()
assert ac.ac_residual_pu.max()<1e-5 and ac.ac_loss_balance_residual_mw.abs().max()<1e-4
assert np.all(ac.ac_added_local_hvo_mw>0)
ac['ac_fuel_cost_cad_per_h'] = ac.ac_added_local_hvo_mw * 328.7
# Keep machine-readable figure and condensed summary with validated source values.
summary = {
 'screen':'hypothetical 17-load winter N0 plus 98 single contingencies',
 'n_cases':len(ac),
 'ac_converged_count':int(ac.ac_converged.sum()),
 'ac_passed_all_screen_criteria_count':int(ac.ac_balanced_pass.sum()),
 'grid_import_ceiling_mw':2500,
 'actual_ac_grid_slack_mw_min':float(ac.ac_grid_slack_mw.min()),
 'actual_ac_grid_slack_mw_max':float(ac.ac_grid_slack_mw.max()),
 'active_AC_losses_mw_min':float(ac.ac_loss_mw.min()),
 'active_AC_losses_mw_max':float(ac.ac_loss_mw.max()),
 'additional_local_HVO_mw_min':float(ac.ac_added_local_hvo_mw.min()),
 'additional_local_HVO_mw_max':float(ac.ac_added_local_hvo_mw.max()),
 'illustrative_added_fuel_CAD_per_screened_hour_min':float(ac.ac_fuel_cost_cad_per_h.min()),
 'illustrative_added_fuel_CAD_per_screened_hour_max':float(ac.ac_fuel_cost_cad_per_h.max()),
 'ac_bus_min_voltage_pu':float(ac.min_bus_vm_pu.min()),
 'ac_branch_max_MVA_loading_pct':float(ac.ac_max_branch_loading_pct.max()),
 'ac_voltage_limit_failure_count':int((ac.ac_voltage_violations>0).sum()),
 'ac_thermal_limit_failure_count':int((ac.ac_thermal_violations>0).sum()),
 'n0_winter_AC_slack_mw':float(ac.loc[ac.outage=='N0','ac_grid_slack_mw'].iloc[0]),
 'n0_winter_extra_HVO_mw':float(ac.loc[ac.outage=='N0','ac_added_local_hvo_mw'].iloc[0]),
 'major_limitations': ['Synthetic, unsurveyed transmission topology and impedances','Ideal net Q/P 0.04 at the seventeen campus buses, no actual STATCOM controller limits','No dynamic, contingency protection or short-circuit studies','No synchronized 16-year loss-aware AC grid-dispatch optimization','No awarded 2.5-GW utility import or 3-GW export rights','Static HVO redispatch does not demonstrate contracted fuel availability'],
 'cost_convention':'Incremental HVO variable cost for screened winter hour only; cannot annualise these winter extrema to the 16-year system cost.'
}
(out/'loss_aware_accounting_audit.json').write_text(json.dumps(summary,indent=2)+'\n')
# Figure S14: contingency cases, sorted to show import boundary and redispatch.
srt=ac.sort_values('ac_loss_mw').reset_index(drop=True)
fig,ax=plt.subplots(figsize=(8.4,4.6),dpi=170)
xx=np.arange(1,len(srt)+1)
ax.plot(xx,srt.ac_loss_mw,color='#26828e',lw=2,label='AC resistive losses (MW)')
ax.plot(xx,srt.ac_added_local_hvo_mw,color='#d48c2f',lw=2,label='Additional local HVO dispatch (MW)')
ax.set(ylabel='MW',xlabel='Ranked intact and N−1 winter contingency cases (n=99)',title='Loss-aware correction: local firming supplies transmission losses')
ax.legend(loc='upper left');ax.grid(alpha=.17);fig.tight_layout()
for dirx in [figdir,out]:
 fig.savefig(dirx/'Figure_S14_AC_Loss_Aware_N1.png',dpi=200,bbox_inches='tight')
 fig.savefig(dirx/'Figure_S14_AC_Loss_Aware_N1.pdf',bbox_inches='tight')
plt.close(fig)

# Build a fully independent smoke validator with source/output consistency (no hard-coded claims about data sources).
validator='''#!/usr/bin/env python3
"""Audit loss-aware winter AC N0/N-1 screens (not an operator certificate)."""
from pathlib import Path
import json, numpy as np, pandas as pd
p=Path(__file__).resolve().parent/'N1_QSUPPORT_loss_aware'
a=pd.read_csv(p/'ac_voltage_screen.csv')
s=json.loads((p/'loss_aware_accounting_audit.json').read_text())
assert len(a)==99==s['n_cases']
assert len(a['outage'].unique())==99
assert a['ac_converged'].all() and a['ac_balanced_pass'].all()
assert (a['ac_grid_slack_mw']<=2500.02).all()
assert (a['ac_voltage_violations']==0).all()
assert (a['ac_thermal_violations']==0).all()
assert (a['unserved_mw']<1e-5).all()
assert (a['ac_residual_pu']<1e-5).all()
assert (a['ac_loss_balance_residual_mw'].abs()<1e-4).all()
assert (a['ac_total_hvo_after_balance_mw'] <= 17*160+1e-5).all()
assert (a['ac_added_local_hvo_mw']>0).all()
assert abs(a['ac_loss_mw'].min()-s['active_AC_losses_mw_min'])<1e-8
assert abs(a['ac_loss_mw'].max()-s['active_AC_losses_mw_max'])<1e-8
assert abs(a['ac_grid_slack_mw'].max()-s['actual_ac_grid_slack_mw_max'])<1e-8
assert (p/'Figure_S14_AC_Loss_Aware_N1.png').exists()
print('PASS: 99 loss-aware AC N0/N−1 cases; import <=2.5 GW; 0 voltage/thermal/shortfall failures. Screening assumptions only.')
'''
(rc/'validate_loss_aware_qsupport.py').write_text(validator)
# Add detailed methods, summary, data protection and explicit economic boundary
methods=f'''# Loss-aware static AC N−1 correction and interpretation

This is a synthetic grid screening test and **NOT** a BC Hydro model, an interconnection request, a route design, or a North American reliability certificate. Run from `RESEARCH_CODE/`:

```bash
QTAG=loss_aware QRESIDUAL=0.04 python GRID_CONNECTED_REOPT/run_loss_aware_qsupport.py
python GRID_CONNECTED_REOPT/validate_loss_aware_qsupport.py
```

`run_loss_aware_qsupport.py` independently reads the existing 5.856-GW wind, 4.866-GW solar, 3.133-GWh battery configuration. For each intact or one-at-a-time line/transformer or wind-region failure, the preexisting linearised DC dispatch is solved with a **2,500-MW import and 3,000-MW export ceiling**. The subsequent AC PQ-bus load flow calculates true slack-bus real-power consumption and line losses. If the AC grid slack exceeds 2,500 MW, available local HVO generation is increased at the 17 campuses, apportioned according to unused nameplate headroom. The AC model is re-solved until the **actual slack** satisfies the import ceiling. HVO increments are explicitly bounded above by 160 MW per site. The final check evaluates AC solution convergence, voltage band [0.95,1.05] pu, branch MVA ratings, unserved load and AC import slack. No hidden grid import supplies system losses.

### Reproduced central winter results

| Item | Result |
|---|---:|
| AC states (intact plus 98 contingencies) | {summary['n_cases']} |
| AC solves converged and passed all stated static criteria | {summary['ac_passed_all_screen_criteria_count']} |
| Uncompensated winter voltage violations (separate screen) | 14/99 |
| Ideal net Q/P = 0.04, loss-aware voltage violations | 0/99 |
| AC grid import | {summary['actual_ac_grid_slack_mw_min']:.2f}–{summary['actual_ac_grid_slack_mw_max']:.2f} MW |
| AC resistance losses | {summary['active_AC_losses_mw_min']:.2f}–{summary['active_AC_losses_mw_max']:.2f} MW |
| Additional local HVO output | {summary['additional_local_HVO_mw_min']:.2f}–{summary['additional_local_HVO_mw_max']:.2f} MW |
| Min. AC voltage | {summary['ac_bus_min_voltage_pu']:.3f} pu |
| Max. branch MVA utilisation | {summary['ac_branch_max_MVA_loading_pct']:.1f}% |
| Total lost load | 0 MW in screened cases |
| Extra firming fuel variable cost in modeled winter hour | C${summary['illustrative_added_fuel_CAD_per_screened_hour_min']:,.0f}–{summary['illustrative_added_fuel_CAD_per_screened_hour_max']:,.0f}/h |

These tests are **snapshot comparisons**, not 16 years of hourly AC OPF. The historical portfolio optimisation's C$191.50/MWh does **not** include chronologically calculated nodal ohmic losses or the incremental 931-MVAr reactive equipment. The extra HVO result cannot be applied uniformly to 8,760 h/year. A full network dispatch re-optimization requires real routes, transmission thermal and short-circuit ratings, transformer taps, reactive equipment limits, station connection studies and hour-specific generator dispatch, losses and fuel limits.

### Wind and contract feasibility

Five GWA 100-m samples and ERA5 reanalysis adjusted to site means are **not** micro-sited resource campaigns for the 732-turbine fleet. The historical monthly BC provincial-generation comparison is weak (r≈0.18, r≈0.24 with 2020 excluded) and is a proxy only. Planned grid import/export rights, revenue, price assumptions, liquid-fuel/biomethane availability and waste-heat customer offtake remain noncontracted. This file makes no claim to utility-grade reliability or economic bankability.
'''
(rc/'LOSS_AWARE_AC_METHODS.md').write_text(methods)


print("PASS: loss-aware quantitative audit and Figure S14 regenerated from saved AC states")
