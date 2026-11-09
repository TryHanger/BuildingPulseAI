import type { components, paths } from '../types/openapi-v1.generated';

type Schema = components['schemas'];
type InvestigationQuery = NonNullable<paths['/api/v1/investigation']['get']['parameters']['query']>;
export const demoDatasetId = 'demo-g4-mat';

export function investigationLinks(datasetId: string, event: Schema['RuntimeG4Event'], at = event.confirmed_at) {
  return `/assets/ahu-sd?${new URLSearchParams({
    dataset_id: datasetId, timestamp: at, incident_id: event.event_id, window_start: event.first_observed, confirmed_at: event.confirmed_at,
  })}`;
}

export function ReportLinks({ scope }: { scope: InvestigationQuery }) {
  const href = (format: 'json' | 'html') => {
    const query = new URLSearchParams({ dataset_id: scope.dataset_id, format });
    if (scope.start) query.set('start', scope.start);
    if (scope.limit) query.set('limit', String(scope.limit));
    if (scope.event_id) query.set('event_id', scope.event_id);
    return `/api/v1/investigation?${query}`;
  };
  return <div className="flex flex-wrap gap-3 text-sm">
    <a className="text-sky-300 underline" href={href('json')} download="buildingpulse-investigation.json">Скачать JSON</a>
    <a className="text-sky-300 underline" href={href('html')} target="_blank" rel="noreferrer">Открыть HTML-отчёт</a>
  </div>;
}

export function InvestigationDetails({ result }: { result: Schema['RuntimeG4Investigation'] }) {
  const { rule, coverage, source_coverage: full } = result;
  const sourcePercent = full.samples ? (100 * full.evaluated / full.samples).toFixed(2).replace('.', ',') : '—';
  return <div className="space-y-2 break-words text-xs text-slate-300">
    <p className="font-medium text-slate-100">Проверка нижней границы температуры смеси</p>
    <dl className="grid grid-cols-2 gap-2 sm:grid-cols-4" aria-label="Итог окна">
      {[
        ['Оценено', `${coverage.evaluated} из ${coverage.samples}`],
        ['Нарушающие отсчёты без подтверждения', result.unconfirmed_violated_samples],
        ['Подтверждённые эпизоды', result.events.length],
        ['Не оценено', coverage.not_evaluable],
      ].map(([label, value]) => <div className="min-w-0 rounded bg-slate-800 p-2" key={label}>
        <dt>{label}</dt><dd className="mt-1 text-sm font-semibold text-slate-100">{value}</dd>
      </div>)}
    </dl>
    {result.confirmation_state === 'PENDING' && <div className="rounded border border-amber-700 bg-amber-950/60 p-2 text-amber-100">
      <p className="font-semibold">Нарушение продолжается на границе окна</p>
      <p>К концу окна эпизод ещё не подтверждён. Статус может измениться при поступлении следующих отсчётов.</p>
    </div>}
    {result.confirmation_state === 'UNCONFIRMED' && <p className="text-amber-200">
      Зафиксированы нарушения без подтверждения эпизода в этом окне.
    </p>}
    <p>Весь источник · оценено {sourcePercent}% ({full.evaluated} из {full.samples}) · не оценено {full.not_evaluable} · подтверждено эпизодов {result.source_confirmed_episodes}</p>
    <details>
      <summary className="cursor-pointer">Условия проверки, входы и ограничения</summary>
      <p className="mt-1">{result.status} · {result.evidence_status} · {result.cause_state}</p>
      <p>{result.formula} · допуск {rule.lower_margin_deg_f} °F · разнос входов ≥ {rule.min_inlet_separation_deg_f} °F</p>
      <p>RUNNING после {result.mode_policy.hold_seconds} с · статус ON · команда &gt; {rule.min_fan_command_exclusive} · подтверждение {rule.confirmation_duration_seconds} с</p>
      <p className="break-all">{rule.method_id} · v{rule.model_or_rule_version} · {result.rule_fingerprint}</p>
      <p>Разрывы · {result.time_quality.gaps} · Пропущенные минуты · {result.time_quality.missing_samples} · Всего нарушающих отсчётов · {coverage.violated}</p>
      <ul className="space-y-1">
        {result.inputs.map(input => <li key={input.canonical_id}>{input.canonical_id} · {input.kind} · {input.unit} · {input.available ? 'AVAILABLE' : 'UNAVAILABLE'}</li>)}
        {Object.entries(result.not_evaluable_reasons).map(([reason, count]) => <li key={reason}>{reason} · {count}</li>)}
        {result.mode_segments.map(mode => <li key={mode.first}>
          {mode.mode} · {mode.first} → {mode.last} · {mode.samples} отсч.
        </li>)}
        {result.inapplicable_checks.map(check => <li key={check}>{check}</li>)}
      </ul>
    </details>
    <details>
      <summary className="cursor-pointer">Журнал анализа</summary>
      <ol className="list-decimal space-y-1 pl-5">
        {result.analysis_journal.map(row => <li key={row.step}>{row.step} · {row.result}</li>)}
      </ol>
      <p className="break-all">Source SHA-256 {result.source_sha256}</p>
      <p className="break-all">Index SHA-256 {result.index_sha256}</p>
      <p className="break-all">Run SHA-256 {result.run_sha256}</p>
    </details>
  </div>;
}

export function EventEvidence({ datasetId, event, at, onSeek }: {
  datasetId: string; event: Schema['RuntimeG4Event']; at?: string; onSeek?: (at: string) => void;
}) {
  return <div className="space-y-2 break-words text-sm">

    <p>Первый отсчёт {event.first_observed} · Подтверждение {event.confirmed_at}</p>
    <p>Последний отсчёт в окне {event.last_seen} · {event.gap_reason}</p>
    <p className="text-slate-300">Подтверждено выполнение условия во времени. Механическая причина требует внешних свидетельств.</p>
    <details>
      <summary className="cursor-pointer">Evidence Inspector · {event.sensor_root_count} каналов · {event.observation_count} отсчётов</summary>
      <p className="break-all text-xs text-slate-400">ID {event.event_id}</p>
      <p className="text-xs text-slate-400">{event.time_window.first} → {event.time_window.last} · 1 вычисленный факт на тех же входах</p>
      <p className="break-words text-xs text-slate-400">{event.derived_fact.code} · {event.derived_fact.depends_on.join(', ')}</p>
      {event.raw_lineage.map(root => <details className="mt-1 rounded bg-slate-800 p-2" key={root.canonical_id}>
        <summary className="cursor-pointer text-xs">{root.canonical_id} · {root.kind} · {root.observations.length} наблюдений</summary>
        <ul className="mt-1 space-y-1 text-xs">
          {root.observations.map(record => <li key={record.evidence_id} className={at === record.timestamp ? 'text-amber-200' : 'text-slate-300'}>
            {onSeek ? <button type="button" className="underline" onClick={() => onSeek(record.timestamp)}>{record.timestamp}</button>
              : <a className="underline" href={investigationLinks(datasetId, event, record.timestamp)}>{record.timestamp}</a>}
            {' · '}{record.value ?? '—'} {record.unit}
          </li>)}
        </ul>
      </details>)}
    </details>
    <details>
      <summary className="cursor-pointer">Возможные объяснения</summary>
      <p className="text-xs text-slate-300">Эти варианты совместимы с симптомом. Механизм требует внешних свидетельств.</p>
      <ul className="text-xs text-slate-300">
        {event.possible_causes.map(cause => <li key={cause}>{cause}</li>)}
      </ul>
    </details>
  </div>;
}
