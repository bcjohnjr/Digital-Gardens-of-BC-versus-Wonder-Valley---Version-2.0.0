import bootstrap
from bootstrap import ROOT
import json,platform,sys
import numpy as np,pandas as pd
import scipy,numba,matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import evidence_model as m

s=pd.read_csv(ROOT/'results/scenario_summary.csv');a=pd.read_csv(ROOT/'results/scenario_annual.csv')
fit=json.loads((ROOT/'results/fit_results.json').read_text());caps=fit['selected_capacities']
labels={'old_build_constant_access':'Old build, constant access','old_build_observed_shape':'Old build, variable access','new_build_observed_shape':'New build, variable access','new_build_wind_minus10pct':'New build, wind -10%','new_build_half_access':'New build, half access','new_build_local160MW':'New build, 160 MW/site','new_build_clock_minus1h':'New build, clock -1 hour','new_build_clock_plus1h':'New build, clock +1 hour'}
labels.update(new_build_missing_TTC_previous='New build, prior-value gap fill',new_build_local160MW_gapfilled='160 MW/site, prior-value gap fill')
s['scenario_label']=s.scenario.map(labels)
s['full_service_cost_CAD_MWh']=s.cost_CAD_MWh.where(s.total_unserved_GWh<1e-7)
s['fuel_margin_ML']=m.HVO_CAP-s.max_HVO_ML
s.to_csv(ROOT/'results/report_summary.csv',index=False)
grid=np.load(ROOT/'inputs/grid_access.npz');missing=(grid['import_missing'].ravel()>0)|(grid['export_missing'].ravel()>0)
hourstats=[]
for case in s.scenario.unique():
 h=pd.read_csv(ROOT/'results'/f'{case}_hourly.csv.gz',parse_dates=['time_utc'])
 hourstats.append({'scenario':case,'unserved_hours':int((h.unserved_MW>1e-6).sum()),'unserved_MWh_at_missing_grid_records':float(h.loc[missing,'unserved_MW'].sum()),'unserved_MWh_at_other_hours':float(h.loc[~missing,'unserved_MW'].sum()),'max_firm_output_MW':float((h.B100_MW+h.HVO_MW).max()),'mean_annual_B100_GWh':h.B100_MW.sum()/16000,'initial_soc_MWh':0,'final_soc_MWh':float(h.soc_MWh.iloc[-1])})
pd.DataFrame(hourstats).to_csv(ROOT/'results/hourly_reliability_audit.csv',index=False)
plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'figure.dpi':160})
fig,ax=plt.subplots(2,1,figsize=(9.5,7.5),sharex=True)
for case,color in [('old_build_observed_shape','#7a8793'),('new_build_observed_shape','#137f82'),('new_build_wind_minus10pct','#c77829')]:
 d=a[a.scenario==case];ax[0].plot(d.year,d.HVO_ML,'o-',label=labels[case],color=color);ax[1].plot(d.year,d.unserved_GWh,'o-',color=color)
ax[0].axhline(m.HVO_CAP,color='#943535',ls='--',label='Assumed fuel ceiling');ax[0].set_ylabel('Annual HVO (million litres)');ax[0].legend(fontsize=8,ncol=2)
ax[1].set_ylabel('Annual unmet load (GWh)');ax[1].set_xlabel('Weather year')
for p in ax:p.axvline(2019.5,color='#444',ls=':');p.grid(alpha=.2)
ax[0].set_title('Historical transfer reductions change fuel adequacy\nCapacity fitting: 2010-2019; frozen-capacity evaluation: 2020-2025')
fig.tight_layout();fig.savefig(ROOT/'figures/Figure_1_fuel_and_adequacy.png');plt.close(fig)
fig,ax=plt.subplots(1,2,figsize=(9.5,4))
old=np.array([5.856,4.866102824424832,3.1329541684394684]);new=np.array([sum(caps[:5]),caps[5],caps[6]])
x=np.arange(3);ax[0].bar(x-.18,old,.36,label='Original',color='#7a8793');ax[0].bar(x+.18,new,.36,label='Revised',color='#137f82');ax[0].set_xticks(x,['Wind\nGW','Solar\nGW','Battery\nGWh']);ax[0].legend();ax[0].set_title('Capacity change')
for case,color in [('old_build_constant_access','#7a8793'),('new_build_observed_shape','#137f82')]:
 vals=s[(s.scenario==case)&s.period.isin(['training','held_out'])].cost_CAD_MWh.to_numpy();offset=-.18 if case.startswith('old') else .18;ax[1].bar(np.arange(2)+offset,vals,.36,color=color,label=labels[case])
ax[1].set_xticks([0,1],['2010-2019','2020-2025']);ax[1].set_ylabel('Conditional cost (C$/MWh)');ax[1].set_title('Different access assumptions, shown explicitly');ax[1].legend(fontsize=7)
fig.tight_layout();fig.savefig(ROOT/'figures/Figure_2_capacity_and_cost.png');plt.close(fig)
fig,ax=plt.subplots(figsize=(9.5,4.5))
g=np.load(ROOT/'inputs/grid_access.npz');years=np.arange(2010,2026)
ax.plot(years,g['import_factor'].mean(axis=1),'-o',label='Import factor',color='#137f82');ax.plot(years,g['export_factor'].mean(axis=1),'-o',label='Export factor',color='#ad6f28');ax.set_ylim(0,1.03);ax.set_ylabel('Annual mean normalized TTC index');ax.set_xlabel('Year');ax.set_title('Historical directional TTC used as a hypothetical access stress\nNot project rights, unused headroom or simultaneous transfer capacity');ax.grid(alpha=.2);ax.legend();fig.tight_layout();fig.savefig(ROOT/'figures/Figure_3_grid_access.png');plt.close(fig)
versions={'python':platform.python_version(),'numpy':np.__version__,'pandas':pd.__version__,'scipy':scipy.__version__,'numba':numba.__version__,'matplotlib':matplotlib.__version__}
(ROOT/'results/runtime_versions.json').write_text(json.dumps(versions,indent=2)+'\n')
(ROOT/'requirements.txt').write_text('\n'.join(k+'=='+v for k,v in versions.items() if k!='python')+'\nreportlab\npypdf\n')
print(s[s.period=='all'][['scenario_label','full_service_cost_CAD_MWh','total_unserved_GWh','fuel_margin_ML']].to_string(index=False))
