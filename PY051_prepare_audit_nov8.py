#!/usr/bin/env python3
"""Non-deceptive project inventory & release permissions register, not legal advice nor ISO-certified LCA."""
from pathlib import Path
import json,pandas as pd,numpy as np
ROOT=Path(__file__).resolve().parents[1];R=ROOT/'results'; A=ROOT/'audit'; A.mkdir(exist_ok=True)
annual=pd.read_csv(R/'scenario_annual.csv');central=annual[annual.scenario=='new_build_observed_shape'];robust=pd.read_csv(R/'NOV8_08_rounded_robust_central_annual.csv')
# list complete ledger by process, with quantified/assumed vs missing status; no fabricated factors.
inventory=[
 ('Wind electricity, 2010–2025','generation','Included as 11 g CO2e/kWh default aggregated cradle-to-grave rate','modelled MWh, inherited generic intensity','assumed, not supplier/project verified','Do not separately double-count turbine embodied burden'),
 ('Solar electricity, 2010–2025','generation','Included as 35 g CO2e/kWh default aggregated cradle-to-grave rate','modelled MWh, inherited generic intensity','assumed, not supplier/project verified','Requires PV bill of materials and site-specific irradiance'),
 ('Battery modules and replacements','storage','70 kg CO2e/kWh assumed, straight-line over 15 y','capacity installed and generic embodied factor','assumed, not supplier/project verified','Battery roundtrip losses counted in dispatch; grid source emissions also counted'),
 ('Grid import production and delivery','imports','100 g CO2e/kWh central; 15, 250 sensitivities','modelled import MWh','assumed, not source-specific','Marginal/time-matched hourly intensity and regional trading mix not established'),
 ('HVO well-to-wheel fuel pathway','fuel','25 g CO2e/MJ central; 15,35 sensitivities','HVO ML x 36.51 MJ/L','assumed, not procurement-specific','Feedstock, indirect land use, logistics, carbon accounting verification missing'),
 ('B100 well-to-wheel fuel pathway','fuel','30 g CO2e/MJ; engine efficiency 0.54','B100 generation and thermal efficiency','assumed, not supplier-specific','Actual B100 feedstock/biogas plant inventory not documented'),
 ('Hydropower construction and operations','generation','','hydro output in model','MISSING FACTOR','Source facilities and historical share-specific intensity needed'),
 ('Wind turbine foundations, roads, transmission collection','construction','','inventoried by conceptual capacities only','MISSING BILL OF MATERIALS','Avoid double counting with generic wind LCA factor, reconcile system boundary'),
 ('Solar modules, foundations, inverters, cables','construction','','generic factor only','MISSING BILL OF MATERIALS','Avoid double counting with generic solar LCA factor'),
 ('Battery supply chain and replacement schedule','construction','','generic rate only','MISSING CERTIFIED INVENTORY','Chemistry, manufacturer, degradation, retirement, recycling needed'),
 ('Substations, interconnection, rights-of-way','construction','','no site-specific engineering','MISSING','Transmission environmental declarations / line lengths / permits needed'),
 ('Thermal recovery plant and district heat pipes','thermal infrastructure','','no supplier/process quantities','MISSING','Steel, concrete, pumps, leakage, commissioning emissions'),
 ('Greenhouses and agricultural operations','food co-products','','not included','MISSING','Lighting, fertilizers, methane, growing medium, transport allocation'),
 ('Aquaculture and seafood production','food co-products','','not included','MISSING','Feed, oxygenation, discharge, refrigeration, methane; product allocation'),
 ('Biogas digester and B100 production','fuels','','not included outside WTW assumptions','MISSING','Feedstocks, methane slip, fuel upgrading, waste accounting'),
 ('Industrial drying and thermal products','co-products','','electric booster load in dispatch','MISSING process burdens','No unverified avoided-emissions or selling price credit'),
 ('Data-centre GPUs and server production','IT equipment','','not included','MISSING','GPU replacement cycles, materials, semiconductors, cooling loops'),
 ('Direct thermal venting, refrigerant losses','operations','','not included','MISSING','Refrigerant type, charge, leakage & GWP'),
 ('Water, wastewater and chemicals','operations','','not included','MISSING','Water quality, pumping, treatment, greywater'),
 ('Construction transport and contractors','construction','','not included','MISSING','Freight distance, fabrication origin, commissioning fuels'),
 ('Facility retirements and reclamation','end of life','','not included','MISSING','Recycling, backfill, waste, land restoration'),
 ('Land use change and biodiversity','land-use','','not included','MISSING','Site-specific ecological baseline; no offset credit'),
 ('Wonder Valley comparator fuel lifecycle','counterfactual','','not recalculated','MISSING comparable boundary','Need same activity types, stages, climate factors and operating window'),
 ('Carbon counterfactual displacements / negative credits','credits','','excluded intentionally','NOT CLAIMED','Do not claim avoided gas/food/drying emissions without additionality study')
]
pd.DataFrame(inventory,columns=['category','lifecycle_stage','quantification','activity_evidence','verification_status','requirements_or_double_count_control']).to_csv(A/'NOV8_08_LIFECYCLE_COMPLETENESS_REGISTER.csv',index=False)
# Compare two portfolios under identical generic intensity factors (not new LCA)
assumptions={'wind_gCO2e_kWh':11.0,'solar_gCO2e_kWh':35.,'battery_kgCO2e_kWh':70.,'battery_life_y':15.,'grid_gCO2e_kWh':100.,'hvo_gCO2e_MJ':25.,'HVO_MJ_L':36.51,'b100_gCO2e_MJ':30.,'b100_eff':.54}
res=[]
for name,df,bat in [('baseline',central,3.040640152610841),('robust_integer',robust,25.000727923953733)]:
 xx=df.copy(); comps={
  'wind_proxy_MtCO2e':xx.wind_TWh*assumptions['wind_gCO2e_kWh']/1000,
  'solar_proxy_MtCO2e':xx.solar_TWh*assumptions['solar_gCO2e_kWh']/1000,
  'battery_proxy_MtCO2e':bat*1e6*assumptions['battery_kgCO2e_kWh']/assumptions['battery_life_y']/1e9,
  'grid_import_proxy_MtCO2e':xx.import_TWh*assumptions['grid_gCO2e_kWh']/1000,
  'HVO_WTW_proxy_MtCO2e':xx.HVO_ML*assumptions['HVO_MJ_L']*assumptions['hvo_gCO2e_MJ']/1e6,
  'B100_WTW_proxy_MtCO2e':xx.B100_GWh*3.6*assumptions['b100_gCO2e_MJ']/assumptions['b100_eff']/1e6}
  # calculation intentionally identical to NOV8_07 methods; not a new certified factor
 for col,values in comps.items():xx[col]=values
 xx['partial_proxy_MtCO2e']=xx[list(comps)].sum(axis=1);xx['portfolio']=name
 res.append(xx[['portfolio','year']+list(comps)+['partial_proxy_MtCO2e']])
out=pd.concat(res);out.to_csv(A/'NOV8_08_BOUNDED_LCA_PROXY_ANNUAL.csv',index=False)
means=out.groupby('portfolio').mean(numeric_only=True).drop(columns='year').reset_index()
means.to_csv(A/'NOV8_08_BOUNDED_LCA_PROXY_MEAN.csv',index=False)
licences=[
 ('BC Hydro historical TTC, load, directional flows',91,'BC Hydro','https://www.bchydro.com/siteinfo/legal.html','Publisher claims protected content and permission for online re-use on a case-by-case basis','HOLD','Raw workbook XLS; prepared TTC/capacity indices; derived files until rights resolved','Request reuse of specific historical data, identify workbook rights and attributes; keep private'),
 ('ECCC Historical Climate Data station-month CSV',1364,'Environment and Climate Change Canada','https://climate.weather.gc.ca/','Published government climate data; historically specific data licence; applicable portal licence needs exact-version confirmation','CONDITIONAL','Attributions and original datasets conditional on source-specific licence','Verify exact download licence and attribution wording, preserve date and modification statement'),
 ('ECCC MSC Open Data feeds',0,'Environment and Climate Change Canada','https://eccc-msc.github.io/open-data/licence/readme_en/','August 2026 MSC open data licence permits copying, adaptation and distribution with acknowledgement','APPROVED ONLY IF SAME LICENCE APPLIES','Those feeds whose download source is explicitly the MSC Open Data service','Do not extrapolate this permission to historical portal without source check'),
 ('AESO five-wind-facility generation dataset',1,'Alberta Electric System Operator','https://aeso.ca/legal/','General site copyright permits noncommercial personal/educational copying, other use needs written permission','HOLD','Raw AESO CSV; bundled source archive and close source-level derived material','Written permission or legal review of exact dataset terms needed for public deposit'),
 ('Copernicus ERA5-derived shapes',None,'Copernicus Climate Change Service','https://cds.climate.copernicus.eu/licences/licence-to-use-copernicus-products','Copernicus licence explicitly permits adaptation, distribution and combination with attribution','ATTRIBUTION REQUIRED','ERA5-derived arrays whose provenance is confirmed','Provide required Copernicus service acknowledgement, product and year'),
 ('Global Wind Atlas base maps/resources',None,'DTU / World Bank / GWA','https://globalwindatlas.info/about/TermsOfUse','Works licensed CC BY 4.0 unless specific work explicitly has different licence','ATTRIBUTION REQUIRED','Original GWA work only where licence and title match','Credit DTU, GWA version, partners and modifications; no implied endorsement'),
 ('Original author-written software and original figures',None,'Author / software dependency copyright holders','','Author-controlled code likely sharable only after checking upstream inclusions, patents and dependency terms','AUTHOR CHECK','code/, originals, figures only','Check upstream code owner and patent disclosure, annotate software dependencies and exact versions'),
 ('Zenodo DOI registration',None,'CERN / Zenodo','https://help.zenodo.org/docs/deposit/create-new-upload/','New deposit DOI is registered when published; prepublication reservation is not a registered DOI','UNAVAILABLE WITHOUT AUTHORIZED DEPOSIT','Metadata release pending','Do not assert DOI; deposit rights-cleared snapshot and publish under authorised Zenodo account')
]
pd.DataFrame(licences,columns=['material','source_file_count','rights_holder','official_terms_url','verified_scope','disposition','file_classes_affected','release_conditions']).to_csv(A/'NOV8_08_SOURCE_RIGHTS_AUDIT.csv',index=False)
(A/'NOV8_08_SOURCE_RIGHTS_AUDIT.md').write_text('''# Source permissions and public-release decision — 8 November 2026

**Decision: do not publish this complete archive or the previous repository candidate yet.** This is a good-faith source-based review, not legal sign-off.

- **BC Hydro:** published site terms reserve reuse rights and require case-specific permission for covered content. It is not clear whether downloaded transmission worksheets and all derived access factors carry those terms; hold them for review. https://www.bchydro.com/siteinfo/legal.html
- **AESO:** site copyright restricts copying to noncommercial personal or educational use; other re-use needs written permission. Hold the raw five-facility CSV and derived material for review. https://aeso.ca/legal/
- **ECCC:** the Historical Climate Data site and its licensing can differ from the current MSC Open Data Service. The MSC 2026 open licence allows redistribution with attribution. Confirm the licence attached to the exact 1,364 station CSV downloads before a public release. https://climate.weather.gc.ca/  and  https://eccc-msc.github.io/open-data/licence/readme_en/
- **Copernicus:** its licence permits redistribution/adaptation of Copernicus Products with required credit; verify the exact underlying product. https://cds.climate.copernicus.eu/licences/licence-to-use-copernicus-products
- **Global Wind Atlas:** CC BY 4.0 by default, except individually differently licensed works; attribution/changes/no endorsement apply. https://globalwindatlas.info/about/TermsOfUse
- **Author code and figures:** verify all imported baseline material is owned or appropriately licensed and that any pending-patent disclosure does not conflict with release choices.

**Repository design:** include own code and non-sensitive original explanatory materials; provide retrieval scripts and provenance hashes in place of uncertain raw data. Do not distribute prepared access arrays or previous zipped original source downloads until specific rights are settled. A code-only release is unlikely to reproduce the exact frozen run without separately acquired, licensed inputs; disclose this limitation. No unrestricted research DOI is issued, and no online upload occurred.

Official legal references and a file-class disposition table are in NOV8_08_SOURCE_RIGHTS_AUDIT.csv. Commercial law counsel or publisher repository staff should check ambiguous use rights.
''')
(A/'NOV8_08_LIFECYCLE_STATUS.md').write_text('''# Lifecycle-accounting status (not a completed full LCA)

The attached ledger contains annual fuel, electricity and storage activities for 2010–2025, two portfolios, and six *assumed* carbon factors. It is internally reproducible but **not a verified cradle-to-grave, ISO 14040/14044-compliant lifecycle inventory**. It covers inherited wind/solar aggregate lifecycle proxies, battery embodied proxy, HVO and B100 generic well-to-wheel fuel proxy, and generic grid imports. The lifecycle completeness register identifies missing hydropower, plant/civil works, greenhouse and aquaculture, computers/GPUs, methane/refrigerants, decommissioning, fuel feedstocks, actual-hour grid mix, actual equipment bills of materials, and matched gas-comparator stages. Some generic factors already include manufacturing so adding equipment construction separately would double count emissions.

The arithmetic result is a *partial proxy*, not evidence of a 2.089-Mt whole-network emissions figure or a lifecycle advantage over Wonder Valley. Neither comparative percent reduction nor claims of zero carbon should appear in the manuscript. The register gives every unresolved required stage with a source and ownership pathway. No supplier-certified EPDs, fuel delivery records, final equipment schedule, or fuel-pathway verification were attached, so these stages cannot be calculated honestly.

The six initial factors are inherited assumptions (11 g/kWh wind, 35 g/kWh solar, 70 kg/kWh battery, 25 g/MJ HVO, 30 g/MJ B100, 100 g/kWh grid). The 2010–2025 dispatch and annual inventory are computed in the supplied code. See NOV8_08_BOUNDED_LCA_PROXY_ANNUAL.csv. Missing components are not assumed zero.
''')
meta={'title':'Digital Gardens versus Wonder Valley: 2010–2025 conditional electricity dispatch and robustness research (NOV8_08)', 'upload_type':'dataset','creators':[{'name':'Bily, Jonathan Karl','orcid':'0009-0004-3526-7271','affiliation':'Independent researcher'}], 'description':'Full 2010–2025 conditional research model and fixed-build stress/synthetic security screens; not physically validated. DOI deposit is paused pending source redistribution rights and reviewer sign-off.', 'keywords':['energy systems','artificial intelligence','renewables','British Columbia','wind','power systems','transmission','research reproducibility'],'version':'NOV8_08', 'access_right':'restricted','license':'Rights review required; no blanket licence assigned', 'doi':'NOT ISSUED','status':'DRAFT METADATA ONLY — no deposition performed'}
(A/'NOV8_08_ZENODO_METADATA_DRAFT.json').write_text(json.dumps(meta,indent=2)+'\n')
(A/'NOV8_08_ZENODO_DOI_INSTRUCTIONS.md').write_text('''# DOI: pending authorised, licence-cleared deposition

No Zenodo session, API authentication or publication permission is available in this working environment. A DOI cannot be truthfully fabricated. Publication would also expose materials under unresolved third-party redistribution terms. A DOI is thus **not obtained**.

After clearing rights, make a Zenodo *new upload* (or an explicitly compatible new version of a pre-existing record), upload the frozen rights-cleared research snapshot, enter creators/ORCID and version, reserve a DOI if needed for manuscript typesetting, review visibility and licence, then publish. Only publication registers the DOI; confirm it resolves to the exact artifact/version. Replace the manuscript's release-pending statement and corresponding checksum with that DOI. Do not reuse the older 8-to-10-MW research DOI as though it identifies this new model snapshot.

Source: https://help.zenodo.org/docs/deposit/create-new-upload/ ; https://help.zenodo.org/docs/deposit/manage-versions/
''')
print('LCA means:\n',means.to_string(index=False));print('rights rows:',len(licences))
