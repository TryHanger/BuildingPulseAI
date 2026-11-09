"""One separately frozen row-bagging hypothesis; no changes to the v1 arm."""
import argparse
from pathlib import Path

import numpy as np

from research.ml_reproduction import run as v1
from research.ml_reproduction.sources import BASELINE, CASES, sha
from research.ml_repro_02.controls import HERE, evaluate, inputs, load


def main(d0, ttl, output):
    columns, graph, registry, params = inputs(d0, ttl)
    mode = v1.MODES[0]
    features, raw, _ = v1.plans(graph, columns, registry, mode)
    healthy, mask = v1.prepare(load(d0, BASELINE), mode, raw)
    cutoff, _ = v1.split(healthy, mask, True)
    train = healthy.loc[mask & (healthy.index < cutoff)]
    calibrate = healthy.loc[mask & (healthy.index >= cutoff)]
    configs = (0, 1)
    models = {freq: v1.fit(train, calibrate, features, ("LightGBM",),
                           {**params, "subsample_freq": freq}, 42, 4, raw, mixing=False)[0]
              for freq in configs}
    negative = {freq: evaluate(calibrate, features, model, {})["LightGBM"] for freq, model in models.items()}
    calendar_minutes = int((healthy.index >= cutoff).sum())
    calendar_days = healthy.index[healthy.index >= cutoff].normalize().nunique()
    del healthy, train, calibrate
    rows = []
    for member, (label, _) in CASES.items():
        if member == BASELINE:
            continue
        frame, eligible = v1.prepare(load(d0, member), mode, raw)
        subset = frame.loc[eligible & (frame.index >= cutoff)]
        for freq, model in models.items():
            positive = evaluate(subset, features, model, {})["LightGBM"]
            dates = positive.index.intersection(negative[freq].index)
            rows.append({
                "status": "POST_HOC_SENSITIVITY", "hypothesis_sha256": sha(HERE / "BAGGING_HYPOTHESIS.yaml"),
                "scenario": label, "member": member, "subsample_freq": freq, "subsample": params["subsample"],
                "calendar_minutes": calendar_minutes, "calendar_days": calendar_days, "paired_days": len(dates),
                "excluded_calendar_days": calendar_days - len(dates),
                "fault_eligible_minutes": len(subset), "fault_excluded_minutes": calendar_minutes - len(subset),
                "healthy_eligible_minutes": int(np.count_nonzero(mask & (frame.index >= cutoff))),
                **v1.summarize(negative[freq].loc[dates], positive.loc[dates]),
            })
        print("Scored", label, flush=True)
    v1.write_table(output / "POST_HOC_BAGGING.csv", rows)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("d0", "ttl", "output"):
        parser.add_argument(name, type=Path)
    main(**vars(parser.parse_args()))
