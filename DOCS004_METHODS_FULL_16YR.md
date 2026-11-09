# Full 2010–2025 hourly network-loss chronology (Digital Gardens versus Wonder Valley)

## Reproduce

From `RESEARCH_CODE/` (Python 3.11+, numpy, pandas, scipy, numba, matplotlib):

```bash
python GRID_CONNECTED_REOPT/FULL_16YR_LOSS_AWARE/run_full_chronology.py
python GRID_CONNECTED_REOPT/FULL_16YR_LOSS_AWARE/validate_full_chronology.py
```

This fixed-installed-capacity scenario replays 16 annual 8,760-hour sequences (140,160 hourly records), reconstructing separate hourly wind-generation vectors for the five GWA/ERA5 wind regions. Demand includes the hourly electric drying booster. Battery charge/discharge state and annual B100/HVO quantities evolve sequentially, resetting at each simulated year as in the published optimizer. Purchase and sale transactions are capped at 2.5 GW and 3.0 GW, with the *same hypothetical hourly prices*, respectively. Every hour iterates on losses before committing battery, grid, renewable-fuel, gas, and unmet-load transactions.

The synthetic 37-bus, 93-branch intact network is read from the same `N1_QSUPPORT_loss_aware/assumed_{buses,branches}.csv` used for the 99-case static AC model. Bus injections represent the **original five wind-collector sites** and **uniformly distributed** campus loads, PV, local hydro, batteries and firm generation across 17 proposed communities. Excess renewable curtailment is proportional across sources, a declared simplification. The DC distribution factors follow branch reactances. The per-hour resistive loss approximation is

\[ E_{loss,t}\;(\mathrm{MWh})=\sum_{\ell=1}^{93} r_{\ell,pu} F_{\ell,t}^{2}/S_{base}\,,\quad S_{base}=1{,}000\ \mathrm{MVA}\,.\]

This assumes 1 pu line-end voltage and neglects reactive current and AC nonlinear feedback; **it is a network-based I²R approximation rather than an actual AC power-flow solution in every hour.** Cases at 0.75, 1 and 1.25 times the resulting I²R losses show uncertainty in line impedances, voltages and siting. This intact-network DC I²R step remains distinct from the subsequently completed 140,160-hour × 94-state nonlinear AC intact and single-branch outage study, reported in METHODS_FULL_HOURLY_AC_N1.md. The DC dispatch step itself does not conduct AC N−1 optimization.

The hourly energy ledger balances to less than 0.000001 MWh in the saved output. Nominal hourly losses average 219.876 GWh/year across 2010–2025, purchase transactions rise from 12.405 to 12.518 TWh/year, export transactions fall from 1.062 to 1.012 TWh/year, and HVO volume rises from 471.388 to 481.537 million L/year. Emergency fossil-gas and unserved electricity remain zero in this screen; intact-network branch loadings and the modeled 160 MW/campus firm-generation allocation remain within assumed limits. The annualized variable cost rises C$0.970/MWh, yielding **C$192.472/MWh** before reactive-compensation equipment capital or utility interconnection upgrades.

Because the portfolio has **not** been re-optimized against losses or actual utility tariffs, this figure is a fixed-build operating correction, not a proven global optimum. The ±25% loss-range screens span 165.03–274.63 GWh/year and C$192.23–192.72/MWh before reactive capex. HVO upstream emissions (25 g CO₂e/MJ) and extra imported-electricity emissions (100 g/kWh center, 20–250 sensitivity) add ~0.021 Mt CO₂e/year to the existing carbon ledger. This is a partial emissions adjustment and not an independent recomputation of SCR/N₂O or fully spatial LCA.

The modeled price and emissions do not establish actual BC Hydro transmission/interconnection entitlements, procurement contracts, grid-settlement prices or environmental permissions. Actual conductor types, voltage-support equipment, thermal ratings, losses, protection, site coordinates and wind-farm installations must be surveyed. The 17 campus buses use community *proxy coordinates*, not confirmed property boundaries or substation sites.

## File contents

- `nominal_i2r_hourly_2010_2025.csv.gz`: the 140,160-hour dispatch ledger, including grid transactions, diesel/B100/gas, SOC, renewable generation, load, computed losses and assumed max branch loading. Units are given in column headings. Annual columns are aggregated from this ledger.
- `{pooled_zero_losses,nominal_i2r,lower_i2r_075,upper_i2r_125}_annual.csv`: one row per year with purchases, sales, fuel, losses, cost and constraints.
- `full_16yr_loss_results.json`: summary, original pooled-benchmark identity check, scenario means, LCA partial adjustments and explicit exclusions.
- `Figure_S15_Full_16yr_Network_Losses.png`: loss sensitivity plot.
- `validate_full_chronology.py`: independent integrity checks against saved outputs.
