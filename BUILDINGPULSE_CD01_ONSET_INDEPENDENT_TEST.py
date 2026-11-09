"""Independent minimal regression revealing the CD01 scorer's onset definition issue.
Run from extracted CD01 root: python /path/to/BUILDINGPULSE_CD01_ONSET_INDEPENDENT_TEST.py ROOT_OF_CD01
This is a non-mutating demonstration of semantic ambiguity, not a diagnosis claim.
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
sys.path.insert(0,str(Path(sys.argv[1])/'code/common'))
from core import annotate,evaluate
idx=pd.date_range('2020-01-01 09:00',periods=5,freq='5min')
x=pd.DataFrame({'fan':[60.0]*5,'oat':[10.0]*5,'rat':[22.0]*5,'sat':[21.0]*5},index=idx)
event=(idx[1],idx[4],{'valve'})
x=annotate(x,{'train':[],'cal':[],'eval':['20200101']},[event],0)
x['mode']='test';x['object']='test';x['ood']=False
score=pd.Series([8.,8.,0.,8.,0.],index=idx)
metrics,rows,fire,onset=evaluate(x,score,5.,[event])
assert [str(t) for t in onset[onset].index] == ['2020-01-01 09:00:00','2020-01-01 09:15:00']
assert rows[0]['new'] is False
print('COUNTEREXAMPLE CONFIRMED: a NEW onset at 09:15 is excluded by event-level preexisting at 09:05.')
print('This is not evidence that the 09:15 alarm was caused by the fault; expose both onset definitions.')
