import bootstrap
from bootstrap import ROOT
import argparse,hashlib,json,re,datetime as dt
from pathlib import Path
import numpy as np,pandas as pd

DEFAULT=Path(r'C:\Users\jonbi\OneDrive\Attachments\Desktop\Digital-Gardens-of-BC\NOV8-Download\downloaded_evidence')

def verify(root):
 rows=[]
 for line in (root/'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines():
  expected,name=line.split('  ',1);p=root/name;h=hashlib.sha256(p.read_bytes()).hexdigest()
  if h!=expected:raise ValueError('Source hash mismatch '+name)
  rows.append({'path':name,'sha256':h,'bytes':p.stat().st_size})
 pd.DataFrame(rows).to_csv(ROOT/'results/download_source_hashes.csv',index=False)
 print('Verified source manifest:',len(rows),'files',flush=True)

def num(v):
 if v is None:return np.nan
 try:return float(str(v).replace(',','').strip())
 except ValueError:return np.nan

def chronological_dates(possible):
 # Select date interpretations from chronological continuity, including files
 # that change display convention mid-year. Do not cache ambiguous text across
 # nonadjacent blocks: 05/01 can mean Jan 5 early and May 1 later in one sheet.
 blocks=[];mapping=[]
 for r,h in possible:
  text=r[0].strip()
  if not blocks or text!=blocks[-1]:blocks.append(text)
  mapping.append(len(blocks)-1)
 candidates=[]
 for text in blocks:
  m=re.match(r'^(\d{1,2})/(\d{1,2})/(\d{4})(?:\s|$)',text)
  if m:
   a,b,y=map(int,m.groups());c=[]
   for mo,day in [(a,b),(b,a)]:
    try:
     d=pd.Timestamp(year=y,month=mo,day=day)
     if d not in c:c.append(d)
    except ValueError:pass
  else:
   try:c=[pd.to_datetime(text).normalize()]
   except (ValueError,TypeError):c=[]
  if not c:raise ValueError('Invalid data date: '+text)
  candidates.append(c)
 if not candidates:return [],0
 costs=[0.]*len(candidates[0]);paths=[]
 for i in range(1,len(candidates)):
  nc=[];back=[]
  for d in candidates[i]:
   options=[]
   for k,prev in enumerate(candidates[i-1]):
    delta=(d-prev).days
    penalty=abs(delta-1)+(100000 if delta<0 else 0)
    options.append(costs[k]+penalty)
   ix=int(np.argmin(options));nc.append(options[ix]);back.append(ix)
  costs=nc;paths.append(back)
 state=int(np.argmin(costs));penalty=costs[state];chosen=[candidates[-1][state]]
 for i in range(len(candidates)-2,-1,-1):
  state=paths[i][state];chosen.append(candidates[i][state])
 chosen.reverse()
 if penalty>=100000:raise ValueError('Chronology cannot resolve date display conventions')
 return [chosen[i] for i in mapping],penalty

def grid():
 records=[];audit=[]
 for p in sorted((ROOT/'inputs/grid_workbook_extracts').glob('*.xls.json')):
  j=json.loads(p.read_text(encoding='utf-8-sig'));name=j['source_file'];upper=name.upper()
  if 'ANDCONSTRAINT' in upper:
   audit.append({'file':name,'status':'excluded overlapping legacy constraint workbook'});continue
  if 'TTC' in upper:
   if upper.startswith('ABBC'):kind='ttc_ab_bc'
   elif upper.startswith('BCAB') or upper.startswith('DEC2010'):kind='ttc_bc_ab'
   elif upper.startswith('BCUS'):kind='ttc_bc_us'
   elif upper.startswith('USBC'):kind='ttc_us_bc'
   else:raise ValueError(name)
  elif 'LOAD' in upper:kind='load'
  elif 'TIELINE' in upper:kind='flow'
  else:raise ValueError(name)
  for s in j['sheets']:
   raw=s['rows'];ttc_col=None
   for r in raw[:25]:
    for k,v in enumerate(r):
     if str(v).strip().upper() in ['TTC','FINAL HOURLY TTC']:ttc_col=k
   if kind.startswith('ttc') and ttc_col is None:
    audit.append({'file':name,'sheet':s['sheet'],'status':'no TTC data header'});continue
   possible=[]
   for r in raw:
    if len(r)<3 or not isinstance(r[0],str):continue
    h=num(r[1])
    if np.isfinite(h) and h==int(h) and 1<=h<=24:
     possible.append((r,int(h)))
   slash=[]
   for r,h in possible:
    m=re.match(r'^(\d{1,2})/(\d{1,2})/(\d{4})',r[0])
    if m:slash.append(tuple(map(int,m.groups())))
   dayfirst=any(a>12 for a,b,c in slash)
   monthfirst=any(b>12 for a,b,c in slash)
   dates,date_penalty=chronological_dates(possible);good=0;bad=0
   for (r,h),date in zip(possible,dates):
    stamp=date+pd.Timedelta(hours=h-1+8) # explicit fixed-PST, hour beginning, UTC
    if kind=='flow':cols=[('flow_us',2),('flow_ab',3)]
    else:cols=[(kind,ttc_col if kind.startswith('ttc') else 2)]
    for series,k in cols:
     v=num(r[k]) if k<len(r) else np.nan
     if np.isfinite(v):records.append((stamp,series,v,name,s['sheet']))
    good+=1
   audit.append({'file':name,'sheet':s['sheet'],'status':'parsed','kind':kind,'rows_parsed':good,'invalid_date_rows':bad,'mixed_slash_conventions':dayfirst and monthfirst,'date_sequence_penalty_days':date_penalty,'types':str(s['column_types'])})
 data=pd.DataFrame(records,columns=['time_utc','series','value','source_file','source_sheet'])
 data=data[(data.time_utc>='2010-01-01')&(data.time_utc<'2026-01-01')]
 dup=data.groupby(['time_utc','series']).agg(count=('value','size'),min=('value','min'),max=('value','max'))
 dup[dup['count']>1].to_csv(ROOT/'results/grid_duplicate_audit.csv')
 # Different legacy versions/clock duplicates are not silently counted twice.
 parts=[]
 for series,g in data.groupby('series'):
  series_data=g.groupby('time_utc').value.min() if series.startswith('ttc') else g.groupby('time_utc').value.mean()
  parts.append(series_data.rename(series))
 full=pd.concat(parts,axis=1).sort_index()
 idx=pd.date_range('2010-01-01','2026-01-01',freq='h',inclusive='left')
 full=full.reindex(idx);full.index.name='time_utc'
 full.to_csv(ROOT/'inputs/grid_hourly_utc.csv.gz',compression='gzip')
 pd.DataFrame(audit).to_csv(ROOT/'results/grid_parsing_audit.csv',index=False)
 coverage=full.groupby(full.index.year).agg(['count','min','max','mean'])
 coverage.to_csv(ROOT/'results/grid_annual_source_summary.csv')
 full['import_ttc_index_MW']=full[['ttc_ab_bc','ttc_us_bc']].sum(axis=1,min_count=2)
 full['export_ttc_index_MW']=full[['ttc_bc_ab','ttc_bc_us']].sum(axis=1,min_count=2)
 training=full.index.year<=2019
 norms={x:float(full.loc[training,x+'_ttc_index_MW'].quantile(.95)) for x in ['import','export']}
 for x in ['import','export']:
  full[x+'_availability']=np.clip(full[x+'_ttc_index_MW']/norms[x],0,1)
  full[x+'_missing']=full[x+'_availability'].isna().astype(int)
  full[x+'_availability']=full[x+'_availability'].fillna(0)
 model_idx=idx[~((idx.month==2)&(idx.day==29))]
 use=full.reindex(model_idx)
 np.savez_compressed(ROOT/'inputs/grid_access.npz',import_factor=use.import_availability.to_numpy().reshape(16,8760),export_factor=use.export_availability.to_numpy().reshape(16,8760),import_missing=use.import_missing.to_numpy().reshape(16,8760),export_missing=use.export_missing.to_numpy().reshape(16,8760))
 report={'normalization_training_2010_2019_p95_MW':norms,'time_alignment':'HE -> hour beginning; assumed fixed PST = UTC-8. Hour-shift sensitivity required; historical DST convention not established for every workbook.',
 'duplicate_policy':'TTC minimum; load/flow mean at duplicate timestamps; disagreements retained in audit',
 'missing_conservative_zero_hours':{x:int(use[x+'_missing'].sum()) for x in ['import','export']},
 'availability_summary':{x:{'mean':float(use[x+'_availability'].mean()),'p05':float(use[x+'_availability'].quantile(.05)),'zero_hours':int((use[x+'_availability']==0).sum())} for x in ['import','export']},
 'duplicate_timestamp_series':int((dup['count']>1).sum()),'conflicting_duplicate_timestamp_series':int(((dup['count']>1)&(dup['max']!=dup['min'])).sum()),
 'interpretation':'The sum of directional TTC is a regional stress index, NOT simultaneous transfer capability or capacity awarded to this project.'}
 (ROOT/'results/grid_access_assumptions.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps(report,indent=2),flush=True)

def longest_run(mask):
 a=np.asarray(mask,dtype=bool);edges=np.flatnonzero(np.diff(np.r_[False,a,False]));return int(np.max(edges[1::2]-edges[::2])) if len(edges) else 0

def weather(root):
 stations=json.loads((root/'selected_stations.json').read_text());summary=[];series=[]
 for s in stations:
  files=sorted((root/'weather'/str(s['station_id'])).glob('*.csv'))
  a=pd.concat([pd.read_csv(p,low_memory=False) for p in files],ignore_index=True)
  times=pd.to_datetime(a['Date/Time (LST)']);offset={'PST':8,'MST':7}[s['timezone']]
  x=pd.DataFrame({'time_utc':times+pd.Timedelta(hours=offset),'station_id':s['station_id'],'wind_ms':pd.to_numeric(a['Wind Spd (km/h)'],errors='coerce')/3.6,'temperature_C':pd.to_numeric(a['Temp (°C)'],errors='coerce'),'wind_flag':a['Wind Spd Flag'].fillna(''),'temperature_flag':a['Temp Flag'].fillna('')})
  if x.time_utc.duplicated().any():raise ValueError('Duplicate weather timestamp')
  x.loc[x.wind_flag!='','wind_ms']=np.nan;x.loc[x.temperature_flag!='','temperature_C']=np.nan
  x=x.set_index('time_utc').reindex(pd.date_range(times.min()+pd.Timedelta(hours=offset),times.max()+pd.Timedelta(hours=offset),freq='h'));x.index.name='time_utc';x['station_id']=s['station_id']
  for year,g in x.groupby(x.index.year):
   if not 2010<=year<=2025:continue
   summary.append({'station_id':s['station_id'],'name':s['name'],'year':year,'expected_period_hours':len(g),'wind_valid_hours':int(g.wind_ms.count()),'temperature_valid_hours':int(g.temperature_C.count()),'mean_wind_ms':g.wind_ms.mean(),'wind_p95_ms':g.wind_ms.quantile(.95),'temperature_min_C':g.temperature_C.min(),'cold_below_minus10_hours':int((g.temperature_C<-10).sum()),'low_wind_below3_ms_hours':int((g.wind_ms<3).sum()),'longest_low_wind_hours':longest_run(g.wind_ms<3),'joint_cold_low_wind_hours':int(((g.temperature_C<-10)&(g.wind_ms<3)).sum())})
  series.append(x.reset_index()[['time_utc','station_id','wind_ms','temperature_C']])
 pd.DataFrame(summary).to_csv(ROOT/'results/weather_station_annual.csv',index=False)
 pd.concat(series,ignore_index=True).to_csv(ROOT/'inputs/weather_qc_hourly.csv.gz',index=False,compression='gzip')
 (ROOT/'inputs/selected_stations.json').write_text(json.dumps(stations,indent=2)+'\n')
 print('Weather annual records:',len(summary),flush=True)

def aeso(root):
 a=pd.read_csv(root/'aeso/five_wind_facilities_2010_2019.csv');a['time_utc']=pd.to_datetime(a.dt_Begin_GMT,format='%d%b%Y:%H:%M:%S')
 if a.time_utc.duplicated().any():raise ValueError('Duplicate AESO GMT hours')
 assets=['CR1','CRW1','IEW1','IEW2','OWF1'];rows=[]
 for asset in assets:
  for year,g in a.groupby(a.time_utc.dt.year):
   v=g[asset];q=v.quantile(.10)
   rows.append({'asset':asset,'year':int(year),'available_hours':int(v.count()),'missing_hours':int(v.isna().sum()),'mean_MWh_per_hour':v.mean(),'max_MWh_per_hour':v.max(),'p10_MWh_per_hour':q,'zero_output_hours':int((v==0).sum()),'max_abs_hourly_ramp_MW':v.diff().abs().max(),'longest_below_own_p10_hours':longest_run(v<q)})
 pd.DataFrame(rows).to_csv(ROOT/'results/aeso_asset_annual.csv',index=False)
 a[assets].corr().to_csv(ROOT/'results/aeso_output_correlation.csv')
 meta={'start_utc':str(a.time_utc.min()),'end_utc':str(a.time_utc.max()),'rows':len(a),'all_five_observed_hours':int(a[assets].notna().all(axis=1).sum()),'notes':'No nameplate capacities inferred. Missing generation is not zero. Out-of-region generation benchmark, not BC ridge-yield validation.'}
 (ROOT/'results/aeso_coverage.json').write_text(json.dumps(meta,indent=2)+'\n');print(meta,flush=True)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--evidence',type=Path,default=DEFAULT);p.add_argument('--skip-hashes',action='store_true');args=p.parse_args()
 if not args.skip_hashes:verify(args.evidence)
 grid();weather(args.evidence);aeso(args.evidence)
