import json
import pandas as pd

with open("research/runs/stage8a_control_effort_results.json", "r", encoding="utf-8") as f:
    res = json.load(f)

for ahu in ["ahu9", "ahu10"]:
    print(f"\n=================== {ahu.upper()} DETAILED EVENT DETECTION ===================")
    ev_T = {e["fault_id"]: e for e in res[ahu]["detailed_events_T"]}
    ev_u = {e["fault_id"]: e for e in res[ahu]["detailed_events_U"]}
    ev_F = {e["fault_id"]: e for e in res[ahu]["detailed_events_Fusion"]}

    fault_ids = list(ev_T.keys())
    for fid in fault_ids:
        t_det = ev_T[fid]["detected"]
        u_det = ev_u[fid]["detected"]
        fus_det = ev_F[fid]["detected"]
        meta = ev_T[fid]
        if t_det or u_det or fus_det:
            diff_flag = " *** GAIN ***" if (fus_det and not t_det) else ""
            print(f"ID {fid:3d} | {meta['fault_type'][:22]:22s} | Mag={meta['magnitude']:5.1f} | Start={meta['start']} | T={str(t_det):5s} U={str(u_det):5s} FUS={str(fus_det):5s}{diff_flag}")
