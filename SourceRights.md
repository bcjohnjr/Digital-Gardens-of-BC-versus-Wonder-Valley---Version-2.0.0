# NOV9_17 data copyright, licence and provenance assessment

Date reviewed: 9 November 2026. This is a documented research-release assessment, not a court decision or assurance that any particular account agreement has been satisfied.

## Corrected legal principle

Under Canadian copyright law, individual factual observations (hourly megawatt load/transfer limits, temperature, wind speed and generation readings) are not copyrighted merely by recording or publishing them. CIPO explicitly distinguishes facts from original expression. BC Hydro's general website legal notice speaks of editorial content, graphics and website HTML; it does **not**, on its face, confer exclusive copyright in the underlying numerical facts. It would therefore be incorrect to make blanket BC Hydro permission an automatic prerequisite for republishing independently normalised measurements.

This does not rule out protection for sufficiently original compilations, expressive document structures, software, images and written explanations, nor contractual restrictions accepted for a particular login/API/download or EU sui generis database rights. Those issues depend on specific facts. No private provider account contracts were supplied for inspection. The research package removes downloaded source XLS sheets, original document graphics and complete provider download bundles. It includes author-prepared numerical inputs, transformed factual measurement tables and code. Provenance is documented; this is not an assertion that all possible legal issues have been conclusively resolved.

## Source register

| Source | Included source fact/model artefact | Publication assessment / conditions |
|---|---|---|
| BC Hydro | `inputs/grid_hourly_utc.csv.gz`, prepared `grid_access.npz`, `model_inputs.npz` | Measurements are facts; blanket website copyright notice alone does not establish exclusive rights over numbers. Original XLS workbooks/graphics excluded; check any separately agreed download/portal terms and database rights. BC Hydro data do not imply actual interconnection availability. |
| AESO | `inputs/selected_AESO_wind_generation_numeric_facts_2010_2019.csv.gz` (reformatted timestamp/value table) | Factual numbers not independently copyright-protected as such; original source file/layout excluded. Check download-specific accepted access agreements and provenance. |
| ECCC weather | `inputs/weather_qc_hourly.csv.gz` (author-processed numerical station/time table) | ECCC meteorological data available under applicable open government/open meteorological data licences, with appropriate source acknowledgments. This file is normalised, gap/QC processed, not a certified copy of source readings. |
| Copernicus ERA5 | Derived wind-resource shapes within `model_inputs.npz`; baseline configuration | Copernicus Products licence permits reuse, adaptation and distribution with credit; cite 'Generated using Copernicus Climate Change Service information' and product years where known. |
| Open-Meteo | Weather-API-derived data in provenance if present | Open-Meteo API data under CC BY 4.0 with attribution and modification notice; API subscription/rate terms are separate. |
| Global Wind Atlas | Ridge-resource assumptions in baseline and comparative code | Licence CC BY 4.0 unless item-specific exceptions; credit DTU, World Bank Group and dataset version; avoid implied endorsement. |
| Original code, transformed arrays and result tables | This archive's code/results files | Author-produced research contributions: licence decision rests with the author, subject to external dependencies and any patent rights. No general grant of copyright over third-party material is purported. |

## Source links / primary legal material

* Canadian Intellectual Property Office, Guide to copyright: https://ised-isde.canada.ca/site/canadian-intellectual-property-office/en/guide-copyright
* BC Hydro general legal page: https://www.bchydro.com/siteinfo/legal.html
* BC Hydro historical transmission data: https://www.bchydro.com/energy-in-bc/operations/transmission/transmission-system/balancing-authority-load-data/historical-transmission-data.html
* AESO historical generation data: https://www.aeso.ca/market/market-and-system-reporting/data-requests/historical-generation-data/
* ECCC MSC Open Data Licence v2.1.1: https://eccc-msc.github.io/open-data/licence/readme_en/
* Government of Canada Open Government Licence: https://open.canada.ca/en/open-government-licence-Canada
* Copernicus Products Licence: https://cds.climate.copernicus.eu/licences/licence-to-use-copernicus-products
* Open-Meteo dataset licence: https://open-meteo.com/en/pricing
* Global Wind Atlas: https://globalwindatlas.info/about/TermsOfUse
* EU database protection: https://digital-strategy.ec.europa.eu/en/policies/protection-databases

## Outstanding release checks

1. Confirm whether the person who downloaded BC Hydro, AESO or other third-party data accepted a provider-specific contract or restricted portal terms. A website copyright notice is not itself proof that a contract was agreed to.
2. Verify actual provenance and any product-specific conditions, in particular Global Wind Atlas/ERA5 and any historical ECCC datasets.
3. Confirm the author-selected licence for the **original** code and processed datasets; do not mislabel a multi-provider bundle as solely owned by one party.
4. Inspect the specific repository deposit before pressing Publish. A DOI is assigned only by the repository, never by a prefilled draft.
