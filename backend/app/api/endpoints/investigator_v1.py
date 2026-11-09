from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response

from backend.app.services import g3_incidents, g4_investigation, g36_benchmark, g36_week, g36_week_benchmark, investigator_v1 as runtime

router = APIRouter(prefix="/v1", include_in_schema=False)
Panel = Literal["BASIC", "EXTRA"]
SOURCE_TIME = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$"


def local_time(value):
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        runtime.fail(422, "INVALID_SOURCE_TIME", "Use a valid source-local calendar timestamp")


@router.get("/datasets")
def datasets(demo: bool = False):
    return {"items": [runtime.demo_dataset()] if demo else runtime.datasets()}


@router.get("/datasets/{dataset_id}/signals")
def signals(dataset_id: str, panel: Panel = "BASIC"):
    _, frame = runtime.dataset_data(dataset_id)
    return {"items": runtime.signal_catalog(frame, panel)}


@router.get("/series")
def series(dataset_id: str, signal_ids: Annotated[list[str], Query(min_length=1, max_length=30)],
           panel: Panel = "BASIC", start: Annotated[str | None, Query(pattern=SOURCE_TIME)] = None,
           limit: Annotated[int, Query(ge=1, le=1440)] = 480):
    timestamp = local_time(start) if start else None
    source, frame = runtime.dataset_data(dataset_id, timestamp, limit)
    return {
        **runtime.series_window(frame, panel, list(dict.fromkeys(signal_ids)), timestamp, limit),
        "dataset_id": dataset_id, "source_sha256": source["sha256"], "result_origin": runtime.result_origin(source),
    }


@router.get("/modes")
def modes(request: Request, dataset_id: str, start: Annotated[str | None, Query(pattern=SOURCE_TIME)] = None,
          limit: Annotated[int, Query(ge=1, le=1440)] = 480):
    unknown = set(request.query_params) - {"dataset_id", "start", "limit"}
    if unknown:
        runtime.fail(422, "UNKNOWN_MODES_PARAMETER", ", ".join(sorted(unknown)))
    timestamp = local_time(start) if start else None
    source, frame = runtime.mode_input_window(dataset_id, timestamp, limit)
    return runtime.mode_segments(source, frame, timestamp, limit)


@router.get("/incidents")
def incidents(request: Request, dataset_id: str, start: Annotated[str | None, Query(pattern=SOURCE_TIME)] = None,
              limit: Annotated[int, Query(ge=1, le=1440)] = 480):
    unknown = set(request.query_params) - {"dataset_id", "start", "limit"}
    if unknown:
        runtime.fail(422, "UNKNOWN_INCIDENTS_PARAMETER", ", ".join(sorted(unknown)))
    return g3_incidents.incidents(dataset_id, local_time(start) if start else None, limit)


@router.get("/investigation")
def investigation(request: Request, dataset_id: str,
                  start: Annotated[str | None, Query(pattern=SOURCE_TIME)] = None,
                  limit: Annotated[int, Query(ge=1, le=1440)] = 480,
                  event_id: Annotated[str | None, Query(pattern=r"^[0-9a-f]{64}$")] = None,
                  format: Literal["json", "html"] = "json"):
    allowed = {"dataset_id", "start", "limit", "event_id", "format"}
    if set(request.query_params) - allowed or len(request.query_params.multi_items()) != len(request.query_params):
        runtime.fail(422, "UNKNOWN_INVESTIGATION_PARAMETER", "Use only documented, single-valued parameters")
    result = g4_investigation.with_run_hash(
        g4_investigation.investigate(dataset_id, local_time(start) if start else None, limit, event_id)
    )
    headers = {"X-Content-Type-Options": "nosniff"}
    if format == "html":
        headers["Content-Security-Policy"] = "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'"
        return HTMLResponse(g4_investigation.render_html(result), headers=headers)
    return Response(g4_investigation.canonical_json(result), media_type="application/json", headers=headers)


@router.get("/diagnostics")
def diagnostics(request: Request, dataset_id: str, at: Annotated[str, Query(pattern=SOURCE_TIME)], panel: Panel = "BASIC"):
    unknown = set(request.query_params) - {"dataset_id", "at", "panel"}
    if unknown:
        runtime.fail(422, "UNKNOWN_DIAGNOSTICS_PARAMETER", ", ".join(sorted(unknown)))
    timestamp = local_time(at)
    source, frame = runtime.mode_input_window(dataset_id, timestamp, 1)
    index = runtime.start_index(frame.index, timestamp)
    if index == len(frame) or frame.index[index] != timestamp:
        runtime.fail(404, "NO_SAMPLE", "No observation at the requested source timestamp")
    mode, = runtime.mode_contexts(frame, index, index + 1)
    previous = frame.index[index - 1] if index else None
    return runtime.evaluate_point(source, frame.iloc[index], at, panel, mode, previous)


@router.get("/g36-benchmark")
def g36_benchmark_window(request: Request, scenario: Literal["NOMINAL", "VALVE_CLOSED", "DAMPER_OPEN", "DUCT_LEAK"] = "VALVE_CLOSED",
                         panel: Literal["BASIC", "EXTRA_SIMULATED"] = "BASIC",
                         start: Annotated[int | None, Query(ge=0)] = None,
                         dataset: Literal["g36-5wk", "g36-1wk"] = "g36-5wk",
                         limit: Annotated[int, Query(ge=1, le=288)] = 145):
    if set(request.query_params) - {"scenario", "panel", "start", "limit", "dataset"} or len(
        request.query_params.multi_items()
    ) != len(request.query_params):
        runtime.fail(422, "UNKNOWN_G36_PARAMETER", "Use documented, single-valued parameters")
    if dataset == "g36-1wk":
        return g36_week_benchmark.benchmark(scenario, panel, g36_week.FIRST if start is None else start, limit)
    return g36_benchmark.benchmark(scenario, panel, g36_benchmark.START if start is None else start, limit)


@router.get("/g36-benchmark/comparison")
def g36_benchmark_comparison(request: Request):
    if request.query_params:
        runtime.fail(422, "UNKNOWN_G36_PARAMETER", "The frozen comparison takes no parameters")
    return g36_benchmark.comparison()


@router.get("/openapi.json")
def openapi_v1():
    path = runtime.settings.BASE_DIR / "contracts" / "openapi-v1.yaml"
    return JSONResponse(runtime.json.loads(path.read_text()))
