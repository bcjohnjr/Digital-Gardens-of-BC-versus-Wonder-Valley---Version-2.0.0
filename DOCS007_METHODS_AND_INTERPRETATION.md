# Integrated grid-connected primary model: reproducibility and limits

## Architecture

The study supplies 17 proposed BC AI sites with grid purchases and export capability. The sixteen 2010–2025 ERA5/GWA-corrected hourly series are run using engineering proxy power curves for an 8-MW SANY turbine, with five independent farm-capacity decision variables, PV and batteries. The imported grid power cap is 2.5 GW and exports 3 GW. The final site allocations are snapped to whole 8 MW turbines and replayed (732 turbines total). Any cost optimization is finite and cannot establish a globally optimal design.

The code explicitly models grid purchases and sales at hour-specific **scenario** price functions based on season, hour of day and normalized solar production. These are **not observed BC Hydro tariffs, hourly Mid-C traded settlement records, or approved power purchase agreements**. Fixed-portfolios under alternate hourly price scenarios are exported as sensitivities. A system-impact and market-access study would be required to establish real terms and feasible transactions.

## Heat/power accounting

The heat-matching model creates hourly dryer booster electricity consumption, with annual total 0.246 TWh. This electric booster is added to load *before* battery discharge, grid purchases, renewable-fuel engines, and exports. The same MWh is therefore not both exported and credited as zero-price drying power. Re-optimise using `--boost-load`, then run `reconcile_heat_gpu.py`. Drying supplier profitability is **negative** under the central screening contracts.

## Carbon and business accounting

The lifecycle ledger includes wind/solar/battery embodied contributions, HVO upstream emissions, SCR N2O and grid purchased energy. It does **not** claim credit for displacing fossil grid output with exports, and excludes voluntary host-community savings from the computing footprint. GPU label premiums are derived from a full 25-year project NPV function with matched GPU purchases, utilisation, refresh cycles and tax assumptions, including an illustrative turbine-year-21 life-extension allowance. Pricing uplift is a mathematical break-even value, **not measured client willingness to pay**.

## AC/N−1

`run_network_reoptimized.py` uses a hypothetical 500/230 kV topology and transformer/line impedance assumptions; it screens each of 98 single element contingencies plus intact conditions at grid-connection/dispatch snapshots. The re-optimised central winter case shows **14 of 99 AC-voltage-limit violations**. This is not a passing full utility-grade N−1 study and does not include actual BC Hydro equipment, rights-of-way, grid-forming dynamics or protection design.

## Receiving-water screen and Davies discussion

`river_mixing_screen.py` evaluates one proposed Kamloops site. Under a single assumed recent Thompson River flow of 309 m³/s, the fully mixed peak temperature increase is ≈0.104°C, versus ≈1.04°C if near-field mixing occurs into only a tenth of that flow. This is not a low-flow hydrology model or permit study.

Separately, Robert Davies's preliminary study of Wonder Valley considers a proposed **9 GW electricity** full-build scenario and **16–18 GW thermal fuel input**. That is *not* the 7.5 GW full-build description published by its architect, and neither is identical to the transparent 3.75 GW IT comparator. The popular atomic-bomb analogy describes an energy magnitude and is not a measured local ecosystem impact.

## Commands

From the root `RESEARCH_CODE` folder (Python 3.11+):

```
python GRID_CONNECTED_REOPT/validate_connected_reoptimization.py
python GRID_CONNECTED_REOPT/reoptimize_grid.py --boost-load --iter 45 --popsize 8 --seed 1902
python GRID_CONNECTED_REOPT/reconcile_heat_gpu.py
python GRID_CONNECTED_REOPT/river_mixing_screen.py
python GRID_CONNECTED_REOPT/run_network_reoptimized.py
```

The last command is the more expensive network-contingency screen. Other models in the archive are **alternative fixed-build / no-grid comparators**, not the primary connected-case optimizer.

## AC slack import cap with resistive losses

The standalone `run_loss_aware_qsupport.py` uses the compensated static winter configuration (Q/P=0.04, equivalent to ~931 MVAr local compensation) and computes an AC slack-bus power balance in each intact and single-element contingency. It adds generation at load buses within the 160 MW/site HVO firm-power capacity limit to cover AC transmission losses, rather than allowing the slack to exceed 2.5 GW. The 99 solved contingencies and audit results reside in `N1_QSUPPORT_loss_aware/`. Details and limitations: `LOSS_AWARE_AC_METHODS.md`. This does not modify the 2010–2025 pooled dispatch optimizer or establish certificated reliability.
