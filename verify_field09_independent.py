#!/usr/bin/env python3
"""Independent offline consistency audit of the submitted Stage09 traces.
No imports from Stage09 replay/rules; raw publisher XLSX not shipped.
"""
import csv, json, hashlib
from pathlib import Path
from datetime import datetime, timedelta
from collections import Counter

ROOT=Path(__file__).parent/'source'

def rows(p):
    with (ROOT/p).open(newline='') as f: return list(csv.DictReader(f))

def sha(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for chunk in iter(lambda:f.read(1<<20),b''): h.update(chunk)
    return h.hexdigest()

def ref_state(s,e,h,c):
    if s not in (0,1): return 'INSUFFICIENT_DATA','INSUFFICIENT_DATA'
    a='ON' if s==1 else 'OFF'
    if any(x not in (0,1) for x in (e,h,c)): return a,'INSUFFICIENT_DATA'
    if (h,c)!=(1,0): return a,'NOT_APPLICABLE'
    return a,a if s==e else 'DISAGREE'

def ref_summ(pre, window, attr, start):
    v=[x[attr] for x in window]; before=[x[attr] for x in pre]
    baseline='INSUFFICIENT_DATA' if len(before)<2 or 'INSUFFICIENT_DATA' in before else 'TWO_ON' if before==['ON','ON'] else 'TWO_OFF' if before==['OFF','OFF'] else 'NOT_APPLICABLE'
    good={'ON','OFF','DISAGREE'}
    status='OBSERVED' if any(a in good and b in good for a,b in zip(v,v[1:])) else 'INSUFFICIENT_DATA'
    if v and set(v)=={'NOT_APPLICABLE'}: status='NOT_APPLICABLE'
    change='ABSTAIN' if status!='OBSERVED' or baseline!='TWO_ON' else 'NO_OBSERVED_CHANGE'
    longest=run=0
    for x in v:
        run=run+1 if x=='OFF' else 0
        longest=max(longest,run)
    first=confirm=last=None
    if change=='NO_OBSERVED_CHANGE':
        lastval=before[-1]
        for j,x in enumerate(v[:-1]):
            if (lastval,x,v[j+1])==('ON','OFF','OFF'):
                first=window[j]['time']; confirm=window[j+1]['time']; last=first-timedelta(minutes=5)
                change='BAS_ON_TO_OFF_OBSERVED';break
            lastval=x
    return {
        'status':status,'baseline':baseline,'change':change,
        'off_ticks':v.count('OFF'), 'known_ticks':sum(x in good for x in v),
        'longest_off_sample_span_seconds': (longest-1)*300 if longest else '',
        'last_on_exclusive':last, 'first_off_inclusive':first, 'confirm_off':confirm,
        'first_off_from_log_start_seconds':int((first-start).total_seconds()) if first else '',
        'confirm_from_log_start_seconds':int((confirm-start).total_seconds()) if confirm else '',
    }

def normalize(v): return '' if v in (None,'') else str(v)

result={"sha_manifest":{},"trace_checks":{},"event_metrics":{},"control_metrics":{},"limitations":[]}
manifest=[]
for line in (ROOT/'SHA256SUMS').read_text().splitlines():
    expected,path=line.split('  ',1); manifest.append((expected,path))
    assert sha(ROOT/path)==expected, path
result['sha_manifest']={'verified':len(manifest),'all_pass':True}
assert sha(ROOT/'FIELD_NATIVE_09_PROTOCOL.md')=='868a685798c42c5a271149b64089aba8d72e0e8ed2d50a91900bfbe5587c5358'
assert sha(ROOT/'input-evidence/EVENT_LEDGER_08.csv')=='1d7acd72ff0ec71e1ae0fbd33c5b0b15e3f0f02942b91a74729e65d4ef4bd8fa'

traces=0;ticks=0;comparisons=0
for group,p in [('events','observed/EVENT_OUTCOMES.csv'),('controls','observed/CONTROL_OUTCOMES.csv')]:
    rr=rows(p)
    for record in rr:
        trace=rows('observed/'+record['trace']); traces+=1;ticks+=len(trace)
        assert sha(ROOT/'observed'/record['trace'])==record['trace_sha256']
        assert all(x['rule_version']=='bas-fan-observation@1.0.0' for x in trace)
        assert all(x['raw_sha256']==record['raw_sha256'] for x in trace)
        assert all(x['clock']=='UNKNOWN_CLOCK_NAIVE_WORKBOOK_300S' for x in trace)
        assert len(trace)==20,record['replay_id']
        expected=[]
        for t in trace:
            vals=tuple(int(t[k]) if t[k] in ('0','1') else None for k in ('supply','exhaust','heat_request','cool_request'))
            a,b=ref_state(*vals)
            assert (a,b)==(t['supply_evidence'],t['paired_evidence']),(record['replay_id'],t['native_time'])
            assert 'fault' not in t and 'publisher' not in ''.join(t)
            expected.append({'time':datetime.fromisoformat(t['native_time']),'a':a,'b':b,'vals':vals,'section':t['partition']})
        assert [r['section'] for r in expected[:2]]==['PRE']*2
        assert [r['section'] for r in expected[2:]]==['WINDOW']*18
        assert all((v['time']-u['time']).total_seconds()==300 for u,v in zip(expected,expected[1:])),record['replay_id']
        start=datetime.fromisoformat(record['start_naive']);end=datetime.fromisoformat(record['end_naive_exclusive'])
        assert all(start<=r['time']<end for r in expected[2:])
        pre,window=expected[:2],expected[2:]
        for prefix,attr in [('A_','a'),('B_','b')]:
            s=ref_summ(pre,window,attr,start)
            for k,v in s.items():
                a=normalize(record[prefix+k]);b=normalize(v)
                assert a==b,(record['replay_id'],prefix+k,a,b)
                comparisons+=1
        for key,col in [('supply_available',0),('exhaust_available',1),('heat_available',2),('cool_available',3)]:
            assert int(record[key])==sum(row['vals'][col] is not None for row in window)
            comparisons+=1
        c=Counter((x['vals'][0],x['vals'][1]) for x in window)
        for a in [0,1]:
            for b in [0,1]:
                assert int(record[f'pair_{a}{b}_ticks'])==c[(a,b)]
                comparisons+=1
        assert int(record['both_available'])==sum(c[(a,b)] for a in [0,1] for b in [0,1])
        assert int(record['warm_request_ticks'])==sum(x['vals'][2:]==(1,0) for x in window)
        comparisons+=2
        if group=='events':
            result['event_metrics'][record['ahu']]={
                'A_change':record['A_change'],'B_change':record['B_change'],
                'pair_counts':{f'{a}{b}':c[(a,b)] for a in [0,1] for b in [0,1]},
                'first_off_seconds':record['A_first_off_from_log_start_seconds'],
                'confirmation_seconds':record['A_confirm_from_log_start_seconds'],
            }
        else:
            result['control_metrics'][record['replay_id']]={'A_change':record['A_change'],'B_change':record['B_change'],'paired_on':c[(1,1)]}
result['trace_checks']={'traces':traces,'ticks':ticks,'field_comparisons':comparisons,'pass':True}

screen=rows('observed/CONTROL_SCREENING.csv')
sc=Counter(r['decision'] for r in screen)
assert len(screen)==156
assert sc=={'EXCLUDED_SITE_INTERVENTION_OR_NEXT_DAY':54,'EVENT_PRECONTEXT_NOT_TWO_WARM_PAIRED_ON':51,'CONTROL_PRECONTEXT_NOT_TWO_WARM_PAIRED_ON':45,'QUALIFIED_MATCHED_PRECONTEXT':6}
selected=[x for x in screen if x['decision']=='QUALIFIED_MATCHED_PRECONTEXT']
assert {(x['ahu'],int(x['offset_calendar_days'])) for x in selected}=={(a,n) for a in ('AHU1','AHU18','AHU23') for n in (63,77)}
result['control_screening']={'total':len(screen),'counts':dict(sc),'selected':[{'ahu':x['ahu'],'day_offset':int(x['offset_calendar_days'])} for x in selected]}

# Known provenance-only limits, not independently observed source values.
result['limitations']=[
    'Original 8 XLSX/JPG and source PDF not supplied with Stage09; this pass independently validates saved traces and metadata, not XLSX-to-trace extraction.',
    'Publisher intervention metadata and BAS-reported fan statuses cannot prove physical fan motion.',
    'One site, one intervention day, matched control windows are dependent; no independent health labels or reliable field FPR.',
]
print(json.dumps(result,indent=2,ensure_ascii=False))
Path('/mnt/data/bp_field09_audit/independent_checks.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
