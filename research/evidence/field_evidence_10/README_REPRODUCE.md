# Reproduce BuildingPulse Field Evidence 10

The base is the **accepted Stage09 application snapshot**. The review ZIP identifies its checked files in `evidence/application-before.sha256`. In the local session the verified snapshot was at `/tmp/bp-native09.ruXZ0h/app`. The desktop project directory was an older export without the Stage07 and G-series routes. It had no Git metadata. Implementation and execution used a separate copy of the accepted snapshot. Apply this package to that snapshot or an equivalent checkout. The Stage09 review ZIP alone contains research artifacts and does not contain the full application.

## Apply to a copy of the accepted snapshot

Set `DELIVERY` to the absolute path of this unpacked package. Run these commands at the root of a fresh copy of the accepted app.

```sh
sha256sum -c "$DELIVERY/evidence/accepted-base.sha256"
patch -p1 < "$DELIVERY/field-evidence-10.patch"
cp -R "$DELIVERY/overlay/." .
(cd "$DELIVERY/frozen-data" && sha256sum -c SHA256SUMS)
install -D "$DELIVERY/frozen-data/field_evidence_10.json" backend/app/research_data/field_evidence_10.json
```

The patch touches the research route wiring in three existing source files. The overlay adds the backend endpoint, frontend page, regression tests, audit tools and the standalone research OpenAPI contract. Frozen data live separately in `frozen-data/`. At runtime the service only uses the installed bundle. Its expected digest is pinned independently in source. On a missing or altered bundle the API responds with HTTP 503 and `SOURCE_PROVENANCE_UNVERIFIED`. The route accepts no parameters or writes.

## Run and verify

Install the accepted app's backend and test requirements and run `npm ci` in `frontend`. Use copies of the accepted SQLite and data directory for tests, with `DATABASE_URL` and `DATA_ROOT` pointing to the copies. Stage07 parity uses the existing LBNL fixture. For the configured virtual-sensor test and HTTP parity, set `VIRTUAL_SENSOR_RESEARCH_DIR` and `VIRTUAL_SENSOR_RESEARCH_MANIFEST_SHA256` to the accepted Stage02 research registry and its manifest SHA-256. The tested manifest digest was `359afbe1d3022e64c52ec5e1d916bb731a8c4c45aef9a835d0c9ab6ba73c0734`. These pre-existing artifacts are reused and are absent from this ZIP.

```sh
python -m pytest backend/tests research/ml_domain_shift_07/test_applicability.py research/ml_repro_02/test_research.py
npm --prefix frontend run build
python -m playwright install chromium
```

Run the updated app locally in two terminals.

```sh
python -m uvicorn backend.app.main:app --port 8050
npm --prefix frontend run dev -- --port 5180 --strictPort
```

Open `http://127.0.0.1:5180/research/field-evidence` or follow the research hub link. Set `STAGE09` to the accepted Stage09 review ZIP and `RAW_XLSX` to the directory of locally obtained V1 XLSX originals for the raw audit.

```sh
python research/ml_field_evidence_10/freeze.py "$STAGE09" /tmp/field-evidence-check.json
cmp /tmp/field-evidence-check.json backend/app/research_data/field_evidence_10.json
python research/ml_field_evidence_10/oracle.py "$STAGE09" --url http://127.0.0.1:8050/api/research/field-evidence --raw "$RAW_XLSX"
python research/ml_field_evidence_10/browser.py "$STAGE09" /tmp/field-evidence-screens
```

For HTTP parity, run the accepted and updated apps on ports 18059 and 18060 against separate SQLite copies and the same read-only fixtures and virtual-sensor registry.

```sh
python research/ml_field_evidence_10/http_parity.py http://127.0.0.1:18059 http://127.0.0.1:18060 /tmp/openapi-field-evidence-10.json
```

The independent oracle uses Python ZIP, XML and CSV parsing. It independently checks saved A/B summaries and workbook samples for audit only. Runtime does not import that code or run the replay. Tested dependency versions are recorded in `evidence/versions.log`. The frontend was built with the installed lockfile toolchain via direct TypeScript and Vite invocations. No originals, database or model binaries are included.

Publisher data are Nehasil et al. (2021), Mendeley Data V1, DOI 10.17632/jkw85sm4v4.1, CC BY 4.0. The bundle retains the frozen window data and provenance from Stage09 and adds relative workbook-clock offsets and presentation groupings. [Publisher dataset](https://data.mendeley.com/datasets/jkw85sm4v4/1).
