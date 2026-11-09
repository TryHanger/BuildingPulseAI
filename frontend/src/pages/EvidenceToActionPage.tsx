import { useEffect, useState } from 'react';
import ReactECharts from 'echarts-for-react';
import { loadDecisionTrace, type CaseId, type DecisionTrace } from '../api/evidenceToAction';

const cases: { id: CaseId; name: string; kind: string }[] = [
  { id: 'A', name: 'LBNL · SAT', kind: 'Симуляция · остаток модели' },
  { id: 'B', name: 'G36 · healthy OOD', kind: 'Симуляция · перенос модели' },
  { id: 'C', name: 'Mendeley · AHU23', kind: 'BMS · различающиеся статусы' },
  { id: 'D', name: 'Mendeley · AHU2', kind: 'BMS · неполная телеметрия' },
];

const panel = 'rounded-xl border border-slate-800 bg-slate-900 p-4 sm:p-5';
const muted = 'text-sm leading-relaxed text-slate-300';
const colors = ['#38bdf8', '#fbbf24', '#c4b5fd', '#34d399'];

function Telemetry({ trace, id, staticPlot }: { trace: DecisionTrace; id: CaseId; staticPlot: boolean }) {
  const [cursor, setCursor] = useState(0);
  const sample = trace.samples[cursor];
  const hasValues = trace.samples.some(point => point.values.some(value => value !== null));
  const field = id === 'C' || id === 'D';
  const series = field
    ? [0, 1].map((state) => ({
        name: state === 1 ? 'ON / активен' : 'OFF / неактивен',
        type: 'scatter',
        symbol: state === 1 ? 'circle' : 'emptyCircle',
        symbolSize: 8,
        data: trace.samples.flatMap(point => trace.channels.flatMap((name, index) =>
          point.values[index] === state ? [[point.seconds, name]] : [])),
      }))
    : trace.channels.map((name, index) => ({
        name, type: 'scatter', symbolSize: id === 'A' ? 3 : 6,
        data: trace.samples
          .filter(point => point.values[index] !== null)
          .map(point => [id === 'A' ? point.seconds / 60 : point.seconds, point.values[index]]),
      }));
  return (
    <section className={panel} aria-labelledby="bp15-telemetry">
      <h2 id="bp15-telemetry" className="font-semibold">Нативная телеметрия</h2>
      <p className={muted}>{trace.clock}</p>
      {hasValues
        ? <ReactECharts
            aria-label="График телеметрии"
            style={{ height: 250 }}
            option={{
              ...(staticPlot ? { animation: false } : {}),
              color: colors,
              legend: { top: 0, type: 'scroll', textStyle: { color: '#cbd5e1' } },
              grid: { top: 45, left: field ? 125 : 50, right: 30, bottom: 30 },
              xAxis: {
                type: 'value', min: 'dataMin', max: 'dataMax', axisLabel: { color: '#cbd5e1' },
              },
              yAxis: field ? {
                type: 'category', data: [...trace.channels].reverse(), axisLabel: { color: '#cbd5e1' },
                splitLine: { show: true, lineStyle: { color: '#334155' } },
              } : {
                type: 'value', scale: true, axisLabel: { color: '#cbd5e1' },
                splitLine: { lineStyle: { color: '#334155' } },
              },
              series,
            }}
          />
        : <p className="my-3 rounded-lg bg-slate-950 p-3 text-amber-200">Нет значений для графика. Пропуски сохранены.</p>}
      {sample && <>
        <label className="mt-3 block text-sm" htmlFor="bp15-sample">Отсчёт источника</label>
        <select id="bp15-sample" className="mt-1 max-w-full rounded border border-slate-600 bg-slate-950 p-2 text-sm"
          value={cursor} onChange={event => setCursor(Number(event.target.value))}>
          {trace.samples.map((point, index) => <option key={point.time} value={index}>{point.time}</option>)}
        </select>
        <dl className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
          {trace.channels.map((channel, index) => (
            <div key={channel} className="rounded bg-slate-950 p-2 text-sm">
              <dt className="text-slate-300">{channel}</dt>
              <dd data-testid={`sample-value-${index}`} className="mt-1 font-mono text-sky-200">
                {sample.values[index] ?? 'MISSING'}
              </dd>
            </div>
          ))}
        </dl>
        <p data-testid="sample-context" className={`mt-2 ${muted}`}>{sample.context}</p>
      </>}
    </section>
  );
}

function CaseTrace({ id, simple }: { id: CaseId; simple: boolean }) {
  const [result, setResult] = useState<DecisionTrace | 'UNAVAILABLE'>();
  useEffect(() => {
    const controller = new AbortController();
    loadDecisionTrace(id, controller.signal)
      .then(trace => { if (!controller.signal.aborted) setResult(trace); })
      .catch(() => { if (!controller.signal.aborted) setResult('UNAVAILABLE'); });
    return () => controller.abort();
  }, [id]);

  if (!result) return <p role="status">Загрузка проверенного источника…</p>;
  if (result === 'UNAVAILABLE') {
    return <section role="alert" className={panel}>
      <h2 className="font-semibold text-amber-200">UNAVAILABLE</h2>
      <p className={muted}>Источник или контракт недоступен. Наблюдение и причина не оцениваются.</p>
    </section>;
  }

  return simple ? <SignalOnly anomaly={result.anomaly} /> : <EvidencePresentation result={result} id={id} />;
}

export function SignalOnly({ anomaly }: { anomaly: string }) {
  return (
    <section className={panel} aria-label="Только сигнал">
      <p className="text-sm text-slate-300">Аномалия / наблюдение</p>
      <h2 className="mt-1 break-words font-mono text-lg text-sky-200" data-testid="anomaly">{anomaly}</h2>
    </section>
  );
}

export function EvidencePresentation({ result, id, participant = false }: {
  result: DecisionTrace;
  id: CaseId;
  participant?: boolean;
}) {
  const statuses = (
    <div className={`grid gap-3 ${participant ? '' : 'sm:grid-cols-2'}`}>
      <section className={panel}><h2 className="text-sm text-slate-300">Аномалия / наблюдение</h2>
        <p data-testid="anomaly" className="mt-1 break-words font-mono text-sky-200">{result.anomaly}</p></section>
      <section className={panel}><h2 className="text-sm text-slate-300">Физическая причина</h2>
        <p data-testid="cause" className="mt-1 font-mono text-amber-200">{result.cause}</p></section>
    </div>
  );
  return <>
    {participant && statuses}
    <section className={panel} aria-labelledby="bp15-source">
      <h2 id="bp15-source" className="font-semibold">{result.source}</h2>
      <p data-testid="quality" className={`mt-2 ${muted}`}>{result.quality}</p>
      <p data-testid="applicability" className={muted}>{participant ? result.pilot.method : result.applicability}</p>
      <details className="mt-3 text-sm">
        <summary className="cursor-pointer text-sky-200">Источник, версии и контрольные суммы</summary>
        {!participant && <a href={result.sourceUrl} className="my-2 inline-block text-sky-200 underline">Запись издателя</a>}
        <dl className="grid gap-2 sm:grid-cols-2">
          {result.provenance.map(([label, value]) => <div key={label}>
            <dt className="text-slate-300">{label}</dt>
            <dd className="break-all font-mono text-xs">{value}</dd>
          </div>)}
        </dl>
      </details>
    </section>
    <Telemetry trace={result} id={id} staticPlot={participant} />
    {!participant && statuses}
    {participant ? <section className={panel} aria-labelledby="bp15-evidence">
      <h2 id="bp15-evidence" className="font-semibold">Свидетельства</h2>
      <ul className={`mt-2 list-disc space-y-2 pl-5 ${muted}`}>
        {result.pilot.observations.map(observation => <li key={observation}>{observation}</li>)}
      </ul>
    </section> : <>
      <section className={panel} aria-labelledby="bp15-evidence">
        <h2 id="bp15-evidence" className="font-semibold">Свидетельства</h2>
        <dl className={`mt-2 space-y-2 ${muted}`}>
          <div><dt className="font-medium text-emerald-200">Поддерживают наблюдение</dt><dd data-testid="support">{result.support}</dd></div>
          <div><dt className="font-medium text-amber-200">Ограничивают вывод</dt><dd data-testid="conflict">{result.conflict}</dd></div>
          <div><dt className="font-medium text-sky-200">Отсутствуют</dt><dd data-testid="missing">{result.missing}</dd></div>
        </dl>
      </section>
      <section className="rounded-xl border border-sky-900 bg-sky-950/40 p-4 sm:p-5">
        <h2 className="font-semibold text-sky-100">Следующая проверка инженера</h2>
        <p data-testid="action" className={`mt-2 ${muted}`}>{result.action}</p>
      </section>
    </>}
    {result.blocks && <section className={panel}>
      <h2 className="font-semibold">Сохранённые блочные решения Stage06</h2>
      <table className="mt-2 w-full text-left text-sm">
        <thead><tr><th scope="col">Блок</th><th scope="col">Начало (с)</th><th scope="col">z</th><th scope="col">Результат</th></tr></thead>
        <tbody>{result.blocks.map(block => <tr key={block.block} className="border-t border-slate-800">
          <td>{block.block}</td><td>{block.start_model_s}</td><td>{block.z}</td><td>{block.decision}</td>
        </tr>)}</tbody>
      </table>
    </section>}
  </>;
}

export function EvidenceToActionPage() {
  const [id, setId] = useState<CaseId>('A');
  const [simple, setSimple] = useState(false);
  return (
    <main className="mx-auto max-w-5xl space-y-4 px-4 py-6 sm:px-8">
      <a href="/assets/ahu-sd" className="text-sm text-sky-200 underline">← К телеметрии AHU Investigator</a>
      <header>
        <p className="text-xs font-medium text-sky-300">BP-15 · ИССЛЕДОВАТЕЛЬСКИЙ РЕЖИМ</p>
        <h1 className="mt-1 text-3xl font-semibold">От сигнала к проверке</h1>
        <p className={`mt-2 ${muted}`}>Четыре исторических случая. Сравните сигнал, основания для вывода и следующее измерение.</p>
      </header>
      <div role="group" aria-label="Исторический случай" className="grid grid-cols-2 gap-2 lg:grid-cols-4">
        {cases.map(item => (
          <button key={item.id} type="button" aria-pressed={id === item.id} onClick={() => setId(item.id)}
            className={`rounded-lg border p-3 text-left focus-visible:outline-sky-300 ${id === item.id ? 'border-sky-400 bg-sky-950' : 'border-slate-700 bg-slate-900'}`}>
            <span className="block text-sm font-semibold">{item.id} · {item.name}</span>
            <span className="mt-1 block text-xs text-slate-300">{item.kind}</span>
          </button>
        ))}
      </div>
      <div role="group" aria-label="Представление сигнала" className="flex flex-wrap gap-2 text-sm">
        {[false, true].map(mode => (
          <button key={String(mode)} type="button" aria-pressed={simple === mode} onClick={() => setSimple(mode)}
            className={`rounded border px-3 py-1 focus-visible:outline-sky-300 ${simple === mode ? 'border-sky-400 text-sky-200' : 'border-slate-700 text-slate-300'}`}>
            {mode ? 'Только сигнал' : 'Свидетельства и действие'}
          </button>
        ))}
      </div>
      <CaseTrace key={id} id={id} simple={simple} />
    </main>
  );
}
