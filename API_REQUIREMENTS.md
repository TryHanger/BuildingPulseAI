# API_REQUIREMENTS.md — Требования фронтенда к контракту API v1 (Strong Agent S)

**Версия документа:** `REQ-2026-11-07-v1`  
**Статус:** Предложение контракта и требования от фронтенд-агента (F) к бэкенд-агенту (S).  
**Основание:** `BUILDINGPULSE_MASTER_IMPLEMENTATION_PLAN.md`, разделы MUST и G0–G4.  
**Дисклеймер:** Данный документ фиксирует требования пользовательского интерфейса `UI_MOCK_V0` для бесшовного перехода с синтетических фикстур на реальный серверный контракт `openapi-v1.yaml`.

---

## 1. Общие архитектурные инварианты

1. **Разделение Ground Truth и диагностических выводов:**
   - Поля эталона (`source_fault_label`, `ground_truth_severity`) никогда не передаются в качестве входов правил или скоров.
2. **Отсутствие выдуманных вероятностей:**
   - Категорически исключить вычисление псевдовероятностей неисправности (например, `probability: 0.95`). Диагностические выводы передаются в виде категорий статуса (`DETECTED`, `NOT_EVALUABLE`, `AMBIGUOUS`, `CONFLICTED`).
3. **Четыре независимые оси статуса в каждом инциденте:**
   - `data_state`: `VALID | DEGRADED | INVALID | UNKNOWN`
   - `cause_state`: `UNEXPLAINED | AMBIGUOUS | ISOLATED_CONDITIONAL | CONFIRMED_EXTERNALLY`
   - `model_scope`: `IN_SCOPE | OUT_OF_SCOPE | UNKNOWN`
   - `method_status`: `APPLICABLE | INAPPLICABLE | INCONCLUSIVE` (по каждому методу).
4. **Строгий запрет SYS_CTL как измеримого канала в BASIC:**
   - Канал `SYS_CTL` является метаданными режима симулятора LBNL, а не физическим датчиком. Не включать его в базовый профиль измерений.
5. **Физическая целостность временных рядов:**
   - При интервалах между отсчетами $\Delta t > 30$ минут сервер должен маркировать разрыв или возвращать точки `null` для предотвращения ложной линейной интерполяции через ночь.

---

## 2. Спецификация требуемых эндпоинтов API v1

### 2.1. Каталог датасетов и оборудования

#### `GET /api/v1/datasets`
Возвращает список доступных источников данных с явной маркировкой происхождения:
```json
[
  {
    "id": "ds-lbnl-sdahu",
    "name": "LBNL SD-AHU Simulation Benchmark",
    "source_kind": "SIMULATED_BENCHMARK",
    "provenance_badge": "Simulation (LBNL)",
    "sha256": "d11cbb117b57...",
    "license": "Open Data / LBNL",
    "equipment_ids": ["ahu-sd"]
  }
]
```

#### `GET /api/v1/datasets/{dataset_id}/signals`
Возвращает реестр сигналов с каноническими идентификаторами и уровнем профиля:
```json
[
  {
    "canonical_id": "OA_TEMP",
    "name_ru": "Температура наружного воздуха",
    "unit": "°C",
    "kind": "MEASUREMENT",
    "tier": "BASIC",
    "recorded_in_source": true,
    "verified_semantics": true
  },
  {
    "canonical_id": "CHWC_VLV",
    "name_ru": "Положение штока клапана охлаждения",
    "unit": "%",
    "kind": "MEASUREMENT",
    "tier": "EXTRA",
    "recorded_in_source": true,
    "verified_semantics": true
  }
]
```

---

### 2.2. Эксплуатационные режимы установки

#### `GET /api/v1/equipment/{equipment_id}/modes`
Параметры: `dataset_id: str`, `start: str (ISO 8601)`, `end: str (ISO 8601)`.  
Возвращает временные сегменты режимов работы state machine:
```json
{
  "equipment_id": "ahu-sd",
  "segments": [
    {
      "start": "2026-07-15T06:00:00Z",
      "end": "2026-07-15T07:30:00Z",
      "mode": "OFF",
      "fan_on": false,
      "confidence": "KNOWN"
    },
    {
      "start": "2026-07-15T10:30:00Z",
      "end": "2026-07-15T17:30:00Z",
      "mode": "COOLING",
      "fan_on": true,
      "confidence": "KNOWN"
    }
  ]
}
```

---

### 2.3. Синхронная телеметрия с Min-Max Downsampling

#### `GET /api/v1/series`
Параметры:
- `dataset_id: str`
- `signal_ids: str` (через запятую: `SA_TEMP,SA_TEMPSPT,CHWC_VLV_DM,OA_DMPR_DM,OA_TEMP,RA_TEMP,MA_TEMP`)
- `start: str`, `end: str`
- `max_points: int` (по умолчанию 1500)
- `include_corridor: bool` (по умолчанию `true`)

Возвращает синхронизированные временные ряды:
```json
{
  "time_window": {
    "start": "2026-07-15T06:00:00Z",
    "end": "2026-07-15T18:00:00Z",
    "step_seconds": 300
  },
  "series": [
    {
      "channel": "SA_TEMP",
      "display_name_ru": "Температура притока (SAT)",
      "unit": "°C",
      "chart_group": "chart1_sat",
      "points": [["2026-07-15T06:00:00Z", 22.1], ["2026-07-15T07:00:00Z", 22.3]]
    },
    {
      "channel": "CHWC_VLV_DM",
      "display_name_ru": "Команда клапана охлаждения",
      "unit": "%",
      "chart_group": "chart2_cmd",
      "points": [["2026-07-15T06:00:00Z", 0.0], ["2026-07-15T12:00:00Z", 100.0]]
    }
  ],
  "corridors": [
    {
      "channel": "CHWC_VLV_DM",
      "upper_points": [["2026-07-15T12:00:00Z", 80.0]],
      "lower_points": [["2026-07-15T12:00:00Z", 50.0]]
    }
  ]
}
```

---

### 2.4. Реестр инцидентов и Evidence Inspector

#### `GET /api/v1/analyses/{run_id}/incidents`
Возвращает список обнаруженных инцидентов со статусами:
```json
[
  {
    "id": "inc-2026-001",
    "equipment_id": "ahu-sd",
    "equipment_name": "LBNL SD-AHU 01",
    "timestamp_start": "2026-07-15T11:20:00Z",
    "timestamp_end": "2026-07-15T14:45:00Z",
    "seek_timestamp": "2026-07-15T12:30:00Z",
    "detection_state": "DETECTED",
    "cause_state": "AMBIGUOUS",
    "data_state": "VALID",
    "model_state": "IN_SCOPE",
    "rule_id": "APAR_RULE_02_SAT_COOLING_DEVIATION",
    "rule_name": "Устойчивое отклонение SAT от уставки в режиме охлаждения",
    "severity_category": "OPERATIONAL_DEVIATION",
    "symptom_description": "SAT превышает уставку на +3.8 °C при 100% команде клапана",
    "prerequisites_met": ["SF_RUNNING", "MECHANICAL_COOLING_MODE"],
    "missing_observability": ["CHWC_VLV (обратная связь штока)"],
    "recommended_action": "Проверить фактическое положение штока по месту."
  }
]
```

#### `GET /api/v1/incidents/{incident_id}/evidence`
Возвращает полную структуру EvidenceV1:
```json
{
  "incident_id": "inc-2026-001",
  "rule_evaluation": {
    "rule_id": "APAR_RULE_02_SAT_COOLING_DEVIATION",
    "execution_status": "VIOLATED",
    "threshold": "+1.5 °C for >= 30 min",
    "observed_value": "+4.1 °C for 45 min",
    "quality_status": "VALID_OBSERVABILITY"
  },
  "hypotheses": [
    {
      "id": "hyp-01",
      "code": "COOLING_VALVE_STUCK",
      "name": "Заклинивание штока клапана охлаждения",
      "evidence_status": "SUPPORTED_UNDER_OBSERVABILITY_LIMITS",
      "supporting_evidence": ["Команда удерживается на 100% более 45 минут"],
      "contradicting_evidence": [],
      "missing_evidence": ["Датчик положения штока CHWC_VLV отсутствует в BASIC"]
    }
  ],
  "unexecutable_checks": [
    {
      "check_id": "CHK_VALVE_STEM_TRACKING",
      "name": "Сверка команды с фактическим положением штока",
      "reason_code": "SIGNAL_PHYSICALLY_ABSENT_IN_PROFILE",
      "reason_ru": "Канал CHWC_VLV не смонтирован на установке.",
      "resolution": "Подключить канал CHWC_VLV в Sensor Lab."
    }
  ],
  "recommended_actions_whitelist": [
    {
      "action_id": "REC_ACTUATOR_INSPECTION",
      "priority": "HIGH",
      "title": "Инспекция привода клапана по месту",
      "instruction": "Визуально осмотреть положение индикатора штока.",
      "preconditions": "Соблюдать технику безопасности в венткамере.",
      "safety_note": "Не выполнять принудительное ручное переопределение."
    }
  ],
  "causality_graph": {
    "nodes": [
      {"id": "node_sat_viol", "label": "Симптом: SAT > SPT", "type": "symptom"},
      {"id": "node_hyp_valve", "label": "Гипотеза: Заклинивание", "type": "hypothesis"}
    ],
    "links": [
      {"source": "node_sat_viol", "target": "node_hyp_valve", "relation": "SUPPORTS"}
    ]
  }
}
```

---

### 2.5. Сопоставление норма/авария (Matched Pairs)

#### `GET /api/v1/matched-pairs`
Возвращает список сопоставимых пар сценариев:
```json
[
  {
    "pair_id": "pair-lbnl-summer-25",
    "status": "CONFIRMED_MATCHED",
    "label": "SIMULATION_PHYSICAL_COUNTERFACTUAL",
    "baseline_scenario_id": "sc-lbnl-baseline-annual",
    "fault_scenario_id": "sc-lbnl-valve-stuck-25",
    "justification": "Идентичный метеорологический файл TMY Chicago."
  },
  {
    "pair_id": "pair-csiro-unmatched-blocked",
    "status": "BLOCKED_INCOMPARABLE",
    "label": "INCOMPARABLE_SOURCE",
    "justification": "Блокировка: температура наружного воздуха различается более чем на 12 °C; разный тепловой сезон."
  }
]
```

---

## 3. Требования к обработке ошибок и статусам HTTP

| Код ошибки | Код ответа | Описание поведения |
|---|---|---|
| `INCOMPATIBLE_DATASET_DOMAIN` | HTTP 400 | Запрос инференса модели на физически несогласованном домене (например, модель LBNL на CSIRO). |
| `SIGNAL_PHYSICALLY_ABSENT` | HTTP 422 | Запрос анализа по каналу, физически отсутствующему в выбранном профиле наблюдаемости. |
| `INSUFFICIENT_ACTUATOR_EXCITATION` | HTTP 200 (статус в теле) | Команда клапана постоянна ($\Delta \text{cmd} < 0.15$), статус слежения не может быть объявлен. |
| `INCOMPARABLE_SCENARIO_PAIR` | HTTP 400 | Попытка запроса наложения траекторий для несопоставимой пары без общего метеофайла. |
