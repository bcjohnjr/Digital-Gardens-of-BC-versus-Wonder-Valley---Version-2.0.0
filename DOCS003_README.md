# Full chronological synthetic AC remedial sensitivity (review candidate)

This folder includes **two model-only experiments** following the archived
13,175,040-solution fixed-injection nonlinear AC/N−1 screen:

1. `run_selected_13pct_rating_screen.py`: repeats all 140,160 modeled hours
   for the intact network and six individual wind-collector branch outages.
   Only the MVA nameplate limit of six assumed lines (both circuits of the
   Pennask Mountain, Mount Mabel and Cache Creek collector pairs) is multiplied
   by 1.13. **No impedance or topology changes are simulated.** The six
   previously overheated contingency types have zero thermal exceedances
   afterwards (maximum 99.799% rated). The other 87 original outage types
   had no thermal violations initially, so the complete thermal-screen count
   would be zero if only ratings changed. **Grid import violations remain**
   in 48,827 distinct historical hours: the rating change alone is not a
   complete remedy.

2. `run_preemptive_13pct_sensitivity.py`: repeats ALL 140,160 modeled hours
   and each of the 94 intact / single-branch states, yielding 13,175,040
   further nonlinear balanced AC evaluations. The same six assumed line
   ratings are 13% larger. Local generators at the 17 campus proxies produce
   additional HVO electricity scheduled *before* each hourly outage test:
   `additional_MW = 1.025 * max(0, archived_worst_outage_grid_import_MW - 2499.75)`.
   Total added output is shared equally over the campuses. That schedule
   depends on knowledge of each historical hour's original all-outage result;
   it is **an ex-post perfect-information contingency envelope**, not an
   implementable forecast/control policy. The new AC model is re-solved for
   every contingency, without corrective state-dependent responses. The
   all-contingency output has zero convergence, voltage, thermal, and grid
   exchange violations under the synthetic model and idealized 931 MVAr
   reactive-support assumption. Maximum assumed collector loading 99.799%,
   peak external import 2499.7493 MW. Additional HVO generation is up to
   9.00023 MW, averages 7.4878 GWh/year (1.36726 ML HVO/year) and peaks at
   1.61540 ML in one year. Modeled maximum total annual HVO fuel
   611.5796 ML is below the pre-existing 976.4516 ML site ceiling.

   The **gross incremental HVO cost** equals C$2.4611 million/year at
   C$1.80/L (C$0.06835/MWh of 36.00486 TWh/year served). This is NOT a
   net secured-network electricity price because grid-import reductions,
   real engine operation and maintenance, capital cost, equipment loss
   feedback, interconnection fees and supply-delivery constraints have not
   been re-optimized. At 25 g CO₂e/MJ HVO upstream, an added 0.001248 Mt
   CO₂e/year is a *gross* one-sided estimate, not a new complete LCA.

**Mandatory caveats:** This is NOT a BC Hydro representation, dynamic N−1,
conditional fault response, AC optimal power flow, generator-outage criterion,
annual fuel logistics/commitment model, or a physically engineered/warranted
13%-higher line rating. No actual conductor, switching, transformer, voltage
controller, protective relay, land acquisition, route, or utility capacity
was priced. Wind resource validation has only within-year Pearson r=0.18
against the provincial monthly observed generation series. The initial base-wind remedy replay uses original ERA5/GWA profiles. A separate
10%-derated-wind/HVO/AC contingency sensitivity now appears in the additional
section below. Neither is a jointly re-optimized wind/security/fuel design. No N−1 secure cost for a
real built project is established.

## Reproduce and independently validate

From `RESEARCH_CODE/` with Python dependencies in root requirements:

```bash
OPENBLAS_NUM_THREADS=1 python GRID_CONNECTED_REOPT/FULL_16YR_LOSS_AWARE/CORRECTIVE_SENSITIVITY/run_selected_13pct_rating_screen.py
OPENBLAS_NUM_THREADS=1 python GRID_CONNECTED_REOPT/FULL_16YR_LOSS_AWARE/CORRECTIVE_SENSITIVITY/run_preemptive_13pct_sensitivity.py
python GRID_CONNECTED_REOPT/FULL_16YR_LOSS_AWARE/CORRECTIVE_SENSITIVITY/validate_corrective_sensitivity.py
```

The script names, CSV and JSON tables deliberately identify these as
**sensitivity replays**, not a new optimized construction plan. The
`PREEMPTIVE` subfolder contains the full 16-year reserve ledger, all-case
worst-hour results, per-contingency failures, N0 solved series, annual
fuel checks and summary JSON. The archived original screen in the parent
folder is preserved unchanged.

## Parameterized, UNQUOTED network capital

The same model's CRF = 0.085 and 36.00486 TWh/year load imply the following
annualized cost increments solely for assumed extra network capex:

| Additional capex (C$bn) | Added C$/MWh |
|---:|---:|
| 1 | 2.36 |
| 3 | 7.08 |
| 5 | 11.80 |

These are conversions, not construction estimates. A higher rating requires
actual equipment design and impedance/network-upgrade re-evaluation.


## Additional 10%-wind stress and carbon accounting

`run_adverse_wind10_ac_n1.py` and `run_adverse_wind10_export_capped_ac_n1.py` rerun 140,160 modeled hours and 94 AC states with a 10% uniform delivered-wind derate and HVO energy substitution; the second adds an 8-MW incremental-HVO export cutback when original hourly intended exports exceed 2.99 GW. Both use hypothetical +13% collector MVA ratings and preserve the ex-post original N−1 import reserve. Outputs and validators follow in `ADVERSE_WIND_10PCT` and `ADVERSE_WIND_10PCT_EXPORT_CAPPED`. `reconcile_emissions_and_fuel.py` produces transparent scoped emission and fuel-only cost ledgers. No real grid engineering, network construction quotes, site wind verification, real-time control or full LCA is claimed.
