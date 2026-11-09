import { useEffect, useMemo, useState } from 'react';
import ReactECharts from 'echarts-for-react';
import type { components } from '../types/virtual-sensor-research.generated';

type Metadata = components['schemas']['Metadata'];
type Day = components['schemas']['Day'];

const endpoint = '/api/research/virtual-sensors';
const panel = 'rounded-xl border border-slate-700 bg-slate-900 p-4 sm:p-5';

async function get<T>(url: string, signal: AbortSignal): Promise<T> {
  const response = await fetch(url, { signal });
  if (!response.ok) throw new Error(response.status === 503 ? 'Исследовательский реестр недоступен.' : 'Не удалось загрузить окно.');
  return response.json();
}

function timeLabel(minute: number) {
  return [Math.floor(minute / 60), minute % 60].map(value => String(value).padStart(2, '0')).join(':');
}

function Values({ label, value, id }: { label: string; value: number; id: string }) {
  return <div className="min-w-0 rounded-lg bg-slate-800 p-3">
    <dt className="text-sm text-slate-300">{label}</dt>
    <dd data-testid={id} className="mt-1 break-all font-mono text-lg">{value.toFixed(9)}</dd>
  </div>;
}

export function VirtualSensorResearchPage() {
  const [meta, setMeta] = useState<Metadata>();
  const [loadedResult, setResult] = useState<Day>();
  const [caseId, setCaseId] = useState('healthy');
  const [day, setDay] = useState('');
  const [pointIndex, setPointIndex] = useState(0);
  const [error, setError] = useState('');
  const result = loadedResult?.case.id === caseId && loadedResult.day === day ? loadedResult : undefined;
  const selectedCase = meta?.cases.find(item => item.id === caseId);

  useEffect(() => {
    const controller = new AbortController();
    get<Metadata>(endpoint, controller.signal).then(data => {
      setMeta(data);
      setDay(data.cases.find(item => item.id === 'healthy')?.days[0] ?? '');
    }).catch((failure: Error) => { if (!controller.signal.aborted) setError(failure.message); });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (!day) return;
    const controller = new AbortController();
    setResult(undefined);
    setPointIndex(0);
    setError('');
    const query = new URLSearchParams({ case: caseId, day });
    get<Day>(`${endpoint}/day?${query}`, controller.signal)
      .then(data => { if (!controller.signal.aborted) setResult(data); })
      .catch((failure: Error) => { if (!controller.signal.aborted) setError(failure.message); });
    return () => controller.abort();
  }, [caseId, day]);

  const chart = useMemo(() => {
    const actual: [number, number | null][] = [];
    const predicted: [number, number | null][] = [];
    const residual: [number, number | null][] = [];
    for (const point of result?.points ?? []) {
      const minute = Number(point.timestamp.slice(11, 13)) * 60 + Number(point.timestamp.slice(14, 16));
      const last = actual[actual.length - 1];
      if (last && minute > last[0] + 1) {
        actual.push([last[0] + 1, null]);
        predicted.push([last[0] + 1, null]);
        residual.push([last[0] + 1, null]);
      }
      actual.push([minute, point.actual]);
      predicted.push([minute, point.predicted]);
      residual.push([minute, point.absolute_residual]);
    }
    return {
      animation: false, grid: { left: 47, right: 43, top: 58, bottom: 35 },
      legend: { top: 0, textStyle: { color: '#cbd5e1' } },
      tooltip: { trigger: 'axis' },
      xAxis: { type: 'value', min: 0, max: 1440, interval: 360, axisLabel: { formatter: timeLabel, color: '#cbd5e1' } },
      yAxis: [
        { type: 'value', scale: true, name: 'SAT, °F', nameTextStyle: { color: '#cbd5e1' }, axisLabel: { color: '#cbd5e1' } },
        { type: 'value', min: 0, name: '|Δ|, °F', nameTextStyle: { color: '#e9d5ff' }, axisLabel: { color: '#e9d5ff' }, splitLine: { show: false } },
      ],
      series: [
        { name: 'Измерение', type: 'line', data: actual, connectNulls: false, showSymbol: false, color: '#38bdf8' },
        { name: 'Прогноз', type: 'line', data: predicted, connectNulls: false, showSymbol: false, color: '#fbbf24',
          lineStyle: { type: 'dashed' } },
        { name: 'Абс. остаток', type: 'line', yAxisIndex: 1, data: residual, connectNulls: false,
          showSymbol: false, color: '#d8b4fe', lineStyle: { type: 'dotted' } },
      ],
    };
  }, [result]);
  const point = result?.points[pointIndex];

  return <main className="mx-auto max-w-6xl space-y-5 p-4 sm:p-8">
    <header className="space-y-3">
      <a href="/research" className="text-sm text-sky-300 underline">К лаборатории</a>
      <div className="flex flex-wrap gap-2 text-xs font-semibold tracking-wide">
        <span className="rounded bg-sky-950 px-2 py-1 text-sky-200">SIMULATED_BENCHMARK</span>
        <span className="rounded bg-amber-950 px-2 py-1 text-amber-200">RESEARCH_ONLY</span>
      </div>
      <h1 className="text-3xl font-bold sm:text-4xl">Виртуальный датчик SAT</h1>
      <p className="max-w-3xl text-slate-300">Сравнение температуры приточного воздуха и прогноза LightGBM на архивном окне LBNL SD-AHU. Тревога обозначает аномалию модели в симуляции. BASIC описывает доступность каналов этого стенда. FULL в сравнении со статьёй включает дополнительные симуляционные величины.</p>
    </header>
    {error && <p role="alert" className={panel}>{error} NOT_EVALUABLE</p>}
    {!meta && !error && <p role="status">Проверка исследовательского реестра…</p>}
    {meta && <section className={panel + ' space-y-2'} aria-labelledby="research-boundary">
      <h2 id="research-boundary" className="text-xl font-semibold">Границы проверки</h2>
      <p className="text-sm text-slate-300">Результаты относятся к ранее изученной когорте симуляции. Для независимой проверки пока нет источника с подтверждённой совместимостью всех входов.</p>
      <p data-testid="external-validation" className="break-words font-mono text-xs text-amber-200">{meta.evidence_boundary.external_validation}</p>
    </section>}
    {meta && <section className={panel + ' space-y-3'} aria-label="Архивное окно">
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="space-y-1"><span className="block text-sm text-slate-300">Сценарий</span>
          <select aria-label="Сценарий" value={caseId} className="w-full rounded border border-slate-600 bg-slate-950 p-2"
            onChange={event => {
              const next = meta.cases.find(item => item.id === event.target.value);
              if (next) { setCaseId(next.id); setDay(next.days.includes(day) ? day : next.days[0]); }
            }}>
            {meta.cases.map(item => <option key={item.id} value={item.id}>{item.id === 'healthy' ? 'Исправный прогон' : 'SA +2 °C · условное соответствие'}</option>)}
          </select>
        </label>
        <label className="space-y-1"><span className="block text-sm text-slate-300">Дата источника</span>
          <select aria-label="Дата источника" value={day} onChange={event => setDay(event.target.value)} className="w-full rounded border border-slate-600 bg-slate-950 p-2">
            {selectedCase?.days.map(date => <option key={date}>{date}</option>)}
          </select>
        </label>
      </div>
      {selectedCase && <p className="break-words text-sm text-slate-300"><code>{selectedCase.member}</code> · <strong>{selectedCase.alias_status}</strong></p>}
    </section>}
    {meta && day && !result && !error && <p role="status">Расчёт архивного окна…</p>}
    {result && <section className={panel + ' space-y-4'} aria-label="Исследовательский результат">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h2 className="text-xl font-semibold">SAT-only · суточный результат</h2>
          <p className="text-sm text-slate-300">Среднее минутных z. Порог тревоги z &gt; {result.threshold}. MODEL_ANOMALY означает отклонение измерения от прогноза SAT.</p>
        </div>
        <span data-testid="research-alert" role="status" className="rounded bg-slate-800 px-3 py-1 text-sm">{result.alert ?? (result.status === 'EVALUATED' ? 'Тревог нет' : result.status)}</span>
      </div>
      <p data-testid="coverage" className="text-sm text-slate-300">Оценено {result.evaluated_minutes} из {result.calendar_minutes} мин ({(result.coverage * 100).toFixed(1)}%). Режим {result.metadata.mode}.</p>
      {result.running_minutes != null && <p className="text-sm text-slate-300">
        В режиме RUNNING покрыто {result.evaluated_minutes} из {result.running_minutes} мин. Непрерывный участок до {result.continuous_minutes} мин.
      </p>}
      <p className="break-words text-sm text-slate-300">Политика {result.metadata.policy_version}. Минимум 120 минут, включая 30 подряд, и 80% минут RUNNING.</p>
      {result.reason && <p role="status">{result.reason}</p>}
      {result.daily_score != null && <dl><Values label="Суточный score" value={result.daily_score} id="daily-score" /></dl>}
      {point && <>
        <figure className="min-w-0">
          <div role="img" aria-label="Измерение и прогноз SAT, абсолютный остаток на правой оси. Разрывы обозначают минуты без оценки.">
            <ReactECharts option={chart} style={{ height: 270 }} />
          </div>
          <figcaption className="text-sm text-slate-300">Разрывы обозначают минуты без оценки. Значения доступных минут можно прочитать ползунком ниже.</figcaption>
        </figure>
        <label className="block text-sm text-slate-300">Минута окна · <span data-testid="point-timestamp">{point.timestamp}</span>
          <input className="mt-2 block w-full" type="range" aria-label="Минута окна" min={0} max={result.points.length - 1} value={pointIndex} aria-valuetext={point.timestamp}
            onChange={event => setPointIndex(Number(event.target.value))} />
        </label>
        <dl className="grid grid-cols-2 gap-2 lg:grid-cols-4">
          <Values label="Измерение, °F" value={point.actual} id="actual" />
          <Values label="Прогноз, °F" value={point.predicted} id="predicted" />
          <Values label="Абс. остаток, °F" value={point.absolute_residual} id="absolute-residual" />
          <Values label="Минутный z" value={point.z} id="minute-z" />
        </dl>
      </>}
    </section>}
    {meta && <section className={panel + ' space-y-3'} aria-labelledby="research-methods">
      <h2 id="research-methods" className="text-xl font-semibold">Методы исследования</h2>
      <p className="text-sm text-slate-300">Здесь доступны два архивных окна по семь дней. Метрики полной когорты и границы сравнения методов приведены в отчёте BP-ML-VALIDATION-04.</p>
      <dl className="grid gap-2 sm:grid-cols-3">
        {meta.methods.map(method => <div key={method.id} className="min-w-0 rounded-lg bg-slate-800 p-3 text-sm">
          <dt className="font-semibold">{{
            SAT_ONLY: 'SAT-only virtual sensor',
            SYSTEM_MAX_8: 'Восьмицелевой агрегированный детектор',
            SAT_MINUS_SETPOINT: 'Простая SAT−уставка',
          }[method.id]}</dt>
          <dd className="text-slate-300">{method.availability === 'ARCHIVE_DAY_API' ? 'Доступен в архивном окне' : 'Полная когорта · исследовательский отчёт'}</dd>
          <dd className="break-all text-slate-300">{method.version}</dd>
        </div>)}
      </dl>
    </section>}
    {meta && <details className={panel + ' space-y-3 text-sm'}>
      <summary className="cursor-pointer text-lg font-semibold">Каналы, модель и происхождение</summary>
      <p className="break-all">LightGBM {meta.versions.lightgbm} · {meta.model_id} · {meta.arm}</p>
      <p>{Object.entries(meta.versions).map(([name, version]) => `${name} ${version}`).join(' · ')}</p>
      <p>Часы источника без подтверждённого смещения UTC · {meta.timestamp_format}. Температуры в °F, условные смещения сценариев в °C.</p>
      <p><a href="https://doi.org/10.25984/1881324" className="text-sky-300 underline">Официальный LBNL SD-AHU</a> · <a href="https://doi.org/10.3390/s26113465" className="text-sky-300 underline">Публикация</a> · PAPER_FULL_REPRO: INDEPENDENT_REIMPLEMENTATION.</p>
      <p>Все четыре соответствия <code>coi_bias</code> → <code>sa_bias</code> (±2/±4 °C) имеют статус <strong>UNVERIFIED_PUBLISHER_ALIAS</strong>.</p>
      <p>В наличии в окне: {(result?.present_channels ?? []).join(', ') || 'ожидается проверка окна'}</p>
      <p>Входы в порядке модели: {meta.feature_order.map(field => `${field} (${meta.feature_roles[field]})`).join(', ')}</p>
      <p>Train: {meta.split.train_first} – {meta.split.train_last}. Calibration: {meta.split.calibration_first} – {meta.split.calibration_last}. Test: {meta.split.test_start} – {meta.split.test_end_exclusive} (исключая правую границу).</p>
      <dl className="grid gap-2 break-all font-mono">
        {Object.entries({ source: meta.source_sha256, member: selectedCase?.member_sha256, TTL: meta.ttl_sha256, schema: meta.schema_sha256, protocol: meta.protocol_sha256, pilot: meta.integration_protocol_sha256 }).map(([label, value]) =>
          <div key={label}><dt className="text-slate-400">{label} SHA-256</dt><dd>{value}</dd></div>)}
      </dl>
    </details>}
  </main>;
}
