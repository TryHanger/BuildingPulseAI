import sys
sys.path.insert(0, ".")
import pandas as pd
import numpy as np
from ml.control_aware.dataset import load_canonical_csiro_dataframe
from ml.control_aware.splits import get_stage8a_split
from ml.control_aware.features import extract_control_effort_features
from ml.control_aware.baseline_control import ControlEffortModel

df10, meta10 = load_canonical_csiro_dataframe('data/raw/csiro_ahu10.parquet', ahu_id=10)
df_train, df_val, df_test, s_meta = get_stage8a_split(df10, filter_operating=True)

X_train_u, y_train_u = extract_control_effort_features(df_train, "CHWC_VLV_DM")
X_val_u, y_val_u = extract_control_effort_features(df_val, "CHWC_VLV_DM")
X_test_u, y_test_u = extract_control_effort_features(df_test, "CHWC_VLV_DM")

model_u = ControlEffortModel(model_type="ridge", alpha=1.0)
model_u.fit(X_train_u, y_train_u)
val_cal = model_u.calibrate_on_validation(X_val_u, y_val_u)

preds_val = model_u.predict(X_val_u)
preds_test = model_u.predict(X_test_u)

print("AHU10 U_ONLY Model:")
print("  Train y mean:", y_train_u.mean(), "std:", y_train_u.std(), "min/max:", y_train_u.min(), y_train_u.max())
print("  Val y mean:", y_val_u.mean(), "std:", y_val_u.std(), "min/max:", y_val_u.min(), y_val_u.max())
print("  Test y mean:", y_test_u.mean(), "std:", y_test_u.std(), "min/max:", y_test_u.min(), y_test_u.max())
print("  Val MAE:", val_cal["val_mae"], "R2:", val_cal["val_r2"], "Residual std:", val_cal["val_residual_std"])

res_test = np.abs(y_test_u.values - preds_test)
z_test = res_test / val_cal["val_residual_std"]
print("  Test residual z max:", np.max(z_test), "99th percentile:", np.percentile(z_test, 99))
print("  Points with z >= 5.0:", np.sum(z_test >= 5.0))
print("  Points with z >= 4.0:", np.sum(z_test >= 4.0))
print("  Points with z >= 3.0:", np.sum(z_test >= 3.0))
