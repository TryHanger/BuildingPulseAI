"""Independent, model-free recheck of selected frozen CD02 numerical anchors.
Usage: python BUILDINGPULSE_CD02_INDEPENDENT_RECHECK.py /path/to/extracted/CD02
"""
import sys
from pathlib import Path
import pandas as pd
import numpy as np
from scipy.stats import binomtest
root=Path(sys.argv[1])
p=root/'inputs/cd01/results/lanes/B'
x=pd.read_csv(p/'pointwise.csv',parse_dates=['timestamp']).sort_values('timestamp').reset_index(drop=True)
e=pd.read_csv(p/'eventwise.csv',parse_dates=['start','end'])
v=x.split.eq('eval'); n=v & x.clean; f=v & x.fault
assert (int(n.sum()),int((n&x.active).sum()),int((n&x.active&x.M1_score.notna()).sum()))==(3603,3154,3141)
assert (int(f.sum()),int((f&x.active).sum()))==(1009,834)
dt=x.timestamp.diff().dt.total_seconds().eq(300)&x.timestamp.dt.normalize().eq(x.timestamp.shift().dt.normalize())
early={}
for method in ('M1','ARX'):
 a=x[method+'_alarm'].astype(bool)
 starts=a & (~a.shift(fill_value=False)) & dt
 # Historical alarm creation when preceding point was valid and nonalarming
 quiet=(~a)&x.active&x[method+'_score'].notna()
 starts=a & quiet.shift(fill_value=False) & dt
 wins=[]
 for row in e[e.method.eq(method)].itertuples():
  prior=x.timestamp.eq(row.start-pd.Timedelta(minutes=5))
  has_good_prior=prior.any() and bool(quiet.loc[prior].iloc[0])
  flags=x.timestamp.between(row.start,row.end)&v&x.fault&starts
  early_hit=has_good_prior and bool(((x.loc[flags,'timestamp']-row.start).dt.total_seconds()<=3600).any())
  wins.append((row.family,early_hit))
 early[method]=wins
 k=sum(a for _,a in wins); k_nonbas=sum(a for fam,a in wins if fam!='Setpoint demand adjust')
 print(method,'early',k,'of',len(wins),'excluding setpoint',k_nonbas,'of',sum(fam!='Setpoint demand adjust' for fam,_ in wins))
 assert (k,k_nonbas)==({'M1':(0,0),'ARX':(3,2)}[method])
 alarms=n & a
 print('FAR',int(alarms.sum()),'/',int((n&x.active).sum()),'conditional on fan-on, not all clean intervals')
 assert int(alarms.sum())=={'M1':54,'ARX':47}[method]
print('paired exact p',binomtest(2,2,p=.5).pvalue)
for date,expected in [('2018-07-10',(123,35)),('2018-07-18',(120,50))]:
 sel=f&x.timestamp.dt.strftime('%Y-%m-%d').eq(date)
 got=(int(sel.sum()),int((sel&x.active).sum()))
 print(date,got)
 assert got==expected
print('INDEPENDENT RECHECK PASSED')
