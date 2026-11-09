# BP-ML-FIELD-NATIVE-09

**ACCEPT_FIELD_REPLAY_EXPLORATORY.** The recorded BAS points support a reproducible observability replay on the native 300-second grid. Physical fan state remains **UNKNOWN_PHYSICAL_LINEAGE**.

**REAL_BMS_REPORTED · INJECTED_INTERVENTION_IN_LOG · NOT_PHYSICAL_PROOF · SOURCE_5_MIN · NO_INDEPENDENT_HEALTHY_GROUND_TRUTH**

All eight Nehasil V1 files passed publisher size and SHA-256 checks. The CTU manuscript and the native tag diagram also passed their pinned digests. Six AHUs at one site each have 52,705 strictly increasing 300-second ticks from 2019-03-01 00:00 through 2019-08-31 00:00. Offset and DST conventions are unknown. Analysis uses the naive workbook clock without UTC alignment. [Mendeley V1](https://data.mendeley.com/datasets/jkw85sm4v4/1) · [CTU manuscript](https://dspace.cvut.cz/entities/publication/35d10945-7123-4cdc-8367-50bfdb4c1052)

## Six scheduled windows

Each window is 90 scheduled minutes on 2019-03-01 and contains 18 original ticks under the half-open rule. Pair codes are supply/exhaust. A uses supply status alone. B requires both statuses in heating-on/cooling-off request context and a qualified baseline for change.

| AHU | Both statuses | 00 / 01 / 10 / 11 | A change | B change | Interpretation |
|---|---:|---|---|---|---|
| AHU1 | 18/18 | 17 / 0 / 0 / 1 | Observed | Observed | Two consecutive applicable paired-off ticks |
| AHU2 | 0/18 | 0 / 0 / 0 / 0 | Abstain | Abstain | Both BAS statuses missing |
| AHU8 | 0/18 | 0 / 0 / 0 / 0 | Abstain | Abstain | Both BAS statuses missing |
| AHU18 | 18/18 | 17 / 0 / 0 / 1 | Observed | Observed | Six consecutive applicable paired-off ticks |
| AHU23 | 18/18 | 0 / 17 / 0 / 1 | Observed | No paired change observed | Exhaust still reports on at all 17 supply-off ticks |
| AHU24 | 18/18 | 17 / 0 / 1 / 0 | Observed | Abstain on change | Six applicable paired-off ticks but no warm paired-on baseline |

A observed a BAS supply transition in **4/6** (4/4 evaluable, two abstentions). B observed a context-qualified paired transition in **2/6** (2/3 evaluable for change, one evaluable disagreement, three abstentions). B reports within-window state in 4/6, including AHU24. Four AHUs with A transitions have a first off sample at +300 s and confirmation at +600 s from logged start. The onset bound is (0 s, +300 s] on the workbook clock. The same bound and confirmation offset apply to B on AHU1/18. A's longest off sample span is 4,800 s (17 samples) on each of the four. For B, the longest applicable paired-off sample spans are 300 s on AHU1 and 1,500 s on AHU18 and AHU24. These spans are differences between sample timestamps. State continuity between samples is unknown.

AHU2/8 bounds are 13:37 to 15:07. Their 18 ticks run 13:40 through 15:05. All six windows have 18 exact held-side schedule-title matches. Four on-grid end ticks still carry the title and are excluded. The other two windows have no exact end tick. No selected window overlaps another same-AHU schedule entry. The unchanged Stage 08 ledger retains the dataset-wide 50 schedule/text discrepancies and 107 end-boundary records. The workbook notes broken differential-pressure sensors during AHU23/24 tests. Independent DP confirmation is therefore unavailable. The paper's Table 3 lists four Mervis IDE cases for Fault 12 and a dash in its detected column. The six public schedule entries are kept separate from that denominator and the authors' overall 94/105 APAR result. [CTU manuscript and Table 3](https://dspace.cvut.cz/entities/publication/35d10945-7123-4cdc-8367-50bfdb4c1052)

## Prespecified comparison

Of 156 screened windows, 54 failed the site-wide schedule/day-after exclusion, 51 failed the event precontext criterion and 45 failed the candidate precontext criterion. Six qualified on **2019-05-03 and 2019-05-17** (+63 and +77 days) for AHU1, AHU18 and AHU23. All six had both statuses on at all 18 ticks and warm request context. Both rules have **0/6 observed off transitions and 0/6 abstentions** in these controls. The publisher's no-fault annotation did not select controls and does not independently verify their health. AHU24 has no matched comparison. AHU2/8 are availability controls. The counts are descriptive repeated measurements from one site, one intervention date and two control dates. No FPR or inferential intervals are warranted.

## Limits and product boundary

Optional temperature plausibility check **STOP_THIS_CONTROL**. The paper describes zone-outlet injection scenarios. The verified material does not establish both the exact point crosswalk and an independent engineering or instrument limit for this control.

The additions are offline research code and exports. The rule input is clock and four exact BAS tags. Schedule and labels are joined afterward in the evaluation tables. No app route, UI, alert, incident, physical diagnosis or inference authorization is added. Frontend build, Playwright, screenshots and Docker were outside this offline change. No new training, calibration, LightGBM inference or fault ML scoring was performed.

## Verification

The integrated suite passed 180 tests. Live HTTP returned byte-identical full OpenAPI, Stage 07 research guard and historical incident responses against the Stage 08 base. The offline route returned 404. The standard-library reference matched three actual event traces and two actual control traces. The clean replay matched all 17 output files byte for byte. Source and protected-data digests matched, including the frozen Stage 06 trace, Stage 07 register, full and reduced native models and the isolated SQLite. Logs and manifests are included.
