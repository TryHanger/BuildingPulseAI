# KNOWN LIMITATIONS — Stage 8C Forensic Release Candidate

This document provides a comprehensive scientific record of all known technical, physical, and methodological limitations of the Stage 8C CSIRO AHU-10 evaluation.

---

## 1. Experimental and Dataset Limitations

1. **Facility Test-Exposure (Non-Blind Holdout):**
   - AHU-10 of the CSIRO Energy Centre was already utilized in Stage 8A (control effort modeling) and Stage 8B (cross-facility exploration).
   - Test dates (2013-11-07 and 2013-11-11) were previously inspected.
   - Consequently, this study is classified strictly as `TEST_EXPOSED_FORENSIC_REANALYSIS`. It cannot serve as prospective validation on an untouched physical site.

2. **Left-Censored Fault Onset (IDs 176, 194, 322):**
   - In 3 out of 10 evaluated experiments, physical fault injection was initiated at 08:30–08:31, whereas BMS telemetry archiving began at 09:00:00.
   - Alarms occurring after 09:00 represent detection of an already active fault during AHU startup, not observation of the fault's inception or transition dynamics.
   - True onset latency is physically unobservable for these 3 events.

3. **Telemetry Stream Identity (MA_TEMP == SA_TEMP):**
   - In the TAC Vista export `data/raw/csiro_ahu10.parquet`, the column `AHU10ahuMaTemp` duplicates `AHU10ahuSaTemp` on all 422,169 rows (max difference 0.0).
   - This prevents independent thermal verification across the cooling coil and mixed air plenum.
   - This identity is documented as telemetric redundancy, not hardware proof of absent sensors.

---

## 2. Model Performance and Operational Viability Limitations

1. **Severe False Alarm Rate Budget Violation:**
   - In production building operations, false alarm rates must remain strictly $\le 5.0\%$ to avoid operator alarm fatigue.
   - On the 1861 clean operational baseline points, the local control model (M2 $\tau=4.00$) triggers 750 false alarm points (**40.30% FAR**, 1.65 episodes/8h).
   - The local thermal model (M1 $\tau=3.00$) triggers 979 false alarm points (**52.61% FAR**).
   - These models are completely unviable for autonomous commercial deployment in their current form.

2. **Massive Cross-Seasonal Distribution Shift:**
   - Models trained on 9 days of shoulder season data (September 2013) fail catastrophically during peak summer cooling (January 2014):
     - M2 Control Local $\tau=4.00$: **45.36% FAR** (220 / 485 points).
     - M1 Thermal Local $\tau=3.00$: **98.97% FAR** (480 / 485 points).
   - This demonstrates that static linear models without exogenous weather/seasonal conditioning cannot track long-term seasonal setpoint and load changes.

3. **Weak Observable Fault Sensitivity:**
   - On the 7 events with observable physical onset, the detection rates are:
     - M1 Thermal Local $\tau=3.00$: 4/7 (57.1%), 95% CI [18.4%, 90.1%]
     - M2 Control Local $\tau=4.00$: 2/7 (28.6%), 95% CI [3.7%, 71.0%]
     - M6 Direct Damper: 0/7 (0.0%), 95% CI [0.0%, 41.0%]
   - Control inversion alone fails to detect damper stuck faults at moderate loads.

---

## 3. Physical and Cross-Domain Semantic Limitations

1. **Actuator Feedback vs Controller Command Incompatibility:**
   - RBC-Nesbitt trained M2 on $CCV\_FBK$ (potentiometer feedback from the valve actuator stem).
   - CSIRO TAC Vista records only $CCV\_CMD$ (controller output command).
   - These signals represent opposite sides of the actuation loop. Comparing $CCV\_CMD$ to a model predicting $CCV\_FBK$ is semantically invalid (`NOT_COMPARABLE`).

2. **Absence of Actuator Excitation During Static Regimes:**
   - When control commands remain static ($\Delta \text{cmd} < 15\%$), a stuck actuator cannot be distinguished from a healthy actuator holding position.

3. **5-Minute Aggregation Resolution:**
   - Resampling 30-second raw telemetry to 5-minute averages smooths sub-minute hunting, valve chatter, and transient overshoot, reducing the detectability of fast dynamic instabilities.

4. **Autocorrelation and Invalidation of i.i.d. Assumptions:**
   - Strong minute-to-minute autocorrelation violates the exchangeability assumption required for standard split conformal prediction and statistical independence tests.
