import { useEffect, useMemo, useState } from 'react';
import { investigatorV1 } from '../api/investigatorV1';
import { AHUIndustrialSchematic } from '../components/AHUIndustrialSchematic';
import { demoDatasetId, EventEvidence, InvestigationDetails, ReportLinks } from '../components/InvestigationEvidence';
import { ReplayClockBar } from '../components/ReplayClockBar';
import { sourceSeconds, SynchronousTelemetryCharts } from '../components/SynchronousTelemetryCharts';
import type { components } from '../types/openapi-v1.generated';

type Schema = components['schemas'];
type Panel = Schema['Panel'];
type WindowData = { catalog: Schema['RuntimeSignal'][]; series: Schema['RuntimeSeries'] };
const modeColors: Record<Schema['RuntimeFanMode'], string> = {
  OFF: 'bg-slate-500',
  UNKNOWN: 'bg-violet-500',
  TRANSITION_HOLD: 'bg-amber-500',
  RUNNING: 'bg-emerald-500',
};
const qualityLabels: Record<Schema['RuntimeQualityFlag'], string> = {
  MISSING_COLUMN: 'Канал отсутствует',
  MISSING_VALUE: 'Пропуск значения',
  NON_NUMERIC_OR_NON_FINITE: 'Некорректное число',
  NON_BINARY_STATUS: 'Статус вне 0/1',
  COMMAND_OUT_OF_RANGE: 'Команда вне [0, 1]',
  MEASUREMENT_FRACTION_OUT_OF_RANGE: 'Измеренная доля вне [0, 1]',
  SUSPECT_TEMPERATURE: 'Подозрительная температура',
  SEMANTICS_UNVERIFIED: 'Единица не проверена',
};
const card = 'min-w-0 rounded-xl border border-slate-800 bg-slate-900 p-4';

function ApiError({ message }: { message: string }) {
  return <p role="alert" className="rounded border border-rose-700 p-3 text-rose-300">
    Ошибка API v1 · {message}
  </p>;
}

export function RuntimeInvestigatorPage({ initialDatasetId, initialTimestamp }: {
  initialDatasetId?: string;
  initialTimestamp?: string;
}) {
  const isDemo = initialDatasetId === demoDatasetId;
  const [datasets, setDatasets] = useState<Schema['RuntimeDataset'][]>();
  const [error, setError] = useState('');
  const [selected, setSelected] = useState('');
  const [panel, setPanel] = useState<Panel>('BASIC');
  useEffect(() => {
    const controller = new AbortController();
    investigatorV1.datasets(controller.signal, isDemo).then(({ items }) => {
      if (controller.signal.aborted) return;
      const requested = items.find(item => item.dataset_id === initialDatasetId);
      if (initialDatasetId && !requested) {
        setError('Запрошенный источник отсутствует в реестре выбранного режима.');
        return;
      }
      setDatasets(items);
      setSelected((requested ?? items.find(item => item.availability === 'AVAILABLE') ?? items[0])?.dataset_id ?? '');
    }).catch((failure: Error) => {
      if (!controller.signal.aborted) setError(failure.message);
    });
    return () => controller.abort();
  }, [initialDatasetId, isDemo]);

  const dataset = datasets?.find(item => item.dataset_id === selected);
  return (
    <main className="mx-auto max-w-[1920px] space-y-4 p-3 sm:p-4">
      <section className={card}>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h1 className="text-lg font-semibold">AHU Investigator</h1>
          <a className="text-sm text-sky-300 underline" href="/assets/ahu-g36">Сценарий G36-5wk</a>
        </div>
        <p className="mb-3 text-sm text-slate-300">{isDemo ? 'DEMO_FIXTURE · синтетические исходные ряды G4' : 'Исходные ряды симуляции LBNL SD-AHU · API v1'}</p>
        {error && <ApiError message={error} />}
        {!error && !datasets && <p role="status">Загрузка датасетов…</p>}
        {datasets?.length === 0 && <p>В реестре нет датасетов.</p>}
        {dataset && <div className="flex flex-wrap gap-3 text-sm">
          <label className="min-w-0">Датасет
            <select className="ml-2 max-w-[min(16rem,65vw)] rounded bg-slate-800 p-2" value={selected}
              onChange={event => setSelected(event.target.value)}>
              {datasets?.map(item => <option key={item.dataset_id} value={item.dataset_id}>
                {item.name} · {item.is_full_year ? 'год' : 'срез'} · {item.rows ?? '—'} строк · {item.last ?? '—'} · {item.dataset_id}{item.availability === 'MISSING_SOURCE' ? ' · файл отсутствует' : ''}
              </option>)}
            </select>
          </label>
          <label>Панель
            <select className="ml-2 rounded bg-slate-800 p-2" value={panel}
              onChange={event => setPanel(event.target.value as Panel)}>
              <option value="BASIC">BASIC</option>
              <option value="EXTRA">EXTRA_SIMULATED</option>
            </select>
          </label>
        </div>}
      </section>
      {dataset && <RuntimeDataset key={`${selected}:${panel}`} dataset={dataset} panel={panel}
        initialTimestamp={(!initialDatasetId || selected === initialDatasetId) ? initialTimestamp : undefined} />}
    </main>
  );
}

function RuntimeDataset({ dataset, panel, initialTimestamp }: {
  dataset: Schema['RuntimeDataset']; panel: Panel; initialTimestamp?: string;
}) {
  const initialStart = initialTimestamp && /^2018-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$/.test(initialTimestamp)
    && dataset.first && dataset.last && initialTimestamp >= dataset.first && initialTimestamp <= dataset.last
    ? initialTimestamp : undefined;
  const query = new URLSearchParams(window.location.search);
  const incidentId = initialStart && query.get('incident_id') || undefined;
  const confirmedAt = incidentId && query.get('confirmed_at') || undefined;
  const windowStart = incidentId && query.get('window_start');
  const replayStart = windowStart && dataset.first && initialStart && windowStart >= dataset.first
    && windowStart <= initialStart ? windowStart : initialStart;
  const [starts, setStarts] = useState<Array<string | undefined>>([replayStart]);
  const [initialCursor, setInitialCursor] = useState(initialStart);
  const start = starts[starts.length - 1];
  const [seek, setSeek] = useState(initialStart ?? dataset.first ?? '');
  const [seekError, setSeekError] = useState('');
  return <>
    <section className={`${card} text-sm`}>
      <div>{dataset.clock_kind} · шаг {dataset.sample_seconds} с</div>
      {dataset.first && dataset.last && <div>
        {dataset.is_full_year ? 'Годовой файл' : 'Срез'} · {dataset.rows} строк · {dataset.first} → {dataset.last}
      </div>}
      <form className="my-2 flex flex-wrap items-end gap-2" onSubmit={event => {
        event.preventDefault();
        if (!/^2018-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$/.test(seek)
            || !dataset.first || !dataset.last || seek < dataset.first || seek > dataset.last) {
          setSeekError('Введите время источника в диапазоне датасета в формате 2018-MM-DDTHH:MM:SS.');
          return;
        }
        setSeekError('');
        setInitialCursor(undefined);
        setStarts([seek]);
      }}>
        <label className="grid gap-1">
          Время источника
          <input className="rounded bg-slate-800 p-2 font-mono" type="text" value={seek}
            placeholder="2018-MM-DDTHH:MM:SS" maxLength={25}
            disabled={dataset.availability !== 'AVAILABLE'}
            onChange={event => { setSeek(event.target.value); setSeekError(''); }} />
        </label>
        <button type="submit" className="rounded bg-slate-800 px-3 py-2 disabled:opacity-40"
          disabled={dataset.availability !== 'AVAILABLE'}>Перейти ко времени</button>
      </form>
      {seekError && <p role="alert" className="text-amber-300">{seekError}</p>}
      <div className="break-all text-xs text-slate-400">SHA-256 {dataset.source_sha256}</div>
      <div className="mt-2 text-amber-300">{dataset.pair_status} · сопоставимость сценариев не проверена</div>
      <button type="button" className="mt-1 text-slate-400" disabled>Наложение недоступно</button>
    </section>
    <RuntimeWindow key={start ?? 'first'} datasetId={dataset.dataset_id} sourceSha={dataset.source_sha256} panel={panel} start={start}
      initialCursor={initialCursor} incidentId={incidentId} confirmedAt={confirmedAt}
      onPrevious={starts.length > 1 ? () => setStarts(items => items.slice(0, -1)) : undefined}
      onNext={next => setStarts(items => [...items, next])} />
  </>;
}

function ModeTimeline({ modes, active, onSeek }: {
  modes: Schema['RuntimeModes'];
  active: Schema['RuntimeModeSegment'] | undefined;
  onSeek: (timestamp: string) => void;
}) {
  const { segments, time_quality: quality } = modes;
  if (!segments.length) return null;
  const origin = sourceSeconds(segments[0].first);
  const duration = sourceSeconds(segments[segments.length - 1].last) - origin + modes.sample_seconds;
  return <section className={`${card} space-y-2 text-xs`} aria-label="Сегменты режима">
    <div className="flex flex-wrap justify-between gap-2">
      <h2 className="font-semibold">Сегменты режима · исходное время</h2>
      <span className="text-slate-400">Удержание {modes.mode_policy.hold_seconds / 60} мин · v{modes.mode_policy.version}</span>
    </div>
    <div className="relative h-4 rounded bg-slate-950">
      {segments.map((segment, index) => {
        const left = sourceSeconds(segment.first) - origin;
        const next = segments[index + 1];
        const end = Math.min(sourceSeconds(segment.last) - origin + modes.sample_seconds,
          next ? sourceSeconds(next.first) - origin : duration);
        const label = `${segment.mode} · ${segment.first} → ${segment.last}`;
        return <button type="button" key={segment.first} aria-label={label} title={label}
          aria-current={segment === active ? 'true' : undefined}
          className={`absolute top-0 h-full rounded-sm ${modeColors[segment.mode]} ${segment === active ? 'ring-2 ring-white z-10' : 'opacity-80'}`}
          style={{ left: `${100 * left / duration}%`, width: `${100 * (end - left) / duration}%` }}
          onClick={() => onSeek(segment.first)} />;
      })}
    </div>
    <div className="flex flex-wrap gap-3 text-slate-300">
      {(Object.keys(modeColors) as Schema['RuntimeFanMode'][]).map(mode => <span key={mode} className="flex items-center gap-1">
        <span className={`h-2 w-2 rounded ${modeColors[mode]}`} />{mode}
      </span>)}
    </div>
    <p className="text-slate-400">Разрывов в окне {quality.gaps} · Пропущенных минут на сетке {quality.missing_samples} · Шагов вне сетки {quality.off_grid_steps}</p>
  </section>;
}

function RuntimeWindow({ datasetId, sourceSha, panel, start, initialCursor, incidentId, confirmedAt, onPrevious, onNext }: {
  datasetId: string;
  sourceSha: string;
  panel: Panel;
  start?: string;
  initialCursor?: string;
  incidentId?: string;
  confirmedAt?: string;
  onPrevious?: () => void;
  onNext: (next: string) => void;
}) {
  const [windowData, setWindowData] = useState<WindowData>();
  const [error, setError] = useState('');
  const [modes, setModes] = useState<Schema['RuntimeModes']>();
  const [modeError, setModeError] = useState('');
  const [index, setIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(5);
  const [diagnostics, setDiagnostics] = useState<Schema['RuntimeDiagnostics']>();
  const [diagnosticsError, setDiagnosticsError] = useState<{ at: string; message: string }>();
  useEffect(() => {
    const controller = new AbortController();
    async function load() {
      const { items } = await investigatorV1.signals(datasetId, { panel }, controller.signal);
      const series = await investigatorV1.series({
        dataset_id: datasetId, panel, start, signal_ids: items.map(item => item.canonical_id),
      }, controller.signal);
      if (controller.signal.aborted) return;
      if (series.dataset_id !== datasetId || series.source_sha256 !== sourceSha) {
        setError('Телеметрия не совпадает с выбранным источником.');
        return;
      }
      const position = initialCursor ? series.timestamps.indexOf(initialCursor) : 0;
      if (initialCursor && position === -1 && incidentId && series.timestamps[0] <= initialCursor) {
        setError('Подтверждающий ряд не содержит запрошенного исходного отсчёта.');
        return;
      }
      setIndex(Math.max(0, position));
      setWindowData({ catalog: items, series });
    }
    investigatorV1.modes({ dataset_id: datasetId, start }, controller.signal).then(setModes).catch((failure: Error) => {
      if (!controller.signal.aborted) setModeError(failure.message);
    });
    load().catch((failure: Error) => {
      if (!controller.signal.aborted) setError(failure.message);
    });
    return () => controller.abort();
  }, [datasetId, sourceSha, panel, start, initialCursor, incidentId]);

  const at = windowData?.series.timestamps[index];
  const count = windowData?.series.timestamps.length ?? 0;
  const current = diagnostics?.timestamp === at ? diagnostics : undefined;
  const activeSegment = at ? modes?.segments.find(segment => segment.first <= at && at <= segment.last) : undefined;
  useEffect(() => {
    if (!at) return;
    const controller = new AbortController();
    setDiagnosticsError(undefined);
    investigatorV1.diagnostics({ dataset_id: datasetId, panel, at }, controller.signal)
      .then(setDiagnostics)
      .catch((failure: Error) => {
        if (!controller.signal.aborted) setDiagnosticsError({ at, message: failure.message });
      });
    return () => controller.abort();
  }, [at, datasetId, panel]);
  useEffect(() => {
    if (!playing) return;
    if (index >= count - 1) {
      setPlaying(false);
      return;
    }
    const timer = window.setTimeout(() => setIndex(index + 1), Math.max(100, 1000 / speed));
    return () => window.clearTimeout(timer);
  }, [playing, count, index, speed]);

  const chartSeries = useMemo(() => {
    if (!windowData) return [];
    const { series } = windowData;
    return series.signals.flatMap(signal => {
      const id = signal.canonical_id;
      const group = ['SA_TEMP', 'SA_TEMPSPT'].includes(id) ? 'chart1_sat'
        : ['CHWC_VLV_DM', 'OA_DMPR_DM', 'SF_CS', 'SF_SPD_DM'].includes(id) ? 'chart2_cmd'
        : ['OA_TEMP', 'RA_TEMP', 'MA_TEMP'].includes(id) ? 'chart3_thermal' : null;
      if (!group || signal.availability === 'UNAVAILABLE') return [];
      const points: Array<[string, number | null]> = [];
      series.timestamps.forEach((timestamp, i) => {
        const value = signal.values[i];
        points.push([timestamp, value !== null && group === 'chart2_cmd' ? value * 100 : value]);
      });
      return [{ channel: id, display_name_ru: id, unit: group === 'chart2_cmd' ? '%' : '°C', chart_group: group, points }];
    });
  }, [windowData]);

  if (error) return <ApiError message={error} />;
  if (!windowData) return <p role="status">Загрузка сигналов…</p>;
  const { catalog, series } = windowData;
  const availability = new Map(series.signals.map(signal => [signal.canonical_id, signal.availability]));
  const values = Object.fromEntries(series.signals
    .filter(signal => signal.availability === 'AVAILABLE')
    .map(signal => [signal.canonical_id, signal.values[index] ?? null]));
  const diagnosticError = diagnosticsError?.at === at ? diagnosticsError?.message : undefined;
  const quality = new Map(current?.signal_quality.map(item => [item.canonical_id, item.flags]));
  const seekTimestamp = (timestamp: string) => {
    const position = series.timestamps.indexOf(timestamp);
    if (position !== -1) setIndex(position);
  };

  return <>
    <div className="flex flex-wrap gap-3 text-sm">
      <button className="rounded bg-slate-800 px-3 py-1 disabled:opacity-40" onClick={onPrevious}
        disabled={!onPrevious}>Предыдущее окно</button>
      <button className="rounded bg-slate-800 px-3 py-1 disabled:opacity-40"
        onClick={() => series.next_start && onNext(series.next_start)}
        disabled={!series.next_start}>Следующее окно</button>
      <span className="self-center text-slate-400">Отсчётов в окне · {count}</span>
    </div>
    {!at ? <p>В этом окне нет отсчётов.</p> : <>
      <ReplayClockBar clockKind={series.clock_kind} isPlaying={playing}
        onTogglePlay={() => setPlaying(!playing)}
        onReset={() => { setPlaying(false); setIndex(0); }}
        currentIndex={index} totalPoints={count} onSeekIndex={setIndex} currentTimestamp={at}
        playbackSpeed={speed} onChangeSpeed={setSpeed}
        currentMode={current?.mode ?? activeSegment?.mode ?? 'UNKNOWN'} fanOn={current?.fan_on ?? null}
        hasDataGap={series.gap_before[index]} />
      {modeError && <ApiError message={modeError} />}
      {modes && <ModeTimeline modes={modes} active={activeSegment} onSeek={seekTimestamp} />}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="min-w-0 overflow-hidden">
          <AHUIndustrialSchematic sourceSimulation currentValues={values} currentTimestamp={at}
            unverifiedUnitSignals={catalog.filter(item => item.value_status === 'UNVERIFIED_UNIT').map(item => item.canonical_id)}
            fanOn={current?.fan_on === true} activeProfile={panel === "EXTRA" ? "FULL" : "BASIC"} />
        </div>
        <section className={card} aria-label="Проверки источника">
          <h2 className="mb-2 font-semibold">Проверки источника</h2>
          {diagnosticError && <ApiError message={diagnosticError} />}
          {!current && !diagnosticError && <p role="status">Проверка отсчёта…</p>}
          {current && <>
            <dl className="grid grid-cols-1 gap-1 text-xs sm:grid-cols-[auto_1fr]">
              {[
                ['Происхождение результата', current.result_origin],
                ['Режим вентилятора', current.mode],
                ['Погодный контекст', current.weather_context],
                ['Физический режим экономайзера', current.physical_context.economizer_state],
                ['Разрешение механического охлаждения', current.physical_context.mechanical_cooling_enable],
                ['Качество выбранной панели', current.data_status],
                ['Детекция', current.anomaly_status],
                ['Статус проверки', current.display_state],
                ['Причина', current.cause_status],
                ...(current.issue_class ? [['Класс отклонения', current.issue_class]] : []),
                ['Область применимости модели', current.model_scope],
                ['Модель', current.model_status],
              ].map(([label, value]) => <div className="contents" key={label}>
                <dt className="text-slate-400">{label}</dt><dd className="break-words font-mono">{value}</dd>
              </div>)}
            </dl>
            <p className="mt-2 text-xs text-slate-400">
              Погодный диапазон LBNL {current.mode_policy.weather_boundaries_deg_f.map(value => value.toLocaleString('ru-RU')).join('–')} °F.
              Недоступные наблюдения · {current.physical_context.missing_observations.join(', ')}.
            </p>
            <p className="mt-2 text-xs text-slate-400">
              VERIFIED_RUNTIME означает сверку исходных байтов. Проверка команды оценивает кодирование сигнала.
            </p>
            {current.issue_class === 'SIGNAL_RANGE_VIOLATION' && <p className="mt-2 text-xs text-amber-300">
              Нарушение кодирования команды управления. Причина и состояние механики клапана не оценивались.
            </p>}
            {current.methods.map(method => <details key={method.method_id} className="mt-2 border-t border-slate-800 pt-2 text-xs">
              <summary className="cursor-pointer break-words">
                {method.method_id} · {method.method_status} · {method.reason_code}
              </summary>
              <p>{method.predicate} · v{method.method_version}</p>
              {method.missing_signal_ids.length > 0 && <p>Недоступные каналы · {method.missing_signal_ids.join(', ')}</p>}
              {method.invalid_signal_ids.length > 0 && <p>Замечания к входам · {method.invalid_signal_ids.join(', ')}</p>}
              {method.unverified_prerequisites.length > 0 && <p>Неподтверждённые условия · {method.unverified_prerequisites.join(', ')}</p>}
              {method.roots.map(root => <div key={root.evidence_id} className="mt-1 break-all text-slate-400">
                {root.canonical_id} · {root.origin} · {root.value ?? 'нет данных'} {root.unit} · {root.evidence_id}
              </div>)}
            </details>)}
            <details open className="mt-3 border-t border-slate-800 pt-2 text-xs">
              <summary className="cursor-pointer font-semibold">RULE_SYMPTOM · проверка MAT в BASIC</summary>
              <p className="mt-1 break-words">
                {current.symptom_evaluation.applicability} · {current.symptom_evaluation.predicate} · {current.symptom_evaluation.reason_code}
              </p>
              <p className="mt-1 text-slate-400">Оценка по входам правила · {current.symptom_evaluation.rule.sensor_quality_scope} · Расход не подтверждён</p>
              {current.symptom_evaluation.invalid_input_ids.length > 0 && <p>
                Невалидные или отсутствующие входы · {current.symptom_evaluation.invalid_input_ids.join(', ')}
              </p>}
              <p className="mt-1 text-slate-400">
                Нижний допуск {current.symptom_evaluation.rule.lower_margin_deg_f} °F · подтверждение {current.symptom_evaluation.rule.confirmation_duration_seconds} с в ленте
              </p>
              <ul className="mt-1 text-slate-400">
                {current.symptom_evaluation.raw_lineage.map(root => <li key={root.evidence_id}>
                  {root.source_column} · {root.value ?? '—'} {root.unit}
                </li>)}
              </ul>
            </details>
          </>}
        </section>
      </div>
      <SynchronousTelemetryCharts sourceTimestamps={series.timestamps} sourceGapBefore={series.gap_before}
        currentTimestamp={at} series={chartSeries}
        isModelAvailable={false} onSeekTimestamp={seekTimestamp} />
      <CursorInvestigation key={at} datasetId={datasetId} at={at} incidentId={incidentId}
        confirmedAt={confirmedAt} onSeek={seekTimestamp} />
    </>}
    <details className={card} open={datasetId !== demoDatasetId}>
      <summary className="cursor-pointer font-semibold">Качество данных · канонические сигналы</summary>
      {current && <p className="mt-2 text-xs text-slate-400">
        Интервал перед отсчётом · {current.time_quality.elapsed_seconds ?? '—'} с
        {current.time_quality.off_grid_before && ' · шаг вне минутной сетки'}
        {current.time_quality.gap_before && ` · разрыв · пропущено минут ${current.time_quality.missing_samples_before}`}
      </p>}
      <div className="mt-2 grid gap-1 text-xs sm:grid-cols-2 xl:grid-cols-3">
        {catalog.map(item => <div key={item.canonical_id} className="break-words rounded bg-slate-800 p-2">
          <strong>{item.canonical_id}</strong> · {item.origin} · {
            item.availability === 'UNAVAILABLE' || availability.get(item.canonical_id) === 'UNAVAILABLE' ? 'UNAVAILABLE'
              : item.value_status === 'UNVERIFIED_UNIT'
                ? `raw ${values[item.canonical_id] ?? 'нет данных'} · Единица не проверена`
                : values[item.canonical_id] == null ? 'нет данных' : `${values[item.canonical_id]?.toFixed(3)} ${item.unit}`
          }
          {(quality.get(item.canonical_id) ?? []).filter(flag => flag !== 'SEMANTICS_UNVERIFIED').map(flag =>
            <span key={flag} className="mt-1 block text-amber-300">{qualityLabels[flag]}</span>
          )}
        </div>)}
      </div>
    </details>
  </>;
}


function CursorInvestigation({ datasetId, at, incidentId, confirmedAt, onSeek }: {
  datasetId: string; at: string; incidentId?: string; confirmedAt?: string; onSeek: (at: string) => void;
}) {
  const [result, setResult] = useState<Schema['RuntimeG4Investigation']>();
  const [context, setContext] = useState<Schema['RuntimeG4Investigation']>();
  const [error, setError] = useState('');
  const retrospective = Boolean(incidentId && confirmedAt && at < confirmedAt);
  useEffect(() => {
    const controller = new AbortController();
    const load = async () => {
      const current = await investigatorV1.investigation({ dataset_id: datasetId, start: at, limit: 1 }, controller.signal);
      if (controller.signal.aborted) return;
      setResult(current);
      if (retrospective && confirmedAt) {
        const linked = await investigatorV1.investigation({
          dataset_id: datasetId, start: confirmedAt, limit: 1, event_id: incidentId,
        }, controller.signal);
        if (!controller.signal.aborted) setContext(linked);
      }
    };
    load().catch((failure: Error) => {
      if (!controller.signal.aborted) setError(failure.message);
    });
    return () => controller.abort();
  }, [at, datasetId, incidentId, confirmedAt, retrospective]);

  const linked = context?.events.find(event => event.first_observed <= at);
  return <section className={card} aria-label="Расследование по курсору">
    <h2 className="mb-2 font-semibold">Расследование по курсору · BASIC</h2>
    {error && <ApiError message={error} />}
    {!error && !result && <p role="status">Проверка временного условия…</p>}
    {result && <div className="space-y-3">
      <InvestigationDetails result={result} />
      <ReportLinks scope={{ dataset_id: datasetId, start: at, limit: 1 }} />
      {result.events.map(event => <EventEvidence key={event.event_id} datasetId={datasetId} event={event} at={at} onSeek={onSeek} />)}
      {linked && <div className="border-t border-slate-700 pt-2">
        <p className="mb-2 text-xs text-amber-200">Ретроспектива выбранного эпизода · подтверждение после времени курсора</p>
        <EventEvidence datasetId={datasetId} event={linked} at={at} onSeek={onSeek} />
      </div>}
    </div>}
  </section>;
}
