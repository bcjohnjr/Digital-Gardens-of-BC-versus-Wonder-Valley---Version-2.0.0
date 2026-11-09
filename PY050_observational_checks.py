import bootstrap
from bootstrap import ROOT
import json,math
import numpy as np,pandas as pd

def km(a,b):
 p1,p2=map(math.radians,[a['latitude'],b['latitude']]);dl=math.radians(b['longitude']-a['longitude'])
 return 6371*2*math.asin(math.sqrt(math.sin((p2-p1)/2)**2+math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2))

stations=json.loads((ROOT/'inputs/selected_stations.json').read_text())
base=ROOT/'baseline/RESEARCH_CODE/DATA/WEATHER';towns=json.loads((base/'locations.json').read_text())
obs=pd.read_csv(ROOT/'inputs/weather_qc_hourly.csv.gz',parse_dates=['time_utc'])
rows=[];pairs=[]
for st in stations:
 town=min(towns,key=lambda x:km(st,x));distance=km(st,town)
 pairs.append({'station_id':st['station_id'],'station':st['name'],'nearest_municipal_proxy':town['community'],'distance_km':distance,'included_under25km':distance<=25,'timezone_metadata':st['timezone']})
 if distance>25:continue
 key=town['community'].lower().replace(' ','_')
 model=pd.read_csv(base/(key+'_hourly_era5.csv.gz'),usecols=['time_utc','temperature_2m','wind_speed_100m'],parse_dates=['time_utc'])
 merged=obs[obs.station_id==st['station_id']].merge(model,on='time_utc')
 for label,mask in [('2010_2019',merged.time_utc.dt.year<=2019),('2020_2025',merged.time_utc.dt.year>=2020),('2010_2025',merged.time_utc.dt.year.between(2010,2025))]:
  a=merged[mask];t=a[['temperature_C','temperature_2m']].dropna();w=a[['wind_ms','wind_speed_100m']].dropna();err=t.temperature_2m-t.temperature_C
  rows.append({'station_id':st['station_id'],'station':st['name'],'municipal_proxy':town['community'],'distance_km':distance,'period':label,'temperature_pairs':len(t),'temperature_bias_model_minus_observed_C':err.mean(),'temperature_MAE_C':err.abs().mean(),'temperature_RMSE_C':np.sqrt((err**2).mean()),'temperature_Pearson_r':t.corr().iloc[0,1],'wind_pairs':len(w),'wind_temporal_Pearson_r_surface_vs100m':w.corr().iloc[0,1],'interpretation':'Regional temporal comparison, not colocated hub-height validation; no wind bias correction applied.'})
pd.DataFrame(pairs).to_csv(ROOT/'results/weather_pair_selection.csv',index=False)
pd.DataFrame(rows).to_csv(ROOT/'results/weather_regional_comparison.csv',index=False)
# Describe joint observations without using surface wind as turbine output.
temp=obs.pivot(index='time_utc',columns='station_id',values='temperature_C');wind=obs.pivot(index='time_utc',columns='station_id',values='wind_ms')
common=pd.DataFrame({'regional_median_temperature_C':temp.median(axis=1).where(temp.count(axis=1)>=3),'regional_median_surface_wind_ms':wind.median(axis=1).where(wind.count(axis=1)>=3)})
grid=pd.read_csv(ROOT/'inputs/grid_hourly_utc.csv.gz',parse_dates=['time_utc']).set_index('time_utc')
common=common.join(grid[['ttc_ab_bc','ttc_us_bc','load']]);common['import_ttc_index']=common[['ttc_ab_bc','ttc_us_bc']].sum(axis=1,min_count=2)
joint=[]
for year,g in common.groupby(common.index.year):
 if not 2010<=year<=2025:continue
 valid=g[['regional_median_temperature_C','regional_median_surface_wind_ms','import_ttc_index','load']].notna().all(axis=1);g=g[valid]
 cold=g.regional_median_temperature_C<-10;calm=g.regional_median_surface_wind_ms<3;restricted=g.import_ttc_index<.6*3500
 joint.append({'year':year,'joint_valid_hours':len(g),'cold_low_surface_wind_hours':int((cold&calm).sum()),'cold_low_wind_and_low_TTC_index_hours':int((cold&calm&restricted).sum()),'peak_observed_BC_load_MW':g.load.max(),'note':'At least three observed stations per hourly median; not a wind-farm CF or project grid-access observation.'})
pd.DataFrame(joint).to_csv(ROOT/'results/joint_weather_grid_observations.csv',index=False)
print(pd.DataFrame(rows).to_string(index=False),flush=True)
