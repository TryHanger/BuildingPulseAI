# STAGE 7 — ПАСПОРТ МОДЕЛЕЙ И АРТЕФАКТОВ BUILDINGPULSE AI (MODEL CARDS)

- **Версия ревизии:** `v1.0-stage7`
- **Дата актуализации:** 2026-11-03
- **Назначение:** Полный технический паспорт всех моделей машинного обучения и доменной адаптации, входящих в дипломный прототип BuildingPulse AI.

---

## 1. Сводный реестр моделей

| ID модели | Назначение | Архитектура | Обучающий датасет | Входные каналы | Статус доменной валидации |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `vs-sa-temp-v2` | Виртуальный датчик $SA\_TEMP$ | LightGBM Regressor (100 деревьев, $lr=0.05$) | LBNL SD-AHU 4 сезона ($N=51\,840$) | Basic (7 каналов) | `SIMULATED_BENCHMARK_VALIDATED` |
| `vs-sa-temp-baseline-ridge-v2` | Контрольный линейный виртуальный датчик | Ridge Regression ($\alpha=10.0$) | LBNL SD-AHU 4 сезона ($N=51\,840$) | Basic (7 каналов) | `SIMULATED_BENCHMARK_VALIDATED` |
| `classifier_basic` | Классификатор дефектов (профиль Basic) | LightGBM Classifier (30 деревьев) | LBNL Faults (25%, 75% stuck; $\pm 4^\circ\text{C}$ bias) | 11 признаков Basic | `SIMULATED_BENCHMARK_VALIDATED` |
| `classifier_basic_plus_valve` | Классификатор дефектов (+ обратная связь клапана) | LightGBM Classifier (30 деревьев) | LBNL Faults (25%, 75% stuck; $\pm 4^\circ\text{C}$ bias) | 14 признаков (+ $CHWC\_VLV$) | `SIMULATED_BENCHMARK_VALIDATED` |
| `classifier_basic_plus_damper` | Классификатор дефектов (+ обратная связь заслонки) | LightGBM Classifier (30 деревьев) | LBNL Faults (25%, 75% stuck; $\pm 4^\circ\text{C}$ bias) | 14 признаков (+ $OA\_DMPR$) | `SIMULATED_BENCHMARK_VALIDATED` |
| `classifier_basic_plus_both` | Классификатор дефектов (+ оба привода) | LightGBM Classifier (30 деревьев) | LBNL Faults (25%, 75% stuck; $\pm 4^\circ\text{C}$ bias) | 17 признаков | `SIMULATED_BENCHMARK_VALIDATED` |
| `classifier_full` | Классификатор дефектов (полная наблюдаемость) | LightGBM Classifier (30 деревьев) | LBNL Faults (25%, 75% stuck; $\pm 4^\circ\text{C}$ bias) | 19 признаков (+ мощность, расход) | `SIMULATED_BENCHMARK_VALIDATED` |
| `csiro-ahu9-affine-v1` (**C2**) | Аффинный калибратор переноса на CSIRO AHU9 | Linear Ridge ($y = a \cdot y_{\text{src}} + b$) | CSIRO Train Local ($N=1\,588$ чистых точек) | Прогноз `vs-sa-temp-v2` | `LOCALLY_EVALUATED: REGRESSION_ONLY` |
| `csiro-ahu9-bias-v1` (**C1**) | Константное смещение переноса на CSIRO AHU9 | Скалярный сдвиг ($y = y_{\text{src}} + b$) | CSIRO Train Local ($N=1\,588$ чистых точек) | Прогноз `vs-sa-temp-v2` | `LOCALLY_EVALUATED: REGRESSION_ONLY` |
| `csiro-ahu9-local-lgbm-v1` (**L2**) | Локальный бустинг CSIRO (без источника) | LightGBM Regressor ($depth=3, leaves=7$) | CSIRO Train Local ($N=1\,588$ чистых точек) | Локальные каналы CSIRO (7 шт.) | `LOCALLY_EVALUATED: REGRESSION_ONLY` |
| `csiro-ahu9-residual-ridge-v1` (**A1**) | Локальная гребневая регрессия невязки LBNL | Ridge над остатками ($\alpha=10.0$) | CSIRO Train Local ($N=1\,588$ чистых точек) | Локальные каналы + $y_{\text{src}}$ | `LOCALLY_EVALUATED: REGRESSION_ONLY` |
| `csiro-ahu9-local-ridge-v1` (**L1**) | Автономная линейная модель CSIRO | Ridge с нуля ($\alpha=10.0$) | CSIRO Train Local ($N=1\,588$ чистых точек) | Локальные каналы CSIRO (7 шт.) | `LOCALLY_EVALUATED: REGRESSION_ONLY` |

---

## 2. Детальная спецификация моделей переноса CSIRO AHU9

### 2.1. CSIRO Affine Calibrator C2 (`csiro-ahu9-affine-v1`)
- **Тип:** Аффинная одномерная калибровка масштаба и сдвига отклика базовой модели LBNL.
- **Точные верифицированные параметры:**
  - Наклон (slope / $a$): $2.013821390416395$
  - Сдвиг (intercept / $b$): $-10.110449452489096^\circ\text{C}$
  - Уравнение: $\hat{y}_{C2} = 2.013821 \cdot \hat{y}_{Z0} - 10.110449^\circ\text{C}$
- **Метрики отложенного теста (Held-Out Test, $N=1\,074$):**
  - $\text{MAE} = 1.1062^\circ\text{C}$ (снижение на $75.2\%$ относительно $Z0$)
  - $\text{RMSE} = 1.6661^\circ\text{C}$
  - $\text{Mean Residual Bias} = +0.3260^\circ\text{C}$
  - $R^2 = 0.4669$
- **Диагностический порог:**
  - $3\sigma$ порог, калиброванный на валидации: $\tau = 3.0085^\circ\text{C}$
  - Каузальный фильтр: $K=10$ минут из окна $N=15$ минут
  - Частота ложных тревог (норма): $2.79\%$ (30 минут, $1.79$ эп/день)
  - Полнота детекции заклинивания клапана охлаждения: $1$ из $4$ ($25.0\%$)
- **Статус безопасности (Domain Guard):** `LOCALLY_EVALUATED`. Запрещено использовать для автоматического диагноза неисправности.

### 2.2. CSIRO Constant Bias Corrector C1 (`csiro-ahu9-bias-v1`)
- **Тип:** Одномерная аддитивная поправка систематического сдвига.
- **Точные верифицированные параметры:**
  - Подогнанный сдвиг ($b$): $+4.59326801179734^\circ\text{C}$
  - Уравнение: $\hat{y}_{C1} = \hat{y}_{Z0} + 4.593268^\circ\text{C}$
- **Метрики отложенного теста (Held-Out Test, $N=1\,074$):**
  - $\text{MAE} = 1.2037^\circ\text{C}$ (снижение на $73.0\%$ относительно $Z0$)
  - $\text{RMSE} = 1.6048^\circ\text{C}$ (**лучший RMSE среди всех методов**)
  - $\text{Mean Residual Bias} = -0.1381^\circ\text{C}$ (**минимальный остаточный сдвиг**)
  - $R^2 = 0.5054$ (**лучший $R^2$ среди всех методов**)
- **Диагностический порог:**
  - $3\sigma$ порог: $\tau = 3.4318^\circ\text{C}$
  - Частота ложных тревог: $2.51\%$ (27 минут, $1.34$ эп/день)
  - Полнота по клапану охлаждения: $1$ из $4$ ($25.0\%$)

---

## 3. Политика доменных барьеров (Domain Guard Policy)

1. **Режим `SIMULATED_BENCHMARK` (LBNL SD-AHU):**
   - Разрешены: инференс `vs-sa-temp-v2`, расчет невязки, классификаторы дефектов, Decision Layer, профили наблюдаемости и рекомендатель каналов.
2. **Режим `REAL_FIELD_BMS` (CSIRO AHU9):**
   - Разрешены: отображение телеметрии, расчет физического качества данных, инференс адаптированных моделей $C1, C2, L2$ со статусом `LOCALLY_EVALUATED`.
   - Заблокированы: классификация причин неисправностей (Decision Layer) без отдельного локального дообучения классификатора.
3. **Режим `SYNTHETIC_DEMO` / `USER_UPLOADED`:**
   - Невязки отображаются исключительно в исследовательском режиме с предупреждением `OUT_OF_DOMAIN_UNVALIDATED`.
