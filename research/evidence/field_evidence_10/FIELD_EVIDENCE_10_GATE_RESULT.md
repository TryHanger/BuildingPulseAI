# FIELD EVIDENCE 10 — PASS

**Gate** `ACCEPT_RESEARCH_EVIDENCE_UI_ONLY`

The read-only page `/research/field-evidence` exposes the frozen Stage09 observations from six AHUs at one site. It shows six scheduled intervention windows from one day and six selected controls. It distinguishes the workbook's 300-second samples from publisher schedule and fault metadata. The research API withholds all observations if the frozen bundle cannot be read or its SHA-256 differs from the pin in code.

| Intervention | A · supply BAS status | B · paired BAS status during a heating request |
| --- | --- | --- |
| AHU1, AHU18 | ON → OFF observed | ON → OFF observed |
| AHU23 | ON → OFF observed | No paired transition. Exhaust continues to report ON. |
| AHU24 | ON → OFF observed | ABSTAIN for a new transition. The two preceding samples do not establish a qualified paired-on baseline. |
| AHU2, AHU8 | ABSTAIN. Fan status is unavailable. | ABSTAIN. Paired statuses are unavailable. |

For the observed transitions, the first OFF sample is five minutes after the logged start and the second OFF sample is ten minutes after it. These times use the workbook clock. The six selected control windows show zero transitions. Independent health labels and a field false-positive rate are unavailable.

## Verification

| Check | Result |
| --- | --- |
| Accepted inputs and independent oracle | 49/49 Stage09 ZIP payload hashes. All fields of the 12 outcome records and 240 trace rows match the API. 384 outcome fields independently reproduced from the submitted traces. |
| Raw publisher cross-check | All six AHU XLSX hashes match publisher V1. A standard-library XLSX reader reproduced the workbook timestamps and four inputs for all 12 windows. The schedule workbook hash also matches. |
| Backend, strict frontend and Chromium | 279 pytest passes, including Stage07 and configured virtual-sensor tests. Strict TypeScript and Vite build passed. Chromium rendered all 12 previews with exact tick and rule fields. Five screenshots cover desktop 1440 px and mobile 390 px. |
| Existing HTTP and OpenAPI | Byte-identical Stage07 guard, configured virtual-sensor metadata and sampled day, sampled historical FDD response, ML model list and diagnostic OpenAPI. General OpenAPI adds one research GET and five schemas. |
| Storage | Publisher originals and the original SQLite files kept the same SHA-256. HTTP test copies also kept their initial SHA-256. |
| Docker | Compose configuration passed. Docker Engine did not respond over the local socket. Both `docker info` and `docker compose ps` timed out at 15 seconds (exit 124). Container runtime verification is outstanding. |

## Scientific boundary

The UI establishes selected **BAS-reported** states and archived Stage09 rule outcomes. It does not establish fan rotation, drive run proof, airflow, physical alarm severity, exact onset, causality, or independently healthy operation. The publisher's intervention could override BAS tags. The differential-pressure notes for AHU23 and AHU24 provide no independent pressure proof. This release supplies neither a field accuracy estimate nor production FDD authorization. It runs no inference and emits no incidents.
