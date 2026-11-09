# Loss-aware static AC N−1 correction and interpretation

This is a synthetic grid screening test and **NOT** a BC Hydro model, an interconnection request, a route design, or a North American reliability certificate. Run from `RESEARCH_CODE/`:

```bash
QTAG=loss_aware QRESIDUAL=0.04 python GRID_CONNECTED_REOPT/run_loss_aware_qsupport.py
python GRID_CONNECTED_REOPT/build_loss_aware_summary.py
python GRID_CONNECTED_REOPT/validate_loss_aware_qsupport.py
```

`run_loss_aware_qsupport.py` independently reads the existing 5.856-GW wind, 4.866-GW solar, 3.133-GWh battery configuration. For each intact or one-at-a-time line/transformer or wind-region failure, the preexisting linearised DC dispatch is solved with a **2,500-MW import and 3,000-MW export ceiling**. The subsequent AC PQ-bus load flow calculates true slack-bus real-power consumption and line losses. If the AC grid slack exceeds 2,500 MW, available local HVO generation is increased at the 17 campuses, apportioned according to unused nameplate headroom. The AC model is re-solved until the **actual slack** satisfies the import ceiling. HVO increments are explicitly bounded above by 160 MW per site. The final check evaluates AC solution convergence, voltage band [0.95,1.05] pu, branch MVA ratings, unserved load and AC import slack. No hidden grid import supplies system losses.

### Reproduced central winter results

| Item | Result |
|---|---:|
| AC states (intact plus 98 contingencies) | 99 |
| AC solves converged and passed all stated static criteria | 99 |
| Uncompensated winter voltage violations (separate screen) | 14/99 |
| Ideal net Q/P = 0.04, loss-aware voltage violations | 0/99 |
| AC grid import | 2499.40–2499.70 MW |
| AC resistance losses | 16.99–23.31 MW |
| Additional local HVO output | 17.29–23.92 MW |
| Min. AC voltage | 0.958 pu |
| Max. branch MVA utilisation | 55.3% |
| Total lost load | 0 MW in screened cases |
| Extra firming fuel variable cost in modeled winter hour | C$5,684–7,861/h |

These tests are **snapshot comparisons**, not 16 years of hourly AC OPF. The historical portfolio optimisation's C$191.50/MWh does **not** include chronologically calculated nodal ohmic losses or the incremental 931-MVAr reactive equipment. The extra HVO result cannot be applied uniformly to 8,760 h/year. A full network dispatch re-optimization requires real routes, transmission thermal and short-circuit ratings, transformer taps, reactive equipment limits, station connection studies and hour-specific generator dispatch, losses and fuel limits.

### Wind and contract feasibility

Five GWA 100-m samples and ERA5 reanalysis adjusted to site means are **not** micro-sited resource campaigns for the 732-turbine fleet. The historical monthly BC provincial-generation comparison is weak (r≈0.18, r≈0.24 with 2020 excluded) and is a proxy only. Planned grid import/export rights, revenue, price assumptions, liquid-fuel/biomethane availability and waste-heat customer offtake remain noncontracted. This file makes no claim to utility-grade reliability or economic bankability.
