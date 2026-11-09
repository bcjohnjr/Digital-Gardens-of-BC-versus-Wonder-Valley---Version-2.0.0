# CCGT cogeneration and continuous drying methods

Run: `python RESEARCH_CODE/GRID_CONNECTED_REOPT/ccgt_chp_drying24h.py` from repository root. Requires numpy, pandas and numba.

Existing 2.955 TWh/year drying and its 0.246 TWh electric boosters are already in the archived hourly load. Additional 50/150/300 MWth 24-hour capable contracts are tested at 75/95/100% operational duty. IT heat is allocated only from the previously rejected remainder, with 25/50/75/100% direct low-temperature use; the rest requires a COP 2.5 heat pump. Fan/pump load is 2% of thermal delivered and the electrical load is rerun through the 16-year grid/HVO dispatch, including forfeited exports.

360 MW CCGT is simulated from the same 2x180 MW block dispatch; heat is recovered only in hours units operate, never assumed baseload. Low-grade residual heat is capped by co-located greenhouse/aquaculture demand at 40/100/180 MWth and recovered 30/50/65%; no steam extraction beyond the steam cycle is credited for free. CHP total useful-energy efficiency = (net electric + matched useful heat)/thermal fuel LHV, not net electric efficiency.

Pricing from FortisBC business Rate 5 and Rate 3 published July 2026 variable components (C$4.614 and C$9.305 per GJ) with 82% burner/boiler efficiency. Fixed tariff demand charges, taxes, process transport, feedstock purchase, product handling, exact plant quotes and contracts are NOT included.

Sources: https://www.epa.gov/chp/methods-calculating-chp-efficiency ; https://www.fortisbc.com/accounts/billing-rates/natural-gas-rates/business-rates ; https://www.ornl.gov/publication/district-heating-utilizing-waste-heat-data-center-high-temperature-heat-pumps
