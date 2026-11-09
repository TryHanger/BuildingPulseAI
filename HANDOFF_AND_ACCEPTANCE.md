# Protocol: S ↔ F integration and acceptance

## Single source of truth

- S owns API JSON Schema + `/contracts/openapi-v1.yaml` and sample JSON fixtures validated against it.
- F owns rendering, route/layout/types generated from OpenAPI, does not define diagnostic meaning.
- Before frozen API: F uses `UI_MOCK_V0`, each fixture marked `SYNTHETIC_UI_ONLY`.
- After API freeze: fixtures migrate with schema tests; no undisclosed mixing of actual/fixture data.
- Breaking changes require `API_CHANGE_REQUEST.md`, new version, documented migration, S and F tests. Owner approval when changing product meaning.

## Gate deliverable template (both agents)

```text
GATE_ID:
IMPLEMENTED:
VERIFIED (exact tests/commands):
UNVERIFIED:
BLOCKED:
PRIMARY SOURCES / LICENSES:
API_SCHEMA_VERSION:
DATA_SOURCE_HASHES:
FILES_CHANGED:
TEST_RESULTS:
REPRO_COMMANDS:
SCREENSHOTS / SCIENCE REPORT:
DECISION_CHANGES (ID, reason):
ZIP_PATH AND SHA256:
GIT_STATUS:
```

## Integration acceptance tests

1. On `/assets/:id`, `Dataset.source_type=SIMULATION` visible, not `LIVE`.
2. Correct time cursor across SVG + plots + incident cards (±one sample interval).
3. Any missing signal appears as `NOT_EVALUABLE`, not a zero or healthy.
4. No `ISOLATED` state possible via user-supplied discriminator string.
5. If SAT quality invalid, dependent rules have inconclusive result; independent alarms remain visible.
6. Two contradictory methods appear in the inspector, not silently discarded.
7. BASIC cannot use actual valve position `CHWC_VLV`; EXTRA explicitly marks sensor origin.
8. No hidden `SYS_CTL` in BASIC.
9. Matched normal/fault visible only with verified source `pair_id` and simulation label.
10. No research metric computed from UI synthetic fixture or from ground_truth_only signals.
11. Min/max envelope preserves short peaks and raw zoom shows exact source values.
12. Incidents are event-level, not one alarm per minute.

## Stop-before-build criterion

Before S begins any candidate integration, publish `METHOD_CARD` with: TASK, INPUTS, MODES, TRAINING LABELS, KNOWN INCOMPATIBILITIES, AUTHOR IMPLEMENTATION, LICENSE, THRESHOLD OR CALIBRATION, VALIDATION DATA, SUCCESS/FAILURE CRITERIA, COMPLEXITY and GO/STOP. If known inputs or task mismatch, STOP without coding and document replacement candidate. This is the direct answer to “не тратить время на заведомо неприменимый метод”.
