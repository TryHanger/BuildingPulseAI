# API CONTRACT — Спецификация REST API BuildingPulse AI

Базовый префикс всех маршрутов: `/api`

### 1. GET `/api/health`
Проверка работоспособности сервиса и доступности базы данных.
**Ответ:**
```json
{
  "status": "ok",
  "service": "buildingpulse-api",
  "database": "ok"
}
```

---

### 2. GET `/api/datasets`
Список зарегистрированных датасетов.
**Ответ:**
```json
{
  "items": [
    {
      "id": "ds_fa24dd6dbcdb",
      "name": "lbnl_AHU_annual.csv",
      "source_kind": "SIMULATED_BENCHMARK",
      "source_url": "https://faultdetection.lbl.gov/dataset/simulated-sd-ahu/",
      "license_note": "Open Access / US DOE",
      "sha256": "3e4b...",
      "size_bytes": 140571390,
      "imported_at": "2026-11-02T12:51:00",
      "processing_version": "1.0.0",
      "status": "READY",
      "provenance_note": "Официальный датасет LBNL Single Duct AHU..."
    }
  ],
  "total": 1
}
```

---

### 3. GET `/api/scenarios?dataset_id=...`
Список сценариев с временными границами и исходными метками неисправностей.
**Ответ:**
```json
{
  "items": [
    {
      "id": "sc_d11cbb117b57",
      "dataset_id": "ds_fa24dd6dbcdb",
      "name": "Сценарий: lbnl_AHU_annual.csv",
      "start_at": "2018-01-01 01:00:00",
      "end_at": "2018-01-08 00:59:00",
      "sample_interval_seconds": 60,
      "timezone_status": "unknown",
      "source_fault_label": "FAULT_FREE",
      "source_fault_label_type": "FAULT_FREE",
      "description": "...",
      "total_rows": 10080
    }
  ],
  "total": 1
}
```

---

### 4. GET `/api/sensors?scenario_id=...`
Справочник каналов измерений и команд для сценария.
**Ответ:**
```json
{
  "items": [
    {
      "id": 1,
      "scenario_id": "sc_d11cbb117b57",
      "canonical_key": "OA_TEMP",
      "original_column": "OA_TEMP",
      "display_name_ru": "Температура наружного воздуха",
      "unit_raw": "degF",
      "unit_normalized": "degF",
      "component": "OUTDOOR",
      "signal_kind": "MEASUREMENT",
      "is_basic": true,
      "is_available": true
    }
  ],
  "total": 30
}
```

---

### 5. GET `/api/telemetry?scenario_id=...&channels=SA_TEMP,MA_TEMP&start=...&end=...&max_points=1500`
Запрос временных рядов с серверным downsampling Min-Max.
**Ответ:**
```json
{
  "scenario_id": "sc_d11cbb117b57",
  "range": {
    "start": "2018-01-01 01:00:00",
    "end": "2018-01-08 00:59:00",
    "timezone_status": "unknown"
  },
  "series": [
    {
      "channel": "SA_TEMP",
      "display_name_ru": "Температура приточного воздуха",
      "unit": "degF",
      "component": "FAN",
      "signal_kind": "MEASUREMENT",
      "points": [
        ["2018-01-01 01:00:00", 66.37],
        ["2018-01-01 01:01:00", 66.37]
      ]
    }
  ],
  "sampling": {
    "aggregated": true,
    "method": "min_max_bucket",
    "returned_points": 1498,
    "total_source_points": 10080
  },
  "source_kind": "SIMULATED_BENCHMARK"
}
```

---

### 6. POST `/api/datasets/import` (multipart/form-data)
Импорт CSV файла с автоматическим сопоставлением каналов и конвертацией в Parquet.

---

### 7. GET `/api/data-quality?scenario_id=...`
Отчет о качестве данных (монотонность, дубликаты времени, разрывы в связи, замирание сигналов).

---

### 8. POST `/api/diagnostics/run-rules`
Запуск детерминированных правил детекции на заданном интервале.

---

### 9. GET `/api/diagnostics/events?scenario_id=...`
Получение списка зафиксированных диагностических событий.
