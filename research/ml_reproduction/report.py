"""Recheck published experiment outputs independently and render compact tables."""
import argparse
from collections import defaultdict
import csv
import json
import math
from pathlib import Path

PAPER_METRICS = {
    "SA +2 C": (.9992, 1, .833, .4942),
    "SA +4 C": (1, 1, .983, .4906),
    "SA -2 C": (1, 1, 1, .510),
    "SA -4 C": (1, 1, 1, .5272),
    "Damper stuck 10%": (1, 1, 1, .3639),
    "Damper stuck 25%": (1, 1, 1, .7769),
    "Damper stuck 75%": (1, 1, 1, .3319),
    "Valve stuck 10%": (1, 1, 1, .5458),
    "Valve stuck 50%": (1, 1, 1, .511),
    "Valve stuck 75%": (1, 1, 1, .500),
    "Valve leak (unique payload)": (1, 1, 1, .5050),
}
PAPER_ERRORS = {
    "SA_TEMP": (.1516, .0388, .1465), "MA_TEMP": (.1919, .0910, .1689),
    "RA_TEMP": (.1266, .0714, .1045), "ZONE_TEMP_1": (.2238, .1355, .1781),
    "ZONE_TEMP_2": (.5980, .3886, .4545), "ZONE_TEMP_3": (.5474, .3955, .3785),
    "ZONE_TEMP_4": (.4995, .3310, .3741), "ZONE_TEMP_5": (.9865, .7213, .6730),
}
MONTHS = {"all": range(1, 13), "winter": (12, 1, 2), "spring": (3, 4, 5),
          "summer": (6, 7, 8), "autumn": (9, 10, 11)}


def read(path):
    with path.open(newline="") as stream:
        return list(csv.DictReader(stream))


def write(path, rows):
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def independently_check(directory, metrics):
    daily = defaultdict(dict)
    for row in read(directory / "daily.csv"):
        daily[row["scenario"], row["model"]][row["day"]] = row
        if row["model"] in ("LightGBM", "Ridge", "PCA-input-matched"):
            values = [float(row[name]) for name in PAPER_ERRORS if row[name]]
            assert math.isclose(max(values), float(row["raw"]), abs_tol=1e-12)
    for row in metrics:
        method = row["model"]
        healthy = daily["healthy", method]
        fault = daily[row["scenario"], method]
        common = sorted(day for day in healthy.keys() & fault.keys()
                        if int(day[5:7]) in MONTHS[row["season"]])
        assert len(common) == int(row["healthy_days"])
        negatives = [healthy[day] for day in common]
        positives = [fault[day] for day in common] if row["scenario"] != "healthy" else []
        assert len(positives) == int(row["fault_days"])
        if positives and negatives:
            pairs = [float(pos["raw"]) - float(neg["raw"]) for pos in positives for neg in negatives]
            expected = (sum(diff > 0 for diff in pairs) + .5 * pairs.count(0)) / len(pairs)
            assert math.isclose(expected, float(row["auc"]), abs_tol=1e-14)
        if negatives and all(record["z"] for record in negatives + positives):
            fp = sum(float(record["z"]) > 3 for record in negatives)
            tp = sum(float(record["z"]) > 3 for record in positives)
            assert (fp, tp, len(negatives)-fp, len(positives)-tp) == tuple(map(int, (row["fp"], row["tp"], row["tn"], row["fn"])))
    print(f"PASS {directory.name}: {len(metrics)} stratified records, independent pairwise AUC and confusion", flush=True)


def reference(row, key):
    scenario, model = row["scenario"], row["model"]
    source = PAPER_METRICS.get(scenario)
    if model == "LightGBM" and key == "fpr":
        return 0
    if source is None:
        return None
    if model == "LightGBM" and key in ("auc", "precision", "recall"):
        return source[("auc", "precision", "recall").index(key)]
    if model == "PCA-paper" and key == "auc":
        return 1
    if model == "Mixing residual" and key == "auc":
        return source[3]
    return None


def compare(bundle, seed_root):
    modes = {}
    for directory in sorted((bundle / "experiments").iterdir()):
        metrics = read(directory / "metrics.csv")
        independently_check(directory, metrics)
        modes[directory.name] = metrics
    paper = modes["PAPER_FULL_REPRO"]
    results = []
    for row in paper:
        if row["season"] != "all":
            continue
        for metric in ("auc", "precision", "recall", "fpr"):
            published = reference(row, metric)
            actual = float(row[metric]) if row[metric] else None
            results.append({"scenario": row["scenario"], "method": row["model"], "metric": metric, "value": actual,
                            "published": published, "delta": actual-published if actual is not None and published is not None else None,
                            "status": "REIMPLEMENTED" if published is not None else "NOT_COMPARABLE",
                            "healthy_days": row["healthy_days"], "fault_days": row["fault_days"]})
    for row in read(bundle / "experiments/PAPER_FULL_REPRO/validation-errors.csv"):
        if row["model"] != "LightGBM":
            continue
        for metric, published in zip(("rmse_f", "mae_f", "abs_sd_f"), PAPER_ERRORS[row["target"]], strict=True):
            actual = float(row[metric])
            results.append({"scenario": "healthy calibration", "method": row["model"], "target": row["target"],
                            "metric": metric, "value": actual, "published": published, "delta": actual-published,
                            "status": "REIMPLEMENTED"})
    write(bundle / "PAPER_REPLICATION_RESULTS.csv", results)
    write(bundle / "STRICT_HOLDOUT_RESULTS.csv", modes["STRICT_HOLDOUT"])
    write(bundle / "PRODUCT_BASIC_RESULTS.csv", [
        {"panel": label, **row} for label, mode in (("WITH_COMMANDS", "PRODUCT_BASIC"),
                                                   ("WITHOUT_COMMANDS", "PRODUCT_BASIC_WITHOUT_COMMANDS"))
        for row in modes[mode]
    ])
    if seed_root and seed_root.exists():
        seeds = [{"seed": seed, **row} for seed in range(10) if (seed_root / str(seed) / "metrics.csv").exists()
                 for row in read(seed_root / str(seed) / "metrics.csv") if row["season"] == "all"]
        if seeds:
            write(bundle / "SEED_SWEEP_RESULTS.csv", seeds)


def figure(bundle):
    import matplotlib.pyplot as plt
    modes = ("PAPER_FULL_REPRO", "STRICT_HOLDOUT", "PRODUCT_BASIC", "PRODUCT_BASIC_WITHOUT_COMMANDS")
    methods = ("LightGBM", "PCA-paper", "Ridge", "PCA-input-matched")
    biases = ("SA +2 C", "SA +4 C", "SA -2 C", "SA -4 C")
    fig, axes = plt.subplots(2, 2, figsize=(10.5, 7.6), sharey=True, layout="constrained")
    for axis, mode in zip(axes.flat, modes, strict=True):
        selected = {(r["scenario"], r["model"]): float(r["auc"]) for r in read(bundle / "experiments" / mode / "metrics.csv")
                    if r["season"] == "all" and r["scenario"] in biases}
        for k, method in enumerate(methods):
            axis.bar([i+(k-1.5)*.19 for i in range(4)], [selected[bias, method] for bias in biases], width=.18, label=method)
        axis.set_xticks(range(4), [bias.replace(" C", " °C") for bias in biases])
        axis.set_title(mode)
        axis.set_ylim(0, 1.05)
        axis.set_ylabel("Daily ROC-AUC")
        axis.grid(axis="y", alpha=.2)
    axes.flat[0].legend(fontsize=8, loc="lower right")
    fig.suptitle("LBNL SD-AHU simulation · observed-day discrimination")
    fig.savefig(bundle / "bias-daily-auc.png", dpi=145)
    plt.close(fig)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--seed-root", type=Path)
    parser.add_argument("--figure", action="store_true")
    args = parser.parse_args()
    compare(args.bundle, args.seed_root)
    if args.figure:
        figure(args.bundle)
