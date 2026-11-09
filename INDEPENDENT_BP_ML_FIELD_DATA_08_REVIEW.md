# BuildingPulse AI — independent audit, BP-ML-FIELD-DATA-QUALIFICATION-08

**Verdict: `ACCEPT_SOURCE_QUALIFICATION_ONLY`; frozen 60-second Stage07 paths remain `STOP_NON_MINUTE_CADENCE`. Do not infer general impossibility of real-data FDD.**

## Independently checked in this session

1. Opened delivered ZIP (45 entries, approximately 111 KiB); archive CRC PASS and all **44/44** listed SHA-256 digests PASS.
2. Verified hashes of three Stage07 base files against the **previously accepted actual Stage07 overlay** in this working environment; all three match `BASE_FILES_SHA256`.
3. Applied delivered patch over the Stage07 overlay: clean application. All **9/9** resulting Stage08 overlay files match the delivered copies byte for byte. Compiled Python modules successfully.
4. Independently checked internal arithmetic and relationships of supplied **derived** ledgers: 6 AHUs × 52,705 rows = 316,230; 1,104 AHU-day records, six uniform 300-s timestamp grids, 118 schedule records containing 25 IDs, 2,735 scheduled 5-minute grid observations, 50 schedule/text disagreement records, 107 fault-label records at exact event end boundaries, zero independently verified healthy windows, no confirmed active SAT setpoint. The source has **one pilot building, not six independent buildings**.
5. Inspected API patch: only adds three explicit limitation flags to `ReducedSATResearchContract` and `ApplicabilityResult`, with inheritance. `inference_authorized`, `deployment_eligible`, `incident_eligible` remain false. No training/scoring implementation was added by Stage08.
6. Cross-checked publisher public Mendeley listing: six named AHU XLSX, one fault schedule XLSX, one legend image; publisher identifies BMS data with induced faults and CC BY 4.0. DOI `10.17632/jkw85sm4v4.1`. The corresponding original scientific paper DOI `10.1016/j.enbuild.2021.110781` confirms an APAR-derived method validated at a pilot installation, with ~90% detected author-defined cases.

**Limits on independence:** the eight original Mendeley files and the 1.8 MB university manuscript are NOT contained in this compact review ZIP; they were not independently re-downloaded and reparsed during this audit due to inaccessible source downloads from this runtime. SHA-256 of original publisher files, all original worksheet values, and the author's 97/48 pytest results are agent S's provided evidence, **not independently repeated source-byte verification**. The derived-ledger consistency checks do not replace raw-source validation. This is a conditional acceptance of source qualification, not a full independent rerun of ingestion.

## Key audit facts

| Check | Result | Consequence |
|---|---|---|
| Native cadence | Five minutes (300 seconds), 52,705 timestamps/AHU | Hard STOP for unchanged **60-second** Stage07 transfer protocols; do not fabricate minute samples by interpolation. |
| Required transfer features | MAT, OAT, active SAT setpoint absent or unqualified | Saved LBNL reduced SAT model cannot be used on this export with defensible semantic matching. |
| Telemetry extent | SAT reported for AHU1/18/23/24; absent completely for AHU2/8 | Per-AHU availability and refusal are mandatory. |
| AHU2 and AHU8 | Only two non-null non-metadata channels in each; both numerically identical on aligned grids | Signal independence/physical lineage unknown. No site diversity from duplicate telemetry. |
| Healthy ground truth | Publisher tag `no fault` exists; independently certified normal intervals **not provided** | Cannot claim general false-positive rate on objectively healthy operation. |
| Fault source | 118 schedule windows, 25 fault labels, discrepancies in some title/label pairs | 118 is not 118 independent faults or the **105** author-evaluated cases; keep annotation separate from runtime inputs. |
| Timestamp | Naive local timestamps; DST convention unverified | Preserve raw time + 300-s observed grid; no guessed timezone correction. |
| Fan state | BAS `real_value` logic not independently certified tachometer/contact | May report BAS status but not physically confirmed shutdown. |
| Stage08 product guard | Explicit self-attested metadata + 1D bounds limitation flags | Correct, but not proof of joint physical applicability. |

### Scientific and methodological judgment

- Source qualification **succeeded**: an original public, real-site BMS dataset was obtained and inventoried by S, with pinning/provenance and sensible restrictions. The legacy 60-s transfer experiment **failed eligibility**.
- `STOP_NON_MINUTE_CADENCE` is **not** a reason to discard this dataset. Five-minute native signals are entirely legitimate for a different, preregistered question with time-aware rules. The 1-minute protocol must stay frozen; do not loosen its thresholds retroactively.
- Do not report six independently replicated building outcomes: all six AHUs share the same site and sometimes the same intervention period. Preserve site/event grouping.
- Especially important: source labels can describe BAS/SCADA overrides, not independent physical faults. Numeric equality of channels does not prove duplicate sensors, and `real_value` names do not prove untampered sensors during an induced fault.
- The newly proposed fan-off study is feasible only as **BAS reported-state / observability** analysis unless wiring and physical fan run-proof is independently verified. It does not represent validated failure-cause identification or a novel FDD algorithm.

## Decision and next step

**`GO_NATIVE_5MIN_EXPLORATORY_REPLAY_09`, distinct from Stage07.** Implement a small, read-only, reproducible real-field replay at the original 300-s cadence for an objectively narrow question: do the **available** BAS channels provide adequate observability of scheduled fan-off interventions, and does the system abstain when channels are absent? Optionally include a separately qualified extreme-temperature sensor override as a data-quality control, not as main model success. Pre-register and freeze all channel-role mappings and comparator windows before examining new outcome values; document prior exposure and do not claim blinded confirmatory evaluation. No fitted ML, no retrofitting saved LBNL weights, no FDD automatic incidents, no deployment.

The work needs a real evidence trail: actual original XLSX + audit scripts, source SHA checks, event-level (not minute-independent) outcomes, negative/scheduled-off matched controls or explicit failure to find them, missingness/abstention, and a compact code+diff+manifest review ZIP. No raw multi-megabyte publisher files need be duplicated inside the submission; use pinned hashes and official download links.
