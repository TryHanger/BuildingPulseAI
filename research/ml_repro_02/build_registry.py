"""Produce native local model artifacts and an independent v1 SAT replay receipt."""
import argparse
from importlib.metadata import version
import json
from pathlib import Path
import platform

import numpy as np
import pandas as pd

from backend.app.services.virtual_sensor_research import schema_digest
from research.ml_reproduction import run as v1
from research.ml_reproduction.sources import BASELINE, BIASES, CASES, sha
from research.ml_repro_02.controls import HERE, inputs, load
from research.ml_repro_02.gate import SOURCE_SHA, TTL_SHA, V1_SHA


def write_json(path, payload):
    path.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n")


def main(d0, ttl, gate, output, receipts):
    result = json.loads(gate.read_text())
    protocol_sha = sha(HERE / "PROTOCOL.yaml")
    if (result["status"] != "GO_RESEARCH_ONLY_PRODUCT_PILOT" or result["protocol_sha256"] != protocol_sha
            or result["source_sha256"] != SOURCE_SHA):
        raise ValueError("Research pilot gate did not pass")
    audit = json.loads((d0 / "source-audit.json").read_text())
    columns, graph, registry, params = inputs(d0, ttl)
    mode = "PRODUCT_BASIC"
    features, raw, _ = v1.plans(graph, columns, registry, mode)
    if len(features) != 8:
        raise ValueError("BASIC feature plan incomplete")
    schema = {"feature_orders": features, "available_channels": raw,
              "feature_roles": {**{field: registry[field]["kind"] for field in raw},
                                **{field: "CALENDAR_CONTEXT" for field in v1.TEMPORAL}}}
    healthy, healthy_mask = v1.prepare(load(d0, BASELINE), mode, raw)
    first, second = v1.split(healthy, healthy_mask, False)
    train = healthy.loc[healthy_mask & (healthy.index < first)]
    calibrate = healthy.loc[healthy_mask & (healthy.index >= first) & (healthy.index < second)]
    fitted, _, errors = v1.fit(train, calibrate, features, ("LightGBM",), params, 42, 4, raw, mixing=False)
    models = fitted["LightGBM"]
    output.mkdir(parents=True, exist_ok=False)
    split = {"train_first": str(train.index[0]), "train_last": str(train.index[-1]), "train_minutes": str(len(train)),
             "calibration_first": str(calibrate.index[0]), "calibration_last": str(calibrate.index[-1]),
             "calibration_minutes": str(len(calibrate)), "test_start": str(second),
             "test_end_exclusive": "2019-01-01 00:00:00"}
    del train, calibrate
    entries = {}
    for target, (model, center, scale) in models.items():
        model_path = output / f"{target}.lightgbm.txt"
        model.booster_.save_model(str(model_path))
        model_sha = sha(model_path)
        entries[target] = {"model_id": f"bp-ml-repro-02-basic-{target.lower()}-{model_sha[:12]}",
                           "target": target, "file": model_path.name, "sha256": model_sha,
                           "format": "LIGHTGBM_NATIVE_TEXT", "feature_order": features[target],
                           "scaler": "NONE_NATIVE_LIGHTGBM", "abs_center": float(center),
                           "abs_scale": None if scale is None else float(scale)}
    windows, offline = {}, []
    sat_model, center, scale = models["SA_TEMP"]
    for case_id, member in (("healthy", BASELINE), ("sa-plus-2", "coi_bias_2_annual.csv")):
        frame, eligible = (healthy, healthy_mask) if member == BASELINE else v1.prepare(load(d0, member), mode, raw)
        window = (frame.index >= second) & (frame.index < second + pd.Timedelta(days=7))
        export = frame.loc[window, raw].rename_axis("timestamp").reset_index()
        export["eligible"] = eligible[window]
        path = output / f"{case_id}.parquet"
        export.to_parquet(path, index=False, compression="zstd")
        windows[case_id] = {"id": case_id, "label": CASES[member][0], "member": member,
                            "member_sha256": audit["members"][member]["sha256"], "source_sha256": SOURCE_SHA,
                            "alias_status": "UNVERIFIED_PUBLISHER_ALIAS" if member in BIASES else "PUBLISHER_BASELINE",
                            "days": export.timestamp.dt.strftime("%Y-%m-%d").unique().tolist(),
                            "file": path.name, "sha256": sha(path)}
        evaluated = frame.loc[window & eligible]
        actual = evaluated.SA_TEMP.to_numpy()
        predicted = sat_model.predict(evaluated[features["SA_TEMP"]])
        absolute = np.abs(actual - predicted)
        z = v1.zscore(absolute, center, scale)
        scores = v1.scores(evaluated, features, {"SA_TEMP": models["SA_TEMP"]})["SA_TEMP"]
        for ts, a, p, r, value in zip(evaluated.index, actual, predicted, absolute, z, strict=True):
            offline.append({"case_id": case_id, "timestamp": str(ts), "actual": a, "predicted": p,
                            "absolute_residual": r, "z": value, "daily_score": scores.loc[ts.normalize()]})
    incremental = pd.read_csv(gate.with_name("INCREMENTAL_VALUE_MATRIX.csv"))
    compare_fields = ["arm", "comparator", "paired_days", "lgbm_tp", "comparator_tp",
                      "lgbm_fp", "comparator_fp", "both_tp"]
    comparisons = incremental.loc[incremental.member == "coi_bias_2_annual.csv", compare_fields].to_dict("records")
    manifest = {
        "scope": "SIMULATED_BENCHMARK", "use": "RESEARCH_ONLY", "arm": mode,
        "source": "Official LBNL SD-AHU 10.25984/1881324",
        "source_sha256": SOURCE_SHA, "ttl_sha256": TTL_SHA, "schema_sha256": schema_digest(schema),
        "protocol_sha256": V1_SHA, "integration_protocol_sha256": protocol_sha,
        "schema": schema, "source_timezone": "SOURCE_LOCAL_UNVERIFIED_UTC_OFFSET",
        "timestamp_format": "YYYY-MM-DD HH:MM:SS", "mode": "lbnl-fan-hold@1.0.0 RUNNING 300s",
        "split": split, "seed": 42, "threads": 4, "lightgbm_parameters": params,
        "versions": {"python": platform.python_version(), **{name: version(name) for name in
                     ("lightgbm", "numpy", "pandas", "scikit-learn", "rdflib", "pyarrow", "PyYAML")}},
        "training_member": BASELINE, "training_member_sha256": audit["members"][BASELINE]["sha256"],
        "models": entries, "windows": windows, "comparisons": comparisons,
        "p1_gate_sha256": sha(gate),
    }
    write_json(output / "MODEL_ARTIFACT_MANIFEST.json", manifest)
    v1.write_table(receipts / "SAT_OFFLINE_WINDOW.csv", offline)
    v1.write_table(receipts / "BASIC_CALIBRATION_ERRORS.csv", errors)
    print("PASS eight native models and two frozen test windows", len(offline), "eligible SAT rows")
    print("Pinned manifest SHA-256", sha(output / "MODEL_ARTIFACT_MANIFEST.json"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("d0", "ttl", "gate", "output", "receipts"):
        parser.add_argument(name, type=Path)
    main(**vars(parser.parse_args()))
