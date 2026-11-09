import bootstrap
import unittest
import numpy as np
import evidence_model as m
from prepare_evidence import chronological_dates

def reference(gen,load,ic,ec,battery,engine):
 soc=0.;out=[];pmax=battery*1000/8
 for y in range(len(gen)):
  b=m.B100_MWh;h=m.HVO_CAP*1e6/m.HVO_L_PER_MWH
  for t in range(len(gen[y])):
   g=gen[y,t];l=load[y,t];ch=dis=im=ex=bb=hh=shed=curt=0.
   if g>=l:
    ch=min(g-l,pmax,(battery*1000-soc)/.94);soc+=ch*.94
    ex=min(g-l-ch,ec[y,t]);curt=g-l-ch-ex
   else:
    need=l-g;dis=min(need,pmax,soc*.94);soc-=dis/.94;need-=dis
    im=min(need,ic[y,t]);need-=im
    available=min(need,engine);bb=min(b,available);b-=bb;available-=bb
    hh=min(h,available);h-=hh;shed=need-bb-hh
   out.append([g,0.,0.,l,0.,im,ex,bb,hh,shed,curt,ch,dis,soc,ic[y,t],ec[y,t],0.,0.])
 return np.array(out)

class Tests(unittest.TestCase):
 def test_independent_dispatch_and_causality(self):
  rng=np.random.default_rng(81);ny=2;nt=160
  gen=rng.uniform(0,11000,(ny,nt));load=rng.uniform(3000,6500,(ny,nt));w=np.zeros((ny,5,nt));w[:,0,:]=gen
  zeros=np.zeros((ny,nt));ic=rng.uniform(0,2500,(ny,nt));ec=rng.uniform(0,3000,(ny,nt));c=np.array([1,0,0,0,0,0,3.])
  a,h=m.simulate(c,w,zeros,zeros,load,zeros,zeros,ic,ec,np.zeros((6,6)),2720.,1.,True)
  np.testing.assert_allclose(h,reference(gen,load,ic,ec,3.,2720.),atol=1e-9)
  w2=w.copy();w2[1,:,80:]=0
  _,h2=m.simulate(c,w2,zeros,zeros,load,zeros,zeros,ic,ec,np.zeros((6,6)),2720.,1.,True)
  np.testing.assert_allclose(h[:240],h2[:240],atol=1e-9)
 def test_quadratic_matches_direct_line_losses(self):
  q,v,r=m.loss_quadratic();rng=np.random.default_rng(17)
  import pandas as pd
  resistance=pd.read_csv(m.G/'N1_QSUPPORT_loss_aware/assumed_branches.csv').r_pu.to_numpy()
  for _ in range(100):
   x=rng.uniform(-3000,3000,6);expected=np.sum(resistance*(v@x)**2)/1000
   self.assertAlmostEqual(x@q@x,expected,places=9)
 def test_mixed_date_convention(self):
  rows=[(['30/04/2021','24'],24),(['05/01/2021','1'],1),(['05/02/2021','1'],1),(['05/13/2021','1'],1)]
  dates,pen=chronological_dates(rows)
  self.assertEqual([str(x.date()) for x in dates],['2021-04-30','2021-05-01','2021-05-02','2021-05-13'])
 def test_no_free_battery_or_fuel(self):
  n=9000;zero=np.zeros((1,n));w=np.zeros((1,5,n));load=np.full((1,n),5000.);c=np.array([0.,0,0,0,0,0,3])
  a,h=m.simulate(c,w,zero,zero,load,zero,zero,zero,zero,np.zeros((6,6)),5100.,1.,True)
  self.assertEqual(h[:,12].sum(),0);self.assertAlmostEqual(a[0,0],m.HVO_CAP,places=7)
  self.assertAlmostEqual(a[0,8],m.B100_MWh/1000,places=7);self.assertGreater(a[0,1],30000)

if __name__=='__main__':unittest.main(verbosity=2)
