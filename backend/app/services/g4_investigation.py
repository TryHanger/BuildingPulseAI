"""Read-only engineering investigation and deterministic report rendering."""
import hashlib
import json
from datetime import datetime
from html import escape

from backend.app.services import g3_incidents, investigator_v1 as runtime
from backend.app.services.g3_symptom import ROLES, SOURCE_KINDS

FORMULA = "MA_TEMP < min(OA_TEMP, RA_TEMP) − lower_margin_deg_f"
LIMITATIONS = [
    "Zero confirmed symptoms does not establish zero faults.",
    "Confirmation means the temporal condition held. The mechanical cause requires external evidence.",
    "The temperature thresholds are engineering policy. SD-AHU sensor accuracy and airflow are unverified.",
    "Source-local timestamps have no validated UTC offset. The benchmark is a simulation.",
]
SAFETY_CATALOG = {
    "REVIEW_SOURCE_QUALITY": "Review excluded observations, time gaps and input provenance before interpreting coverage.",
    "REVIEW_INSTRUMENTATION": "Review sensor placement, calibration records and independent measurements with site personnel.",
}
STATUS = {
    "DETECTED_SYMPTOM": "CONFIRMED_SYMPTOM",
    "NO_SYMPTOMS_ON_EVALUATED_WINDOWS": "NOT_DETECTED",
    "NOT_EVALUABLE": "NOT_EVALUABLE",
}


def canonical_json(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def group_event(event):
    grouped = {key: [] for key in ROLES}
    for record in event["raw_lineage"]:
        grouped[record["canonical_id"]].append(record)
    return {
        **{key: value for key, value in event.items() if key not in {"raw_lineage", "cause_status"}},
        "cause_state": "AMBIGUOUS",
        "sensor_root_count": len(grouped),
        "observation_count": len(event["raw_lineage"]),
        "raw_lineage": [
            {"canonical_id": key, "kind": SOURCE_KINDS[key], "role": ROLES[key], "observations": observations}
            for key, observations in grouped.items()
        ],
        "derived_fact": {"code": "LOWER_ENVELOPE_TEMPORALLY_CONFIRMED", "depends_on": list(grouped)},
    }


def investigate(dataset_id, start, limit, event_id):
    source, frame = runtime.mode_input_window(dataset_id, start, limit, require_index=True)
    indexed, index_sha = g3_incidents.registered_record(dataset_id, source)
    window = g3_incidents.incident_window(dataset_id, source, frame, start, limit, indexed)
    timing = runtime.mode_segments(source, frame, start, limit)
    is_demo = dataset_id == runtime.DEMO_ID
    coverage = window["coverage"]
    events = [group_event(event) for event in window["events"] if event["last_seen"] >= window["first"]]
    # An episode counts only once it is confirmed by the window cutoff.
    # G3 episodes are disjoint, minute-contiguous and contain only violations.
    confirmed_samples = sum(
        int((datetime.fromisoformat(event["last_seen"]) -
             datetime.fromisoformat(max(window["first"], event["first_observed"]))).total_seconds()
            // runtime.SAMPLE_SECONDS) + 1
        for event in events
    )
    unconfirmed_samples = coverage["violated"] - confirmed_samples
    if unconfirmed_samples < 0:
        runtime.fail(409, "INCIDENT_INDEX_INTEGRITY", "Confirmed intervals exceed observed violations")
    confirmation_state = "CONFIRMED" if events else "NO_VIOLATIONS" if coverage["evaluated"] else "NOT_EVALUABLE"
    if unconfirmed_samples:
        last = runtime.start_index(frame.index, datetime.fromisoformat(window["last"]))
        _, terminal = next(g3_incidents.window_evaluations(frame, last, last + 1, runtime.SIGNALS))
        terminal_confirmed = any(event["last_seen"] == window["last"] for event in events)
        confirmation_state = "PENDING" if terminal.predicate == "VIOLATED" and not terminal_confirmed else "UNCONFIRMED"
    if event_id:
        events = [event for event in events if event["event_id"] == event_id]
        if not events:
            runtime.fail(404, "INCIDENT_NOT_IN_WINDOW", "No confirmed episode with that ID at the source window")
    status = ("DETECTED_SYMPTOM" if events else "NO_SYMPTOMS_ON_EVALUATED_WINDOWS"
              if coverage["evaluated"] else "NOT_EVALUABLE")
    counts = indexed["coverage"]
    full_coverage = {
        "samples": sum(counts.values()),
        "evaluated": counts.get("NOT_VIOLATED", 0) + counts.get("VIOLATED", 0),
        "not_evaluable": counts.get("NOT_EVALUABLE", 0),
        "violated": counts.get("VIOLATED", 0),
    }
    if full_coverage["samples"] != source["rows"]:
        runtime.fail(409, "INCIDENT_INDEX_INTEGRITY", "The offline coverage differs from the registered row count")
    dataset = runtime.demo_dataset(source) if is_demo else {
        "name": source["archive_member"].rsplit("/", 1)[-1],
        "equipment_id": g3_incidents.EQUIPMENT_ID,
        "source_member": source["archive_member"],
        "release_id": runtime.MANIFEST["release_id"],
    }
    return {
        **window,
        "report_version": "1.2.0",
        "confirmation_state": confirmation_state,
        "unconfirmed_violated_samples": unconfirmed_samples,
        "index_sha256": index_sha,
        "dataset_name": dataset["name"],
        "equipment_id": dataset["equipment_id"],
        "source_member": dataset["source_member"],
        "release_id": dataset["release_id"],
        "provenance": "DEMO_FIXTURE" if is_demo else "SIMULATED_BENCHMARK",
        "signal_profile": "BASIC",
        "analysis_scope": {
            "kind": "SOURCE_WINDOW",
            "requested_start": start.isoformat() if start else None,
            "limit": limit,
            "event_id": event_id,
        },
        "status": status,
        "evidence_status": STATUS[status],
        "cause_state": "AMBIGUOUS" if events else "NOT_ASSESSED",
        "events": events,
        "formula": FORMULA,
        "source_coverage": full_coverage,
        "source_confirmed_episodes": len(indexed["episodes"]),
        "inputs": [
            {**item, "kind": SOURCE_KINDS[item["canonical_id"]],
             "available": item["canonical_id"] in frame}
            for item in window["rule"]["required_channel_roles"]
        ],
        "mode_policy": timing["mode_policy"],
        "mode_segments": timing["segments"],
        "time_quality": timing["time_quality"],
        "limitations": LIMITATIONS,
        "recommendations": [
            {"code": code, "text": SAFETY_CATALOG[code]}
            for code in (SAFETY_CATALOG if events else ["REVIEW_SOURCE_QUALITY"])
        ],
        "analysis_journal": [
            {"step": "VERIFY_SOURCE_AND_OFFLINE_INDEX", "result": window["result_origin"]},
            {"step": "CHECK_MODE_QUALITY_AND_APPLICABILITY", "result": f"{coverage['evaluated']}/{coverage['samples']}"},
            {"step": "CHECK_TEMPORAL_SYMPTOM", "result": status},
            {"step": "ASSESS_CAUSAL_SCOPE", "result": "AMBIGUOUS" if events else "NOT_ASSESSED"},
        ],
    }


def with_run_hash(investigation):
    return {**investigation, "run_sha256": hashlib.sha256(canonical_json(investigation)).hexdigest()}


def render_html(report):
    def value(item):
        return escape("—" if item is None else str(item), quote=True)

    def table(headers, rows):
        head = "".join(f"<th>{value(item)}</th>" for item in headers)
        body = "".join("<tr>" + "".join(f"<td>{value(item)}</td>" for item in row) + "</tr>" for row in rows)
        return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"

    def items(rows):
        return "<ul>" + "".join(f"<li>{value(row)}</li>" for row in rows) + "</ul>"

    rule = report["rule"]
    coverage = report["coverage"]
    full = report["source_coverage"]
    sections = [
        "<h1>BuildingPulse engineering investigation</h1>",
        items([
            f"{report['provenance']} · {report['result_origin']} · {report['dataset_name']}",
            f"Dataset {report['dataset_id']} · Equipment {report['equipment_id']} · {report['signal_profile']}",
            f"Source member {report['source_member']} · Release {report['release_id']}",
            f"Source SHA-256 {report['source_sha256']}", f"Offline index SHA-256 {report['index_sha256']}",
            f"Run SHA-256 {report['run_sha256']}",
            f"{report['clock_kind']} · {report['first']} → {report['last']}",
            f"Requested start {report['analysis_scope']['requested_start']} · Limit {report['analysis_scope']['limit']}",
            f"{report['status']} · {report['evidence_status']} · {report['cause_state']}",
            f"Window confirmation state: {report['confirmation_state']}",
            *(["The window ends during an unconfirmed violation. Later samples can change confirmation."]
               if report["confirmation_state"] == "PENDING" else []),
        ]),
        "<h2>Rule and coverage</h2>",
        items([
            f"{rule['method_id']} v{rule['model_or_rule_version']} · {report['rule_fingerprint']}",
            f"{report['formula']} · margin {rule['lower_margin_deg_f']} °F",
            f"Minimum inlet separation {rule['min_inlet_separation_deg_f']} °F · fan command > "
            f"{rule['min_fan_command_exclusive']} · RUNNING hold {report['mode_policy']['hold_seconds']} s",
            f"Confirmation {rule['confirmation_duration_seconds']} s · {rule['sensor_quality_scope']}",
            f"Evaluated {coverage['evaluated']} of {coverage['samples']} · Not evaluated {coverage['not_evaluable']}"
            f" · Violated samples {coverage['violated']} · Unconfirmed violated samples {report['unconfirmed_violated_samples']}"
            f" · Confirmed episodes {len(report['events'])}",
            f"Whole registered source (offline index): evaluated {full['evaluated']} of {full['samples']} "
            f"· not evaluated {full['not_evaluable']} · confirmed episodes {report['source_confirmed_episodes']}",
        ]),
        table(["Input", "Role", "Kind", "Native unit", "Available"], [
            (item["canonical_id"], item["role"], item["kind"], item["unit"], item["available"])
            for item in report["inputs"]
        ]),
        "<h2>Mode and time quality</h2>",
        items(f"{key}: {count}" for key, count in report["time_quality"].items()),
        table(["Mode", "First", "Last", "Samples", "Gap before"], [
            (item["mode"], item["first"], item["last"], item["samples"], item["gap_before"])
            for item in report["mode_segments"]
        ]),
        "<h2>Reasons for abstention and checks outside scope</h2>",
        items(f"{reason}: {count}" for reason, count in report["not_evaluable_reasons"].items()),
        items(report["inapplicable_checks"]),
    ]
    for event in report["events"]:
        sections += [
            "<h2>Confirmed temporal symptom</h2>",
            items([
                f"{event['kind']} · {event['event_id']}",
                f"First {event['first_observed']} · Confirmed {event['confirmed_at']} · Last in scope {event['last_seen']}",
                f"Boundary {event['gap_reason']} · {event['sensor_root_count']} distinct input channels "
                f"· {event['observation_count']} timestamped records · one dependent fact",
                event["derived_fact"]["code"],
            ]),
            table(["Source time", "Column", "Raw value", "Unit"], [
                (record["timestamp"], record["source_column"], record["value"], record["unit"])
                for root in event["raw_lineage"] for record in root["observations"]
            ]),
            "<h3>Possible explanations</h3>", items(event["possible_causes"]),
        ]
    sections += [
        "<h2>Analysis journal</h2>",
        table(["Step", "Result"], [(row["step"], row["result"]) for row in report["analysis_journal"]]),
        "<h2>Limitations</h2>", items(report["limitations"]),
        "<h2>Safety catalogue</h2>", items(row["text"] for row in report["recommendations"]),
    ]
    return """<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>BuildingPulse investigation</title>
<style>
body{max-width:70rem;margin:2rem auto;padding:0 1rem;font:16px system-ui;overflow-wrap:anywhere}
table{width:100%;border-collapse:collapse;table-layout:fixed}
th,td{border:1px solid #bec8cf;padding:.35rem;text-align:left}th{background:#edf2f5}
</style>
<body>""" + "\n".join(sections) + "</body></html>\n"
