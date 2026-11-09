# Investigator · интеграция API v1

`frontend/src/api/investigatorV1.ts` получает параметры и ответы из `frontend/src/types/openapi-v1.generated.ts`. Генерация и проверка повторяются из корня снимка.

```sh
npx --yes openapi-typescript@7.10.1 contracts/openapi-v1.yaml -o frontend/src/types/openapi-v1.generated.ts
npm --prefix frontend run build
python contracts/check_fixture_types.py
```

Основной Investigator получает каталог, сигналы, окно и диагностику с FastAPI. При ошибке отображается код HTTP. Время передаётся в ECharts как исходная строка, пропуски отмечаются отдельной пустой точкой. UI_MOCK_V0 выбирается отдельно и маркирует все свои результаты `DEMO_FIXTURE`. Monitoring, Diagnostics и Research используют прежний клиент и отображаются как `LEGACY_ANALYSIS`.
