# Журнал спецификации статьи

| Узел | Статус | Первичный источник | Поле и результат |
|---|---|---|---|
| Данные | published / verified_from_data | §2.2, Table 2, inventory | 12 уникальных полных 30+Datetime payload, два семейства дублей, алиасы описаны в D0. |
| Цели | published / verified_from_data | §2.3, Algorithm 1, Table 3 | SA_TEMP, MA_TEMP, RA_TEMP, ZONE_TEMP_1…5. OA_TEMP доступен как признак, исключён как цель. |
| RDF | published | §2.3, Algorithm 1 | rdflib, hasPoint/hasPart и inverse, union всех доступных соседей, min=3, fallback только когда граф не дал целей. feeds зафиксирован в графе, псевдокод не использует его для сокращения union. |
| Время и режим | published / implementation_choice | §2.4–2.5 | Datetime source-local, SYS_CTL>=1, 80/20 eligible minutes. На граничном дне fault начинаем не раньше первой validation минуты. hour целое, month 1…12, dow 0…6. Точный minute/day cutoff UNSPECIFIED_BY_PAPER. |
| LightGBM | published / unknown | §2.4 | 300/6/0.05/0.8/0.8/42/50; LightGBM версии автора и subsample_freq UNSPECIFIED_BY_PAPER. Здесь 4.6.0 и freq=0, bagging выключен, colsample активен. |
| Исключение target | published / inconsistency | Algorithm 1, Figure 15 | Ни один target не участвует в собственных признаках. SA_TEMP на рисунке является неразрешённой несогласованностью. SYS_CTL и derived occupancy представлены разными именами PAPER. |
| Нормировка | published / implementation_choice | §2.4–2.5, Tables 4,6 | abs error, здоровый validation mean/SD, ddof=0 как зафиксированная трактовка, near-zero abstain. Дневное среднее per-target, max system, порог >3. Healthy validation одновременно negative comparator, возможен optimistic bias. |
| Isolation | published | §2.6, Table 7 | full scenario median daily per-target, ранги и разница первых двух. Строгий/BASIC режим использует test only. Ранжирование аномальности. |
| Discrimination | published / unknown | §2.7, Table 8 | OA_DMPR_DM/OA_DMPR, CHWC_VLV_DM/CHWC_VLV, MAE. Граница окна UNSPECIFIED_BY_PAPER. Здесь native eligible оценочный период, отдельно полный eligible период. BASIC запрещён. |
| PCA | published / unknown | §2.8, Table 9 | PCA 95% all numeric standardized train only, дневной MSE, sklearn full SVD зафиксирован здесь. Порог PCA UNSPECIFIED_BY_PAPER, отдельно z3 extension. |
| Ridge и PCA-input-matched | implementation_choice | не из статьи | Ridge α=1 и PCR 95% по тем же per-target входам. SAT comparator abs SAT−SP daily. |
| Стабильность | published / implementation_choice | §4.3 | seed 42 основной. 0…9 отдельный запуск только при ресурсах. Табличные результаты статьи ориентир, не критерий подбора. |
| Код и дополнения | unknown | §6, Data Availability | Код по запросу, общедоступный авторский файл не найден в публикации. Версия и параметры, не указанные в §2, не приписываются авторам. |

[Chahine & Noura, 2026](https://doi.org/10.3390/s26113465)
