from pathlib import Path
import csv
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
p=Path(__file__).resolve().parent
with (p/'NOV8_16_MATCHED_COMMUNITY_EMISSIONS.csv').open(newline='',encoding='utf-8') as f: d=list(csv.DictReader(f))
central={r['project_scenario']:r for r in d if r['heat_case']=='full_service' and r['stress_case']=='central'}
order=['Digital Gardens','Wonder Valley: no CCS + CH4','Wonder Valley: 90% CCS + CH4','Wonder Valley: 95% CCS + CH4']
labels=['Digital Gardens','WV CCGT / no capture','WV CCGT / 90% CCS','WV CCGT / 95% CCS']
fig,axs=plt.subplots(1,2,figsize=(11.2,4.45),sharey=True)
for ax,(col,title) in zip(axs,[('gross_partial_MtCO2e_y','Gross partial inventories'),('conditional_partial_net_MtCO2e_y','Conditional net, matched credit')]):
 values=[float(central[key][col]) for key in order]
 bars=ax.bar(range(len(values)),values)
 ax.set_xticks(range(4),labels,rotation=20,ha='right',fontsize=8)
 ax.set_title(title,fontsize=11)
 ax.set_ylim(0,16)
 ax.grid(axis='y',alpha=0.2)
 for b,v in zip(bars,values):ax.text(b.get_x()+b.get_width()/2,v+0.17,f'{v:.3f}',ha='center',va='bottom',fontsize=9)
axs[0].set_ylabel('Mt CO2e per year (modelled partial boundary)')
fig.suptitle('Digital Gardens vs. Wonder Valley — identical electric and heat service',fontsize=12,y=.99)
fig.text(.50,.005,'Conditional credit: 0.497 Mt/y applied equally to every project; hypothetical CCS and CH4.\nBoundaries differ: DG includes selected lifecycle proxies; WV includes combustion + assumed upstream methane.',ha='center',va='bottom',fontsize=8)
fig.tight_layout(rect=[0,0.11,1,.94],w_pad=2)
fig.savefig(p.parent/'figures/NOV8_16_Figure_1_symmetric_carbon.png',dpi=190,bbox_inches='tight')
plt.close(fig)

cases=['no_network','half_connected','limited_plant','full_service']
fig,ax=plt.subplots(figsize=(9.8,4.9))
for key,lab in [('Digital Gardens','Digital Gardens'),('Wonder Valley: 95% CCS + CH4','Wonder Valley / 95% CCS')]:
 vals=[float(next(r for r in d if r['heat_case']==c and r['stress_case']=='central' and r['project_scenario']==key)['conditional_partial_net_MtCO2e_y']) for c in cases]
 ax.plot(range(4),vals,marker='o',linewidth=2,label=lab)
ax.set_xticks(range(4),['No network','Half connected','Plant 1.0x','Full service'])
ax.set_ylabel('Conditional partial net, Mt CO2e/year')
ax.set_title('Matched heat-service sensitivity — same fossil displacement credit')
ax.grid(alpha=.25);ax.legend(loc='best')
fig.text(.5,.005,'Different emissions inventory boundaries; heat-service and CCS assumptions are prospective.',ha='center',fontsize=8)
fig.tight_layout(rect=[0,.045,1,1])
fig.savefig(p.parent/'figures/NOV8_16_Figure_5_symmetric_heat_sensitivity.png',dpi=190,bbox_inches='tight')
plt.close(fig)
