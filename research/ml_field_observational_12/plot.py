"""Draw native workbook samples and separate publisher annotations."""
import argparse
from collections import defaultdict
import csv
from datetime import datetime, time
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def read(path):
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def minute(value):
    native = datetime.fromisoformat(value)
    return (native - datetime.combine(native.date(), time(9))).total_seconds() / 60


def graph(artifacts):
    protocol = json.loads((artifacts / "FIELD_OBSERVATIONAL_12_PREREG.json").read_text())
    selection = json.loads((artifacts / "SELECTION_12.json").read_text())
    raw = defaultdict(list)
    annotation = defaultdict(list)
    for row in read(artifacts / "RAW_SLICE_12.csv"):
        raw[row["window_id"]].append(row)
    for row in read(artifacts / "PUBLISHER_ANNOTATIONS_12.csv"):
        annotation[row["window_id"]].append(row)
    choices = selection["selected"]
    if not choices:
        return
    names = {
        "event": "Scheduled intervention", "comparison": "Same-AHU comparison",
        **{f"negative_control_{i}": f"Negative control {i}" for i in range(1, 4)},
    }
    sat = protocol["sat"]
    before, behind, exhaust = protocol["secondary"]
    valve, pump, heat, cool, bypass = protocol["commands"]
    status = protocol["status"]
    fig, axes = plt.subplots(6, len(choices), squeeze=False, sharex=True, sharey="row",
                             figsize=(5.2 * len(choices) + 0.7, 10),
                             gridspec_kw={"height_ratios": (0.7, 1.4, 1.4, 1.15, 1.2, 1.5)})
    for index, (day, label) in enumerate(choices.items()):
        column = axes[:, index]
        rows = raw[label]
        x = [minute(row["Time"]) for row in rows]
        for ax in column:
            ax.axvspan(0, 120, color="#dfeaf2", zorder=0)
            ax.axvline(0, color="#536678", lw=0.8)
            ax.axvline(120, color="#536678", lw=0.8)
            ax.grid(axis="y", color="#e6e9eb", linewidth=0.7)
            ax.spines[["top", "right"]].set_visible(False)
            ax.set_xlim(-32, 151)
        column[0].set_title(f"{names[label]}\n{day}", fontsize=11, weight="bold")
        column[0].set_ylim(0, 1)
        column[0].set_yticks([])
        if label == "event":
            column[0].hlines(0.72, 0, 120, colors="#6554a1", linewidth=2)
            column[0].text(60, 0.81, "Publisher schedule [09:00, 11:00)", ha="center", fontsize=8)
        else:
            column[0].text(60, 0.76, "No intervention in the published schedule", ha="center", fontsize=8)
        marked = [minute(row["Time"]) for row in annotation[label]
                  if row["publisher_fault_evaluation_only"].casefold() not in ("", "no fault")]
        column[0].scatter(marked, [0.26] * len(marked), marker="|", color="#6554a1", s=37)
        column[0].text(60, 0.03, "Workbook labels: " + (f"{len(marked)} marked ticks" if marked else "no fault tags"),
                       ha="center", fontsize=8)
        for pos, phase in ((-15, "PRE"), (60, "[start, end)"), (135, "POST")):
            column[1].text(pos, 1.025, phase, transform=column[1].get_xaxis_transform(),
                           ha="center", fontsize=8, color="#394c5c")

        def series(ax, field, name, color):
            y = [float(row[field]) if row[field] else float("nan") for row in rows]
            ax.plot(x, y, "-o", lw=0.9, ms=2.6, color=color, label=name)

        series(column[1], sat, "SAT", "#146d9c")
        series(column[2], before, "heater_before", "#d27322")
        series(column[2], behind, "heater_behind", "#008678")
        series(column[3], exhaust, "Extract inlet", "#41674b")
        series(column[4], valve, "Valve request", "#9b3e70")
        series(column[4], bypass, "Bypass request", "#344b6d")
        for i, (field, color) in enumerate(((pump, "#813b74"), (heat, "#a75d12"),
                                           (cool, "#146d9c"), (status, "#41674b"))):
            y = [i + 0.37 * float(row[field]) if row[field] else float("nan") for row in rows]
            column[5].plot(x, y, "o", ms=2.2, color=color)
        column[5].set_yticks([0.18, 1.18, 2.18, 3.18], ["Pump req.", "Heat req.", "Cool req.", "Fan BAS"])
        column[5].set_ylim(-0.3, 3.65)
        for ax in (column[2], column[4]):
            ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.0), ncols=2, fontsize=7, frameon=False)
        column[5].set_xticks([-30, 0, 30, 60, 90, 120, 150],
                             ["08:30", "09:00", "09:30", "10:00", "10:30", "11:00", "11:30"])
        column[5].set_xlabel("Workbook clock · no UTC offset established")
    for ax, label in zip(axes[:, 0], ("Annotations", "SAT (°C)", "Liquid tags (°C)", "Extract inlet (°C)",
                                      "BAS commands (%)", "BAS bits\n0 low / 1 high")):
        ax.set_ylabel(label, fontsize=9)
    fig.suptitle("AHU1 · Reported BMS measurements and heating intervention", fontsize=15, weight="bold", y=0.985)
    fig.text(0.5, 0.017, "Native 300 s samples · blue band = analysis window in both columns · sensor independence unattested",
             ha="center", fontsize=9)
    fig.tight_layout(rect=(0.015, 0.035, 0.99, 0.96))
    (artifacts / "plots").mkdir(exist_ok=True)
    fig.savefig(artifacts / "plots/REPORTED_SAT_AND_COMMANDS_12.png", dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifacts", type=Path)
    graph(parser.parse_args().artifacts)
