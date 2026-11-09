# Reproduce Stage 09

The frozen protocol hash is **868a685798c42c5a271149b64089aba8d72e0e8ed2d50a91900bfbe5587c5358**. No Stage 09 fan values or control outcomes were inspected before freeze. Stage 08 aggregates were known. The exact Stage 08 event ledger is under input-evidence/. The runner enforces both hashes. Accepted base ZIP identities are in evidence/base.sha256.

Use Python 3.12.3. Download the eight public files with their exact names from the URLs in code/research/ml_field_data_08/PUBLISHER_FILES_V1.json. This manifest pins publisher file IDs, version, sizes and hashes. The manuscript is 1,814,037 bytes with SHA-256 4a03914e8064ae3b42ffce9a806a724f7451bae7596d940ff3884b6c50a072ef and publisher MD5 a4749a55c2366deb298a3cae6104c504. [Publisher file list](https://data.mendeley.com/public-api/datasets/jkw85sm4v4/files?folder_id=root&version=1) · [Official manuscript](https://dspace.cvut.cz/server/api/core/bitstreams/2f9d64ab-bbd6-487c-b120-3d01bcbf4af2/content)

From the unpacked archive root:

```bash
sha256sum -c SHA256SUMS
python3.12 -m venv /tmp/bp09-venv
source /tmp/bp09-venv/bin/activate
export PYTHONDONTWRITEBYTECODE=1
python -m pip install -r code/research/ml_field_native_09/requirements.txt
RAW=/absolute/path/to/downloads
PAPER="$RAW/CTU_AAM_350037.verified.pdf"
REPLAY="$(mktemp -d)/replay"
cd code
python -m research.ml_field_native_09.replay "$RAW" "$PAPER" \
    ../input-evidence/EVENT_LEDGER_08.csv ../FIELD_NATIVE_09_PROTOCOL.md "$REPLAY"
diff -r ../observed "$REPLAY"
python -m research.ml_field_native_09.reference_check "$RAW" "$REPLAY"
```

The primary replay opens originals read-only. The independent check decodes XLSX XML with Python's standard library and recalculates selected statuses and transitions. All 12 trace files omit labels. Outcome files record each trace SHA, rule version, source workbook/sheet and clock.

For application regression, copy only code/research/ml_field_native_09/ into an isolated Stage 07 checkout with the Stage 08 patch already applied. Install its existing app/test requirements plus the pinned Excel dependencies. Set DATABASE_URL, DATA_ROOT, BUILDINGPULSE_AUDIT_SCRATCH and BUILDINGPULSE_PROTECTED_ROOTS for isolated tests. Set BP08_RAW to the verified downloads.

```bash
python -m pytest -q research/ml_field_native_09 research/ml_field_data_08 research/ml_domain_shift_07 \
    backend/tests/test_health.py backend/tests/test_g2_runtime.py backend/tests/test_g3_symptoms.py \
    backend/tests/test_g4_investigation.py backend/tests/test_g56_evidence_metadata.py \
    backend/tests/test_g57_observability.py contracts/test_evidence_v1.py
```

The workspace has no Git metadata. The code is supplied as a directly copyable overlay.
