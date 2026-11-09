import bootstrap
from bootstrap import ROOT
import json,html
import pandas as pd,numpy as np
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,PageBreak,Image
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4

s=pd.read_csv(ROOT/'results/report_summary.csv');allr=s[s.period=='all'].set_index('scenario')
primary=allr.loc['new_build_observed_shape'];old=allr.loc['old_build_constant_access']
fit=json.loads((ROOT/'results/fit_results.json').read_text());c=fit['selected_capacities']
validation=json.loads((ROOT/'results/model_validation.json').read_text())
weather=pd.read_csv(ROOT/'results/weather_regional_comparison.csv');weather=weather[weather.period=='2010_2025']
aes=json.loads((ROOT/'results/aeso_coverage.json').read_text())

intro=f"The downloaded evidence supports a new conditional capacity-and-dispatch model. The selected candidate contains {sum(c[:5]):.3f} GW wind (763 whole 8-MW turbines), {c[5]:.3f} GW solar and {c[6]:.3f} GWh storage. It supplies every modeled central-case hour in 2010-2025, including the frozen-capacity 2020-2025 evaluation. This is an energy-adequacy result under specified assumptions, not demonstrated engineering feasibility."
cost=f"The central-case conditional cost is C${primary.cost_CAD_MWh:.2f}/MWh over all sixteen years. The original build under the same revised cost accounting and constant access costs C${old.cost_CAD_MWh:.2f}/MWh. The preceding paper's C$192.47/MWh used different inventory/chronology assumptions; do not present the difference as a pure observed-data effect. The original pooled C$191.5020775/MWh result was first reproduced exactly."
margin=f"Mean annual HVO use is {primary.mean_HVO_ML:.1f} ML and the maximum is {primary.max_HVO_ML:.3f} ML against an assumed 976.4516-ML ceiling. The worst-year margin is only {primary.fuel_margin_ML:.3f} ML (about {100*primary.fuel_margin_ML/976.4516:.3f}%). Fuel sourcing, delivery timing and engine operating constraints remain unverified."
access="Hourly project ceilings are varied using a normalized historical directional TTC index. AB/US directional values are summed only as a stress index, divided by the 2010-2019 95th percentile (3,500 MW import; 3,600 MW export), clipped to one and multiplied by the assumed 2.5/3-GW project ceilings. This is hypothetical exposure to transfer reductions. It is not spare capacity, simultaneous path capability or a project interconnection award."
method="Two seeded bounded searches fit capacities on 2010-2019 only. Whole turbine counts are then selected on the same training period and frozen. No 2020-2025 result is used to select capacities. The inherited ERA5/GWA resource calibration used the original full archive, so the held-out claim concerns capacity planning conditional on those supplied resource shapes, not independent wind prediction."
dispatch="Hourly dispatch uses only current supply, demand, access and stored inventories. Storage starts empty and carries state across years. Annual assumed fuel allowances reset at year boundaries; February 29 is omitted to retain the inherited 8,760-hour years. Endogenous losses use the original synthetic intact-network DC flow model, reduced to an equivalent quadratic expression. No old ex-post contingency reserve schedule is used."
limitations="The new build has not undergone a new nonlinear AC/N-1, reactive capability, dynamic stability or unit-commitment assessment. Public weather stations do not validate the proposed ridge yields. Equipment curves, construction costs, electricity prices and fuel procurement remain assumptions. The prior 2.089-Mt emissions result must not be transferred to this portfolio: this revision reports only clearly scoped HVO-upstream and grid-emission components, not a new whole-system LCA."

stress_ids=['old_build_observed_shape','new_build_observed_shape','new_build_wind_minus10pct','new_build_half_access','new_build_local160MW','new_build_clock_minus1h','new_build_clock_plus1h','new_build_missing_TTC_previous','new_build_local160MW_gapfilled']
table_md='| Scenario | Unmet energy, 2010-2025 (GWh) | Full-service cost (C$/MWh) |\n|---|---:|---:|\n'
for k in stress_ids:
 r=allr.loc[k];v=f'{r.full_service_cost_CAD_MWh:.2f}' if pd.notna(r.full_service_cost_CAD_MWh) else 'Not qualified'
 table_md+=f'| {r.scenario_label} | {r.total_unserved_GWh:,.3f} | {v} |\n'
period=s[s.scenario=='new_build_observed_shape']
period_md='| Period | Conditional cost (C$/MWh) | Mean HVO (ML/year) | Mean import (TWh/year) | Unmet energy (GWh) |\n|---|---:|---:|---:|---:|\n'
for r in period.itertuples():period_md+=f'| {r.first_year}-{r.last_year} ({r.period}) | {r.cost_CAD_MWh:.2f} | {r.mean_HVO_ML:.1f} | {r.mean_import_TWh:.3f} | {r.total_unserved_GWh:.3f} |\n'
weather_md='| Station / municipal proxy | Distance (km) | Temperature MAE (C) | Temperature r | Surface-vs-100m wind temporal r |\n|---|---:|---:|---:|---:|\n'
for r in weather.itertuples():weather_md+=f'| {r.station} / {r.municipal_proxy} | {r.distance_km:.1f} | {r.temperature_MAE_C:.2f} | {r.temperature_Pearson_r:.3f} | {r.wind_temporal_Pearson_r_surface_vs100m:.3f} |\n'
md=f'''# New model and results: Digital Gardens versus Wonder Valley

8 November 2026

## Result

{intro}

{cost}

{period_md}

{margin}

## What changed

{access}

{method}

{dispatch}

The unchanged resource shapes remain modelled proxies. New weather observations are used for transparent comparisons, not to fabricate a ridge wind calibration. The AESO data provide an Alberta benchmark, not BC measurements. No new repository or DOI has been created.

## Fixed-build stresses

{table_md}

The original build fails the new access scenario in 1,900 modeled hours, totaling 2.773 TWh of unmet load, all in the fitting period. The revised central build removes those energy shortfalls but is not robust to all tested stresses. The 10% wind reduction produces 512.259 GWh of unmet load. Half access produces 34.377 TWh. The 160-MW/site limit produces 65.872 GWh; prior-value gap treatment still leaves 61.281 GWh. The clock-minus-one-hour case produces 4.243 GWh. No emergency fossil fuel is silently invented to cover these deficits. Expenditure figures for cases with unmet load must not be called reliable-service electricity prices.

## Observational evidence

All 1,456 planned data files were present; all 2,922 source-manifest entries passed hash checks. The data comprise 91 BC Hydro workbooks, 1,364 station-month CSVs and one AESO file. Some workbooks change day/month convention mid-sheet; chronological parsing is documented. There are 1,439 duplicate timestamp/series combinations, including 633 disagreements, retained in the audit. Missing TTC affects 16 import-factor hours and 32 export-factor hours. The central case uses zero access only at these flagged gaps; alternative gap handling is separately reported.

{weather_md}

Only three station/municipal pairs meet the predeclared 25-km comparison screen. Temperature differences include location/elevation mismatch. Wind correlations compare surface observations with municipal ERA5 100-m temporal variation; they do not establish speed bias, hub-height capacity factors or ridge-farm output. Station observations may have contributed to reanalysis. No bias correction was applied. Summerland's supplied station-inventory timezone is MST and was retained; metadata verification remains a qualification.

The AESO file actually spans {aes['start_utc']} to {aes['end_utc']}, with {aes['rows']:,} rows and {aes['all_five_observed_hours']:,} hours containing all five assets. Asset-pair generation correlations range approximately 0.665-0.925 over pairwise available records, indicating strong dependence in this external benchmark. Missing asset records were not replaced by zero, and nameplate capacities were not inferred from observed maxima.

## Verification and interpretation

Four focused tests passed: independent dispatch/causality, fuel exhaustion/no free storage, quadratic versus direct branch-loss calculation, and mixed-date handling. All ten full scenarios passed energy balance, state continuity, fuel, power and grid-cap checks. Maximum energy-balance residual is below 2e-12 MW; maximum loss fixed-point residual is below 1e-7 MW. The selected build's intact synthetic DC loading maximum is 57.07% of assumed ratings, with no intact DC thermal exceedance. This is not an AC/N-1 result.

{limitations}

The paper is stronger as a reproducible conditional study because it now tests historical access variation, separates fitting from evaluation, exposes missing-data handling and reports adverse outcomes. The evidence does not support replacing that claim with construction readiness or a guaranteed secure electricity price.

## Reproduction and source rights

See README.md and METHODS_AUDIT_NOTES.md. Prepared inputs allow replay without network access or an Excel reader. The bundle contains original third-party data for the author's research; it is not the sanitized public repository candidate. Source terms must be checked before public redistribution. Original input files and the earlier manuscript archive remain unchanged.

Official sources: [BC Hydro historical load/TTC](https://www.bchydro.com/energy-in-bc/operations/transmission/transmission-system/balancing-authority-load-data/historical-transmission-data.html), [BC Hydro actual flows](https://www.bchydro.com/energy-in-bc/operations/transmission/transmission-system/actual-flow-data/historical-data.html), [ECCC observations](https://climate.weather.gc.ca/), [AESO five-facility dataset](https://www.aeso.ca/market/market-and-system-reporting/data-requests/hourly-metered-volumes-for-five-wind-facilities-2010-2019/).
'''
(ROOT/'NEW_MODEL_RESULTS.md').write_text(md,encoding='utf-8')
draft=f'''# Draft replacement methods/results text

This text describes the new model; reconcile the article, supplement, figures, availability statements and emissions accounting before submission. Earlier AC/N-1 results concern the earlier portfolio and cannot be carried over as validation of this build.

We introduced a conditional project-access scenario shaped by BC Hydro's historical directional total-transfer-capacity records. The normalized index modulates assumed import/export ceilings without representing awarded access or residual headroom. We preserved the inherited ERA5/GWA resource shapes and used newly retrieved ECCC observations for separate regional consistency checks. An hourly causal dispatch model carries storage across years and includes endogenous synthetic-network DC I-squared-R losses. Capacity selection uses 2010-2019 only, followed by frozen-capacity evaluation in 2020-2025.

{intro}

The 16-year central-case cost screen is C$202.47/MWh under inherited price and capital assumptions, with mean imports of 9.087 TWh/year, exports of 2.389 TWh/year and network losses of 193.5 GWh/year. The 2020-2025 evaluation yields C$196.23/MWh and no unmet load. These values are not a secure-project tariff or utility-approved cost estimate. Mean annual HVO use is 676.2 ML, with a maximum of 975.199 ML against an assumed 976.4516-ML limit.

The central result is sensitive to uncertainty. A fixed-build 10% wind reduction causes 512.3 GWh of unmet load over the sixteen years; half the modeled access causes 34.38 TWh. A 160-MW-per-campus firm-generation limit causes 65.9 GWh (61.3 GWh with alternative gap treatment), and a one-hour alignment sensitivity causes 4.24 GWh. These results preclude a robust engineering-feasibility claim. New site-resource, equipment, fuel-supply, dynamic-network and AC/N-1 evidence is required. A complete emissions ledger must be recomputed for the new portfolio before replacing the previous whole-system emissions headline.
'''
(ROOT/'DRAFT_REVISED_RESULTS.md').write_text(draft,encoding='utf-8')

styles=getSampleStyleSheet();styles.add(ParagraphStyle(name='BodySmall',fontName='Helvetica',fontSize=9.4,leading=13,spaceAfter=7));styles.add(ParagraphStyle(name='Tiny',fontName='Helvetica',fontSize=8,leading=10.5,spaceAfter=5));styles['Title'].fontSize=22;styles['Title'].leading=26;styles['Heading1'].fontSize=15;styles['Heading1'].leading=19
story=[]
def P(text,style='BodySmall'):return Paragraph(text,styles[style])
def add(text,style='BodySmall'):story.append(P(text,style))
def table(data,widths):
 wrapped=[[P(html.escape(str(x)),'Tiny') for x in row] for row in data]
 t=Table(wrapped,colWidths=widths,repeatRows=1,hAlign='LEFT')
 t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e5efef')),('VALIGN',(0,0),(-1,-1),'TOP'),('LINEBELOW',(0,0),(-1,0),.6,colors.HexColor('#137f82')),('LINEBELOW',(0,1),(-1,-1),.3,colors.HexColor('#d4dddd')),('LEFTPADDING',(0,0),(-1,-1),6),('RIGHTPADDING',(0,0),(-1,-1),6),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),4)]));story.append(t);story.append(Spacer(1,9))
def figure(name,w,h):story.append(Image(str(ROOT/'figures'/name),width=w,height=h));story.append(Spacer(1,5))
add('Digital Gardens versus Wonder Valley','Title');add('New model and results | 8 November 2026','Heading2');add(intro)
table([['Capacity','Original build','Revised build'],['Wind', '5.856 GW / 732 turbines',f'{sum(c[:5]):.3f} GW / 763 turbines'],['Solar','4.866 GW',f'{c[5]:.3f} GW'],['Battery energy','3.133 GWh',f'{c[6]:.3f} GWh']],[160,175,175])
add('Central-case results','Heading1')
table([['Period','C$/MWh','HVO ML/year','Imports TWh/year','Unmet GWh']]+[[f'{r.first_year}-{r.last_year}',f'{r.cost_CAD_MWh:.2f}',f'{r.mean_HVO_ML:.1f}',f'{r.mean_import_TWh:.3f}',f'{r.total_unserved_GWh:.3f}'] for r in period.itertuples()],[115,85,105,115,90])
add(cost);add(margin);add('Referee interpretation: a stronger conditional study, with a narrow fuel margin. It does not demonstrate that the proposed physical system can be built and operated as assumed.','Heading2')
story.append(PageBreak())
add('How the new evidence enters the model','Heading1');add(access);figure('Figure_3_grid_access.png',510,241)
add(method);add(dispatch)
add('Data audit','Heading2');add('All 2,922 manifest entries matched their hashes. The 1,456 source files include 91 grid workbooks and 1,364 weather station-months. Mixed day/month conventions were resolved by chronological continuity. Duplicate TTC values use the lower value; 633 conflicting timestamp/series combinations remain visible in the audit. Missing TTC affects 16 import and 32 export factor hours. Missing values are flagged; zero access is a conservative scenario assumption.')
add('Time alignment uses hour-ending labels converted to hour beginning under fixed PST. Because every historical daylight-saving convention could not be established, plus/minus-one-hour and gap-treatment sensitivities are reported. These are qualifications, not corrections asserted as observations.','Tiny')
story.append(PageBreak())
add('Stress tests at the frozen revised build','Heading1')
data=[['Scenario','Unmet energy, all 16 years (GWh)','Full-service C$/MWh']]
for k in stress_ids:
 r=allr.loc[k];data.append([r.scenario_label,f'{r.total_unserved_GWh:,.3f}',f'{r.full_service_cost_CAD_MWh:.2f}' if pd.notna(r.full_service_cost_CAD_MWh) else 'Not qualified'])
table(data,[250,145,115]);add('No emergency fossil supply is invented to erase deficits. Costs for unmet-load cases are not qualified full-service electricity costs. The revised portfolio was not retuned after these stress outcomes.','Tiny')
figure('Figure_1_fuel_and_adequacy.png',460,363)
story.append(PageBreak())
add('Observations, verification and paper implications','Heading1')
table([['Station / nearby proxy','Distance km','Temp. MAE C','Temp. r','Wind timing r']]+[[r.station+' / '+r.municipal_proxy,f'{r.distance_km:.1f}',f'{r.temperature_MAE_C:.2f}',f'{r.temperature_Pearson_r:.3f}',f'{r.wind_temporal_Pearson_r_surface_vs100m:.3f}'] for r in weather.itertuples()],[220,65,80,65,80])
add('Three pairs meet the 25-km screen. These are regional comparisons, not colocated ridge observations. Wind timing correlations compare surface measurements with modeled municipal 100-m wind, so they cannot validate capacity factors or support a direct speed correction. Reanalysis may assimilate station data. Source timezone metadata, including Summerland MST, was retained and remains a qualification.')
add(f'The AESO benchmark contains {aes["rows"]:,} hourly rows ending 1 October 2019, rather than a complete 2019 year. Only {aes["all_five_observed_hours"]:,} hours contain all five assets. Pairwise generation correlations are about 0.665-0.925. Missing asset output is preserved, and no installed capacity is inferred from observed maxima.')
add('Verification','Heading2');add('Independent dispatch/causality, fuel exhaustion, quadratic-loss equivalence and mixed-date tests pass. All ten full scenarios pass energy, storage, fuel and grid-limit audits. Energy-balance error is below 2e-12 MW; loss fixed-point error is below 1e-7 MW. Intact synthetic DC branch loading reaches 57.07%, without a thermal exceedance. This does not establish AC voltage or contingency security.')
add(limitations)
add('Use in the paper','Heading2');add('Report the central case together with its failures and uncertainty. Replace the old portfolio/cost claims consistently; keep old results as a labelled comparison. Recompute the complete emissions ledger before changing the carbon headline. README.md gives replay commands; DRAFT_REVISED_RESULTS.md supplies manuscript text. This bundle includes third-party source data for research and is not a sanitized public release.')
add('Official source pages','Heading2')
for label,url in [('BC Hydro historical load and TTC','https://www.bchydro.com/energy-in-bc/operations/transmission/transmission-system/balancing-authority-load-data/historical-transmission-data.html'),('BC Hydro historical actual flows','https://www.bchydro.com/energy-in-bc/operations/transmission/transmission-system/actual-flow-data/historical-data.html'),('ECCC historical observations','https://climate.weather.gc.ca/'),('AESO five wind facilities','https://www.aeso.ca/market/market-and-system-reporting/data-requests/hourly-metered-volumes-for-five-wind-facilities-2010-2019/')]:add(f'<link href="{url}" color="#137f82">{label}</link>','Tiny')
def footer(canvas,doc):
 canvas.setFont('Helvetica',8);canvas.setFillColor(colors.HexColor('#555555'));canvas.drawString(43,24,'Digital Gardens / Wonder Valley - conditional modelling results');canvas.drawRightString(A4[0]-43,24,str(doc.page))
doc=SimpleDocTemplate(str(ROOT/'NEW_MODEL_RESULTS.pdf'),pagesize=A4,leftMargin=43,rightMargin=42,topMargin=38,bottomMargin=40,title='Digital Gardens versus Wonder Valley: New Model and Results',author='Research revision')
doc.build(story,onFirstPage=footer,onLaterPages=footer)
print('Created report and manuscript draft',flush=True)
