import { useEffect, useLayoutEffect, useRef, useState, type FormEvent } from 'react';
import { loadDecisionTrace, type DecisionTrace } from '../api/evidenceToAction';
import { EvidencePresentation, SignalOnly } from '../pages/EvidenceToActionPage';
import { options, questions } from './questions';
import { downloadResponses, getSequence, getTasks, type Choices, type Response, type Task } from './session';

const caseNames = { A: 'LBNL SD-AHU', B: 'G36-1wk', C: 'Mendeley AHU23', D: 'Mendeley AHU2' };
const panel = 'rounded-xl border border-slate-800 bg-slate-900 p-5';
const button = 'rounded-lg border border-sky-600 bg-sky-950 px-4 py-2 font-medium text-sky-100 focus-visible:outline-sky-300 disabled:opacity-50';

function TaskForm({ task, trace, onSubmit }: {
  task: Task;
  trace: DecisionTrace;
  onSubmit: (response: Response) => void;
}) {
  const [choices, setChoices] = useState<Partial<Choices>>({});
  const started = useRef(0);
  const interrupted = useRef(false);
  const submitted = useRef(false);
  const heading = useRef<HTMLHeadingElement>(null);

  useLayoutEffect(() => {
    heading.current?.focus();
    started.current = performance.now();
    interrupted.current = document.hidden;
    const onVisibility = () => { if (document.hidden) interrupted.current = true; };
    document.addEventListener('visibilitychange', onVisibility);
    return () => document.removeEventListener('visibilitychange', onVisibility);
  }, []);

  const { decision, inference, measurement } = choices;
  function submit(event: FormEvent) {
    event.preventDefault();
    if (submitted.current || decision === undefined || inference === undefined || measurement === undefined) return;
    submitted.current = true;
    onSubmit({
      ...task,
      anomaly: trace.anomaly,
      choices: { decision, inference, measurement },
      elapsed_ms: Math.round(performance.now() - started.current),
      interrupted: interrupted.current || document.hidden,
    });
  }

  return <>
    <header>
      <p className="text-sm text-slate-400">Задание {task.position} из 4</p>
      <h2 ref={heading} tabIndex={-1} className="mt-1 text-2xl font-semibold">Случай {task.case_id}</h2>
      <p className="text-sm text-slate-300">{caseNames[task.case_id]}</p>
    </header>
    <div className="grid items-start gap-4 lg:grid-cols-2">
      <div data-testid="stimulus" data-condition={task.condition} className="space-y-3">
        {task.condition === 'signal-only' ? <SignalOnly anomaly={trace.anomaly} />
          : <EvidencePresentation result={trace} id={task.case_id} participant />}
      </div>
      <form className="space-y-3" onSubmit={submit}>
        {questions.map(([id, label]) => (
          <fieldset key={id} className={panel}>
            <legend className="px-1 font-medium text-sky-200">{label}</legend>
            <div className="space-y-2">
              {options[task.case_id][id].map((answer, index) => (
                <label key={answer} className="flex items-start gap-3 rounded-lg border border-slate-700 p-3 text-sm hover:border-sky-500">
                  <input type="radio" name={id} value={index + 1} required className="mt-0.5 accent-sky-400"
                    checked={choices[id] === index + 1} onChange={() => setChoices({ ...choices, [id]: index + 1 })} />
                  <span>{answer}</span>
                </label>
              ))}
            </div>
          </fieldset>
        ))}
        <button className={button} disabled={decision === undefined || inference === undefined || measurement === undefined}>
          Подтвердить ответы
        </button>
      </form>
    </div>
  </>;
}

function OpenTask({ task, onSubmit }: { task: Task; onSubmit: (response: Response) => void }) {
  const [result, setResult] = useState<DecisionTrace | 'UNAVAILABLE'>();
  useEffect(() => {
    const controller = new AbortController();
    loadDecisionTrace(task.case_id, controller.signal)
      .then(trace => {
        if (!controller.signal.aborted) setResult(trace.anomaly === 'UNAVAILABLE' ? 'UNAVAILABLE' : trace);
      })
      .catch(() => { if (!controller.signal.aborted) setResult('UNAVAILABLE'); });
    return () => controller.abort();
  }, [task.case_id]);

  if (!result) return <p role="status" className={panel}>Загружается исторический случай…</p>;
  if (result === 'UNAVAILABLE') return <p role="alert" className={panel}>UNAVAILABLE · источник недоступен. Сообщите ведущему.</p>;
  return <TaskForm task={task} trace={result} onSubmit={onSubmit} />;
}

function Session({ sequence }: { sequence: number }) {
  const [sessionId, setSessionId] = useState<string>();
  const [responses, setResponses] = useState<Response[]>([]);
  const [opened, setOpened] = useState(false);
  const [withdrawn, setWithdrawn] = useState(false);
  const [exportRequested, setExportRequested] = useState(false);
  const task = getTasks(sequence)[responses.length];

  function record(response: Response) {
    setResponses(previous => [...previous, response]);
    setOpened(false);
    window.scrollTo(0, 0);
  }

  function withdraw() {
    if (!window.confirm('Прервать сессию и удалить введённые ответы?')) return;
    setResponses([]);
    setSessionId(undefined);
    setWithdrawn(true);
  }

  if (withdrawn) return <p role="status" className={panel}>Сессия прервана. Сообщите ведущему.</p>;
  if (!sessionId) return <section className={panel}>
    <h2 className="text-xl font-semibold">Перед началом</h2>
    <p className="my-3 max-w-2xl text-slate-300">
      Вы увидите четыре исторических случая. В каждом выберите решение, допустимый вывод и следующее измерение.
      Время учитывается с появления задания. Сессия добровольная, ответы можно удалить до выгрузки.
      В конце сохраните один локальный файл по инструкции ведущего.
    </p>
    <button className={button} onClick={() => setSessionId(crypto.randomUUID())}>Начать сессию</button>
  </section>;

  if (!task) return <section className={panel}>
    <h2 className="text-xl font-semibold">Четыре задания завершены</h2>
    <p className="my-3 text-slate-300">Сохраните локальный файл и сообщите ведущему.</p>
    <div className="flex flex-wrap gap-3">
      <button className={button} onClick={() => {
        downloadResponses(sessionId, sequence, responses);
        setExportRequested(true);
      }}>Сохранить ответы</button>
      {!exportRequested && <button onClick={withdraw} className="text-sm underline focus-visible:outline-sky-300">
        Удалить ответы до выгрузки
      </button>}
    </div>
    {exportRequested && <p role="status" className="mt-3 text-sm text-slate-300">Проверьте, что файл сохранился в браузере.</p>}
  </section>;

  return <>
    <button onClick={withdraw} className="text-sm text-slate-300 underline focus-visible:outline-sky-300">Прервать сессию</button>
    {opened ? <OpenTask key={task.position} task={task} onSubmit={record} /> : <section className={panel}>
      <h2 className="text-xl font-semibold">Задание {task.position} из 4</h2>
      <p className="my-3 text-slate-300">Откройте задание, когда готовы начать.</p>
      <button className={button} onClick={() => setOpened(true)}>Открыть задание</button>
    </section>}
  </>;
}

export default function PilotPage() {
  const parameters = new URLSearchParams(window.location.search);
  const sequence = parameters.getAll('sequence').length === 1 ? getSequence(parameters.get('sequence')) : undefined;

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100">
      <div className="mx-auto max-w-5xl space-y-4 px-4 py-8 sm:px-8">
        <header>
          <p className="text-xs font-semibold tracking-wide text-sky-300">BUILDINGPULSE AI · BP-16</p>
          <h1 className="mt-1 text-3xl font-semibold">Инженерный разбор</h1>
        </header>
        {sequence ? <Session sequence={sequence} /> :
          <p role="alert" className={panel}>Нужен корректный код назначения. Обратитесь к ведущему.</p>}
      </div>
    </main>
  );
}
