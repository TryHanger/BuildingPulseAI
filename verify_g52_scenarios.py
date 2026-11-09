#!/usr/bin/env python3
"""Independent, standard-library audit of frozen G36-5wk rule across 4 scenarios.

This is NOT an out-of-sample validation or a fault-classification metric.
Run: python verify_g52_scenarios.py /path/to/unzipped/g36-5wk --output report.json
No imports from BuildingPulse backend; checks source SHA and exact data grid.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
from math import isfinite

START, END = 16_354_800, 18_730_800
STEP, HOLD, THRESHOLD = 300, 600, 2.0
SOURCES = {
    'BaselineSystem': 'fe744430e7800d6d33847137346032501e63f0cd30fec6bef9b41b0f8ec1569d',
    'CooCoiValStuck_0': 'b71d2aa060bd126376848c2826e4990f53986b3f665b2c670c75ad01ebef0ff9',
    'OADamStuck_100': '18dd3dbc16adead32dc9233b408b42462994a353c4badc1c5efe409977f610b0',
    'SupDucLea_20': '793fc4819831b71bd065c549f9a8903a8ee86391b5f80ec207ba74ccf5ebce46',
}
C = {
    'time': 'time (s)',
    'sat': 'AHU Supply Air Temperature (°K)',
    'sp': 'AHU Supply Air Temperature Setpoint (°K)',
    'mat': 'AHU Mixed Air Temperature (°K)',
    'fan': 'AHU Supply Air Fan Status (0: off, 1: on)',
    'cool': 'Control Signal for AHU Cooling Coil Valve from BAS (fraction, 0: valve should be fully closed to 1: valve should be fully open)',
    'heat': 'Control Signal for AHU Heating Coil Valve (fraction, 0: valve should be fully closed to 1: valve should be fully open)',
}

def load_csv(root, name):
    p = root / f'{name}.csv'
    actual = hashlib.sha256(p.read_bytes()).hexdigest()
    assert actual == SOURCES[name], f'UNTRUSTED_SOURCE {name} {actual}'
    with p.open(newline='', encoding='utf-8-sig') as fd:
        reader=csv.DictReader(fd)
        assert set(C.values()) <= set(reader.fieldnames), f'Missing channels: {name}'
        rows=[]
        for row in reader:
            sample = {key:float(row[col]) for key,col in C.items()}
            assert all(isfinite(x) for x in sample.values()), f'Non-finite {name}'
            assert sample['time'].is_integer(), f'Bad time {name}'
            if rows: assert sample['time']-rows[-1]['time'] == STEP, f'Time mismatch {name}'
            rows.append(sample)
    assert len(rows)==10081 and rows[0]['time']==15724800 and rows[-1]['time']==18748800
    return rows

def eval_period(rows):
    # Fresh state at each labeled period boundary. Only BASIC channels are considered.
    counts={'samples':len(rows), 'applicable':0, 'point_exceedances':0,
            'confirmed_samples':0, 'symptom_starts':0, 'abstentions':{}}
    onset=None; last=None; prev_confirmed=False
    for r in rows:
        valid=all(230<=r[k]<=340 for k in ('sat','sp','mat')) and r['fan'] in (0,1) \
              and 0<=r['cool']<=1 and 0<=r['heat']<=1
        if not valid: reason='INVALID_INPUT'
        elif r['fan']==0:reason='FAN_OFF'
        elif r['cool']<.20:reason='LOW_COOLING_COMMAND'
        elif r['heat']>.01:reason='HEATING_COMMAND'
        elif r['mat']-r['sp']<2:reason='LOW_TEMPERATURE_LIFT'
        else:reason='APPLICABLE'
        counts['applicable'] += reason=='APPLICABLE'
        if reason!='APPLICABLE': counts['abstentions'][reason]=counts['abstentions'].get(reason,0)+1
        over=reason=='APPLICABLE' and r['sat']-r['sp']>THRESHOLD
        counts['point_exceedances'] += over
        if not over:onset=None
        elif onset is None or last is None or r['time']-last!=STEP:onset=r['time']
        confirmed=over and (r['time']-onset)>=HOLD
        counts['confirmed_samples']+=confirmed
        counts['symptom_starts']+=bool(confirmed and not prev_confirmed)
        prev_confirmed=confirmed;last=r['time']
    return counts

def main():
    ap=argparse.ArgumentParser();ap.add_argument('source_dir',type=Path);ap.add_argument('--output',type=Path)
    args=ap.parse_args()
    results={}
    for name in SOURCES:
        rows=load_csv(args.source_dir,name)
        parts={'pre': [r for r in rows if r['time']<START],
               'active': [r for r in rows if START<=r['time']<END],
               'post': [r for r in rows if r['time']>=END]}
        results[name]={phase:eval_period(data) for phase,data in parts.items()}
    b=results['BaselineSystem']['active']; f=results['CooCoiValStuck_0']['active']
    assert (b['applicable'], b['point_exceedances'], b['confirmed_samples'], b['symptom_starts'])==(2800,92,60,8)
    assert (f['applicable'], f['point_exceedances'], f['confirmed_samples'], f['symptom_starts'])==(7428,7428,7420,4)
    result={'dataset_family':'G36-5wk','metric_scope':'descriptive, dependent samples',
            'rules':'BASIC SAT-SP>2K, eligibility, hold>=600s; no fault labels in worker',
            'period_interval':[START,END], 'scenario_results':results,
            'publisher_limits':'one simulation campaign, no physical isolation or independent field test'}
    if args.output: args.output.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
    print('PASS: source SHA, original CSV grid, frozen rule, 4 scenarios')
    for name,val in results.items():
        d=val['active']; print(f"{name}: eligible={d['applicable']}, exceeds={d['point_exceedances']}, confirmed={d['confirmed_samples']}, episodes={d['symptom_starts']}")

if __name__=='__main__': main()
