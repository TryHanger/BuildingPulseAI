"""Train the two reduced pilots only on the pinned, healthy LBNL member."""
import argparse
import csv
from importlib.metadata import version
import json
from pathlib import Path
import platform

from lightgbm import LGBMRegressor
import numpy as np
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from research.ml_transfer_05.contract import (
    ContractError, FEATURES, PROTOCOL_SHA, block_rows, blocks, input_support, load_protocol, masks, read_input, sha,
)

METHODS = ("lightgbm_reduced", "ridge_reduced", "sat_minus_sp")


def source_partition(clock, rules):
    start, train_end, cal_end, end = (rules[key] for key in
                                       ("start", "train_end_exclusive", "cal_end_exclusive", "end_exclusive"))
    return {
        "train": ((clock >= start) & (clock < train_end)).to_numpy(),
        "calibration": ((clock >= train_end) & (clock < cal_end)).to_numpy(),
        "source_normal_exploratory": ((clock >= cal_end) & (clock < end)).to_numpy(),
    }


def write_json(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def score_source(data, partitions, denominator, eligible, lightgbm, ridge, protocol):
    if data.role != "source":
        raise ContractError("SOURCE_ONLY_SCORING")
    labels = blocks(data, protocol)
    rows = []
    for phase in ("calibration", "source_normal_exploratory"):
        selected = partitions[phase]
        selected_labels = set(labels.loc[selected])
        for label, positions, row in block_rows(labels, denominator, eligible & selected, protocol):
            if label not in selected_labels:
                continue
            row["phase"] = phase
            if row["status"] == "EVALUABLE":
                group = data.channels.iloc[positions]
                actual = group.SA_TEMP.to_numpy()
                x = group.loc[:, list(FEATURES)]
                predictions = (lightgbm.predict(x), ridge.predict(x), group.SA_TEMPSPT.to_numpy())
                for method, prediction in zip(METHODS, predictions, strict=True):
                    row[method + "_mae_degF"] = float(np.abs(actual - prediction).mean())
            rows.append(row)
    return rows


def calibrate(rows, rule):
    scores = [row for row in rows if row["phase"] == "calibration" and row["status"] == "EVALUABLE"]
    if len(scores) < rule["minimum_evaluated_days"]:
        raise ContractError("SOURCE_CALIBRATION_INSUFFICIENT_DAYS")
    result = {}
    for method in METHODS:
        raw = np.array([row[method + "_mae_degF"] for row in scores])
        center, scale = float(raw.mean()), float(raw.std(ddof=0))
        if not np.isfinite(center) or not np.isfinite(scale) or scale <= rule["minimum_scale"]:
            raise ContractError(f"SOURCE_CALIBRATION_INVALID_SCALE:{method}")
        result[method] = {"center": center, "scale": scale, "days": len(raw)}
    return result


def main(inputs, output):
    protocol = load_protocol()
    versions = {"python": platform.python_version(),
                **{name: version(name) for name in ("lightgbm", "scikit-learn", "pandas", "numpy")}}
    if versions != protocol["versions"]:
        raise ContractError("TRAINING_VERSIONS_NOT_PINNED")
    data = read_input(inputs, "source")
    denominator, eligible = masks(data, protocol)
    partitions = source_partition(data.clock, protocol["partition"])
    training = data.channels.loc[partitions["train"] & eligible]
    if training.empty:
        raise ContractError("SOURCE_TRAIN_EMPTY")
    x = training.loc[:, list(FEATURES)]
    target = training.SA_TEMP
    support = {name: [float(x[name].min()), float(x[name].max())] for name in FEATURES}
    lightgbm = LGBMRegressor(**protocol["models"]["lightgbm"]).fit(x, target)
    ridge = make_pipeline(StandardScaler(), Ridge(alpha=protocol["models"]["ridge"]["alpha"])).fit(x, target)
    eligible &= input_support(data.channels, support)
    rows = score_source(data, partitions, denominator, eligible, lightgbm, ridge, protocol)
    calibration = calibrate(rows, protocol["calibration"])
    for row in rows:
        if row["phase"] == "source_normal_exploratory" and row["status"] == "EVALUABLE":
            for method, params in calibration.items():
                score = (row[method + "_mae_degF"] - params["center"]) / params["scale"]
                row[method + "_z"] = score
                row[method + "_alarm"] = score > protocol["calibration"]["alarm_z"]

    output.mkdir(parents=True, exist_ok=False)
    native = output / "REDUCED_SAT.lightgbm.txt"
    lightgbm.booster_.save_model(str(native))
    scaler, linear = ridge.steps[0][1], ridge.steps[1][1]
    ridge_path = output / "REDUCED_SAT_RIDGE.json"
    write_json(ridge_path, {"feature_order": list(FEATURES), "mean": scaler.mean_.tolist(),
                            "scale": scaler.scale_.tolist(), "coefficient": linear.coef_.tolist(),
                            "intercept": float(linear.intercept_)})
    daily = output / "SOURCE_NORMAL_DAILY.csv"
    with daily.open("x", newline="") as stream:
        columns = list(dict.fromkeys(key for row in rows for key in row))
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    windows = {
        phase: {"calendar_days": sum(row["phase"] == phase for row in rows),
                "evaluated_days": sum(row["phase"] == phase and row["status"] == "EVALUABLE" for row in rows),
                "warm_running_minutes": int((denominator & dates).sum()),
                "usable_minutes_before_daily_abstention": int((eligible & dates).sum())}
        for phase, dates in partitions.items() if phase != "train"
    }
    write_json(output / "SOURCE_FIT_RECEIPT.json", {
        "scope": "SOURCE_NORMAL_ONLY", "protocol_sha256": PROTOCOL_SHA,
        "source_sha256": protocol["files"]["source"]["sha256"], "feature_order": list(FEATURES),
        "versions": versions, "train_minutes": len(x), "partitions": protocol["partition"],
        "train_support_degF": support, "calibration": calibration, "windows": windows,
        "source_normal_exploratory_alarm_days": {name: sum(row.get(name + "_alarm", False) for row in rows)
                                                 for name in METHODS},
        "artifacts": {path.name: sha(path) for path in (native, ridge_path, daily)},
        "target_prediction_executed": False, "fault_prediction_executed": False,
    })
    print(f"PASS two source-normal fits on {len(x)} shared train minutes; no target or fault inference")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", type=Path)
    parser.add_argument("output", type=Path)
    main(**vars(parser.parse_args()))
