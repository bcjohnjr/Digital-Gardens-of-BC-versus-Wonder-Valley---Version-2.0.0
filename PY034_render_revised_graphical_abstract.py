#!/usr/bin/env python3
"""Create the scientific graphical abstract from audited research archive results.
Visual only: model-specific screening values; no engineering certification.
"""
from pathlib import Path
import json
from PIL import Image,ImageDraw,ImageFont
R=Path(__file__).resolve().parent
C=R.parent
J=json.loads((R/'GRID_CONNECTED_REOPT/FULL_16YR_LOSS_AWARE/CORRECTIVE_SENSITIVITY/EMISSIONS_AND_FUEL_RECONCILIATION.json').read_text())
assert abs(J['central_at_100']['wind_minus10_full_hvo_substitution']-2.392588568070207)<1e-7
W=1200;H=1200
img=Image.new('RGB',(W,H),'#f3f7f9');d=ImageDraw.Draw(img)
font='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf';bold='/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
def F(sz,b=False):return ImageFont.truetype(bold if b else font,sz)
def center(t,y,sz,fill='#153648',bold_=False,x=600):
 f=F(sz,bold_);bb=d.textbbox((0,0),t,font=f);d.text((x-(bb[2]-bb[0])/2,y),t,font=f,fill=fill)
def txt(t,x,y,sz,fill='#18384b',b=False):d.text((x,y),t,font=F(sz,b),fill=fill)
def box(xy,fill,stroke=None,rad=20,width=2):d.rounded_rectangle(xy,radius=rad,fill=fill,outline=stroke,width=width)
navy='#123447';teal='#0e7978';orange='#b65e39'
box((25,20,1175,142),navy,rad=19)
center('Digital Gardens versus Wonder Valley',45,37,'#ffffff',True)
center('Matched 3.75 GW IT planning comparison  |  2010-2025 modeled history',108,16,'#d5e8f0')
# main panels
box((32,169,594,560),'#ffffff','#a2c3c5',17,2)
box((610,169,1168,560),'#ffffff','#a8bbc6',17,2)
box((48,182,578,243),teal,rad=15)
box((626,182,1152,243),'#496577',rad=15)
center('DIGITAL GARDENS',197,24,'#ffffff',True,x=315)
center('MODELED GAS COUNTERFACTUAL',198,20,'#ffffff',True,x=890)
center('17-node renewable network in British Columbia',259,16,x=315)
# three capacity tiles
for k,(lab,v) in enumerate([('WIND','5.856 GW'),('SOLAR','4.866 GW'),('BATTERY','3.133 GWh')]):
 x=53+k*175
 box((x,316,x+168,418),'#e4f3f1','#aad3d1',12,1)
 center(lab,335,15,'#28615e',True,x=x+84)
 center(v,375,18,navy,True,x=x+84)
center('Grid imports: 12.518 TWh/year',455,19,navy,True,x=315)
center('Potential exports: 1.012 TWh/year',494,16,'#4a687c',x=315)
center('57% electrical efficiency (assumed)',279,19,'#4a687c',True,x=890)
center('Not measured Wonder Valley performance',317,15,'#506779',x=890)
center('C$75-114/MWh model cost range',398,21,navy,True,x=890)
center('15.369 Mt CO2e/year (modeled)',463,20,orange,x=890)
# security panel
box((32,586,1168,843),'#e8f3f6','#a8c7d0',17,2)
center('FULL HISTORICAL SYNTHETIC AC / N-1 SCREEN',604,23,navy,True)
center('13,175,040 AC solves per scenario  |  93 branch outages per modeled hour',648,16,'#4a687c')
center('72.5% of hours fail original fixed-dispatch security checks',688,21,orange,True)
center('Base wind: assumed +13% collector rating and preventive HVO   ->   0 failed cases',742,15,navy)
center('10% less wind: HVO plus export-aware cutback   ->   0 failed cases',777,15,navy)
# cost and emissions panels
box((32,867,1168,1147),navy,rad=18)
center('FUEL-ONLY COSTS  |  SCOPED LIFECYCLE FACTORS',886,19,'#d8ebf1',True)
d.line((601,938,601,1081),fill='#8ca6af',width=2)
center('Original wind, intact-loss-aware',929,17,'#dcecf0',x=316)
center('10% wind shortfall, HVO replacement',929,17,'#dcecf0',x=886)
center(f"C${J['cost_CAD_MWh']['intact_i2r_loss']:.2f}/MWh",967,29,'#ffffff',True,x=316)
center(f"C${J['cost_CAD_MWh']['wind_minus10_full_hvo_substitution']:.2f}/MWh",967,29,'#ffffff',True,x=886)
center(f"{J['central_at_100']['intact_i2r_loss']:.3f} Mt CO2e/year",1026,22,'#dcecf0',True,x=316)
center(f"{J['central_at_100']['wind_minus10_full_hvo_substitution']:.3f} Mt CO2e/year",1026,22,'#dcecf0',True,x=886)
center('NOT physically designed, priced or certified N-1-secure interconnections',1095,16,'#eef3f4',True)
center('Wind resources, fuel delivery, reactive equipment and collector reinforcement remain unverified',1162,12,'#4b6575')
p=C/'SUBMISSION/Joule_Graphical_Abstract.png';img.save(p,optimize=True)
print(p,img.size)
