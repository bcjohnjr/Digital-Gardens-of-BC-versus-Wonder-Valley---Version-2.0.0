"""Digital Gardens vs Wonder Valley: transparent preliminary transmission DC/AC screening.
This is NOT a BC Hydro network model, protection study, route or NERC TPL certification.
"""
from pathlib import Path
import math, json, csv
import numpy as np
import pandas as pd
import networkx as nx
from scipy.optimize import linprog, root
from scipy.sparse import lil_matrix, csc_matrix
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent.parent
SRC=ROOT/'RESEARCH_CODE'
OUT=HERE/'N1_REOPT'
OUT.mkdir(exist_ok=True,parents=True)
SBASE=1000.0 # MVA

def slug(s): return s.lower().replace(' / ','_').replace(' ','_').replace('-','_')

def distance(a,b):
 la1,lo1=a;la2,lo2=b
 r1,r2=map(math.radians,(la1,la2));dr=r2-r1; dl=math.radians(lo2-lo1)
 h=math.sin(dr/2)**2+math.cos(r1)*math.cos(r2)*math.sin(dl/2)**2
 return 6371*2*math.asin(math.sqrt(h))

nodes=pd.read_csv(SRC/'OBSERVATIONAL_VALIDATION/solar_nodes.csv')
wind_sites=pd.read_csv(SRC/'OBSERVATIONAL_VALIDATION/ridge_sites.csv')
d=json.loads((HERE/'reoptimized_grid_case.json').read_text())
opt={'candidate':{'wind_gw_by_site':d['wind_capacity_GW_by_site'],'solar_gw':d['solar_GW'],'battery_gwh':d['battery_GWh']}}
wind_cap=opt['candidate']['wind_gw_by_site']
assert len(nodes)==17 and len(wind_cap)==5
# key performance metrics are printed after solving

# Existing site coordinates are approximate proxies, *not project land coordinates*.
loc={slug(r.community):(float(r.latitude),float(r.longitude)) for r in nodes.itertuples()}
hubnames=['cache_creek','kamloops','salmon_arm','kelowna','penticton','hope','abbotsford']
loadnames=list(loc)
hub_of={s:min(hubnames,key=lambda h:distance(loc[s],loc[h])) for s in loadnames}
# user-supplied proxy site metadata
windlat={}
for x in wind_sites.to_dict('records'):
 key=x.get('site_key',x.get('key',''))
 for candidate in ['latitude','lat','latitude_deg']:
  if candidate in x:
   la=float(x[candidate]);break
 else:continue
 for candidate in ['longitude','lon','longitude_deg']:
  if candidate in x:
   lo=float(x[candidate]);break
 else:continue
 windlat[key]=(la,lo)

buses=[]
def add_bus(name,kind,kv,coord):
 buses.append(dict(bus=name,kind=kind,kv=kv,latitude=coord[0],longitude=coord[1]))
add_bus('GRID','external_equivalent',500,(50.0,-120.75)) # synthetic external bus, not geographic interconnect point
for h in hubnames:
 add_bus('H_'+h,'conceptual_500kV_hub',500,loc[h]);add_bus('T_'+h,'conceptual_230kV_bus',230,loc[h])
for s in loadnames: add_bus('L_'+s,'load_230kV',230,loc[s])
for w,c in wind_cap.items():
 if w in windlat: coord=windlat[w]
 else:
  # NO invented coordinates: missing source coordinate is a hard error
  raise ValueError('Missing ridge coordinates for '+w)
 add_bus('W_'+w,'wind_collector_500kV',500,coord)
bi={r['bus']:i for i,r in enumerate(buses)}

branches=[]
def add_branch(a,b,kind,n,cap_mw,km,r_ohm_per_km,x_ohm_per_km,voltage_kv,extra_r=0.,extra_x=0.):
 assert a in bi and b in bi
 # per-unit on actual nominal voltage at each line side; transformers entered at a 500-kV-equivalent voltage
 zbase=voltage_kv**2/SBASE
 for c in range(n):
  branches.append(dict(line=f'{kind}:{a}>{b}:c{c+1}',a=a,b=b,kind=kind,km=round(km,2),rating_mva=cap_mw,r_pu=(km*r_ohm_per_km)/zbase+extra_r,x_pu=(km*x_ohm_per_km)/zbase+extra_x, nominal_kv=voltage_kv))

# Completely hypothetical 500kV corridors selected to connect the supplied city proxies.
connections=[('cache_creek','kamloops'),('cache_creek','hope'),('kamloops','salmon_arm'),('salmon_arm','kelowna'),('kelowna','penticton'),('penticton','hope'),('hope','abbotsford'),('kamloops','kelowna'),('salmon_arm','penticton'),('kelowna','hope'),('cache_creek','penticton')]
for a,b in connections:
 km=distance(loc[a],loc[b])*1.20 # illustrative route-length factor, not a surveyed corridor
 add_branch('H_'+a,'H_'+b,'500kV_backbone',2,1900,km,.026,.30,500)
# 3 assumed grid connections, each two independent 500kV circuits.
for h in ['kamloops','kelowna','abbotsford']:
 add_branch('GRID','H_'+h,'500kV_external_grid',2,2600,30,.026,.30,500)
# 500/230kV hub transformers each 1250MVA, 3 units, equivalent ideal ratio on pu bases
for h in hubnames:
 add_branch('H_'+h,'T_'+h,'500_230_transformer',3,1250,0,0,0,500,extra_r=.004,extra_x=.10*SBASE/1250)
# dual 230kV feeder corridors for each campus, even at same-town proxy minimum 10 km
for s in loadnames:
 h=hub_of[s]; km=max(10,distance(loc[h],loc[s])*1.18)
 add_branch('T_'+h,'L_'+s,'230kV_campus_feeder',2,550,km,.075,.38,230)
# each wind collector double 500kV circuits to nearest hub; no confirmed right of way.
windhub={}
for w in wind_cap:
 h=min(hubnames,key=lambda k:distance(windlat[w],loc[k]));windhub[w]=h
 km=max(12,distance(windlat[w],loc[h])*1.2)
 add_branch('W_'+w,'H_'+h,'500kV_wind_collector',2,1400,km,.026,.30,500)

pd.DataFrame(buses).to_csv(OUT/'assumed_buses.csv',index=False)
pd.DataFrame(branches).to_csv(OUT/'assumed_branches.csv',index=False)
pd.DataFrame([{'site':s,'assumed_hub':hub_of[s],'straight_line_km':distance(loc[s],loc[hub_of[s]])} for s in loadnames]).to_csv(OUT/'assumed_site_connections.csv',index=False)

nb=len(buses); nl=len(branches)
B=np.zeros((nb,nb)); flows=np.zeros((nl,nb));
for k,e in enumerate(branches):
 i,j=bi[e['a']],bi[e['b']];p=1/e['x_pu']
 B[i,i]+=p;B[j,j]+=p;B[i,j]-=p;B[j,i]-=p
 flows[k,i]=p*SBASE;flows[k,j]=-p*SBASE
ids=np.array([i for i in range(nb) if i!=bi['GRID']]);
# available wind and solar are dispatchable (curtailment allowed)
solar_total_mw=opt['candidate']['solar_gw']*1000
windcap={w:wind_cap[w]*1000 for w in wind_cap}
mean_load_mw=(36.00486+0.246358418)*1e6/8760 # 36.00486 TWh/y -> MW

# Import/export limits are ASSUMPTIONS for proposed negotiated transmission service,
# not BC Hydro reservations. Normal: 2.5 GW import, 3.0 GW export; sensitivity 1/1 and 4/6 GW.
# High renewable output deliberately tests curtailment with capped export. All numbers MW.
SCENARIOS=[
 {'name':'connected_average_import2500_export3000','load_multiplier':1.,'solar_cf':.25,'wind_cf':.33,'hvo_limit_mw_per_site':160,'import_cap_mw':2500,'export_cap_mw':3000},
 {'name':'connected_winter_import2500_export3000','load_multiplier':1.25,'solar_cf':.02,'wind_cf':.10,'hvo_limit_mw_per_site':160,'import_cap_mw':2500,'export_cap_mw':3000},
 {'name':'connected_highrenew_import2500_export3000','load_multiplier':1.,'solar_cf':.70,'wind_cf':.40,'hvo_limit_mw_per_site':160,'import_cap_mw':2500,'export_cap_mw':3000},
 {'name':'connected_winter_import1000_export1000','load_multiplier':1.25,'solar_cf':.02,'wind_cf':.10,'hvo_limit_mw_per_site':160,'import_cap_mw':1000,'export_cap_mw':1000},
 {'name':'connected_winter_import4000_export6000','load_multiplier':1.25,'solar_cf':.02,'wind_cf':.10,'hvo_limit_mw_per_site':160,'import_cap_mw':4000,'export_cap_mw':6000},
 {'name':'islanded_winter_stress_no_interchange','load_multiplier':1.25,'solar_cf':.02,'wind_cf':.10,'hvo_limit_mw_per_site':160,'import_cap_mw':0,'export_cap_mw':0},
]
GRID_IMPORT_PRICE_CAD_MWH=125.0 # illustrative all-in energy purchase + losses margin, NOT an actual BC Hydro tariff
GRID_EXPORT_PRICE_CAD_MWH=50.0 # illustrative negotiated offtake, NOT a BC Hydro export guarantee

# LP components: theta(non-grid), renewable dispatch(17+5), HVO (17), grid net interchange(sign), unserved (17)
renewables=['L_'+s for s in loadnames]+['W_'+w for w in windcap]
HVO=['L_'+s for s in loadnames]
RG=['GRID_IMPORT','GRID_EXPORT'] # two nonnegative ledger variables with separate buy/sell prices
nth=len(ids); ng=len(renewables); ne=len(HVO);nt=len(RG); nu=len(loadnames)
o_theta=0;o_renew=nth;o_hvo=nth+ng;o_grid=nth+ng+ne;o_shed=nth+ng+ne+nt;nvar=o_shed+nu
# grid net exchange positive = import from external network, negative = export
Aeq=np.zeros((nb,nvar));Aeq[:nb-1,:nth]=B[np.ix_(ids,ids)]*SBASE
for k,name in enumerate(renewables):
 if bi[name]!=0: Aeq[np.where(ids==bi[name])[0][0],o_renew+k]=-1
for k,name in enumerate(HVO):
 Aeq[np.where(ids==bi[name])[0][0],o_hvo+k]=-1
# Both settlement variables connect only at GRID slack: no injection at local hubs.
for k,name in enumerate(loadnames):
 Aeq[np.where(ids==bi['L_'+name])[0][0],o_shed+k]=-1
# Last equality enforces TOTAL generation + imports + HVO + shed = total load; otherwise the slack silently creates unlimited energy!
Aeq[-1,o_renew:o_hvo]=-1;Aeq[-1,o_hvo:o_grid]=-1;Aeq[-1,o_grid]=-1;Aeq[-1,o_grid+1]=1;Aeq[-1,o_shed:]=-1
# Branch constraints |flows * theta| <= thermal ratings (MW approximates MVA at pf~1)
F=flows[:,ids]
Aub=np.zeros((2*nl,nvar));Aub[:nl,:nth]=F;Aub[nl:,:nth]=-F
rvec=np.array([e['rating_mva'] for e in branches])
bub=np.r_[rvec,rvec]

# For contingencies rebuild B and line matrix, reuse everything else.
def solve(sc,out_idx=None):
 if out_idx is not None:
  e=branches[out_idx];i,j=bi[e['a']],bi[e['b']]; x=1/e['x_pu'];
  bc=B.copy()
  bc[i,i]-=x;bc[j,j]-=x;bc[i,j]+=x;bc[j,i]+=x
  A=Aeq.copy();A[:nb-1,:nth]=bc[np.ix_(ids,ids)]*SBASE
  Au=np.delete(Aub,[out_idx,nl+out_idx],axis=0)
  bu=np.delete(bub,[out_idx,nl+out_idx])
 else: A=Aeq; Au=Aub;bu=bub
 # When islanded, no electrical flow through the external-grid supernode is permitted.
 if sc['import_cap_mw']==0 and sc['export_cap_mw']==0:
  A=A.copy();Au=Au.copy();bu=bu.copy()
  b_island=B.copy()
  for ix,el in enumerate(branches):
   if el['kind']=='500kV_external_grid':
    ii,jj=bi[el['a']],bi[el['b']];xx=1/el['x_pu'];b_island[ii,ii]-=xx;b_island[jj,jj]-=xx;b_island[ii,jj]+=xx;b_island[jj,ii]+=xx
    Au[ix,:]=0;Au[ix+nl,:]=0
  if out_idx is not None and branches[out_idx]['kind']!='500kV_external_grid':
   el=branches[out_idx];ii,jj=bi[el['a']],bi[el['b']];xx=1/el['x_pu'];b_island[ii,ii]-=xx;b_island[jj,jj]-=xx;b_island[ii,jj]+=xx;b_island[jj,ii]+=xx
  A[:nb-1,:nth]=b_island[np.ix_(ids,ids)]*SBASE
  # Fix angular reference on the island to avoid a redundant rotational degree of freedom.
  refrow=np.zeros(nvar);refrow[np.where(ids==bi['H_kamloops'])[0][0]]=1
  A=np.vstack([A,refrow]);rhs_ref=True
 else:rhs_ref=False
 load_mw=mean_load_mw*sc['load_multiplier']/17
 target=np.zeros(nb)
 for s in loadnames:target[bi['L_'+s]]=load_mw
 rhs=np.r_[-target[ids],-target.sum()]
 if rhs_ref:rhs=np.r_[rhs,0.]
 bounds=[(-1,1)]*nth
 bounds += [(0,solar_total_mw/17*sc['solar_cf'])]*17
 bounds += [(0,0 if w==sc.get('wind_outage') else windcap[w]*sc['wind_cf']) for w in windcap]
 bounds += [(0,sc['hvo_limit_mw_per_site'])]*ne
 bounds += [(0.,sc['import_cap_mw']),(0.,sc['export_cap_mw'])]
 bounds += [(0,load_mw)]*nu
 c=np.zeros(nvar);c[o_renew:o_hvo]=-15;c[o_hvo:o_grid]=328.7 # C$1.80/L / (HVO LHV*54% conversion), illustrative fuel marginal cost
 #  positive grid purchase +, negative export -; minimal import unless needed
 c[o_grid]=GRID_IMPORT_PRICE_CAD_MWH;c[o_grid+1]=-GRID_EXPORT_PRICE_CAD_MWH;c[o_shed:]=100000
 res=linprog(c,A_ub=Au,b_ub=bu,A_eq=A,b_eq=rhs,bounds=bounds,method='highs',options={'presolve':True})
 if not res.success: return {'status':'LP failed: '+res.message,'scenario':sc['name'],'outage':branches[out_idx]['line'] if out_idx is not None else ('wind_plant_outage:'+sc['wind_outage'] if sc.get('wind_outage') else 'N0')}
 v=res.x;theta=np.zeros(nb);theta[ids]=v[:nth]
 lineflow=flows@theta
 if out_idx is not None:lineflow[out_idx]=0
 if sc['import_cap_mw']==0 and sc['export_cap_mw']==0:
  for k,el in enumerate(branches):
   if el['kind']=='500kV_external_grid':lineflow[k]=0
 peak=np.max(np.abs(lineflow)/rvec * np.where(np.arange(nl)==out_idx,0,1))
 used=np.sum(v[o_renew:o_hvo]);available=sum(z[1] for z in bounds[o_renew:o_hvo]);
 Q=[]
 for s in loadnames:Q.append(load_mw*.22) # ~0.976 pf with local reactor/VAR support
 # AC initial bus injection (excluding slack) from optimized active dispatch
 P=np.zeros(nb); Qvec=np.zeros(nb)
 for s in loadnames: P[bi['L_'+s]]-=load_mw;Qvec[bi['L_'+s]]-=load_mw*.22
 for k,name in enumerate(renewables): P[bi[name]]+=v[o_renew+k]
 for k,name in enumerate(HVO): P[bi[name]]+=v[o_hvo+k]
 P[bi['GRID']]+=v[o_grid]-v[o_grid+1]
 for k,s in enumerate(loadnames):P[bi['L_'+s]]+=v[o_shed+k]
 # Losses are absent from dispatch LP: use AC stage separately.
 return dict(status='ok',scenario=sc['name'],outage=branches[out_idx]['line'] if out_idx is not None else ('wind_plant_outage:'+sc['wind_outage'] if sc.get('wind_outage') else 'N0'),outage_kind=branches[out_idx]['kind'] if out_idx is not None else ('wind_plant_unit_stress' if sc.get('wind_outage') else 'none'),out_idx=out_idx,unserved_mw=float(v[o_shed:].sum()),renewable_available_mw=float(available),renewable_delivered_mw=float(used),curtailed_mw=float(available-used),hvo_mw=float(v[o_hvo:o_grid].sum()),grid_net_import_mw=float(v[o_grid]-v[o_grid+1]),grid_purchase_mw=float(v[o_grid]),grid_sale_mw=float(v[o_grid+1]),grid_net_settlement_cad_h=float(v[o_grid]*GRID_IMPORT_PRICE_CAD_MWH-v[o_grid+1]*GRID_EXPORT_PRICE_CAD_MWH),max_branch_loading_pct=float(100*peak),theta=theta,P=P,Q=Qvec,branch_flow=lineflow)

# AC model: power injection into each bus and a common slack. No reactive controller or shunt model.
def ac_flow(sol):
 active=np.ones(nl,dtype=bool)
 if sol['out_idx'] is not None:active[sol['out_idx']]=False
 Y=np.zeros((nb,nb),complex)
 for k,e in enumerate(branches):
  if not active[k] or (sol['scenario']=='islanded_winter_stress_no_interchange' and e['kind']=='500kV_external_grid'): continue
  y=1/(e['r_pu']+1j*e['x_pu']);i,j=bi[e['a']],bi[e['b']]
  Y[i,i]+=y;Y[j,j]+=y;Y[i,j]-=y;Y[j,i]-=y
 Ptar=sol['P'][ids]/SBASE;Qtar=sol['Q'][ids]/SBASE
 def residual(z):
  th=np.zeros(nb);th[ids]=z[:nth]; Vm=np.ones(nb);Vm[ids]=z[nth:]
  V=Vm*np.exp(1j*th)
  S=V*np.conj(Y@V)
  return np.r_[S.real[ids]-Ptar,S.imag[ids]-Qtar]
 guess=np.r_[np.zeros(nth),np.ones(nth)]
 r=root(residual,guess,method='hybr',options={'maxfev':2500,'xtol':1e-9})
 mismatch=np.max(np.abs(residual(r.x)))
 if not r.success and mismatch>1e-5:return dict(ac_converged=False,ac_residual_pu=float(mismatch))
 if np.min(r.x[nth:])<.5 or np.max(r.x[nth:])>1.5:return dict(ac_converged=False,ac_residual_pu=float(mismatch),ac_note='nonphysical voltage root')
 th=np.zeros(nb);th[ids]=r.x[:nth];Vm=np.ones(nb);Vm[ids]=r.x[nth:];V=Vm*np.exp(1j*th)
 S=V*np.conj(Y@V);losses=float(S.real.sum()*SBASE)
 loadings=[]
 for k,e in enumerate(branches):
  if not active[k] or (sol['scenario']=='islanded_winter_stress_no_interchange' and e['kind']=='500kV_external_grid'):continue
  y=1/(e['r_pu']+1j*e['x_pu']); i,j=bi[e['a']],bi[e['b']]
  sf=V[i]*np.conj((V[i]-V[j])*y)*SBASE;st=V[j]*np.conj((V[j]-V[i])*y)*SBASE
  loadings.append(max(abs(sf),abs(st))/e['rating_mva'])
 if sol['outage']=='N0':
  pd.DataFrame([{'bus':buses[i]['bus'],'kind':buses[i]['kind'],'v_pu':float(Vm[i]),'site':buses[i]['bus'].removeprefix('L_')} for i in range(nb)]).to_csv(OUT/('ac_bus_voltages_'+sol['scenario']+'.csv'),index=False)
 return dict(ac_converged=True,ac_residual_pu=float(mismatch),min_bus_vm_pu=float(min(Vm)),min_bus_name=buses[int(np.argmin(Vm))]['bus'],max_bus_vm_pu=float(max(Vm)),ac_loss_mw=losses,ac_max_branch_loading_pct=float(100*max(loadings)),ac_voltage_violations=int(((Vm[ids]<.95)|(Vm[ids]>1.05)).sum()),ac_thermal_violations=int((np.asarray(loadings)>1).sum()))

records=[];acrows=[];n0objs={}
for s in SCENARIOS:
 n0=solve(s);n0objs[s['name']]=n0
 cases=[n0]
 for k in range(nl):cases.append(solve(s,k))
 for w in windcap:cases.append(solve({**s,'wind_outage':w}))
 for d in cases:
  rec={k:v for k,v in d.items() if isinstance(v,(str,int,float,bool,type(None)))}
  records.append(rec)
  if d['status']=='ok' and s['import_cap_mw']>0 and (d['outage']=='N0' or s['name'].startswith('connected_winter_')):
   ac=ac_flow(d);acrows.append({**rec,**ac})
  
res=pd.DataFrame(records);res.to_csv(OUT/'n0_n1_contingency_results.csv',index=False)
acdata=pd.DataFrame(acrows);acdata.to_csv(OUT/'ac_voltage_screen.csv',index=False)
summary=[]
for s in SCENARIOS:
 x=res[res.scenario==s['name']];a=x[x.outage=='N0'].iloc[0];cc=x[x.outage!='N0']
 summary.append(dict(scenario=s['name'],N0_unserved_MW=a.unserved_mw,N0_grid_net_import_MW=a.grid_net_import_mw,N0_grid_purchase_MW=a.grid_purchase_mw,N0_grid_sale_MW=a.grid_sale_mw,N0_grid_cost_CAD_per_hour=a.grid_net_settlement_cad_h,N0_curtailed_MW=a.curtailed_mw,N0_HVO_MW=a.hvo_mw,N0_max_DC_line_loading_percent=a.max_branch_loading_pct,N1_count=len(cc),N1_worst_unserved_MW=cc.unserved_mw.max(),N1_failed_secure_cases=int((cc.unserved_mw>1e-3).sum()),N1_max_curtailment_MW=cc.curtailed_mw.max(),N1_max_grid_purchase_MW=cc.grid_purchase_mw.max(),N1_max_grid_sale_MW=cc.grid_sale_mw.max(),N1_worst_grid_import_MW=cc.grid_net_import_mw.max(),N1_thermal_screen_pass=bool((cc.max_branch_loading_pct<=100.001).all())))
summarydf=pd.DataFrame(summary);summarydf.to_csv(OUT/'network_summary.csv',index=False)

# Map topology, show hubs / load locations (not existing transmission map)
fig,ax=plt.subplots(figsize=(12,8),dpi=160)
for a,b in connections:
 x1,y1=loc[a][1],loc[a][0];x2,y2=loc[b][1],loc[b][0]
 ax.plot([x1,x2],[y1,y2],color='#5f7890',lw=1.8,alpha=.65,zorder=1)
for s in loadnames:
 h=hub_of[s];x1,y1=loc[s][1],loc[s][0];x2,y2=loc[h][1],loc[h][0]
 ax.plot([x1,x2],[y1,y2],color='#8bb2b2',lw=.85,alpha=.65,zorder=1)
ax.scatter([loc[x][1] for x in loadnames],[loc[x][0] for x in loadnames],s=30,c='#307c8e',label='17 load proxies',zorder=3)
ax.scatter([loc[x][1] for x in hubnames],[loc[x][0] for x in hubnames],s=105,c='#d39a3d',marker='s',label='Proposed 500 kV hubs',zorder=4)
for w in wind_cap:
 c=windlat[w];ax.scatter(c[1],c[0],marker='^',c='#6d9652',s=75,zorder=4)
for s in hubnames:ax.text(loc[s][1]+.03,loc[s][0]+.03,s.replace('_',' ').title(),fontsize=8)
ax.set(xlabel='Longitude',ylabel='Latitude',title='Illustrative BC transmission screening topology — NOT actual or permitted routes')
ax.legend(loc='best');ax.grid(alpha=.15);fig.tight_layout();fig.savefig(OUT/'Figure_S6_Conceptual_Network_Map.png',dpi=190);fig.savefig(OUT/'Figure_S6_Conceptual_Network_Map.pdf');plt.close(fig)
# Chart N1 deficits and curtailment
fig,ax=plt.subplots(figsize=(9,4.8),dpi=160)
labels=['Mean\nconnected','Winter\n2.5GW import','Solar surplus\n3GW export','Winter\n1GW import','Winter\n4GW import','Grid lost\nwinter']
x=np.arange(len(summarydf));a=summarydf
ax.bar(x-.2,a.N0_unserved_MW/1000,.4,label='Base-case unserved GW');ax.bar(x+.2,a.N1_worst_unserved_MW/1000,.4,label='Worst N−1 unserved GW')
ax.set_xticks(x,labels);ax.set_ylabel('Unserved load (GW)');ax.set_title('Transmission-constrained screening: shortages under assumed topology');ax.legend();fig.tight_layout();fig.savefig(OUT/'Figure_S7_N1_Resilience.png',dpi=190);fig.savefig(OUT/'Figure_S7_N1_Resilience.pdf');plt.close(fig)
# Visualize worst N0 voltage values for campuses
acwinter=pd.read_csv(OUT/'ac_bus_voltages_connected_winter_import2500_export3000.csv')
acwinter=acwinter[acwinter.bus.str.startswith('L_')].sort_values('v_pu')
fig,ax=plt.subplots(figsize=(11,5.5),dpi=150)
ax.bar(np.arange(len(acwinter)),acwinter.v_pu.values,color=['#b46b44' if x<.95 else '#4e8896' for x in acwinter.v_pu])
ax.axhline(.95,color='#a74d45',ls='--',lw=1.4,label='Illustrative lower voltage screen (0.95 pu)')
ax.set_xticks(np.arange(len(acwinter)),[x.replace('L_','').replace('_',' ') for x in acwinter.bus],rotation=65,ha='right',fontsize=8)
ax.set_ylim(.88,1.02);ax.set_ylabel('Bus voltage (per unit)');ax.set_title('Illustrative winter-peak AC load flow: local voltage limits not always met');ax.legend(fontsize=8);fig.tight_layout();fig.savefig(OUT/'Figure_S8_AC_Voltage_Screen.png',dpi=180);fig.savefig(OUT/'Figure_S8_AC_Voltage_Screen.pdf');plt.close(fig)
# reproduction record
with (OUT/'NETWORK_METHODS.md').open('w') as f:
 f.write('''# Preliminary BC network load-flow and N−1 contingency screen\n\n''')
 f.write('''This is a **synthetic, unverified transmission expansion**, not a model of BC Hydro's actual network, and not an interconnection or NERC-compliance study. Its purpose is to test whether the manuscript's pooled electricity dispatch can be assumed deliverable at all 17 communities.\n\n''')
 f.write(f'''Input: 17 published town proxies, site-optimised SANY 8 MW capacity ({sum(windcap.values()):.3f} GW wind, {opt['candidate']['solar_gw']:.3f} GW PV), 36.00486 TWh/year campus electricity. Load distributed equally across 17 nodes (average {mean_load_mw/17:.1f} MW/node); six static operating states.\n\n''')
 f.write('''Architecture (all **assumed and entirely new**): seven 500-kV hub proxies, 500-kV mesh with 2 circuits per listed route (1900 MVA each), seven 500/230 kV substations with three 1250 MVA transformers each, 17 dual-circuit 230-kV 550 MVA feeder pairs, five doubled 500-kV wind connections (1400 MVA/circuit), and three grid gateways with two 2600 MVA circuits each. Lengths = geodesic x1.2 for HV routes, geodesic x1.18 (10-km floor) for 230-kV feeders. No project-specific rights-of-way, transformer contracts, line thermal studies, transmission-service arrangements, reactive plant or station drawings exist.\n\n''')
 f.write('''Active-power DC load flow: linear Kirchhoff susceptance model, each line/transformer capacity limited independently; scipy.optimize.linprog obtains constrained post-contingency corrective redispatch, curtailment, grid net imports/exports, HVO, and unmet load. IEEE-style voltage and branch ratings are **screening assumptions**, not BC Hydro planning criteria. Balanced positive-sequence steady-state AC power flow is solved independently using scipy.optimize.root with PQ buses and a common external GRID slack bus (no realistic frequency, governor, inverter reactive limits, tap controls, shunts, charging currents, faults or dynamic stability). No AC feasibility claim may be made when an AC solve fails or voltage limits are violated. No electrical losses were charged into LP dispatch (AC losses are separately reported). 500-kV corridors approximate R/X = .026/.30 ohm/km; 230-kV feeders .075/.38; transformer .004+j.08 pu on 1000 MVA base. See source for full inputs.\n\n''')
 f.write('''N−1 removes *each assumed line circuit or transformer individually* and reoptimizes dispatch immediately (optimistic remedial action). Failure to deliver after a contingency is reported as unserved MW. Simultaneous terminal faults, station outages, two-circuit shared-tower faults, loss of entire grid bus, fault-level/synchronism, generator-loss and inertia studies are not certified here. Sensitivities: connected average, winter peak/low renewables under 1/2.5/4 GW assumed imports, solar/wind export at 3 GW assumed limit, and complete grid-disconnection (grid-import/export forced to zero). Generation availability is static and uniformly scaled, not an additional 16-year hourly spatial-power study.\n\n''')
 f.write('''External-grid interchange is injected ONLY at the GRID equivalent (single slack terminal) and uses separate nonnegative import/export variables; imports cost C$125/MWh and exports receive an assumed C$50/MWh if an offtake agreement exists. Its power must flow across the individually rated gateway circuits: grid purchase is not placed directly on a local hub bus, and the system-wide Kirchhoff balance is enforced explicitly. The island case removes all GRID branches and sets external exchange to zero. Import/export ceilings are capacity sensitivities, not BC Hydro confirmed access. Local loads are always served first and export is capped; excess is curtailed. Export is never assumed to be compensated at retail customer rates.

''')
 f.write('''Five additional plant-collector loss stresses remove the entire modeled production of one of the five wind regions, one at a time. These are severe grouped-plant tests rather than a standard individual 8-MW turbine N−1 outage.

''')
 f.write('''Importantly the external grid equivalent does not represent a secured BC Hydro interconnection. External power imports are **not verified 100%-renewable supply**, and zero model emergency-gas generation cannot be inferred from grid imports. A distinct 16-year pooled bidirectional-grid dispatch is provided in hourly_grid_exchange.py; it is not chronologically coupled to the nodal AC/DC screen and does not incorporate line congestion, losses, or site-specific import restrictions.\n\n''')
 f.write('''References (screening context): BC Hydro provincial transmission maps https://www.bchydro.com/energy-in-bc/operations/transmission/transmission-system/maps.html ; NERC TPL-001-5.1 https://www.nerc.com/pa/Stand/Reliability%20Standards/TPL-001-5.1.pdf . Neither source validates any proposed corridor or transformer ratings. The static nodal network screen does not dispatch the selected battery; a simulated restricted-import winter shortfall is therefore not a proof of loss of load after battery dispatch.\n\nThe static network screens do **not** dispatch the proposed battery; this conservative winter snapshot is not a proof of actual loss of load at restricted import limits, because stored energy may bridge short deficits. AC checks use synthetic PQ buses and no compensating VAR controls.\n''')

print('\nNETWORK SUMMARY\n',summarydf.to_string(index=False))
print('AC screened',len(acdata),'cases; converged',int(acdata.ac_converged.sum()),'winter cases failing voltage',int(((acdata.scenario=='connected_winter_import2500_export3000')&(acdata.ac_voltage_violations>0)).sum()),'winter cases exceeding AC branch ratings',int(((acdata.scenario=='connected_winter_import2500_export3000')&(acdata.ac_max_branch_loading_pct>100)).sum()))
