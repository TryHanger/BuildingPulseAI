# BuildingPulse — реестр решений (начальные записи)

**Политика:** один статус решения и причина изменения. Новая публикация НЕ меняет стек автоматически. Исторические эксперименты B0–B5 не переименовываем задним числом; новый план — `PLAN-2026-11-07-v1.0`, эксперимент `EXP-HYBRID-v1`.

| ID | Предмет | Текущее решение | Факт / ограничение | Условие пересмотра |
|---|---|---|---|---|
| D001 | Продукт | GO: interactive AHU investigator на существующем FastAPI/React | Визуализация и воспроизведение возможно без ML | Если аудит обнаружит недоступность базового runtime |
| D002 | `coi_bias` vs `sa_bias` | BLOCK научный claim | Официальный PDF `sa_bias_*`; source ZIP до независимого сверения непроверен | Хэши/метаданные реального архива и подтверждённая роль SAT |
| D003 | LBNL BASIC | GO с source role policy | CHWC_VLV_DM Y; CHWC_VLV, SYS_CTL, SA_CFM N | Новый явно обоснованный профиль EXTRA, никогда BASIC |
| D004 | Mode state machine | GO раньше ML | SAT control зависит от OAT/economizer/fan и переходов | Только новый официальный control sequence конкретной AHU |
| D005 | Open-FDD rules | CONDITIONAL, 1–3 адаптера | Python oracle != platform; verification pending | Проверка pinned version, inputs, prerequisites, unit tests |
| D006 | LightGBM | CONDITIONAL model candidate | Двухдневный smoke — не научная валидация | Full healthy split + fair comparison vs Ridge/PCA |
| D007 | Controller effort | CONDITIONAL independent specialist | Сильный confounding load/weather/mode | Known normal envelope + incremental value evidence |
| D008 | BN / MAPIE | PARK | Нет независимой полной калибровки | Confirmed labels + scope-specific calibration |
| D009 | Thermal balance BASIC | STOP | Нет необходимых независимых расхода и влажности | Реальная проверенная richer sensor panel |
| D010 | Contract | REPLACE educational prototype | Review 12 negative cases; five statuses not implemented | Strict typed V1 with negative tests |
| D011 | Offline PELT | CONDITIONAL retrospective only | Full-series future lookahead | UI clearly retrospective / separate online algo |
| D012 | Research protocol | FREEZE `EXP-HYBRID-v1` | Old B0–B5 definitions contradictory | Owner and auditor approval with new version |
| D013 | Final demo | GO rules-first | Must not depend on unverified ML/alias | Source-verified recorded example |
| D014 | Frontend work | GO parallel with mock fixtures | No backend model required to build layout | OpenAPI v1 handoff, then adapter integration |
