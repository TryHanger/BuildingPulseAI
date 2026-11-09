import { G36EvidenceLimits } from '../components/G36EvidenceLimits';
import { Fragment, useEffect, useState } from 'react';
import ReactECharts from 'echarts-for-react';
import type { EChartsOption, LineSeriesOption } from 'echarts';
import { investigatorV1 } from '../api/investigatorV1';
import type { components } from '../types/openapi-v1.generated';

type WindowData = components['schemas']['G36BenchmarkWindow'];
type Comparison = components['schemas']['G36BenchmarkComparison'];
type Point = components['schemas']['G36BenchmarkPoint'];
type ValueKey = 'sat_k' | 'setpoint_k' | 'mat_k' | 'cooling_command' | 'reference_oracle';

const card = 'min-w-0 rounded-xl border border-slate-800 bg-slate-900 p-4';
const field = 'max-w-full rounded bg-slate-800 px-2 py-1 text-sm';
const periodNames: Record<string, string> = {
  NOMINAL_PRE_WINDOW: 'Номинальный контроль',
  NOMINAL_COMPARISON_WINDOW: 'Номинальный прогон в тот же период',
  NOMINAL_POST_WINDOW: 'Конец номинального прогона',
  FULL_RUN: 'Полный прогон',
  PUBLISHER_VALVE_CLOSED_SCENARIO: 'Сценарий издателя · заданное закрытие клапана',
  PUBLISHER_NOMINAL: 'Номинальная симуляция',
  PRE_INJECTION_NOMINAL: 'До вмешательства',
  SIMULATED_VALVE_CLOSURE_INTERVAL: 'Интервал заданного закрытия клапана',
  SIMULATED_DAMPER_OPEN_INTERVAL: 'Заданное открытие наружной заслонки',
  SIMULATED_DUCT_LEAK_INTERVAL: 'Заданная утечка воздуховода',
  UNKNOWN_POST_WINDOW: 'После интервала · метка неизвестна',
};

const reasonNames: Record<Point['reason'], string> = {
  APPLICABLE: 'Применимо',
  UNKNOWN_WEATHER_CONTEXT: 'Погодный контекст неизвестен',
  INVALID_INPUT: 'Вход отсутствует или невалиден',
  FAN_OFF: 'Вентилятор выключен',
  LOW_COOLING_COMMAND: 'Низкая команда охлаждения',
  HEATING_COMMAND: 'Есть команда нагрева',
  LOW_TEMPERATURE_LIFT: 'Малый разнос MAT и уставки',
};

const scenarioNames: Record<WindowData['scenario'], string> = {
  NOMINAL: 'Номинальный прогон',
  VALVE_CLOSED: 'Заданное закрытие клапана',
  DAMPER_OPEN: 'Заданное открытие наружной заслонки',
  DUCT_LEAK: 'Заданная утечка воздуховода',
};

function CrossScenarioTable() {
  const [comparison, setComparison] = useState<Comparison>();
  const [error, setError] = useState('');
  useEffect(() => {
    const controller = new AbortController();
    investigatorV1.g36Comparison(controller.signal).then(result => {
      if (!controller.signal.aborted) setComparison(result);
    }).catch((failure: Error) => {
      if (!controller.signal.aborted) setError(failure.message);
    });
    return () => controller.abort();
  }, []);
  return <section className={card} aria-label="Сравнение четырёх прогонов">
    <h2 className="font-semibold">Номинальный и перекрёстные контроли · 5wk</h2>
    <p className="my-2 text-sm text-slate-300">
      Разведочное сравнение после просмотра данных. Один прогон на сценарий, отсчёты внутри прогона зависимы.
      Температурный симптом встречается в нескольких сценариях. Причина не оценивалась.
    </p>
    {error && <p role="alert" className="text-sm text-rose-200">Таблица недоступна · {error}</p>}
    {!comparison && !error && <p role="status">Загрузка сводок прогонов…</p>}
    {comparison && <table className="w-full table-fixed text-left text-xs sm:text-sm">
      <thead className="bg-slate-800 text-slate-200">
        <tr>
          <th scope="col" className="w-[30%] p-1 sm:p-2">Прогон</th>
          <th scope="col" className="w-[21%] p-1 sm:p-2">Оценено / всего</th>
          <th scope="col" className="w-[16%] break-words p-1 sm:p-2"><span className="sm:hidden">Поточ.</span><span className="hidden sm:inline">Поточечные</span></th>
          <th scope="col" className="w-[18%] break-words p-1 sm:p-2"><span className="sm:hidden">Подтв.</span><span className="hidden sm:inline">Подтверждённые</span></th>
          <th scope="col" className="w-[15%] p-1 sm:p-2">Начала</th>
        </tr>
      </thead>
      <tbody>
        {comparison.runs.map(run => <Fragment key={run.scenario}>
          <tr className="border-t border-slate-700 align-top">
            <th scope="row" className="break-words p-1 font-medium sm:p-2">{scenarioNames[run.scenario]}</th>
            <td className="p-1 sm:p-2">{run.summary.applicable} / {run.summary.samples}</td>
            <td className="p-1 sm:p-2">{run.summary.point_exceedances}</td>
            <td className="p-1 sm:p-2">{run.summary.confirmed_samples}</td>
            <td className="p-1 sm:p-2">{run.episode_starts}</td>
          </tr>
          <tr><td colSpan={5} className="px-1 pb-2 text-slate-300 sm:px-2">
            <details>
              <summary className="cursor-pointer">Причины воздержания и распределение команды</summary>
              <p>{Object.entries(run.summary.abstentions).map(([reason, count]) =>
                `${reasonNames[reason as Point['reason']] ?? reason} · ${count}`).join(' · ')}</p>
              <p>Команда охлаждения на применимых отсчётах: {Object.entries(run.cooling_command_bins)
                .map(([range, count]) => `${range} → ${count}`).join(' · ')}</p>
            </details>
          </td></tr>
        </Fragment>)}
      </tbody>
    </table>}
    <details className="mt-2 text-sm text-slate-300">
      <summary className="cursor-pointer">Ограничения сопоставимости</summary>
      <p>В предынъекционной части номинального и клапанного прогонов различаются 59 строк. В полном ряду уставка
        и статус вентилятора различаются на 4 626 отметках. Сводки описывают каждый прогон по его собственному режиму.</p>
      <p>Парное сравнение G36-1wk остаётся заблокированным. Независимое описательное применение доступно в отдельном профиле.</p>
    </details>
  </section>;
}

function chartOptions(points: Point[], cursor: number, unit: string,
  keys: Array<[ValueKey, string, string]>): EChartsOption {
  const series: LineSeriesOption[] = keys.map(([key, name, color]) => ({
    type: 'line', name, symbolSize: 3, connectNulls: false, itemStyle: { color },
    lineStyle: { width: 2, type: key === 'reference_oracle' ? 'dashed' : 'solid' },
    data: points.flatMap((point, i) => {
      const sample = [point.time_s, point[key]];
      return i > 0 && point.gap_before
        ? [[(points[i - 1].time_s + point.time_s) / 2, null], sample]
        : [sample];
    }),
  }));
  series[0].markLine = {
    silent: true, symbol: 'none', label: { show: false }, lineStyle: { color: '#fbbf24' },
    data: [{ xAxis: cursor }],
  };
  return {
    animation: false, tooltip: { trigger: 'axis' },
    grid: { left: 58, right: 20, top: 62, bottom: 40 },
    legend: { top: 0, textStyle: { color: '#cbd5e1' } },
    xAxis: { type: 'value', min: 'dataMin', max: 'dataMax', splitNumber: 3,
      axisLabel: { color: '#94a3b8', hideOverlap: true, fontSize: 10 }, name: 'с', nameLocation: 'end' },
    yAxis: { type: 'value', scale: unit === 'K', max: unit === 'доля' ? 1 : undefined,
      name: unit, axisLabel: { color: '#94a3b8' }, splitLine: { lineStyle: { color: '#334155' } } },
    series,
  };
}

export function G36BenchmarkPage() {
  const [dataset, setDataset] = useState<WindowData['dataset_id']>('g36-5wk');
  const week = dataset === 'g36-1wk';
  const [scenario, setScenario] = useState<WindowData['scenario']>('VALVE_CLOSED');
  const [panel, setPanel] = useState<WindowData['panel']>('BASIC');
  const [start, setStart] = useState(16354800);
  const [seek, setSeek] = useState(String(start));
  const [index, setIndex] = useState(0);
  const [data, setData] = useState<WindowData>();
  const [error, setError] = useState('');
  useEffect(() => {
    const controller = new AbortController();
    setError('');
    setData(undefined);
    setIndex(0);
    investigatorV1.g36Benchmark({ dataset, scenario, panel, start }, controller.signal).then(result => {
      if (!controller.signal.aborted) setData(result);
    }).catch((failure: Error) => {
      if (!controller.signal.aborted) setError(failure.message);
    });
    return () => controller.abort();
  }, [dataset, scenario, panel, start]);
  const point = data?.points[index];
  const showOracle = panel === 'EXTRA_SIMULATED' && data?.panel === 'EXTRA_SIMULATED';

  return <main className="mx-auto max-w-[1280px] space-y-4 p-3 sm:p-4">
    <section className={card}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold text-sky-300">SIMULATED_BENCHMARK · {week ? 'G36-1wk' : 'G36-5wk'}</p>
          <h1 className="text-xl font-semibold">Устойчивое превышение SAT над уставкой при запросе охлаждения</h1>
        </div>
        <a href="/assets/ahu-sd" className="text-sm text-sky-300 underline">Открыть Investigator LBNL</a>
      </div>
      <p className="my-2 text-sm text-slate-300">Каждый прогон оценивается по его собственному режиму и уставке. Окна показывают симптом в симуляции.</p>
      <div className="flex flex-wrap items-end gap-3">
        <label className="grid gap-1 text-xs">Профиль G36
          <select aria-label="Профиль G36" className={field} value={dataset} onChange={event => {
            const value = event.target.value as WindowData['dataset_id'];
            const beginning = value === 'g36-1wk' ? 17625600 : 16354800;
            setDataset(value);
            setPanel('BASIC');
            setStart(beginning);
            setSeek(String(beginning));
            if (scenario === 'DAMPER_OPEN' || scenario === 'DUCT_LEAK') setScenario('VALVE_CLOSED');
          }}>
            <option value="g36-5wk">G36-5wk · шаг 300 с</option>
            <option value="g36-1wk">G36-1wk · шаг 60 с</option>
          </select>
        </label>
        <label className="grid gap-1 text-xs">Прогон
          <select aria-label="Прогон" className={field} value={scenario} onChange={event => setScenario(event.target.value as WindowData['scenario'])}>
            <option value="VALVE_CLOSED">Заданное закрытие клапана</option>
            <option value="NOMINAL">{scenarioNames.NOMINAL}</option>
            {!week && <option value="DAMPER_OPEN">{scenarioNames.DAMPER_OPEN}</option>}
            {!week && <option value="DUCT_LEAK">{scenarioNames.DUCT_LEAK}</option>}
          </select>
        </label>
        <label className="grid gap-1 text-xs">Панель
          <select className={field} value={panel} onChange={event => setPanel(event.target.value as WindowData['panel'])}>
            <option value="BASIC">BASIC</option>
            <option value="EXTRA_SIMULATED">EXTRA_SIMULATED</option>
          </select>
        </label>
        <form className="flex max-w-full flex-wrap items-end gap-2" onSubmit={event => {
          event.preventDefault();
          setStart(Number(seek));
        }}>
          <label className="grid gap-1 text-xs">Начало окна, модельные секунды
            <input className={field} type="number" min={0} required value={seek} onChange={event => setSeek(event.target.value)} />
          </label>
          <button className={field}>Открыть окно</button>
        </form>
        <button className={field} disabled={data?.next_start == null} onClick={() => {
          if (data?.next_start != null) {
            setSeek(String(data.next_start));
            setStart(data.next_start);
          }
        }}>Следующее окно</button>
      </div>
      {error && <p role="alert" className="mt-2 text-rose-200">Ошибка источника G36 · {error}</p>}
      {!data && !error && <p role="status" className="mt-2">Чтение проверенного ряда…</p>}
    </section>
    {week ? <section className={card} aria-label="Ограничения 1wk">
      <h2 className="font-semibold">G36-1wk · отдельная описательная оценка</h2>
      <p className="text-sm text-amber-200">UNPAIRED_DESCRIPTIVE · NOT_BLIND_PREVIEWED_SOURCE · MODEL_SECONDS</p>
      <p className="my-2 text-sm text-slate-300">Каждый прогон оценён отдельно на всех исходных отсчётах. Причина не установлена.</p>
      {data && <p className="text-sm text-slate-300">Отдельная описательная оценка · {data.unpaired_descriptive_gate} ·
        Парная причинная оценка · {data.paired_causal_gate}</p>}
      <details className="text-sm text-slate-300">
        <summary className="cursor-pointer">Ограничения сопоставимости и метки</summary>
        <p>Максимальные различия OAT/OWB между прогонами составляют 0,1497 K и 0,0958 K. Статус вентилятора
          различается на 2 946 отсчётах, уставка SAT — на 3 042. Причина различий неизвестна. Парное сравнение заблокировано.</p>
        <p>Две крайние записи сценария закрытого клапана включены в расчёт. Метка относится ко всему
          издательскому сценарию. Oracle доступен в EXTRA_SIMULATED.</p>
        {showOracle && scenario === 'VALVE_CLOSED' && <p>В двух последних записях модельное положение клапана равно 1.</p>}
      </details>
    </section> : <CrossScenarioTable />}
    {data && <>
      <section className={card} aria-label="Отсчёт и результат">
        {point ? <>
          <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
            <p className="font-semibold">Модельное время {point.time_s} с · {periodNames[point.label]}</p>
            <span className="text-amber-200">{point.confirmed ? 'Температурный симптом подтверждён' :
              point.point_exceeds ? 'Поточечное превышение' : point.method_status === 'INCONCLUSIVE'
                ? 'Оценка не определена' : reasonNames[point.reason]}</span>
          </div>
          <input className="my-2 w-full" type="range" aria-label="Курсор модели" min={0}
            max={data.points.length - 1} value={index} onChange={event => setIndex(Number(event.target.value))} />
          <p className="text-sm text-slate-300">Измерение SAT {point.sat_k ?? '—'} K · Уставка {point.setpoint_k ?? '—'} K · Остаток {point.residual_k?.toFixed(2) ?? '—'} K</p>
          <p className="text-sm text-slate-300">Команда охлаждения {point.cooling_command ?? '—'} · {reasonNames[point.reason]}</p>
          <p className="text-xs text-slate-400">Статус вентилятора {point.fan_mode} · погодный контекст {point.weather_status}
            {' · '}Физическое разрешение охлаждения неизвестно</p>
          <details className="mt-2 text-xs text-slate-300">
            <summary className="cursor-pointer">Свидетельства и роли входов</summary>
            <p>{point.method_status} · {point.predicate} · {data.cause_status}</p>
            <ul className="break-words">{data.evidence_roots.map(root => <li key={root.point}>
              {root.role} · {root.source_column} · {root.unit}
            </li>)}</ul>
            <p>Метка прогона получена из паспорта. Модельный oracle не является независимым свидетельством.</p>
          </details>
          <G36EvidenceLimits coolingEnable={data.cooling_enable} confirmed={point.confirmed} />
          {showOracle && <p className="text-sm text-violet-300">
            REFERENCE_ORACLE · Положение клапана в симуляции {point.reference_oracle ?? '—'} · Вне проверки BASIC
            {point.source_oracle_status && <> · {point.source_oracle_status}</>}
          </p>}
        </> : <p>В этом окне нет отсчётов.</p>}
      </section>
      {point && <div className="grid gap-3 lg:grid-cols-2">
        <section className={card} aria-label="Температуры G36">
          <h2 className="mb-2 font-semibold">Температуры · измерения модели и уставка</h2>
          <ReactECharts style={{ height: 255 }} option={chartOptions(data.points, point.time_s, 'K', [
            ['sat_k', 'SAT · измерение', '#38bdf8'], ['setpoint_k', 'Уставка SAT', '#94a3b8'],
            ['mat_k', 'MAT · измерение', '#fb923c'],
          ])} />
        </section>
        <section className={card} aria-label="Команда и oracle G36">
          <h2 className="mb-2 font-semibold">Клапан охлаждения · {showOracle ? 'команда и модельное положение' : 'команда'}</h2>
          <ReactECharts notMerge style={{ height: 255 }} option={chartOptions(data.points, point.time_s, 'доля', [
            ['cooling_command', 'Команда BAS', '#34d399'],
            ...(showOracle ? [['reference_oracle', 'REFERENCE_ORACLE', '#c084fc'] as const] : [])
              .map(([key, label, color]): [ValueKey, string, string] => [key, label, color]),
          ])} />
        </section>
      </div>}
      <section className={card}>
        <h2 className="mb-2 font-semibold">{week ? 'Сводка полного прогона · модельные секунды' :
          'Сводка прогона · выдержка обнуляется на границах периодов'}</h2>
        {week && <p className="mb-2 text-sm text-slate-300">На сценарий приходится {data.runs_per_scenario} симуляционный прогон.
          Счётчики относятся к минутным отсчётам. Начала подтверждений отмечают эпизоды симптома внутри прогона.</p>}
        <div className="grid gap-2 md:grid-cols-3">
          {data.summaries.map(summary => <div className="rounded bg-slate-800 p-2 text-sm" key={summary.period}>
            <p className="font-medium">{periodNames[summary.period]}</p>
            <p>Применимо {summary.applicable} из {summary.samples}</p>
            <p>Превышения {summary.point_exceedances} · Подтверждённые отсчёты {summary.confirmed_samples}</p>
            <p>Начала подтверждений {summary.symptom_starts}</p>
            <details>
              <summary className="cursor-pointer">Причины воздержания</summary>
              {Object.entries(summary.abstentions).map(([reason, count]) => <p key={reason}>
                {reasonNames[reason as Point['reason']] ?? reason} · {count}
              </p>)}
            </details>
          </div>)}
        </div>
        {data.residual_distribution && <p className="mt-2 text-sm text-slate-300">
          SAT − SP среди {data.residual_distribution.count} применимых отсчётов ·
          медиана {data.residual_distribution.median.toFixed(2)} K ·
          p05…p95 {data.residual_distribution.p05.toFixed(2)}…{data.residual_distribution.p95.toFixed(2)} K
        </p>}
        <p className="mt-2 text-sm text-slate-300">{data.policy_id} · SAT − уставка &gt; {data.threshold_k} K · выдержка {data.confirmation_seconds} с · шаг {data.sample_seconds} с</p>
        <p className="break-all text-xs text-slate-400">{data.source_file} · SHA-256 {data.source_sha256}</p>
      </section>
    </>}
  </main>;
}
