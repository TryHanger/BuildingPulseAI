# Карточки моделей · BP-ML-REPRO-01

| Модель | Обучение | Score и интерпретация |
|---|---|---|
| LightGBM | 8 регрессоров по BRICK-соседям и времени, healthy train | per-target abs residual с калибровкой, mean daily затем max. Sensor rank — медиана дневных residual scores, причина не установлена. |
| Ridge | Те же цели и поля, StandardScaler на train, α=1 | Та же residual математика. Линейный ориентир. |
| PCA-input-matched | Та же регрессионная постановка, train StandardScaler и 95% PCA, OLS в компонентном пространстве | Та же residual математика и сопоставимый per-target rank. |
| PCA-paper | Train StandardScaler, 95% PCA, все разрешённые числовые колонки | Mean daily standardized reconstruction MSE. В STRICT/BASIC набор ограничен постановкой. Для порога применена локальная daily z-калибровка. |
| SAT setpoint | Healthy daily calibration | Среднее абсолютное отклонение SAT−SP, ориентир чувствительности замкнутого контура. |
| Mixing residual | Healthy daily calibration, только FULL | Среднее абсолютной разности MAT и α·OA+(1−α)·RA. α — модельное положение заслонки. |

Входы и training source SHA находятся в run.json каждого режима. Seed 42 основной, отдельный файл seed sweep. Предсказания и метрики описывают уже известные симуляции. Ранжирование и MAE пар команда/положение не подтверждают физическую причину. Модели не экспортируются в продукт. Статус для отсутствующего входа — NOT_EVALUABLE.
