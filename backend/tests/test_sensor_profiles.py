import pytest
import numpy as np
import pandas as pd
from ml.diagnostics.sensor_profiles import (
    SensorProfileRegistry,
    extract_profile_diagnostic_features,
    CANONICAL_BASIC_CHANNELS
)

def test_sensor_profile_registry():
    profiles = SensorProfileRegistry.list_profiles()
    assert len(profiles) == 5
    ids = [p["id"] for p in profiles]
    assert "BASIC" in ids
    assert "BASIC_PLUS_VALVE" in ids
    assert "BASIC_PLUS_DAMPER" in ids
    assert "BASIC_PLUS_BOTH" in ids
    assert "FULL" in ids

    # Test unknown profile raises ValueError
    with pytest.raises(ValueError):
        SensorProfileRegistry.get_profile("UNKNOWN_PROFILE")

def test_hidden_channel_guard_in_basic_profile():
    """
    CRITICAL SCIENTIFIC INVARIANT I2:
    Modifying or corrupting hidden feedback channels (CHWC_VLV, OA_DMPR)
    in the raw DataFrame must NOT alter BASIC profile feature output by a single bit.
    """
    n = 30
    np.random.seed(42)
    raw_df_1 = pd.DataFrame({
        "OA_TEMP": np.random.uniform(0, 15, n),
        "RA_TEMP": np.random.uniform(20, 24, n),
        "MA_TEMP": np.random.uniform(10, 18, n),
        "SA_TEMP": np.random.uniform(12, 16, n),
        "SA_TEMPSPT": np.full(n, 12.8),
        "CHWC_VLV_DM": np.random.uniform(0, 1, n),
        "OA_DMPR_DM": np.random.uniform(0, 1, n),
        "SF_SPD_DM": np.ones(n),
        # Hidden feedback channels for BASIC:
        "CHWC_VLV": np.random.uniform(0, 1, n),
        "OA_DMPR": np.random.uniform(0, 1, n)
    })

    vs_pred = np.random.uniform(12, 16, n)

    feats_1, cols_1 = extract_profile_diagnostic_features(raw_df_1, vs_pred, profile_id="BASIC")

    # Now create raw_df_2 with EXTREME corruption in hidden feedback columns
    raw_df_2 = raw_df_1.copy()
    raw_df_2["CHWC_VLV"] = 9999.0
    raw_df_2["OA_DMPR"] = -8888.0

    feats_2, cols_2 = extract_profile_diagnostic_features(raw_df_2, vs_pred, profile_id="BASIC")

    # Columns must be identical
    assert cols_1 == cols_2
    assert "chwc_vlv_fb" not in cols_1
    assert "oa_dmpr_fb" not in cols_1
    assert "vlv_pos_discrepancy" not in cols_1

    # All values must be EXACTLY identical (zero difference)
    pd.testing.assert_frame_equal(feats_1, feats_2)

def test_profile_feature_differentiation():
    """
    Verifies that enabling BASIC_PLUS_VALVE incorporates valve feedback features,
    and BASIC_PLUS_BOTH incorporates both valve and damper feedback features.
    """
    n = 20
    df = pd.DataFrame({
        "OA_TEMP": np.full(n, 10.0),
        "RA_TEMP": np.full(n, 22.0),
        "MA_TEMP": np.full(n, 15.0),
        "SA_TEMP": np.full(n, 13.0),
        "SA_TEMPSPT": np.full(n, 12.8),
        "CHWC_VLV_DM": np.full(n, 0.4),
        "CHWC_VLV": np.full(n, 0.1),  # Stuck at 0.1
        "OA_DMPR_DM": np.full(n, 0.2),
        "OA_DMPR": np.full(n, 0.2),
        "SF_SPD_DM": np.ones(n)
    })
    vs_pred = np.full(n, 12.8)

    # Basic: only 11 features
    f_basic, cols_b = extract_profile_diagnostic_features(df, vs_pred, "BASIC")
    assert "vlv_pos_discrepancy" not in cols_b

    # Basic + Valve: 14 features (includes vlv_pos_discrepancy)
    f_valve, cols_v = extract_profile_diagnostic_features(df, vs_pred, "BASIC_PLUS_VALVE")
    assert "vlv_pos_discrepancy" in cols_v
    assert f_valve["vlv_pos_discrepancy"].iloc[0] == pytest.approx(0.3, abs=1e-4)

    # Basic + Both: includes both discrepancies
    f_both, cols_both = extract_profile_diagnostic_features(df, vs_pred, "BASIC_PLUS_BOTH")
    assert "vlv_pos_discrepancy" in cols_both
    assert "dmpr_pos_discrepancy" in cols_both
