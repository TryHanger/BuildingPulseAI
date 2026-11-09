# BuildingPulse AI — independent review of BP-ML-FIELD-NATIVE-09

**Decision:** `ACCEPT_FIELD_REPLAY_EXPLORATORY_WITH_LIMITATIONS` as an **offline, descriptive observational replay of real BMS exports**. **NOT** acceptance of physical fan-fault diagnosis, ML field validation, production alerting, or a generalizable fault rate. Data-to-trace publisher extraction has not been independently reproduced in this audit because the compact submission omits raw Mendeley XLSX files.

## 1. Supplied material and integrity

- Received `BUILDINGPULSE_BP_ML_FIELD_NATIVE_09_REVIEW.zip` (50 ZIP entries, including `SHA256SUMS`); **49/49 listed SHA-256 hashes PASS**. No damage found.
- Frozen `FIELD_NATIVE_09_PROTOCOL.md` SHA-256 matches `868a685798c42c5a271149b64089aba8d72e0e8ed2d50a91900bfbe5587c5358` embedded in the runner and the freeze receipt.
- Stage08 event ledger SHA-256 matches `1d7acd72ff0ec71e1ae0fbd33c5b0b15e3f0f02942b91a74729e65d4ef4bd8fa` embedded in the runner.
- Source manifest identifies Mendeley V1 `10.17632/jkw85sm4v4.1`, six AHU XLSX, event schedule XLSX, tag diagram JPG, and the official 2021 manuscript with byte sizes, IDs and SHA-256. Acquisition log claims every source original checked, but original bytes were not included in Stage09 submission.
- Archive contains real offline reader, rules, replay scripts, adversarial tests, independent standard-library XLSX reference for five selected traces, source and storage protection receipts, HTTP parity receipts, deterministic output trace hashes.
- The `evidence/git-status.log` reports `not a git repository` for the provided runtime. Consequently this is not an independently verified git diff/commit-state audit; the Stage09 archive itself contains only research code, metadata and outputs, not a complete baseline application.

## 2. Independent numerical audit from submitted traces

Using **a separate standard-library implementation, without importing submitted replay/rules**, I re-derived all 12 cases from 240 trace rows (2 before + 18 in each window). I verified `384/384` per-window numerical/status fields, including direct state, paired state, baseline classification, change decisions, duration/sample-count accounting, first observed OFF, second confirming OFF, and relative timestamps. Native step 300 s was preserved; time-window rows are within half-open `[start,end)`. All 12 trace file SHA-256 identities match the event/control ledgers.

The 156 control screening decisions exactly reproduce the submitted categories: 54 exclusions for site intervention/adjacent day; 51 for unsuitable event precontext; 45 for unsuitable control precontext; **6 qualified matched windows** (AHU1/18/23 on +63 and +77 days). These selections were checked against the submitted screening table, **not** re-derived from the entire original 6×52,705-row workbook source.

| AHU | A: supply BAS-status change | B: warm-context paired-status change | Paired-status samples within 18 ticks |
|---|---|---|---|
| AHU1 | observed | observed | 17 `00`, 1 `11` |
| AHU2 | abstain: absent data | abstain | 18 missing pairs |
| AHU8 | abstain: absent data | abstain | 18 missing pairs |
| AHU18 | observed | observed | 17 `00`, 1 `11` |
| AHU23 | observed | no paired change | 17 `01`, 1 `11`: exhaust BAS continues to report on |
| AHU24 | observed | abstain as *new change*, missing qualified paired-on baseline | 17 `00`, 1 `10` |

For the four A changes, the first OFF report occurs +300 s from scheduled start; the second OFF sample is +600 s. These are **sample-relative** timestamps only, not verified onset instants of actual fan stops. In all six qualified controls both statuses report on at 18/18 samples, and neither rule observes an OFF transition. No reliable field false-positive rate or recall follows from these tiny, dependent and unverified-health denominators.

### Independent boundary and leakage scrutiny

- `rules.py` takes only four BAS signals: two `logic__real_value__fan_*` statuses and two `logic__required_value__heater/chiller` commands. The documented `signal__required_value__fan_*` command is not substituted for feedback. Fault/schedule annotations enter only after scoring in the evaluation layer. The submitted provenance of the `logic__real_value` bits is **not verified independent electrical or mechanical run proof**.
- AHU23 is an essential counterexample to pretending that reported supply and exhaust status are interchangeable. AHU24 is an essential counterexample to confusing state-within-window with new-transition evidence. AHU2/8 correctly abstain instead of counting as missed diagnoses.
- The paper notes faulty differential-pressure sensors at AHU23/24 during selected interventions. No independent fan-rotation/airflow measurement was shown for any selected interval. The publisher's Table 3 counts four interventions for its own Fault 12 experiment, whereas the released schedule contains six AHU time windows; these denominators must never be conflated.
- Unknown workbook timezone/offset and potential BAS overrides stay explicitly unknown. No claims of physical 5-minute continuity or exact physical response latency.
- The optional injected temperature plausibility experiment was correctly stopped because source point crosswalk and independently justified instrument limits were unavailable.

## 3. Tests and reproducibility limits

- The agent's `pytest.log` reports **180 passed**; replay parity log reports **17 byte-identical outputs**, and live HTTP parity/unchanged SQLite manifests are included.
- I independently executed the offline reference over all **submitted CSV traces**; it passed 49 file hashes and 384 outcome-field comparisons. The provided integrated `test_replay.py` **could not be collected directly from the compact archive** in this sandbox because it imports `backend.app.main`, and the complete backend is not included in Stage09. This is a packaging boundary, not established test failure in the actual working repository.
- The publisher's eight raw files and original 2021 PDF were not present. Stage09 scripts and logs assert their hashes and the independent `reference_check.py` claims XLSX-to-trace parity for five windows; I did not independently reproduce that original-file extraction. A second auditor with those originals should run the supplied reference and compare all 12 windows.

## 4. Scientific decision

**Accept:** auditably reproducible, self-limiting evidence about BAS-observed status transitions in selected *real-field BMS recordings*, with matched descriptive controls and meaningful abstentions. This is a legitimate product ingestion and engineer-evidence milestone.

**Do not accept:** a novel FDD algorithm, physically confirmed stopping of fans, 4/6 fault recall, 0% field false-positive rate, APAR replication, cross-building generalization, or validated field ML. All data are from one site; the selected intervention cases share one day, so treating four AHUs as four independent validation experiments would be misleading.

**Next:** `BP-ML-FIELD-EVIDENCE-10`, a read-only provenance-first engineer-facing research view of these frozen records, while explicitly preserving an independent physical-confirmation STOP. Avoid inventing further fault models or claiming ML transfer progress from this stage.

**Sources:** Publisher Mendeley `https://data.mendeley.com/datasets/jkw85sm4v4/1`; repository publication `https://dspace.cvut.cz/entities/publication/35d10945-7123-4cdc-8367-50bfdb4c1052`.
