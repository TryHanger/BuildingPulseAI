# STAGE 8A BASELINE FREEZE — Фиксация исходного состояния платформы

**Дата фиксации:** 2026-11-04  
**Базовая версия платформы:** `BuildingPulse AI v0.7.1-stage7.1`  
**Статус верификации:** ПРОВЕРЕНО И ЗАФИКСИРОВАНО (GATE 8A.0 PASS)

---

## 1. Итоги предварительной верификации окружения

При запуске Gate 8A.0 выполнены строгие фактические тесты доступного окружения:

1. **Pytest (Backend):**
   - Команда: `pytest backend/tests`
   - Результат: **80 passed in 18.36s (100% PASS)**
   - Проверены сьюты: адаптация API, Decision Layer, диагностика, мониторинг/телеметрия, импорт, физическое опровержение, гигиена экспериментов Stage 5, маппинг Stage 6, сплиты Stage 6, негативные контроли Stage 6, регрессии науки Stage 7.
2. **TypeScript Strict Typecheck & Build (Frontend):**
   - Команда: `npm --prefix frontend run build`
   - Результат: `tsc && vite build` — **успешно завершено за 23.25s, 0 ошибок типов**.
3. **Репозиторий и версионирование:**
   - Git commit/push/merge/reset/clean/deploy **строго запрещены** владельцем.
   - Проект зафиксирован в состоянии `v0.7.1-stage7.1`.

---

## 2. Исходные научные метрики baseline Stage 6/7.1 (CSIRO AHU9 Held-Out)

В качестве температурного детектора (`T_ONLY`) на CSIRO AHU9 выступает калибратор C2 (`csiro-ahu9-affine-v1`), использующий предобученную симуляционную модель LBNL `vs-sa-temp-v2` с аффинным преобразованием $\hat{y}_{C2} = 2.013821 \cdot \hat{y}_{\text{source}} - 10.110449^\circ\text{C}$ и локальным порогом $3\sigma = 3.0085^\circ\text{C}$ с каузальным фильтром $K=10$ из $N=15$ минут.

### Ключевые скалярные метрики
- **Знаменатель чистых рабочих минут (Normal Operating Points):** $N_{\text{normal}} = 1074$ минут.
- **Ложные тревожные минуты (False Alarm Minutes):** $30$ минут.
- **Точечная частота ложных тревог (Pointwise FAR):** $30 / 1074 = 0.0279$ ($2.79\% \le 5.0\%$).
- **Число ложных эпизодов тревоги:** $4$ эпизода на исправных рабочих интервалах.
- **Ложные эпизоды за 8-часовой рабочий день:** $4 / (1074 / 480) = 1.7877$ эп/день.
- **Всего размеченных эпизодов дефектов на тесте:** $34$ эпизода.
- **Обнаружено эпизодов:** $6$ из $34$ ($17.65\%$).
- **CHW Valve Stuck Recall:** $1$ из $4$ ($25.0\%$) — обнаружен только интенсивный эпизод 52.0% stuck (2013-11-11 14:31:15), пропущены 88.0%, 79.0%, и др.

### Поимённый список 6 обнаруженных эпизодов baseline (C2)
1. `Zone Average Temp Drift` (severity: -2.0) — `2013-11-07 11:08:01` — `2013-11-07 12:08:06`, задержка: 21 мин.
2. `OA Damper Stuck Open` (severity: 81.0) — `2013-11-07 11:08:03` — `2013-11-07 12:08:08`, задержка: 21 мин.
3. `CHW Valve Proxy Stuck Open` (severity: 52.0) — `2013-11-11 14:31:15` — `2013-11-11 15:31:25`, задержка: 33 мин.
4. `HW Valve Proxy Stuck Open` (severity: 68.0) — `2013-11-11 14:31:16` — `2013-11-11 15:31:29`, задержка: 33 мин.
5. `RA Damper Stuck Open` (severity: 55.0) — `2013-11-12 14:31:24` — `2013-11-12 15:31:33`, задержка: 54 мин.
6. `Zone Average Temp Drift` (severity: -2.0) — `2013-11-12 14:31:29` — `2013-11-12 15:31:43`, задержка: 54 мин.

*(Примечание: эпизоды инъектировались парами, поэтому в тесте зафиксированы перекрывающиеся интервалы дефектов).*

---

## 3. Криптографические хэши артефактов (SHA-256)

### Модели (`models/`)
| Файл | SHA-256 | Размер (байт) |
|---|---|---|
| `classifier_basic.joblib` | `54e04b931160feb112ab4f6e7c6645549a11ef10eda5c76c8bb38510949b53d9` | 691 149 |
| `classifier_basic_plus_both.joblib` | `b8dd326740c2bfd8b936911216b585263b53c01942afc4ad4faee3aa36be367d` | 640 248 |
| `classifier_basic_plus_damper.joblib` | `3c03389efad8fe9b262917e5499de6926633210c592e8e1e039782f83ada684e` | 670 653 |
| `classifier_basic_plus_valve.joblib` | `94b596bf4fdfa2f43bd546009848627bf39b09dbc8fb16bbe884e6e095f6fc04` | 669 863 |
| `classifier_full.joblib` | `3b42c335501d16a8e49f086863ac4176461ef1482e887650df46aeb55474f1ef` | 632 360 |
| `csiro-ahu9-affine-v1.joblib` | `71a8b5d6c9e9f287557a93e0d9d0692a3d4f1335ed3bba28c31c98b85b99e59e` | 140 |
| `csiro-ahu9-affine-v1_metadata.json` | `e33e844d5974e88efa850d718de06db0317f0c1315f423ed739794dc0ca779b6` | 1 030 |
| `csiro-ahu9-bias-v1.joblib` | `e84fe9561e12740ac71d10d071280e5e1ed664c59c053f498ddbdd1ddcd8104f` | 106 |
| `csiro-ahu9-bias-v1_metadata.json` | `0584c21d45755ac4f0e5e174e4edba1836795ee117d2ddd06fd7d8d9f65703f1` | 1 007 |
| `csiro-ahu9-local-lgbm-v1.joblib` | `6d4e18c23fb0f44953de7d87aaf386040dde4ee8a11e0a367c6a66ba75b6b520` | 42 076 |
| `csiro-ahu9-local-lgbm-v1_metadata.json` | `1b20a5e03f66edf8957ee98c59923cdf40c8ea9ea745b57dd29f38f5c499ec92` | 1 312 |
| `csiro-ahu9-local-ridge-v1.joblib` | `58f42d46edfd8b53c8bf26ca560674fa599e5e229910aead3b3beff2d1f478cc` | 1 636 |
| `csiro-ahu9-local-ridge-v1_metadata.json` | `108856ec60ca61d2e4a23fbd0c3fc3cf0109d8017549835d51e1e975c69b37f4` | 1 260 |
| `csiro-ahu9-residual-ridge-v1.joblib` | `fcd9b2fdfa136fbbe5fd0369a3c4cd771ce89480c8a9a163add1f7c36c4576fe` | 1 636 |
| `csiro-ahu9-residual-ridge-v1_metadata.json` | `5b6ccbf2f496307606b08e608ec0da005a5dec024d494ab24ff78904fcb77fc7` | 1 274 |
| `fault-family-classifier-v1.joblib` | `99ec6a40977125a0cef7345722f1912e02f4141683f75cd2937e56b584b42863` | 539 548 |
| `fault-family-classifier-v1.json` | `0b4879a852d009f6265389d1315dbb34bb955a9e394625d7a34bcf6eb107e9ef` | 922 |
| `vs-sa-temp-v1.joblib` | `7cd63e4c7b111454c43419869a496d6119694cf9b0c6b27865a5c7b0f100bcdc` | 106 501 |
| `vs-sa-temp-v2.joblib` | `9fd340dd28b137e90d37dc4195dc8309e9766130091b82c31082928819c6e48d` | 122 100 |

### Манифесты запусков (`research/runs/`)
| Манифест | SHA-256 |
|---|---|
| `stage6_csiro_adaptation_eval.json` | `364dc6781dd75c3bcdcbeda7102a52400cfeffd597cbdc08dc507753e4d4f4ce` |
| `stage6_csiro_adaptation_train.json` | `2ea9f6d6ad672ab5db8b214f2d2fd515148f8d486036fce6b63e5200775023f0` |
| `stage7_stage6_reproduction.json` | `a71d5a01dbf876e76e01d1b7798fb03b7f01a70cc9b76126cf8256724c28fa27` |
| `stage7_final_scientific_summary.json` | `088862aa3e42a1342dd842aac6a55c417101a02836f4c10d3e1379af6ab79725` |

---

## 4. Перечень защищенных файлов (Не подлежат модификации в Stage 8A)

Следующие директории и файлы содержат зафиксированный фундамент Stages 1–7.1 и **строго защищены от перезаписи**:
- `models/*` (все обученные модели Stages 1–7.1);
- `research/reports/STAGE*` (отчеты Stages 2–7.1);
- `research/protocols/stage3_*`, `stage4_*`, `stage5_*`, `stage6_*`;
- `research/runs/stage3_*`, `stage4_*`, `stage5_*`, `stage6_*`, `stage7_*`;
- `backend/app/api/endpoints/` (существующий production REST API);
- `frontend/src/` (пользовательский интерфейс v0.7.1).

**Все новые разработки Stage 8A изолируются по путям:**
- Код: `ml/control_aware/`
- Протокол: `research/protocols/stage8a_control_effort_v1.md`
- Запуски: `research/runs/stage8a_*.json`
- Отчеты: `docs/STAGE8A_*.md`, `research/reports/STAGE8A_CONTROL_EFFORT_REPORT.md`
- Тесты: `backend/tests/test_stage8a_control_aware.py`

**PASS GATE 8A.0.**
