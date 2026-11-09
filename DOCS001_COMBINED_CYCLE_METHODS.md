# Modular combined-cycle, paid used-oil biodiesel and upgraded-biomethane screening

Reproduce: `python RESEARCH_CODE/GRID_CONNECTED_REOPT/model_combined_cycle.py`

This uses the FIXED grid-connected 732-turbine selected build and 2010–2025 source hourly data including industrial-dryer booster load. The code independently recovers annual HVO volumes and grid imports/exports for every year, asserting equality to `reoptimized_annual.csv`. No hourly purchase/export or renewable capacity is reoptimized.

The existing 54%-net-efficient reciprocating engine meets backup load and consumes HVO, after the archived B100 stock. Small firming demand remains on these engines. When sufficiently loaded, 180-MW modular combined-cycle blocks supply firming energy, using a 53–60% LHV net-efficiency *screen*, cycle derate and discrete start/stop cost. Published SCC-800 specifications are gas-fuel GROSS performance; the net efficiency on HVO and biomethane must be certified for the specific model. 64% is only a high-rated-efficiency envelope; 70% is not modelled as achievable commercial performance.

Fuel shares are applied to thermal LHV: upgraded biomethane may replace 0/10/25% of CCGT input. This is a conditional supply allocation, not a demonstrated HVO-and-gas simultaneous co-firing certification. The manufacturer must authorise the exact fuel specification, changeover system, emissions control and steam cycle. FAME is restricted to the residual reciprocating engines under an additional OEM-approved B05/B20 fuel-blend condition, never assumed drop-in for gas turbines. Raw paid used cooking oil must be converted to finished certified fuel at assumed 88% volume yield. Paying for oil does not establish collectable supply.

Cost: capex new CCGT C$2,900/kW (illustrative), minus C$1,600/kW of displaced-engine capital assumed within an existing lumped equipment/network account; 25-year 8.5% CRF; +C$10/kW-year extra fixed O&M, +C$3/MWh variable O&M, C$2,500/block start. No additional transmission, cooling works, water permits, fuel infrastructure, maintenance overhaul or bottoming-cycle thermal revenue is credited.

Hydraulic screen assumes 45% of CCGT non-electrical heat enters a river-water condenser, with +5 K water temperature; a 360-MW full-output example yields ~5.16 m³/s once-through. Withdrawal is not consumption, and no site hydrology, allowed intake temperature, outfall plume, low-flow or ecological impact is established. River access does NOT imply authorisation under the BC Water Sustainability Act. Steam bottoming-cycle heat is not counted again as industrial drying heat.

Technical sources:
- https://www.siemens-energy.com/global/en/home/products-services/product/sgt-800.html
- https://www.siemens-energy.com/global/en/home/products-services/solutions-usecase/sustainable-fuels.html
- https://www.siemens-energy.com/global/en/home/products-services/product/combined-cycle-power-plants.html
- https://www.iea-amf.org/content/fuel_information/fatty_acid_esters/compatibility
- https://www.bclaws.gov.bc.ca/civix/document/id/complete/statreg/14015
