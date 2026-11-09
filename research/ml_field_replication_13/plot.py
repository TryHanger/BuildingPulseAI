"""Native samples, commands and separately labeled publication metadata."""
import argparse
from collections import defaultdict
import csv
from datetime import datetime, timedelta
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def table(path):
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def charts(data):
    protocol = json.loads((data / "FIELD_REPLICATION_13_PREREG.json").read_text())
    traces, annotations = defaultdict(list), defaultdict(list)
    for row in table(data / "RAW_SLICE_13.csv"):
        traces[row["window_id"]].append(row)
    for row in table(data / "PUBLISHER_ANNOTATIONS_13.csv"):
        annotations[row["window_id"]].append(row)
    sat = protocol["sat"]
    before, behind, exhaust = protocol["secondary"]
    valve, pump, heat, cool, bypass = protocol["commands"]
    status = protocol["status"]
    (data / "plots").mkdir(exist_ok=True)
    for episode in table(data / "EPISODE_LEDGER_13.csv"):
        if episode["analysis_status"] != "QUALIFIED":
            continue
        n = episode["schedule_row"]
        duration = int(episode["duration_minutes"])
        keys = [key for key in (f"row{n}_event", f"row{n}_comparison") if key in traces]
        fig, axes = plt.subplots(6, len(keys), squeeze=False, sharex=True, sharey="row",
                                 figsize=(5.3 * len(keys) + 0.7, 9.4),
                                 gridspec_kw={"height_ratios": (0.68, 1.25, 1.3, 1.08, 1.1, 1.25)})
        for index, key in enumerate(keys):
            points = traces[key]
            column = axes[:, index]
            start = datetime.fromisoformat(next(p["Time"] for p in points if p["partition"] == "WINDOW"))
            event = key.endswith("_event")

            def minute(row):
                return (datetime.fromisoformat(row["Time"]) - start).total_seconds() / 60

            x = [minute(row) for row in points]
            for ax in column:
                ax.axvspan(0, duration, color="#dfeaf2", zorder=0)
                for border in (0, duration):
                    ax.axvline(border, color="#617488", lw=0.7)
                ax.set_xlim(-32, duration + 31)
                ax.spines[["top", "right"]].set_visible(False)
                ax.grid(axis="y", color="#e8ecef", linewidth=0.7)
            column[0].set_title(f"{'Scheduled intervention' if event else 'Same-AHU comparison'} · {start.date()}",
                                fontsize=11, weight="bold")
            column[0].set_ylim(0, 1)
            column[0].set_yticks([])
            column[0].text(duration / 2, 0.78, "Publisher schedule" if event else "No scheduled intervention",
                           ha="center", fontsize=8)
            if event:
                column[0].hlines(0.7, 0, duration, color="#6a4c93", lw=2)
            labels = [minute(row) for row in annotations[key]
                      if row["publisher_fault_evaluation_only"].casefold() not in ("", "no fault")]
            column[0].scatter(labels, [0.3] * len(labels), marker="|", color="#6a4c93", s=32)
            column[0].text(duration / 2, 0.02, f"Workbook fault labels · {len(labels)} marked ticks",
                           ha="center", fontsize=8)
            for x0, name in ((-15, "PRE"), (duration / 2, "[start, end)"), (duration + 15, "POST")):
                column[1].text(x0, 1.02, name, transform=column[1].get_xaxis_transform(),
                               ha="center", fontsize=8, color="#43596c")

            def series(ax, field, name, color):
                ax.plot(x, [float(row[field]) if row[field] else float("nan") for row in points],
                        "-o", lw=0.85, ms=2.4, color=color, label=name)

            series(column[1], sat, "SAT", "#146d9c")
            series(column[2], before, "heater_before", "#a85612")
            series(column[2], behind, "heater_behind", "#008071")
            series(column[3], exhaust, "Extract inlet", "#41674b")
            series(column[4], valve, "Valve request", "#9b3e70")
            series(column[4], bypass, "Bypass request", "#344b6d")
            for i, (field, color) in enumerate(((pump, "#813b74"), (heat, "#a75d12"),
                                               (cool, "#146d9c"), (status, "#41674b"))):
                y = [i + 0.4 * float(row[field]) if row[field] else float("nan") for row in points]
                column[5].plot(x, y, "o", ms=2.4, color=color)
            column[5].set_yticks([0.2, 1.2, 2.2, 3.2], ["Pump req.", "Heat req.", "Cool req.", "Fan BAS"])
            column[5].set_ylim(-0.3, 3.7)
            for ax in (column[2], column[4]):
                ax.legend(loc="lower center", bbox_to_anchor=(0.5, 0.98), ncols=2, fontsize=7, frameon=False)
            marks = list(range(-30, duration + 31, 30 if duration == 120 else 15))
            column[5].set_xticks(marks, [(start + timedelta(minutes=m)).strftime("%H:%M") for m in marks])
            column[5].set_xlabel("Naive workbook clock · UTC offset unknown")
        for ax, label in zip(axes[:, 0], ("Annotations", "SAT (°C)", "Liquid tags (°C)", "Extract inlet (°C)",
                                          "BAS commands (%)", "BAS bits\n0 low / 1 high")):
            ax.set_ylabel(label, fontsize=9)
        fig.suptitle(f"{episode['ahu']} · {episode['fault']} · schedule row {n} · {duration} min",
                     fontsize=14, weight="bold", y=0.984)
        fig.text(0.5, 0.018, "Native 300 s samples · blue band = analysis window · sensor independence unattested",
                 ha="center", fontsize=9)
        fig.tight_layout(rect=(0.012, 0.037, 0.99, 0.96))
        fig.savefig(data / "plots" / f"ROW_{n}_{episode['ahu']}.png", dpi=125)
        plt.close(fig)
        print(f"PASS figure row {n}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifacts", type=Path)
    charts(parser.parse_args().artifacts)
