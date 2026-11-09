"""Build an offline public stimulus set and a separate coordinator manifest."""
import argparse
import csv
from decimal import Decimal
import hashlib
from html import escape
import io
import json
from pathlib import Path
import re
import shutil
from zipfile import ZipFile

PROTOCOL = "2.0.0"
PANEL = "g61.1"
BASE = "2781f810c6c9fc6a38e31531ae1691d219a3987d9f71f480f56c84e390252cbf"
CHANNELS = (
    ("SAT", "K", "AHU Supply Air Temperature (°K)"),
    ("SAT SP", "K", "AHU Supply Air Temperature Setpoint (°K)"),
    ("MAT", "K", "AHU Mixed Air Temperature (°K)"),
    ("Fan", "0/1", "AHU Supply Air Fan Status (0: off, 1: on)"),
    ("Cooling cmd", "0–1", "Control Signal for AHU Cooling Coil Valve from BAS (fraction, 0: valve should be fully closed to 1: valve should be fully open)"),
    ("Heating cmd", "0–1", "Control Signal for AHU Heating Coil Valve (fraction, 0: valve should be fully closed to 1: valve should be fully open)"),
    ("OAT", "K", "AHU Outdoor Air Dry Bulb Temperature (°K)"),
    ("OWB", "K", "AHU Outdoor Air Wet Bulb Temperature (°K)"),
)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def json_bytes(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def read_csv(raw):
    return list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"), newline="")))


def render(common, detector, arm):
    payload = json_bytes({**common, "detector": detector}).replace("<", "\\u003c")
    c_context = """
    <aside aria-label="Контекст источника">
      <h2>Происхождение и виды свидетельств</h2>
      <p>Ряд получен из модели. Температуры относятся к её воздушному тракту.
        Команды контроллера и бинарный статус описывают разные виды записей.
        В показанном наборе нет отдельной записи физического состояния оборудования.</p>
      <p>Возможные виды проверки: независимое наблюдение состояния, повторное измерение температуры,
        проверка привязки и калибровки, сверка режима и времени.</p>
    </aside>""" if arm == "C" else ""
    return f"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'self'; script-src 'self'; connect-src 'none'; base-uri 'none'; form-action 'none'; img-src data:">
<link rel="icon" href="data:,">
<link rel="stylesheet" href="../study.css">
<script defer src="../study.js"></script>
<title>AHU · {escape(common['case_id'])}</title>
</head>
<body>
<main>
<header><h1>AHU · {escape(common['case_id'])}</h1><p>Технический просмотр материалов · сбор исследовательских ответов не открыт</p></header>
<div class="layout">
<section aria-label="Наблюдения">
<h2>Наблюдения до точки решения</h2>
<p>Ноль обозначает фокус. K — кельвин, команды — доля, Fan — двоичный статус. В таблице до трёх знаков после запятой.</p>
<label for="cursor">Курсор · модельные секунды</label>
<input id="cursor" type="range" min="-600" max="0" step="{common['step_seconds']}" value="0">
<output id="cursor-value" for="cursor">0</output>
<div class="table-wrap" role="region" aria-label="Таблица наблюдений" tabindex="0"><table id="signals"></table></div>
</section>
<div class="interpretation">
<section aria-label="Состояние на фокусе"><h2>Оценка на фокусе</h2><dl id="decision"></dl></section>
{c_context}
</div>
</div>
<form id="response">
<h2>Ответ</h2>
<p>Опишите ваше решение без имён и контактных данных. Время на задачу: <output id="timer">180</output> с.</p>
<div class="answers">
<label>Допустимость оценки<textarea name="eligibility" required maxlength="1500"></textarea></label>
<label>Статус симптома во времени<textarea name="temporal" required maxlength="1500"></textarea></label>
<label>Граница вывода о причине и обоснование<textarea name="cause_limit" required maxlength="1500"></textarea></label>
<label>Следующая проверка и какое свидетельство она даст<textarea name="action_evidence" required maxlength="1500"></textarea></label>
</div>
<button type="submit">Зафиксировать ответ</button>
<button type="button" id="download" disabled>Скачать обезличенный JSON</button>
<p id="response-state" role="status"></p>
</form>
</main>
<script id="study-data" type="application/json">{payload}</script>
</body></html>
"""


def build(data_root, original, matrix, public, private):
    policy_path = Path(__file__).resolve().parents[2] / "backend/app/services/g36_policy.py"
    policy_hash = digest(policy_path.read_bytes())
    accepted = original / "BUILDINGPULSE_G5_7_GATE_REVIEW.zip"
    if digest(accepted.read_bytes()) != BASE:
        raise ValueError("G5.7 archive SHA mismatch")
    with matrix.open(encoding="utf-8", newline="") as stream:
        tasks = [row for row in csv.DictReader(stream) if row["cohort"] == "CORE_G36"]
    if len(tasks) != 6 or len({row["source_sha256"] for row in tasks}) != 6:
        raise ValueError("Expected six distinct registered simulation runs")
    public.mkdir(parents=True, exist_ok=False)
    private.mkdir(parents=True, exist_ok=True)
    receipts = {}
    with ZipFile(accepted) as archive:
        manifest = json.loads(archive.read("MANIFEST.json"))
        if manifest["preserved_sha256"]["backend/app/services/g36_policy.py"] != policy_hash:
            raise ValueError("Frozen policy mismatch")
        sources = {row["member_sha256"]: member for member, row in manifest["g36_source_members"].items()}
        sums = {name: sha for sha, name in (line.split("  ", 1) for line in archive.read("SHA256SUMS.txt").decode().splitlines())}
        for task in tasks:
            case, profile = task["task_id"], task["source_profile"]
            source_sha = task["source_sha256"]
            member = sources[source_sha]
            raw = (data_root / f"g36-{profile}" / Path(member).name).read_bytes()
            if digest(raw) != source_sha:
                raise ValueError(f"{case} source SHA mismatch")
            trace_name = task["replay_reference"].split("::")[1]
            trace_bytes = archive.read(trace_name)
            if digest(trace_bytes) != sums[trace_name]:
                raise ValueError(f"{case} trace SHA mismatch")
            start, end, focus = map(int, re.findall(r"\d+", task["native_bounds_and_focus"]))
            if end != focus or focus - start != 600:
                raise ValueError(f"{case} window mismatch")
            step = {"1wk": 60, "5wk": 300}[profile]
            clock = list(range(start, focus + 1, step))
            source = {int(Decimal(row["time (s)"])): row for row in read_csv(raw) if start <= int(Decimal(row["time (s)"])) <= focus}
            trace = {int(row["time_s"]): row for row in read_csv(trace_bytes) if start <= int(row["time_s"]) <= focus}
            if list(source) != clock or list(trace) != clock:
                raise ValueError(f"{case} input grid mismatch")
            points = [[time - focus, *(float(source[time][header]) for _, _, header in CHANNELS)] for time in clock]
            status = trace[focus]
            eligible = status["basic_reason"] == "APPLICABLE"
            flag = status["basic_point_exceeds"] == "True"
            instant = "NOT_EVALUATED" if not eligible else "EXCEEDS" if flag else "NO_ALARM"
            decision = {
                "instant": instant, "applicability": status["basic_reason"],
                "rule": "g36-sat-high@1.0.0 · >2 K · 600 s",
                "temporal": "NOT_EVALUATED" if not eligible else
                    "CONFIRMED" if status["basic_confirmed_timeline"] == "True" else "NOT_CONFIRMED",
                "total_ticks": len(clock),
                "evaluated_ticks": sum(trace[time]["basic_reason"] == "APPLICABLE" for time in clock),
                "missing_ticks": 0,
            }
            common = {
                "protocol": PROTOCOL, "panel_version": PANEL, "case_id": case,
                "window_seconds": [-600, 0], "focus_seconds": 0, "step_seconds": step,
                "channels": [[name, unit] for name, unit, _ in CHANNELS], "points": points,
            }
            (private / f"{case}-decision.json").write_text(json_bytes(decision) + "\n", encoding="utf-8")
            receipts[case] = {
                "source_member": member, "source_sha256": source_sha, "trace": trace_name,
                "trace_sha256": sums[trace_name], "profile": profile, "native_window": [start, focus],
                "model_sha256": None, "model_identity": "Publisher Modelica model; exact executable unavailable; no model executed",
                "policy_sha256": policy_hash, "decision_sha256": digest(json_bytes(decision).encode()),
                "fields": list(common), "conditions": {},
            }
            for arm in "ABC":
                view = {"instant": instant} if arm == "A" else decision
                presentation_id = digest(f"buildingpulse-study:{PANEL}:{case}:{arm}".encode())[:20]
                path = f"cards/{presentation_id}.html"
                (public / "cards").mkdir(exist_ok=True)
                page = render({**common, "presentation_id": presentation_id}, view, arm).encode()
                (public / path).write_bytes(page)
                receipts[case]["conditions"][arm] = {
                    "route": f"/{path}", "presentation_id": presentation_id,
                    "html_sha256": digest(page), "presented_decision_fields": list(view),
                    "additional": "GENERIC_PROVENANCE_CONTEXT" if arm == "C" else None,
                }
    for name in ("study.css", "study.js"):
        shutil.copyfile(Path(__file__).with_name(name), public / name)
    (private / "STUDY_BUILD.json").write_text(json.dumps({
        "protocol": PROTOCOL, "panel_version": PANEL, "accepted_archive_sha256": BASE,
        "assignment_seed": "Coordinator records separately before enrollment; none used for build",
        "collection": "REVIEW_ONLY", "cases": receipts,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("data_root", "original", "matrix", "public", "private"):
        parser.add_argument(name, type=Path)
    build(**vars(parser.parse_args()))
