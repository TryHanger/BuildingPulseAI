import { useEffect, useState } from 'react';

const channels = [
  ['supply', 'Приток', 'Статус BAS'],
  ['exhaust', 'Вытяжка', 'Статус BAS'],
  ['heat_request', 'Нагрев', 'Запрос BAS'],
  ['cool_request', 'Охлаждение', 'Запрос BAS'],
] as const;

type Channel = typeof channels[number][0];
type Bit = 0 | 1 | null;
type Tick = Record<Channel, Bit> & {
  native_time: string;
  partition: 'PRE' | 'WINDOW';
  relative_seconds: number;
  supply_evidence: string;
  paired_evidence: string;
};
type EvidenceWindow = {
  id: string;
  ahu: string;
  kind: 'intervention' | 'matched_control';
  start: string;
  end_exclusive: string;
  observations: Tick[];
  archived_outcome: Record<string, string>;
  evaluation_metadata: Record<string, string>;
};
type SourceFile = { file_id: string; publisher_sha256: string };
export type FieldEvidence = {
  provenance: {
    dataset_doi: string;
    dataset_url: string;
    version: number;
    license: string;
    cadence_seconds: number;
    clock: string;
    rule_version: string;
    timestamp_column: string;
    input_columns: Record<Channel, string>;
    stage09_zip_sha256: string;
    source_manifest_sha256: string;
    files: Record<string, SourceFile>;
  };
  cases: EvidenceWindow[];
};

const panel = 'rounded-xl border border-slate-800 bg-slate-900/80 p-4 sm:p-5';
const focus = 'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-300';
const heading = 'text-lg font-semibold text-slate-100';
const bit = (value: Bit) => value === null ? '—' : value === 1 ? 'ON' : 'OFF';
const relative = (seconds: number) => `${seconds > 0 ? '+' : ''}${seconds / 60} мин`;
const method = { A: 'Статус притока', B: 'Пара в контексте нагрева' };

const verification: Record<string, string> = {
  AHU1: 'Запросить независимую проверку работы приводов или измерение расхода воздуха.',
  AHU18: 'Запросить независимую проверку работы приводов или измерение расхода воздуха.',
  AHU23: 'Проверить привязку противоречащих тегов притока и вытяжки. Запросить независимое подтверждение работы приводов или расхода воздуха.',
  AHU24: 'Уточнить заданный режим и найти предысторию с обоими статусами ON при запросе нагрева.',
  AHU2: 'Запросить отсутствующие точки BAS для притока, вытяжки, нагрева и охлаждения.',
  AHU8: 'Запросить отсутствующие точки BAS для притока, вытяжки, нагрева и охлаждения.',
};

function changeText(item: EvidenceWindow, key: 'A' | 'B') {
  const values = item.archived_outcome;
  const change = values[`${key}_change`];
  if (change === 'BAS_ON_TO_OFF_OBSERVED') return 'Наблюдался переход ON → OFF';
  if (change === 'NO_OBSERVED_CHANGE') return key === 'B' ? 'Парный переход не наблюдался' : 'Переход притока не наблюдался';
  return 'ABSTAIN · вывод о переходе недоступен';
}

function Outcome({ item, rule }: { item: EvidenceWindow; rule: 'A' | 'B' }) {
  const values = item.archived_outcome;
  const first = values[`${rule}_first_off_from_log_start_seconds`];
  const confirm = values[`${rule}_confirm_from_log_start_seconds`];
  const baseline = values[`${rule}_baseline`];
  const status = values[`${rule}_status`];
  return (
    <article className={panel} aria-label={`Правило ${rule}`}>
      <h3 className="text-sm font-medium text-sky-200">{rule} · {method[rule]}</h3>
      <p className="mt-2 text-base font-semibold">{changeText(item, rule)}</p>
      {status === 'INSUFFICIENT_DATA' &&
        <p className="mt-2 text-sm text-slate-300">Статусы вентиляторов отсутствуют в исходном экспорте. Это пример нехватки данных.</p>}
      {rule === 'B' && item.id === 'event-AHU23' &&
        <p className="mt-2 text-sm text-slate-300">Вытяжка сообщает ON, пока приток сообщает OFF. Совместного перехода двух статусов нет.</p>}
      {rule === 'B' && item.id === 'event-AHU24' &&
        <p className="mt-2 text-sm text-slate-300">Перед окном вытяжка уже сообщает OFF. Для вывода о новом переходе нужны два отсчёта с обоими статусами ON при запросе нагрева.</p>}
      {baseline === 'TWO_ON' &&
        <p className="mt-2 text-sm text-slate-300">{rule === 'A' ? 'Два отсчёта притока ON' : 'Два парных отсчёта ON в контексте нагрева'} до начала окна.</p>}
      {first !== '' && confirm !== '' && (
        <dl className="mt-3 grid grid-cols-2 gap-2 rounded-lg bg-slate-950/80 p-3 text-xs text-slate-300">
          <div><dt>Первый OFF</dt><dd className="mt-1 text-base font-semibold text-sky-200">{relative(Number(first))}</dd></div>
          <div><dt>Повторный OFF</dt><dd className="mt-1 text-base font-semibold text-sky-200">{relative(Number(confirm))}</dd></div>
        </dl>
      )}
      <p className="mt-3 text-xs text-slate-400">OFF в окне: {values[`${rule}_off_ticks`]} из {values[`${rule}_known_ticks`]} пригодных отсчётов.</p>
      <details className="mt-3 text-xs">
        <summary className={`cursor-pointer text-sky-200 ${focus}`}>Поля исхода Stage09 · {rule}</summary>
        <dl className="mt-2 space-y-2 break-words">
          {Object.entries(values).filter(([key]) => key.startsWith(rule + '_')).map(([key, value]) =>
            <div key={key}>
              <dt className="font-mono [overflow-wrap:anywhere] text-slate-400">{key}</dt>
              <dd>{value || '—'}</dd>
            </div>)}
        </dl>
      </details>
    </article>
  );
}

function Timeline({ item }: { item: EvidenceWindow }) {
  const values = item.archived_outcome;
  const first = values.A_first_off_from_log_start_seconds;
  const confirm = values.A_confirm_from_log_start_seconds;
  const width = 700;
  const x = (seconds: number) => 12 + (seconds + 600) * (width - 24) / 6000;
  const boundary = x(0);
  const end = x(5400);
  return (
    <section className={panel} aria-labelledby="field-timeline">
      <h2 id="field-timeline" className={heading}>Временная шкала BAS</h2>
      <p className="mt-1 text-sm text-slate-300">{item.start} → {item.end_exclusive} <span className="text-slate-400">(конец исключён)</span></p>
      <p className="mt-1 text-sm text-slate-300">0 мин — {item.kind === 'intervention' ? 'плановое начало по журналу издателя' : 'начало окна сравнения'}. Шаг отсчётов 300 с. Время из книги, смещение неизвестно.</p>
      <div className="mt-4 grid grid-cols-[5.25rem_minmax(0,1fr)] gap-x-2 sm:grid-cols-[7rem_minmax(0,1fr)]">
        <div aria-hidden="true" />
        <div aria-hidden="true" className="relative h-5 text-xs">
          <span className="font-semibold text-slate-300">PRE</span>
          <span className="absolute ml-1 font-semibold text-sky-200" style={{ left: `${boundary / width * 100}%` }}>[start, end)</span>
        </div>
        {channels.map(([key, label, kind]) => (
          <div className="contents" key={key}>
            <div className="my-0.5 flex h-10 flex-col justify-center text-xs sm:text-sm">
              <span className="font-medium">{label}</span>
              <span className="text-[10px] text-slate-400">{kind}</span>
            </div>
            <svg viewBox={`0 0 ${width} 40`} preserveAspectRatio="none" className="my-0.5 h-10 w-full" aria-hidden="true">
              <rect x="0" y="0" width={boundary} height="40" fill="#243044" />
              <rect x={boundary} y="0" width={end - boundary} height="40" fill="#12283b" />
              <path d={`M${boundary} 0v40 M${end} 0v40`} stroke="#809bb3" vectorEffect="non-scaling-stroke" />
              {key === 'supply' && first !== '' && confirm !== '' &&
                [first, confirm].map((time) => (
                  <path key={time} d={`M${x(Number(time))} 0v40`} stroke="#7dd3fc" strokeDasharray="2 3" vectorEffect="non-scaling-stroke" />
                ))}
              {item.observations.map((tick) => {
                const value = tick[key];
                const pos = x(tick.relative_seconds);
                if (value === null) return <path key={tick.native_time} d={`M${pos - 4} 20h8`} stroke="#94a3b8" strokeWidth="2" vectorEffect="non-scaling-stroke" />;
                const y = value === 1 ? 10 : 30;
                return <path key={tick.native_time} d={`M${pos} ${y - 2}v4`} stroke={value === 1 ? '#7dd3fc' : '#cbd5e1'}
                  strokeWidth="4" strokeLinecap={value === 1 ? 'round' : 'square'} vectorEffect="non-scaling-stroke" />;
              })}
            </svg>
          </div>
        ))}
        <div />
        <div aria-hidden="true" className="relative h-5 text-xs tabular-nums text-slate-400">
          {[-10, 0, 30, 60, 90].map((minute) =>
            <span key={minute} className={`absolute whitespace-nowrap ${minute === 90 ? '-translate-x-full' : minute === -10 ? '' : '-translate-x-1/2'}`}
              style={{ left: `${minute === -10 ? 0 : x(minute * 60) / width * 100}%` }}>
              {minute > 0 ? '+' : ''}{minute}
            </span>)}
        </div>
      </div>
      <p className="mt-3 text-xs leading-relaxed text-slate-300">● ON (верхний ряд) · ■ OFF (нижний ряд) · — нет значения. Каждый знак — отдельный отсчёт. Пунктир на притоке отмечает первый и повторный OFF, когда они зафиксированы правилом A.</p>
      <details className="mt-4 border-t border-slate-700 pt-3">
        <summary className={`cursor-pointer text-sm font-medium text-sky-200 ${focus}`}>Все отсчёты · {item.observations.length}</summary>
        <div className="mt-3 overflow-x-auto" tabIndex={0} role="region" aria-label="Таблица отсчётов BAS">
          <table className="w-full text-left text-xs tabular-nums">
            <thead className="text-slate-300">
              <tr>{['Зона', 'Время книги', 'От начала', ...channels.map(([, name]) => name), 'A · состояние', 'B · состояние']
                .map((name) => <th key={name} scope="col" className="whitespace-nowrap p-2">{name}</th>)}</tr>
            </thead>
            <tbody>
              {item.observations.map((tick) => (
                <tr key={tick.native_time} className={tick.partition === 'PRE' ? 'bg-slate-800' : 'border-t border-slate-800'}>
                  {[tick.partition, tick.native_time, relative(tick.relative_seconds), ...channels.map(([key]) => bit(tick[key])),
                    tick.supply_evidence, tick.paired_evidence].map((cell, i) =>
                    <td key={i} className="whitespace-nowrap p-2">{cell}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </section>
  );
}

function Provenance({ item, provenance }: { item: EvidenceWindow; provenance: FieldEvidence['provenance'] }) {
  const file = item.archived_outcome.raw_file;
  const source = provenance.files[file];
  const schedule = provenance.files["Faults_schedule_and_description.xlsx"];
  return (
    <details className={panel}>
      <summary className={`cursor-pointer text-base font-semibold text-sky-200 ${focus}`}>Паспорт источника и контрольные суммы</summary>
      <div className="mt-4 space-y-3 break-words text-sm text-slate-300">
        <p>Nehasil et al., 2021 · Mendeley Data V{provenance.version} · {provenance.license}. <a className="text-sky-200 underline" href={provenance.dataset_url}>{provenance.dataset_doi}</a></p>
        <p>Книга {file}, лист {item.archived_outcome.source_sheet}. ID файла <code>{source.file_id}</code>. SHA-256 <code className="break-all">{source.publisher_sha256}</code>.</p>
        <p>Расписание издателя · ID файла <code>{schedule.file_id}</code>. SHA-256 <code className="break-all">{schedule.publisher_sha256}</code>.</p>
        <p>Правило <code>{provenance.rule_version}</code>. Шаг {provenance.cadence_seconds} с. Колонка времени <code>{provenance.timestamp_column}</code>.</p>
        <ul className="space-y-1">
          {channels.map(([key, name, kind]) => <li key={key}>{name} · {kind} · <code className="break-all">{provenance.input_columns[key]}</code></li>)}
        </ul>
        <p>Проводка и физический смысл обратной связи тегов статуса не подтверждены. Теги <code>signal__required_value__fan_*</code> задают команды приводам. Измерений скорости в этих тегах нет.</p>
        <p>SHA-256 следа <code className="break-all">{item.archived_outcome.trace_sha256}</code></p>
        <p>SHA-256 манифеста источника <code className="break-all">{provenance.source_manifest_sha256}</code></p>
        <p>SHA-256 архива Stage09 <code className="break-all">{provenance.stage09_zip_sha256}</code></p>
      </div>
    </details>
  );
}

export function FieldEvidencePage() {
  const [evidence, setEvidence] = useState<FieldEvidence>();
  const [unavailable, setUnavailable] = useState(false);
  const [ahu, setAhu] = useState('AHU1');
  const [selection, setSelection] = useState('event-AHU1');

  useEffect(() => {
    const controller = new AbortController();
    fetch('/api/research/field-evidence', { signal: controller.signal, cache: 'no-store' })
      .then((response) => {
        if (!response.ok) throw new Error('SOURCE_PROVENANCE_UNVERIFIED');
        return response.json() as Promise<FieldEvidence>;
      })
      .then(setEvidence)
      .catch(() => {
        if (!controller.signal.aborted) setUnavailable(true);
      });
    return () => controller.abort();
  }, []);

  const windows = evidence?.cases.filter((item) => item.ahu === ahu) ?? [];
  const item = windows.find(({ id }) => id === selection);
  const controls = windows.filter(({ kind }) => kind === 'matched_control');
  const event = windows.find(({ kind }) => kind === 'intervention');
  return (
    <main className="mx-auto max-w-7xl space-y-4 px-4 py-6 sm:px-8 sm:py-8">
      <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
        <a href="/research" className={`text-sky-200 underline ${focus}`}>← Научный хаб</a>
        <span className="text-slate-400">Stage10 · Только чтение</span>
      </div>
      <header>
        <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">Полевые свидетельства BAS</h1>
        <p className="mt-2 max-w-3xl text-sm leading-relaxed text-slate-300">6 запланированных вмешательств за один день и 6 подобранных контрольных окон на одном объекте. Записи BAS показывают отчётные состояния. Теги могли быть переопределены или не отражать физическую работу оборудования.</p>
      </header>
      <aside aria-label="Границы свидетельств" className="rounded-xl border border-slate-700 bg-slate-900 p-4 text-sm leading-relaxed text-slate-300">
        <p>Наблюдения каждые 5 минут по часам книги. Часовой пояс, смещение и точный момент вмешательства неизвестны. Независимого подтверждения исправности контрольных окон нет.</p>
        <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[10px] text-slate-300 sm:text-xs">
          {['REAL_BMS_REPORTED', 'INJECTED_INTERVENTION_IN_LOG', 'NOT_PHYSICAL_PROOF', 'SOURCE_5_MIN',
            'UNKNOWN_CLOCK_NAIVE_WORKBOOK_300S', 'NO_INDEPENDENT_HEALTHY_GROUND_TRUTH'].map((tag) =>
            <li key={tag} className="font-mono [overflow-wrap:anywhere]">{tag}</li>)}
        </ul>
      </aside>
      {unavailable && <p role="alert" className={panel}><strong>SOURCE_PROVENANCE_UNVERIFIED</strong> · Происхождение источника не подтверждено. Наблюдения скрыты.</p>}
      {!evidence && !unavailable && <p role="status">Проверяем замороженный архив…</p>}
      {evidence && item && (
        <>
          <div className="flex flex-wrap gap-4">
            <label className="grid gap-1 text-sm">Установка
              <select value={ahu} className={`rounded-lg border border-slate-600 bg-slate-900 px-3 py-2 ${focus}`}
                onChange={(event) => {
                  setAhu(event.target.value);
                  setSelection(`event-${event.target.value}`);
                }}>
                {evidence.cases.filter(({ kind }) => kind === 'intervention').map(({ ahu }) => <option key={ahu}>{ahu}</option>)}
              </select>
            </label>
            <label className="grid min-w-0 gap-1 text-sm">Окно
              <select value={selection} className={`max-w-full rounded-lg border border-slate-600 bg-slate-900 px-3 py-2 ${focus}`}
                onChange={(event) => setSelection(event.target.value)}>
                {windows.map((entry) => <option value={entry.id} key={entry.id}>{entry.kind === 'intervention'
                  ? 'Вмешательство по журналу' : `Контроль · +${entry.evaluation_metadata.offset_calendar_days} дн.`}</option>)}
              </select>
            </label>
          </div>
          <section aria-label={`Исходы ${ahu}`} className="grid gap-3 sm:grid-cols-2" aria-live="polite">
            <Outcome item={item} rule="A" />
            <Outcome item={item} rule="B" />
          </section>
          <Timeline item={item} />
          <section className={panel} aria-labelledby="field-controls">
            <h2 id="field-controls" className={heading}>Подобранные контроли · {ahu}</h2>
            {controls.length ? (
              <>
                <p className="mt-1 text-sm text-slate-300">Для этих окон совпала предыстория из двух парных ON при запросе нагрева. В шести выбранных окнах переходов нет. По ним нельзя оценить полевую частоту ложных срабатываний.</p>
                <div className="mt-3 grid gap-3 sm:grid-cols-2">
                  {controls.map((control) => (
                    <article key={control.id} className="rounded-lg border border-slate-700 bg-slate-950/70 p-3 text-sm">
                      <button type="button" aria-pressed={selection === control.id} onClick={() => setSelection(control.id)}
                        className={`rounded text-left font-semibold text-sky-200 underline ${focus}`}>
                        Контроль · +{control.evaluation_metadata.offset_calendar_days} дн.
                      </button>
                      <p className="mt-1 text-xs text-slate-400">{control.start} → {control.end_exclusive.slice(11)}</p>
                      <p className="mt-2">Оба BAS-статуса ON · {control.archived_outcome.pair_11_ticks}/{control.archived_outcome.window_ticks} отсчётов</p>
                      <p className="mt-1 text-xs text-slate-300">A · {changeText(control, 'A')}<br />B · {changeText(control, 'B')}</p>
                    </article>
                  ))}
                </div>
              </>
            ) : <p className="mt-1 text-sm text-slate-300">Подходящие окна сравнения отсутствуют. В исходном окне не набралось двух пригодных парных ON перед началом.</p>}
          </section>
          <section className={panel} aria-label="Аннотации издателя">
            <h2 className={heading}>Аннотации издателя</h2>
            <p className="mt-1 text-sm text-slate-300">{item.kind === 'intervention'
              ? `PUBLISHER_SCHEDULE · ${item.evaluation_metadata.publisher_id_evaluation_only}, строка ${item.evaluation_metadata.schedule_row}. Издатель запланировал вмешательство для этого окна.`
              : 'Это окно выбрано Stage09 для сравнения с расписанием издателя. Исправность оборудования независимо не подтверждена.'}
              {' '}Расписание и метки служат для оценки и не входят в четыре сигнала правила.</p>
            {event?.evaluation_metadata.note_evaluation_only &&
              <p className="mt-2 text-sm text-slate-300">Издатель сообщил о неисправном датчике перепада давления во время вмешательства. Независимого подтверждения по перепаду давления нет.</p>}
          </section>
          <section className={panel}>
            <h2 className={heading}>Что запросить для проверки</h2>
            <p className="mt-1 text-sm text-slate-300">{verification[ahu]}</p>
          </section>
          <Provenance item={item} provenance={evidence.provenance} />
        </>
      )}
    </main>
  );
}
