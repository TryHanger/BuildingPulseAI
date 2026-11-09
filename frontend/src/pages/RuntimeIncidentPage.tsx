import { useEffect, useState } from 'react';
import { investigatorV1 } from '../api/investigatorV1';
import { EventEvidence, InvestigationDetails, investigationLinks, ReportLinks } from '../components/InvestigationEvidence';
import type { components } from '../types/openapi-v1.generated';

type Schema = components['schemas'];
const card = 'min-w-0 rounded-xl border border-slate-800 bg-slate-900 p-4';
const button = 'rounded bg-slate-800 px-3 py-2 disabled:opacity-40';

export function RuntimeIncidentPage({ demo = false }: { demo?: boolean }) {
  const [datasets, setDatasets] = useState<Schema['RuntimeDataset'][]>();
  const [selected, setSelected] = useState('');
  const [error, setError] = useState('');
  useEffect(() => {
    const controller = new AbortController();
    investigatorV1.datasets(controller.signal, demo).then(({ items }) => {
      setDatasets(items);
      setSelected((items.find(item => item.availability === 'AVAILABLE') ?? items[0])?.dataset_id ?? '');
    }).catch((failure: Error) => {
      if (!controller.signal.aborted) setError(failure.message);
    });
    return () => controller.abort();
  }, [demo]);
  const dataset = datasets?.find(item => item.dataset_id === selected);
  return <main className="mx-auto max-w-[1200px] space-y-4 p-3 sm:p-4">
    <section className={card}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h1 className="text-xl font-semibold">{demo ? 'Синтетический эпизод G4' : 'Инциденты LBNL SD-AHU'}</h1>
          <p className="text-sm text-slate-300">Подтверждённые по времени симптомы · данные симуляции · BASIC</p>
        </div>
        <div className="flex flex-wrap gap-3 text-sm">
          {demo ? <a className="text-sky-300 underline" href="/incidents">Открыть ленту LBNL</a> :
            <a className="text-amber-300 underline" href="/incidents?mode=g4-demo">Открыть синтетический эпизод G4</a>}
          <a className="text-slate-400 underline" href="/incidents?mode=demo">Архивная демо-лента</a>
        </div>
      </div>
      {error && <p role="alert" className="text-rose-300">Ошибка API v1 · {error}</p>}
      {!datasets && !error && <p role="status">Загрузка датасетов…</p>}
      {datasets?.length === 0 && <p>В реестре нет датасетов.</p>}
      {dataset && <label className="mt-3 grid min-w-0 grid-cols-1 gap-1 text-sm">
        Датасет
        <select value={selected} className="w-full min-w-0 rounded bg-slate-800 p-2" onChange={event => setSelected(event.target.value)}>
          {datasets?.map(item => <option key={item.dataset_id} value={item.dataset_id}>
            {item.name} · {item.rows ?? '—'} строк · {item.dataset_id}
          </option>)}
        </select>
      </label>}
    </section>
    {dataset && <IncidentWindow key={selected} dataset={dataset} />}
  </main>;
}

function IncidentWindow({ dataset }: { dataset: Schema['RuntimeDataset'] }) {
  const [starts, setStarts] = useState<Array<string | undefined>>([undefined]);
  const [seek, setSeek] = useState(dataset.first ?? '');
  const [result, setResult] = useState<Schema['RuntimeG4Investigation']>();
  const [error, setError] = useState('');
  const start = starts[starts.length - 1];

  useEffect(() => {
    const controller = new AbortController();
    setResult(undefined);
    setError('');
    investigatorV1.investigation({ dataset_id: dataset.dataset_id, start }, controller.signal)
      .then(data => { if (!controller.signal.aborted) setResult(data); }).catch((failure: Error) => {
        if (!controller.signal.aborted) setError(failure.message);
      });
    return () => controller.abort();
  }, [dataset.dataset_id, start]);

  const scope = { dataset_id: dataset.dataset_id, start };
  return <>
    <section className={card}>
      <form className="flex flex-wrap items-end gap-2 text-sm" onSubmit={event => {
        event.preventDefault();
        setStarts([seek]);
      }}>
        <label className="grid min-w-0 max-w-full grid-cols-1 gap-1">
          Начало окна (время источника)
          <input value={seek} onChange={event => setSeek(event.target.value)} required
            pattern="[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
            placeholder="2018-MM-DDTHH:MM:SS" className="w-full min-w-0 rounded bg-slate-800 p-2 font-mono" />
        </label>
        <button type="submit" className={button}>Проверить окно</button>
      </form>
      {error && <p role="alert" className="mt-3 text-rose-300">Ошибка API v1 · {error}</p>}
      {!result && !error && <p role="status" className="mt-3">Загрузка подтверждённых симптомов…</p>}
      {result && <div className="mt-3 space-y-2 text-sm">
        <p>{result.result_origin} · {result.clock_kind}</p>
        <p>{result.first ?? '—'} → {result.last ?? '—'}</p>
        <InvestigationDetails result={result} />
        <ReportLinks scope={scope} />
        <div className="flex flex-wrap gap-2">
          <button className={button} disabled={starts.length === 1}
            onClick={() => setStarts(items => items.slice(0, -1))}>Предыдущее окно</button>
          <button className={button} disabled={!result.next_start}
            onClick={() => {
              const next = result.next_start;
              if (next) setStarts(items => [...items, next]);
            }}>Следующее окно</button>
        </div>
      </div>}
    </section>
    {result && result.events.length === 0 && result.unconfirmed_violated_samples === 0 && <section className={card}>
      <p>{result.status === 'NOT_EVALUABLE' ? 'Правило неприменимо в этом окне' : 'В проверенном окне подтверждённых симптомов нет'}</p>
      <p className="mt-1 text-sm text-slate-300">Отсутствие подтверждённых симптомов не определяет состояние оборудования.</p>
    </section>}
    {result?.events.map(event => <section className={card} key={event.event_id}>
      <h2 className="text-lg font-semibold">MAT ниже диапазона смешения</h2>
      <a className="my-2 inline-block text-sky-300 underline" href={investigationLinks(dataset.dataset_id, event)}>
        Открыть подтверждающий отсчёт
      </a>
      <EventEvidence datasetId={dataset.dataset_id} event={event} />
      <ReportLinks scope={{ ...scope, event_id: event.event_id }} />
    </section>)}
  </>;
}
