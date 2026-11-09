# Проверки BP-ML-VALIDATION-04

| Проверка | Результат | Квитанция |
|---|---|---|
| Полный набор pytest базы и тесты 04 | PASS, 363 теста. Включены проверки отсутствующего BASIC-сигнала, policy, барьера FDD и отказа при посторонних/дублирующихся параметрах. | `evidence/pytest.log` |
| Frontend strict TypeScript и сборка | PASS. Vite сообщил о размере крупного существующего общего чанка. | `evidence/build.log` |
| OpenAPI | PASS, восемь фикстур и побайтное совпадение нового research OpenAPI и сгенерированных TypeScript-типов. | `evidence/openapi.log` |
| Реальный HTTP и Playwright 1440×900, 390×844 | PASS, 10 981 минутная точка, 14 архивных пар «прогон × дата», отказ для внешних параметров, видимый STOP-статус. Минутные значения совпали, максимум отличия суточного score 3,55 × 10⁻¹⁵. | `evidence/http-playwright.log`, `screenshots/` |
| Docker backend smoke | NOT_TESTED. Docker Engine вернул HTTP 500 на ping, Windows endpoint отсутствовал, повтор после запуска и 16 попыток не восстановил доступ. | `evidence/docker-build.log`, `evidence/docker-smoke.log`, `evidence/docker-diagnosis.log`, `evidence/docker-smoke-final.log` |
| Compose | Статическая конфигурация PASS. Запуск стека в этом задании не проверялся. | `evidence/compose-config.log` |
| Рабочие данные и SQLite | PASS, 562 исходных файла совпали по SHA-256 до и после. Отдельная HTTP SQLite совпала побайтно. Проверка копий архивов REPRO-02/03 после работы также прошла. | `evidence/storage-integrity.log`, `evidence/original-before.sha256`, `evidence/original-after.sha256` |
| Внешний инференс | STOP, пригодность источника не доказана. Проверена семантика и частота без вычисления score. | `EXTERNAL_FEASIBILITY.md`, `EXTERNAL_SOURCE_INVENTORY.json` |
