#!/usr/bin/env python3
"""Optional independent BC surface-wind observations from PCIC PCDS.

Usage (Windows PowerShell or a terminal):
  python BC_WIND_STATIONS.py --dry-run
  python BC_WIND_STATIONS.py --years 2020:2025
  python BC_WIND_STATIONS.py --years 2010:2025 --radius-km 25
  python BC_WIND_STATIONS.py --years 2020:2025 --no-variable-filter

Outputs are downloaded ZIP files + a station/variable inventory; this is not a
validation of 100-m turbine production. Centre points below are geocoded
MUNICIPAL PROXIES from the archived model (NOT exact turbine coordinates).
The PCIC service can return an empty ZIP if no matching public wind data exist.

API documentation: https://services.pacificclimate.org/portal/docs/aggregate.html
Source terms: https://www.uvic.ca/pcic/data-analysis-tools/data-portal/station-data/index.php
"""
from __future__ import annotations
import argparse, csv, hashlib, io, json, math, re, sys, time, urllib.error, urllib.request, zipfile
from pathlib import Path

BASE = 'https://services.pacificclimate.org/met-data-portal-pcds/api/data'
# Model-archive municipality location records; not proposed turbine coordinates.
SITES = {
    'Cache_Creek': (50.81011, -121.32460),
    'Kamloops': (50.66648, -120.31920),
    'Lillooet': (50.68560, -121.94200),
    'Kelowna': (49.88307, -119.48568),
    'Penticton': (49.48062, -119.58584),
}

def make_polygon(lat, lon, radius_km, n=12):
    """Small geographic search polygon; approximate WGS84 radial distance."""
    pts = []
    for i in range(n):
        theta = i * 2 * math.pi / n
        dlat = (radius_km / 111.2) * math.sin(theta)
        dlon = (radius_km / (111.2 * math.cos(math.radians(lat)))) * math.cos(theta)
        pts.append((lon + dlon, lat + dlat))
    pts.append(pts[0])
    return 'POLYGON ((' + ', '.join(f'{x:.6f} {y:.6f}' for x, y in pts) + '))'

def build_payload(lat, lon, start, end, radius_km, unfiltered=False):
    data = {
        'from_date': start, 'to_date': end, 'clip_dates': True,
        'polygon': make_polygon(lat, lon, radius_km), 'format': 'csv'
    }
    if not unfiltered:
        data['variables'] = ['wind_speed']
    return data

def fetch_zip(payload, dest, timeout=180, max_mb=120):
    req = urllib.request.Request(
        BASE + '/agg', data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type':'application/json', 'User-Agent':'BCWindIndependentCheck/1.0 (research)'},
        method='POST')
    tmp = dest.with_suffix('.download')
    h = hashlib.sha256()
    count = 0
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response, tmp.open('wb') as out:
            while True:
                b = response.read(1024 * 1024)
                if not b: break
                count += len(b)
                if count > max_mb * 1024 * 1024:
                    raise ValueError(f'Response > {max_mb} MB; reduce radius or years')
                h.update(b); out.write(b)
        if not zipfile.is_zipfile(tmp):
            raise ValueError('Server did not return a ZIP (inspect service status)')
        with zipfile.ZipFile(tmp) as z:
            if z.testzip(): raise ValueError('ZIP CRC check failed')
            names = [i.filename for i in z.infolist() if not i.is_dir()]
            station_csv = [i for i in names if i.lower().endswith('.csv') and not i.lower().endswith('variables.csv')]
            wind_files=[]
            for filename in station_csv:
                with z.open(filename) as inp:
                    header = inp.read(8192).decode('utf-8-sig',errors='replace').splitlines()[:5]
                if any('wind' in x.lower() for x in header):
                    wind_files.append(filename)
        tmp.replace(dest)
        return {'status':'ok','files':len(names),'csv_files':len(station_csv),
                'csv_with_wind_column':len(wind_files), 'bytes':count, 'sha256':h.hexdigest(),
                'example_wind_member':' | '.join(wind_files[:3])}
    finally:
        if tmp.exists(): tmp.unlink()

def main():
    ap=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--years', default='2020:2025', help='inclusive years (e.g. 2010:2025)')
    ap.add_argument('--radius-km',type=float,default=25)
    ap.add_argument('--sites', nargs='*', choices=sorted(SITES), help='optional subset of model municipal proxies')
    ap.add_argument('--output', default='BC_WIND_OBSERVATIONS')
    ap.add_argument('--no-variable-filter', action='store_true', help='Try if wind_speed selection returned no stations; larger downloads')
    ap.add_argument('--dry-run',action='store_true', help='Print requests; do not download')
    ap.add_argument('--max-mb',type=int,default=120,help='per-response safety limit')
    args=ap.parse_args()
    m=re.fullmatch(r'(20\d\d):(20\d\d)',args.years)
    if not m: ap.error('--years must be YYYY:YYYY in the 2000s')
    first,last=map(int,m.groups())
    if first>last or last>2025 or first<2010:ap.error('Use a range within 2010–2025')
    if not 1<=args.radius_km<=80:ap.error('--radius-km must be between 1 and 80')
    sites = args.sites or list(SITES)
    output=Path(args.output);output.mkdir(parents=True,exist_ok=True)
    rows=[]
    for site in sites:
        lat,lon=SITES[site]
        for year in range(first,last+1):
            payload=build_payload(lat,lon,f'{year}-01-01',f'{year}-12-31',args.radius_km,args.no_variable_filter)
            name=f'{site}_{year}.zip';path=output/name
            print(site,year, 'model municipal proxy (not turbine)',flush=True)
            if args.dry_run:
                print('POST',BASE+'/agg',json.dumps(payload,ensure_ascii=False))
                continue
            try:
                res=fetch_zip(payload,path,max_mb=args.max_mb)
            except (urllib.error.URLError,ValueError,TimeoutError,OSError) as exc:
                res={'status':'ERROR '+str(exc),'files':0,'csv_files':0,'csv_with_wind_column':0,'bytes':0,'sha256':'','example_wind_member':''}
                print('WARNING',res['status'],file=sys.stderr)
            rows.append({'site':site,'proxy_lat':lat,'proxy_lon':lon,'year':year,
                         'radius_km':args.radius_km,'variable_filter':('none' if args.no_variable_filter else 'wind_speed'),
                         'archive':name,**res})
            print(res['status'],'wind-bearing station files:',res['csv_with_wind_column'],flush=True)
            time.sleep(0.3)
    if not args.dry_run:
        with (output/'DOWNLOAD_INDEX.csv').open('w',newline='',encoding='utf-8') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]) if rows else []);w.writeheader();w.writerows(rows)
        (output/'PROVENANCE.txt').write_text(
            'PCIC Provincial Climate Data Set public station downloads.\n'
            'Municipal centre coordinates were taken from model-archive locations.json; they are NOT proposed turbine coordinates.\n'
            'Source: '+BASE+'\nAPI: https://services.pacificclimate.org/portal/docs/aggregate.html\n'
            'PCIC/individual-provider terms apply; preserve original attribution and station metadata.\n'
            'Measurements may be 10 m surface speeds and may be incomplete, duplicate ECCC observations, or irregular.\n'
            'Do not convert surface speeds to hub-height turbine generation without an explicit height/terrain/wake model.\n',
            encoding='utf-8')
        print('\nSaved',output,'; inspect DOWNLOAD_INDEX.csv. If no wind-bearing stations, there is no usable new surface-wind evidence for that area.')
if __name__=='__main__':main()
