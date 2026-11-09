"""Read-only qualification of CSIRO publisher intervals. No detectors or scores."""
import argparse
import hashlib
import json
import re
import sqlite3
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

SHA = {
    "csiro_ahu9.parquet": "d43028c46d6fadbed7f2deb749626f78be277573ead1e8b1abe8babd7515db6d",
    "csiro_ahu10.parquet": "f789b7efc5a0ec9857d5126137f727b94ad0895b63ff9b2170dd5651b26d3610",
    "csiro_fault_experiments.parquet": "b7ebad8a25baa8da7740186eb52a1eb62d0602c82dcc394ed0527ea5c6fd65f2",
}
LABELS = "csiro_fault_experiments.parquet"
CONTEXT = pd.Timedelta(minutes=30)
MIN_BLOCKS = 35
FAMILIES = {
    "CHW Valve Proxy Stuck Open": ("CHW_VALVE_OVERRIDE", "CHW valve command proxy", "ACTUATOR_COMMAND_OVERRIDE"),
    "HW Valve Proxy Stuck Open": ("HW_VALVE_OVERRIDE", "HW valve command proxy", "ACTUATOR_COMMAND_OVERRIDE"),
    "HW Valve Stuck Open": ("HW_VALVE_OVERRIDE", "HW valve command proxy", "ACTUATOR_COMMAND_OVERRIDE"),
    "OA Damper Stuck Open": ("OA_DAMPER_OVERRIDE", "OA damper command proxy", "ACTUATOR_COMMAND_OVERRIDE"),
    "RA Damper Stuck Open": ("RA_DAMPER_OVERRIDE", "RA damper command proxy", "ACTUATOR_COMMAND_OVERRIDE"),
    "SA Duct Leakage": ("SA_DUCT_LEAKAGE_SCENARIO", "Supply duct leakage simulation path", "IMPLEMENTATION_UNVERIFIED"),
    "SA Fan Belt Slip": ("SA_FAN_SLIP_SCENARIO", "Supply fan speed/offset path", "IMPLEMENTATION_UNVERIFIED"),
    "Zone Average Temp Drift": ("ZONE_AVG_TEMP_OVERRIDE", "Zone-average temperature input proxy", "SENSOR_INPUT_OVERRIDE"),
    "Zone Temp Drift": ("ZONE_TEMP_OVERRIDE", "Individual zone temperature input proxy", "SENSOR_INPUT_OVERRIDE"),
}
COMMON = ("OaTemp", "RaTemp", "SaTemp", "SaTempSP")
REFERENCE_STATUS = "UNKNOWN_UNANNOTATED"


def bounds(index, start, end):
    """Publisher join: [start, end) and exact source clock."""
    return index.searchsorted(start, side="left"), index.searchsorted(end, side="left")


def overlap(first, last, start, end):
    return first < end and start < last


def features(frame, ahu):
    # Raw context names only, with identity checked separately. No label join here.
    return frame.loc[:, [f"AHU{ahu}ahu{field}" for field in COMMON]]


def interval_profile(frame, start, end, cadence):
    lo, hi = bounds(frame.index, start, end)
    span = frame.iloc[lo:hi]
    if span.empty:
        return dict(rows=0, missing_cells=0, gap_steps=0, off_grid_steps=0, max_gap_s=None, first=None, last=None,
                    start_lag_s=None, end_lag_s=None, boundary_pass=False)
    ticks = span.index
    steps = ticks[1:] - ticks[:-1]
    return dict(rows=len(span), missing_cells=int((~np.isfinite(span.to_numpy())).sum()),
                gap_steps=int((steps > cadence).sum()),
                off_grid_steps=int((steps < cadence).sum()),
                max_gap_s=float(steps.max().total_seconds()) if len(steps) else None,
                first=str(ticks[0]), last=str(ticks[-1]),
                start_lag_s=(ticks[0]-start).total_seconds(), end_lag_s=(end-ticks[-1]).total_seconds(),
                boundary_pass=bool(ticks[0]-start <= cadence and end-ticks[-1] <= cadence))


def valid_telemetry(profile):
    return profile["boundary_pass"] and not (profile["missing_cells"] or profile["gap_steps"] or profile["off_grid_steps"])


def label_flags(fault_type, name, description, magnitude):
    text = f"{name or ''} {description or ''}"
    flags = []
    if fault_type not in FAMILIES or not name:
        flags.append("MISSING_OR_UNMAPPED_TAXONOMY")
    if pd.isna(magnitude) or magnitude == 0:
        flags.append("MISSING_OR_ZERO_MAGNITUDE")
    if re.search(r"undocumented|\?|\bthen\b|normal running between|unlock|locked at|allowed opening|"
                 r"Leak\.Sim|Fanspd ofs|Zone Temp OFS|with .*proxy", text, re.I):
        flags.append("MULTI_STAGE_OR_SECONDARY_CONTROL_MENTION")
    return flags


def clusters(rows):
    """Whole building days; merge across midnight and across overlapping context."""
    parent = {}

    def root(day):
        while day != parent[day]:
            day = parent[day]
        return day

    for item in rows:
        if not item["valid_interval"]:
            continue
        days = pd.date_range((item["start"]-CONTEXT).normalize(),
                             (item["end"]+CONTEXT-pd.Timedelta(microseconds=1)).normalize(), freq="D")
        first = days[0]
        for day in days:
            parent.setdefault(day, day)
            a, b = sorted((root(first), root(day)))
            parent[b] = a
    return {day: root(day).date().isoformat() for day in parent}


def point_lineage(ahu, frame):
    prefix = f"AHU{ahu}ahu"
    rows = []
    duplicate = frame[prefix+"MaTemp"].equals(frame[prefix+"SaTemp"])
    for point in frame.columns:
        key = point.removeprefix(prefix)
        if key in {"CcValve", "HcValve", "OaDamper", "RaDamper", "SaFanSpeed"}:
            role, use = "CONTROL_OR_PROXY_PATH_UNRESOLVED", "EXCLUDED_POTENTIAL_INJECTION_PATH"
        elif key.startswith(("ZoneTemp", "AvgZoneTemp")):
            role, use = "BMS_SENSOR_PROXY_POSSIBLE", "EXCLUDED_POTENTIAL_INJECTED_SENSOR"
        elif key == "MaTemp" and duplicate:
            role, use = "EXACT_SAT_DUPLICATE_IN_PUBLISHED_BYTES", "EXCLUDED_DUPLICATE"
        elif key == "SaTempSP":
            role, use = "BMS_SETPOINT", "CONTEXT_ONLY_UNTIL_PROVENANCE_VERIFIED"
        else:
            role, use = "BMS_TELEMETRY_POINT", "CONTEXT_ONLY_UNTIL_PROVENANCE_VERIFIED"
        rows.append(dict(ahu=ahu, native_point=point, role=role, use=use, units="NOT_VERIFIED_IN_PINNED_SCHEMA",
                         independent_feedback="UNKNOWN", source_sha256=SHA[f"csiro_ahu{ahu}.parquet"],
                         evidence="publisher README proxy architecture and native Parquet schema"))
    for missing in ("independent_travel", "independent_sat_reference", "verified_enable", "pre_override_demand"):
        rows.append(dict(ahu=ahu, native_point=missing, role="NO_VERIFIED_BINDING", use="UNAVAILABLE_FOR_GATE",
                         units="UNKNOWN", independent_feedback="UNKNOWN",
                         source_sha256=SHA[f"csiro_ahu{ahu}.parquet"], evidence="No documented mapping in public release"))
    for key in ("publisher_index", "start", "end", "magnitude", "proxy_type", "fault_type"):
        rows.append(dict(ahu=ahu, native_point=key, role="LABEL_METADATA", use="EXCLUDED_FROM_FEATURES",
                         units="SEE_PUBLISHER_LOG", independent_feedback="NOT_APPLICABLE",
                         source_sha256=SHA[LABELS], evidence="publisher intervention log; labels are separate from telemetry"))
    return rows


def verify_interval_join(data, ledger):
    """Cross-check per-row join cardinalities with the publisher's SQL inequalities."""
    with sqlite3.connect(":memory:") as connection:
        connection.execute("CREATE TABLE ticks (ahu INTEGER, stamp TEXT, PRIMARY KEY (ahu, stamp))")
        for ahu, frame in data.items():
            connection.executemany("INSERT INTO ticks VALUES (?, ?)",
                                   ((ahu, tick.isoformat(timespec="microseconds")) for tick in frame.index))
        for row in ledger:
            if not row["valid_interval"]:
                continue
            count, = connection.execute(
                "SELECT COUNT(*) FROM ticks WHERE ahu=? AND stamp>=? AND stamp<?",
                (row["ahu"], row["start"].isoformat(timespec="microseconds"),
                 row["end"].isoformat(timespec="microseconds")),
            ).fetchone()
            assert count == (row["during_rows"] or 0), row["publisher_index"]


def analyze(raw, output, reviewed):
    for name, expected in SHA.items():
        with (raw/name).open("rb") as stream:
            assert hashlib.file_digest(stream, "sha256").hexdigest() == expected, name
    published = pd.read_parquet(raw/LABELS)
    data = {ahu: pd.read_parquet(raw/f"csiro_ahu{ahu}.parquet") for ahu in (9, 10)}
    for frame in data.values():
        assert frame.index.tz is None and frame.index.is_unique and frame.index.is_monotonic_increasing
    cadence = {ahu: frame.index.to_series().diff().dropna().mode().iat[0] for ahu, frame in data.items()}
    raw_features = {ahu: features(frame, ahu) for ahu, frame in data.items()}
    points = [row for ahu, frame in data.items() for row in point_lineage(ahu, frame)]
    events = []
    for pos, (publisher_index, row) in enumerate(published.iterrows()):
        start, end = row["Start Datetime"], row["End Datetime"]
        fault_type, name, description = row["Fault Type"], row["Fault Name"], row["Fault Description"]
        family, injection, proxy = FAMILIES.get(fault_type, ("UNKNOWN", "UNKNOWN", "UNKNOWN"))
        events.append(dict(row_number=pos, publisher_index=publisher_index, ahu=int(row["AHU"]), family=family,
                           fault_type=fault_type, fault_name=name, fault_description=description,
                           injection_path_documented_family=injection, proxy_type=proxy,
                           start=start, end=end, duration_native=row["Duration (h:mm)"], magnitude_native=row["Magnitude"],
                           valid_interval=pd.notna(start) and pd.notna(end) and start < end,
                           flags=label_flags(fault_type, name, description, row["Magnitude"])))
    group = clusters(events)
    aliases = Counter((item["ahu"], item["start"], item["end"], item["family"]) for item in events)
    reviewed_blocks = {group.get(pd.Timestamp(day)) for day in reviewed}
    ledger = []
    for item in events:
        start, end, ahu = item["start"], item["end"], item["ahu"]
        valid = item["valid_interval"]
        peers = [other for other in events if other is not item and other["valid_interval"]
                 and valid and overlap(start-CONTEXT, end+CONTEXT, other["start"], other["end"])]
        same_overlap = [other["publisher_index"] for other in peers if other["ahu"] == ahu
                        and overlap(start, end, other["start"], other["end"])]
        cross_overlap = [other["publisher_index"] for other in peers if other["ahu"] != ahu
                         and overlap(start, end, other["start"], other["end"])]
        neighbor = [other["publisher_index"] for other in peers if not overlap(start, end, other["start"], other["end"])]
        block = group.get(start.normalize()) if valid else None
        known_reviewed = block is not None and block in reviewed_blocks
        supported = ahu in data
        profiles = {}
        if valid and supported:
            for name, left, right in (("pre", start-CONTEXT, start), ("during", start, end), ("post", end, end+CONTEXT)):
                profiles[name] = interval_profile(raw_features[ahu], left, right, cadence[ahu])
        complete_context = (interval_profile(raw_features[ahu], start-CONTEXT, end+CONTEXT, cadence[ahu])
                            if valid and supported else None)
        reasons = list(item["flags"])
        if not valid:
            reasons.append("INVALID_NATIVE_INTERVAL")
        if aliases[(ahu, start, end, item["family"])] > 1:
            reasons.append("DUPLICATE_INTERVAL_FAMILY_AHU")
        if not supported:
            reasons.append("NO_RELEASED_AHU_TELEMETRY")
        if same_overlap:
            reasons.append("OVERLAP_SAME_AHU")
        if cross_overlap:
            reasons.append("OVERLAP_OTHER_AHU_SITE_NOT_CLEARED")
        if neighbor:
            reasons.append("ADJACENT_INTERVENTION_WITHIN_WASHOUT")
        for name, profile in profiles.items():
            if not profile["boundary_pass"]:
                reasons.append(f"{name.upper()}_BOUNDARY_UNOBSERVED")
            if profile["gap_steps"]:
                reasons.append(f"{name.upper()}_TELEMETRY_GAP")
            if profile["off_grid_steps"]:
                reasons.append(f"{name.upper()}_TELEMETRY_OFF_GRID")
            if profile["missing_cells"]:
                reasons.append(f"{name.upper()}_INPUT_MISSING")
        if complete_context and any(
            complete_context[key] > sum(profile[key] for profile in profiles.values())
            for key in ("gap_steps", "off_grid_steps")
        ):
            reasons.append("TELEMETRY_GRID_BREAK_ACROSS_INTERVAL_BOUNDARY")
        structural_before_exposure = not reasons and all(valid_telemetry(p) for p in profiles.values())
        if known_reviewed:
            reasons.append("PREVIOUSLY_REVIEWED_BLOCK")
        structural_pass = structural_before_exposure and not known_reviewed
        reasons.extend(("NON_ORACLE_POINT_LINEAGE_UNVERIFIED", "REGIME_OR_EXCITATION_UNVERIFIED"))
        row = {key: value for key, value in item.items() if key != "flags"}
        row.update(label_source_sha256=SHA[LABELS], telemetry_sha256=SHA.get(f"csiro_ahu{ahu}.parquet"),
                   source_clock="NAIVE_SOURCE_LOCAL_UTC_OFFSET_UNVERIFIED",
                   duration_seconds=(end-start).total_seconds() if valid else None,
                   label_class="CONTROLLED_BMS_INTERVENTION_PRESENT" if valid and not item["flags"] else "AMBIGUOUS_PUBLISHER_ROW",
                   outside_interval=REFERENCE_STATUS, onset_clock="NOT_QUALIFIED_FOR_DELAY",
                   alignment_tolerance_seconds=cadence[ahu].total_seconds() if supported else None,
                   available_telemetry="|".join(data[ahu].columns) if supported else "",
                   same_ahu_overlap_ids="|".join(map(str,same_overlap)),
                   other_ahu_overlap_ids="|".join(map(str,cross_overlap)),
                   adjacent_ids="|".join(map(str,neighbor)),
                   campaign_day_block=block, previously_reviewed_block=known_reviewed,
                   structural_pass_before_exposure=structural_before_exposure,
                   structural_pass=structural_pass, qualified=False,
                   verified_reference=False, physical_feedback="UNKNOWN", physical_effect="NOT_IDENTIFIED",
                   native_proxy_point="NOT_PUBLISHED",
                   exclusions="|".join(reasons))
        for name in ("pre", "during", "post"):
            for key in ("rows", "missing_cells", "gap_steps", "off_grid_steps", "max_gap_s", "first", "last",
                        "start_lag_s", "end_lag_s", "boundary_pass"):
                row[f"{name}_{key}"] = profiles.get(name, {}).get(key)
        ledger.append(row)
    verify_interval_join(data, ledger)
    df = pd.DataFrame(ledger)
    output.mkdir(parents=True, exist_ok=True)
    df.to_csv(output/"EVENT_LABEL_LEDGER.csv", index=False)
    pd.DataFrame(points).to_csv(output/"SOURCE_POINT_LINEAGE.csv", index=False)
    matrix = []
    groups = list(df.groupby(["family", "ahu"]))
    groups += [((family, "SUPPORTED_COMBINED"), subset)
               for family, subset in df[df["ahu"].isin(data)].groupby("family")]
    for (family, ahu), subset in groups:
        nonoverlap = subset[subset["valid_interval"] & subset["same_ahu_overlap_ids"].eq("") &
                            subset["other_ahu_overlap_ids"].eq("") &
                            ~subset["exclusions"].str.contains("DUPLICATE_INTERVAL")]
        context_pass = subset[subset["structural_pass"]]
        before_exposure = subset[subset["structural_pass_before_exposure"]]
        matrix.append(dict(family=family, ahu=ahu, published_rows=len(subset),
                           with_native_samples=int(subset["during_rows"].fillna(0).gt(0).sum()),
                           distinct_nonoverlap_rows=len(nonoverlap),
                           distinct_nonoverlap_day_blocks=nonoverlap["campaign_day_block"].nunique(),
                           structural_blocks_before_exposure=before_exposure["campaign_day_block"].nunique(),
                           structural_pass_rows=len(context_pass), structural_pass_blocks=context_pass["campaign_day_block"].nunique(),
                           lineage_and_excitation="UNKNOWN", qualified_blocks=0, minimum_blocks=MIN_BLOCKS,
                           disposition="FAIL" if ahu == 15 else "STOP"))
    pd.DataFrame(matrix).to_csv(output/"ELIGIBILITY_MATRIX.csv", index=False)
    summary = {
        "verdict": "STOP_NO_QUALIFIED_INTERVENTION_FAMILY", "publisher_rows": len(ledger),
        "publisher_join_sql_parity": True,
        "raw_ahu_counts": {str(key): int(value) for key,value in df.groupby("ahu").size().items()},
        "modal_cadence_seconds": {str(key): value.total_seconds() for key,value in cadence.items()},
        "structural_pass_rows": int(df["structural_pass"].sum()),
        "structural_pass_blocks": int(df.loc[df["structural_pass"], "campaign_day_block"].nunique()),
        "max_structural_blocks_one_family": int(df[df["structural_pass"]].groupby("family")["campaign_day_block"].nunique().max())
            if df["structural_pass"].any() else 0,
        "reviewed_days": sorted(reviewed), "qualified_blocks": 0, "verified_reference_blocks": 0,
        "reasons": dict(sorted(Counter(reason for entry in df["exclusions"] for reason in entry.split("|")).items())),
        "source_sha256": SHA,
    }
    (output/"qualification.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("raw", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--reviewed-days", type=Path, required=True)
    args = parser.parse_args()
    analyzed_days = set(args.reviewed_days.read_text().splitlines())
    analyze(args.raw, args.output, analyzed_days)


if __name__ == "__main__":
    main()
