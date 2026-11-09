"""Post-hoc controls frozen before new fits; leave the four original arms intact."""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from research.ml_reproduction import run as v1
from research.ml_reproduction.sources import BASELINE, CASES, sha
from research.ml_repro_02.gate import SOURCE_SHA, TTL_SHA, V1_SHA, check

HERE = Path(__file__).parent
COMPARATORS = ("SAT setpoint", "Ridge", "PCA-paper", "PCA-input-matched")
BASIC_ARMS = v1.MODES[2:]


def inputs(d0, ttl):
    check(ttl, TTL_SHA)
    check(v1.ROOT / "research/ml_reproduction/FROZEN_PROTOCOL.yaml", V1_SHA)
    gate = json.loads((d0 / "verified.json").read_text())
    if gate["status"] != "PASS" or gate["source_sha256"] != SOURCE_SHA or gate["ttl_sha256"] != TTL_SHA:
        raise ValueError("Unqualified source")
    audit = json.loads((d0 / "source-audit.json").read_text())
    columns = audit["members"][BASELINE]["columns"][1:]
    graph, method = v1.derive(ttl, columns)
    protocol = yaml.safe_load((v1.ROOT / "research/ml_reproduction/FROZEN_PROTOCOL.yaml").read_text())
    if method != "BRICK_GRAPH" or set(graph) != set(protocol["targets"]):
        raise ValueError("Unexpected graph targets")
    registry = yaml.safe_load((v1.ROOT / "research/g0-g1/SIGNAL_MAP_V1.yaml").read_text())["signals"]
    return columns, graph, registry, protocol["lightgbm"]


def load(d0, member):
    gate = json.loads((d0 / "verified.json").read_text())
    path = d0 / "cache" / f"{member}.parquet"
    check(path, gate["cache"][path.name])
    return pd.read_parquet(path)


def incremental(accepted):
    records = []
    for arm in BASIC_ARMS:
        daily = pd.read_csv(accepted / arm / "daily.csv")
        for member, (scenario, _) in CASES.items():
            if member == BASELINE:
                continue
            positive = daily[daily.scenario == scenario].pivot(index="day", columns="model", values="z")
            negative = daily[daily.scenario == "healthy"].pivot(index="day", columns="model", values="z")
            days = positive.index.intersection(negative.index)
            for comparator in COMPARATORS:
                names = ["LightGBM", comparator]
                valid = positive.loc[days, names].notna().all(axis=1) & negative.loc[days, names].notna().all(axis=1)
                tp = positive.loc[valid.index[valid], names] > 3
                fp = negative.loc[valid.index[valid], names] > 3
                records.append({
                    "arm": arm, "scenario": scenario, "member": member, "comparator": comparator,
                    "candidate_days": len(days), "paired_days": len(tp), "excluded_days": len(days)-len(tp),
                    "lgbm_tp": int(tp.LightGBM.sum()), "comparator_tp": int(tp[comparator].sum()),
                    "lgbm_fn": int((~tp.LightGBM).sum()), "comparator_fn": int((~tp[comparator]).sum()),
                    "lgbm_fp": int(fp.LightGBM.sum()), "comparator_fp": int(fp[comparator].sum()),
                    "both_tp": int((tp.LightGBM & tp[comparator]).sum()),
                    "lgbm_only_days": "|".join(tp.index[tp.LightGBM & ~tp[comparator]]),
                    "comparator_only_days": "|".join(tp.index[~tp.LightGBM & tp[comparator]]),
                    "both_fp": int((fp.LightGBM & fp[comparator]).sum()),
                    "lgbm_only_fp_days": "|".join(fp.index[fp.LightGBM & ~fp[comparator]]),
                    "comparator_only_fp_days": "|".join(fp.index[~fp.LightGBM & fp[comparator]]),
                    "incremental_tp": int(tp.LightGBM.sum() - tp[comparator].sum()),
                })
    return records


def evaluate(frame, features, fitted, scalar):
    result = {}
    for name, models in fitted.items():
        system = v1.scores(frame, features, models).max(axis=1).dropna()
        result[name] = pd.DataFrame({"raw": system, "z": system})
    for name, (function, center, scale) in scalar.items():
        raw = v1.daily(function(frame), frame.index)[0]
        result[name] = pd.DataFrame({"raw": raw, "z": v1.zscore(raw.to_numpy(), center, scale)})
    return result


def post_hoc(d0, ttl, output):
    columns, graph, registry, params = inputs(d0, ttl)
    specs = [(mode, mode, mode, True) for mode in BASIC_ARMS] + [
        ("STRICT_REFERENCE_RERUN", v1.MODES[1], v1.MODES[1], False),
        ("STRICT_PAPER_MASK_ONLY", v1.MODES[1], v1.MODES[0], False),
        ("STRICT_PAPER_CONTEXT_ONLY", v1.MODES[0], v1.MODES[1], False),
    ]
    all_results = []
    for arm, feature_mode, mask_mode, paired in specs:
        features, raw, _ = v1.plans(graph, columns, registry, feature_mode)
        context_is_paper = feature_mode == v1.MODES[0]

        def prepare(member):
            frame, mask = v1.prepare(load(d0, member), mask_mode, raw)
            if context_is_paper and mask_mode != v1.MODES[0]:
                frame["occupancy"] = (frame.SYS_CTL >= 1).astype(int)
            return frame, mask

        healthy, mask = prepare(BASELINE)
        first, second = v1.split(healthy, mask, False)
        train = healthy.loc[mask & (healthy.index < first)]
        calibrate = healthy.loc[mask & (healthy.index >= first) & (healthy.index < second)]
        fitted, scalar, _ = v1.fit(train, calibrate, features, v1.MODELS if paired else ("LightGBM",),
                                   params, 42, 4, raw, mixing=False)
        healthy_test = healthy.loc[mask & (healthy.index >= second)]
        del healthy, train, calibrate
        test_count = (pd.Timestamp("2019-01-01") - second) // pd.Timedelta(minutes=1)
        test_days = test_count // 1440
        healthy_scores = None if paired else evaluate(healthy_test, features, fitted, scalar)
        for member, (label, _) in CASES.items():
            if member == BASELINE:
                continue
            fault, fault_mask = prepare(member)
            fault_test = fault.loc[fault_mask & (fault.index >= second)]
            common = healthy_test.index.intersection(fault_test.index)
            coverage = {"status": "POST_HOC_SENSITIVITY", "arm": arm, "scenario": label, "member": member,
                        "test_calendar_days": test_days, "test_calendar_minutes": test_count,
                        "eligible_healthy_minutes": len(healthy_test), "eligible_fault_minutes": len(fault_test),
                        "matched_minutes": len(common), "matched_days": common.normalize().nunique(),
                        "excluded_healthy_eligible_minutes": len(healthy_test) - len(common) if paired else 0,
                        "excluded_fault_eligible_minutes": len(fault_test) - len(common) if paired else 0,
                        "evaluated_healthy_minutes": len(common) if paired else len(healthy_test),
                        "evaluated_fault_minutes": len(common) if paired else len(fault_test)}
            if paired and common.empty:
                all_results.append({**coverage, "status": "NOT_EVALUABLE"})
                continue
            negative = evaluate(healthy_test.loc[common], features, fitted, scalar) if paired else healthy_scores
            positive = evaluate(fault_test.loc[common] if paired else fault_test, features, fitted, scalar)
            for name, score in positive.items():
                dates = score.index.intersection(negative[name].index)
                all_results.append({**coverage, "model": name, "paired_days": len(dates),
                                    "excluded_calendar_days": test_days - len(dates),
                                    **v1.summarize(negative[name].loc[dates], score.loc[dates])})
        print(f"Completed {arm}", flush=True)
    v1.write_table(output / "POST_HOC_SENSITIVITY.csv", all_results)


def main(accepted, d0, ttl, output):
    rows = incremental(accepted)
    v1.write_table(output / "INCREMENTAL_VALUE_MATRIX.csv", rows)
    post_hoc(d0, ttl, output)
    primary = next(row for row in rows if row["arm"] == "PRODUCT_BASIC"
                   and row["member"] == "coi_bias_2_annual.csv" and row["comparator"] == "SAT setpoint")
    admitted = primary["incremental_tp"] > 0 and primary["lgbm_fp"] <= primary["comparator_fp"]
    (output / "p1-gate.json").write_text(json.dumps({
        "status": "GO_RESEARCH_ONLY_PRODUCT_PILOT" if admitted else "HOLD",
        "criterion": "extra days versus SAT setpoint in frozen SA+2 BASIC without more healthy alarms; within simulation",
        "primary": primary, "protocol_sha256": sha(HERE / "PROTOCOL.yaml"),
        "source_sha256": SOURCE_SHA,
    }, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("accepted", "d0", "ttl", "output"):
        parser.add_argument(name, type=Path)
    main(**vars(parser.parse_args()))
