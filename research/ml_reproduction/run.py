"""Independent, gated SD-AHU implementation. Writes research artifacts only."""
import argparse
from collections import defaultdict
import csv
import json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from lightgbm import LGBMRegressor
from sklearn.decomposition import PCA
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from research.ml_reproduction.brick import derive
from research.ml_reproduction.sources import BASELINE, CASES, sha

ROOT = Path(__file__).resolve().parents[2]
MODES = ("PAPER_FULL_REPRO", "STRICT_HOLDOUT", "PRODUCT_BASIC", "PRODUCT_BASIC_WITHOUT_COMMANDS")
TEMPORAL = ("hour", "month", "day_of_week")
MODELS = ("LightGBM", "Ridge", "PCA-input-matched")
SEASONS = {"winter": (12, 1, 2), "spring": (3, 4, 5), "summer": (6, 7, 8), "autumn": (9, 10, 11)}
FORBIDDEN = {"Datetime", "fault_label", "source_label", "fault_type", "severity", "oracle"}


def plans(graph, columns, registry, mode):
    paper = mode == MODES[0]
    basic = mode.startswith("PRODUCT_BASIC")
    permitted = set(columns) - FORBIDDEN
    if not paper:
        permitted.discard("SYS_CTL")
    if basic:
        permitted &= {name for name, config in registry.items() if config["basic_eligible"] and config["source_unit"]
                      and (mode != MODES[3] or config["kind"] != "COMMAND")}
    allowed_graph = {target: sorted(set(features) & permitted - {target}) for target, features in graph.items()}
    context = [*TEMPORAL, "occupancy"] if paper else list(TEMPORAL)
    result = {target: features + context for target, features in allowed_graph.items()
              if target in permitted and len(features) >= 3}
    return result, sorted(permitted), {target: len(features) for target, features in allowed_graph.items()}


def fan_running(times, fan):
    """Vectorized lbnl-fan-hold@1.0.0, six consecutive 60 s ON observations."""
    ticks = pd.DatetimeIndex(times).as_unit("ns").asi8
    breaks = np.r_[True, np.diff(ticks) != 60_000_000_000]
    on = np.asarray(fan) == 1
    index = np.arange(len(on))
    last_reset = np.maximum.accumulate(np.where(breaks | ~on, index, -1))
    first = np.where(on[last_reset], last_reset, last_reset + 1)
    return on & (index - first >= 5)


def prepare(frame, mode, raw_columns):
    paper = mode == MODES[0]
    index = pd.DatetimeIndex(frame.pop("Datetime"))
    if paper:
        mask = frame["SYS_CTL"].to_numpy() >= 1
    else:
        mask = fan_running(index, frame["SF_SPD_DM"].to_numpy())
    frame.index = index
    frame["hour"], frame["month"], frame["day_of_week"] = index.hour, index.month, index.dayofweek
    if paper:
        frame["occupancy"] = mask.astype(int)
    return frame, mask & np.isfinite(frame[raw_columns]).all(axis=1).to_numpy()


def split(frame, mask, paper):
    if paper:
        occupied = frame.index[mask]
        cutoff = occupied[int(len(occupied) * .8)]
        return cutoff, cutoff
    days = frame.index.normalize().unique()
    return days[int(len(days) * .6)], days[int(len(days) * .8)]


def daily(values, index):
    return pd.DataFrame(values, index=index).groupby(index.normalize()).mean()


def calibration(values):
    mu = values.mean()
    sd = values.std(ddof=0)
    return mu, sd if sd > 1e-12 else None


def zscore(values, center, scale):
    return (values - center) / scale if scale is not None else np.full(len(values), np.nan)


def regressor(name, params, seed, threads):
    if name == "LightGBM":
        return LGBMRegressor(**{**params, "random_state": seed}, n_jobs=threads, verbosity=-1)
    if name == "Ridge":
        return make_pipeline(StandardScaler(), Ridge(alpha=1.0))
    return make_pipeline(StandardScaler(), PCA(n_components=.95, svd_solver="full"), LinearRegression())


def fit(train, calibrate, features, names, params, seed, threads, raw_columns, mixing):
    fitted, errors = {}, []
    for name in names:
        models = {}
        for target, fields in features.items():
            if target in fields or FORBIDDEN.intersection(fields):
                raise ValueError("Illegal input")
            model = regressor(name, params, seed, threads)
            model.fit(train[fields], train[target])
            residual = np.abs(calibrate[target].to_numpy() - model.predict(calibrate[fields]))
            mu, sd = calibration(residual)
            errors.append({"model": name, "target": target, "n": len(residual), "rmse_f": float(np.sqrt(np.mean(residual ** 2))),
                           "mae_f": float(mu), "median_abs_f": float(np.median(residual)), "abs_sd_f": sd,
                           "constant_features": "|".join(field for field in fields if train[field].nunique() == 1)})
            models[target] = (model, mu, sd)
        fitted[name] = models
        print(f"fit {name} targets={len(models)}", flush=True)
    aux = {}
    if len(names) > 1:
        scaler = StandardScaler().fit(train[raw_columns])
        pca = PCA(n_components=.95, svd_solver="full").fit(scaler.transform(train[raw_columns]))
        def pca_error(frame):
            data = scaler.transform(frame[raw_columns])
            return ((data - pca.inverse_transform(pca.transform(data))) ** 2).mean(axis=1)
        aux["PCA-paper"] = pca_error
        aux["SAT setpoint"] = lambda frame: (frame.SA_TEMP - frame.SA_TEMPSPT).abs().to_numpy()
        if mixing:
            aux["Mixing residual"] = lambda frame: (frame.MA_TEMP - (
                frame.OA_DMPR * frame.OA_TEMP + (1 - frame.OA_DMPR) * frame.RA_TEMP)).abs().to_numpy()
    scalars = {}
    for name, function in aux.items():
        residual = function(calibrate)
        scores = daily(residual, calibrate.index)[0]
        scalars[name] = (function, *calibration(scores.to_numpy()))
        errors.append({"model": name, "target": "SYSTEM", "n": len(residual),
                       "rmse_f": None if name == "PCA-paper" else float(np.sqrt(np.mean(residual ** 2))),
                       "mae_f": None if name == "PCA-paper" else float(np.mean(residual)),
                       "median_abs_f": None if name == "PCA-paper" else float(np.median(residual)),
                       "calibration_minute_mean_score": float(np.mean(residual)),
                       "calibration_minute_median_score": float(np.median(residual)),
                       "calibration_score_unit": "standardized squared" if name == "PCA-paper" else "degF"})
    return fitted, scalars, errors


def scores(frame, features, fitted):
    residuals = {}
    for target, (model, center, scale) in fitted.items():
        absolute = np.abs(frame[target].to_numpy() - model.predict(frame[features[target]]))
        residuals[target] = zscore(absolute, center, scale)
    if not residuals:
        return pd.DataFrame(index=frame.index.normalize().unique())
    return daily(residuals, frame.index)


def summarize(negative, positive):
    actual = np.r_[np.zeros(len(negative)), np.ones(len(positive))]
    raw = np.r_[negative.raw.to_numpy(), positive.raw.to_numpy()]
    binary = np.r_[negative.z.to_numpy(), positive.z.to_numpy()]
    auc = float(roc_auc_score(actual, raw)) if len(negative) and len(positive) else None
    if not np.isfinite(binary).all() or not len(binary):
        return {"auc": auc, "precision": None, "recall": None, "fpr": None, "tp": None, "fp": None, "tn": None, "fn": None}
    alarm = binary > 3
    tp, fp = int((alarm & (actual == 1)).sum()), int((alarm & (actual == 0)).sum())
    fn, tn = len(positive) - tp, len(negative) - fp
    return {"auc": auc, "precision": tp / (tp + fp) if tp + fp else None,
            "recall": tp / len(positive) if len(positive) else None, "fpr": fp / len(negative) if len(negative) else None,
            "tp": tp, "fp": fp, "tn": tn, "fn": fn,
            "false_positive_days": "|".join(str(date.date()) for date in negative.index[negative.z > 3])}


def write_table(path, records):
    fields = list(dict.fromkeys(key for record in records for key in record))
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(records)


def run(cache, receipt, ttl, mode, seed, output, threads):
    audit = json.loads(receipt.read_text())
    if not audit["structural_pass"] or any(audit["members"][name]["nonfinite_cells"] for name in CASES):
        raise ValueError("D0 did not pass for the selected complete archive")
    protocol = yaml.safe_load(Path(__file__).with_name("FROZEN_PROTOCOL.yaml").read_text())
    registry = yaml.safe_load((ROOT / "research/g0-g1/SIGNAL_MAP_V1.yaml").read_text())["signals"]
    columns = audit["members"][BASELINE]["columns"]
    graph, derivation = derive(ttl, columns[1:])
    if set(graph) != set(protocol["targets"]) or derivation != "BRICK_GRAPH":
        raise ValueError("D0 did not derive the eight publisher targets")
    features, raw_columns, counts = plans(graph, columns[1:], registry, mode)
    basic = mode.startswith("PRODUCT_BASIC")
    if not features:
        write_table(output / "metrics.csv", [{"mode": mode, "status": "NOT_EVALUABLE", "reason": "BLOCKED_INSUFFICIENT_INPUTS"}])
        return
    names = MODELS if seed == 42 else ("LightGBM",)
    healthy, mask = prepare(pd.read_parquet(cache / f"{BASELINE}.parquet"), mode, raw_columns)
    paper = mode == MODES[0]
    split1, split2 = split(healthy, mask, paper)
    train = healthy.loc[mask & (healthy.index < split1)]
    calibrate = healthy.loc[mask & (healthy.index >= split1) & ((healthy.index < split2) if not paper else True)]
    fitted, scalar, errors = fit(train, calibrate, features, names, protocol["lightgbm"], seed, threads,
                                 raw_columns, mixing=not basic)
    run_info = {"mode": mode, "seed": seed, "cutoffs": [str(split1), str(split2)], "train_n": len(train),
                "calibration_n": len(calibrate), "train_last": str(train.index[-1]), "calibration_first": str(calibrate.index[0]),
                "calibration_last": str(calibrate.index[-1]), "features": features, "raw_columns": raw_columns,
                "minimum_neighbors": counts, "blocked_targets": sorted(set(graph) - set(features)),
                "protocol_sha256": sha(Path(__file__).with_name("FROZEN_PROTOCOL.yaml")),
                "source_archive_sha256": audit["archive_sha256"], "ttl_sha256": sha(ttl)}
    write_table(output / "validation-errors.csv", errors)
    del train, calibrate
    (output / "run.json").write_text(json.dumps(run_info, indent=2) + "\n")
    runs, rows, ranks, coverage, actuator = {}, [], [], [], []
    for name, (label, _) in CASES.items():
        if name == BASELINE:
            frame, valid = healthy, mask
        else:
            frame, valid = prepare(pd.read_parquet(cache / f"{name}.parquet"), mode, raw_columns)
        selected = frame.loc[valid & (frame.index >= split2)]
        covered = selected.groupby(selected.index.normalize()).size()
        coverage.append({"scenario": label, "source_sha256": audit["members"][name]["sha256"], "source_ticks": len(frame),
                         "mask_ticks_full": int(valid.sum()), "test_ticks": len(selected), "test_days": len(covered),
                         "calendar_ticks": int((frame.index >= split2).sum()),
                         "calendar_days": int(frame.index[frame.index >= split2].normalize().nunique())})
        daily_scores = {}
        for method, models in fitted.items():
            ranking_full = method == "LightGBM" and paper and seed == 42
            # Split at the cutoff before aggregation, so partial validation day never includes training minutes.
            points = scores(selected, features, models)
            daily_scores[method] = pd.DataFrame({"raw": points.max(axis=1), "z": points.max(axis=1)}).dropna()
            ranking = scores(frame.loc[valid], features, models) if ranking_full else points
            medians = ranking.median().dropna().sort_values(ascending=False, kind="stable")
            for rank, (target, median) in enumerate(medians.items(), 1):
                ranks.append({"scenario": label, "model": method, "rank": rank, "target": target, "median_daily_z": median,
                              "rank1_rank2_margin": float(medians.iloc[0] - medians.iloc[1]) if rank == 1 and len(medians) > 1 else None,
                              "scope": "FULL_YEAR" if ranking_full else "TEST"})
            if seed == 42:
                for day, record in points.iterrows():
                    rows.append({"scenario": label, "model": method, "day": str(day.date()), "ticks": int(covered[day]),
                                 "raw": daily_scores[method].raw.get(day), "z": daily_scores[method].z.get(day), **record.to_dict()})
        for method, (function, center, scale) in scalar.items():
            raw = daily(function(selected), selected.index)[0]
            daily_scores[method] = pd.DataFrame({"raw": raw, "z": zscore(raw.to_numpy(), center, scale)})
            for day, record in daily_scores[method].iterrows():
                rows.append({"scenario": label, "model": method, "day": str(day.date()), "ticks": int(covered[day]), **record.to_dict()})
        if not basic and seed == 42:
            for scope, subset in (("TEST", selected), ("FULL_ELIGIBLE", frame.loc[valid])):
                actuator.append({"scenario": label, "scope": scope, "n": len(subset),
                                 "Damper_MAE": (subset.OA_DMPR_DM - subset.OA_DMPR).abs().mean(),
                                 "Valve_MAE": (subset.CHWC_VLV_DM - subset.CHWC_VLV).abs().mean()})
        runs[name] = daily_scores
        print(f"scored {mode} seed={seed}: {name}, {len(selected)} eligible test minutes", flush=True)
    metrics = []
    for name, methods in runs.items():
        label = CASES[name][0]
        for method, candidate in methods.items():
            reference = runs[BASELINE][method]
            dates = reference.index.intersection(candidate.index)
            for season, months in {"all": tuple(range(1, 13)), **SEASONS}.items():
                selected_days = dates[dates.month.isin(months)]
                negatives = reference.loc[selected_days]
                positives = candidate.loc[selected_days] if name != BASELINE else candidate.iloc[:0]
                metrics.append({"scenario": label, "model": method, "season": season,
                                "healthy_days": len(negatives), "fault_days": len(positives),
                                "healthy_available_days": int(reference.index.month.isin(months).sum()),
                                "candidate_available_days": int(candidate.index.month.isin(months).sum()),
                                **summarize(negatives, positives)})
    for name, records in (("metrics", metrics), ("coverage", coverage), ("daily", rows), ("rankings", ranks), ("actuators", actuator)):
        if records:
            write_table(output / f"{name}.csv", records)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("cache", "receipt", "ttl", "output"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--mode", choices=MODES, required=True)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--threads", type=int, default=4)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    run(**vars(args))
