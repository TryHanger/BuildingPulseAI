import type { FieldEvidence } from '../pages/FieldEvidencePage';
import type { components } from '../types/virtual-sensor-research.generated';

export type CaseId = 'A' | 'B' | 'C' | 'D';
type Day = components['schemas']['Day'];
type Sample = {
  time: string;
  seconds: number;
  values: (number | null)[];
  context?: string;
};

export type DecisionTrace = {
  source: string;
  sourceUrl: string;
  provenance: [string, string][];
  quality: string;
  applicability: string;
  anomaly: string;
  cause: 'ABSTAIN';
  support: string;
  conflict: string;
  missing: string;
  action: string;
  clock: string;
  channels: string[];
  samples: Sample[];
  pilot: { method: string; observations: string[] };
  blocks?: { block: number; start_model_s: number; z: number; decision: string }[];
};

type TransferTrace = {
  provenance: Record<string, string>;
  gate: string;
  clock: string;
  calendar_minutes: number;
  eligible_minutes: number;
  independent_normal_runs: number;
  threshold: number;
  blocks: NonNullable<DecisionTrace['blocks']>;
  points: {
    model_seconds: number;
    source_row: number;
    sat_deg_f: number;
    setpoint_deg_f: number;
    prediction_deg_f: number | null;
    fan_status: number;
    plant_mode: number;
    source_support: boolean;
    eligible: boolean;
    abstain_reason: string | null;
  }[];
};
type TransferContract = {
  candidate: string;
  transfer_normal_gate: string;
  training_setpoint_support: { span: [string, string] };
  historical_normal_evidence: { stage06_archive_sha256: string };
};

const memberSha = '78878e54e682a76622c2305f329481f3b5397a61b347f3a783f947a4b9b9d7a4';
const basChannels = ['supply', 'exhaust', 'heat_request', 'cool_request'] as const;

async function read<T>(path: string, signal: AbortSignal): Promise<T> {
  const response = await fetch('/api/research/' + path, { signal, cache: 'no-store' });
  if (!response.ok) throw new Error('SOURCE_OR_CONTRACT_UNAVAILABLE');
  return response.json() as Promise<T>;
}

function lbnl(day: Day): DecisionTrace {
  if (day.case.id !== 'sa-plus-2' || day.day !== '2018-10-20' ||
      day.case.member_sha256 !== memberSha || day.case.alias_status !== 'UNVERIFIED_PUBLISHER_ALIAS' ||
      day.metadata.model_id !== 'bp-ml-repro-02-basic-sa_temp-993f42a79945' ||
      day.method !== 'SAT_ONLY' || day.threshold !== 3 || day.points.length !== day.evaluated_minutes) {
    throw new Error('SOURCE_OR_CONTRACT_UNAVAILABLE');
  }
  const evaluated = day.status === 'EVALUATED' && Number.isFinite(day.daily_score);
  return {
    source: 'LBNL SD-AHU · симуляция · ' + day.case.member,
    sourceUrl: 'https://doi.org/10.25984/1881324',
    provenance: [
      ['SHA-256 члена ZIP', day.case.member_sha256],
      ['SHA-256 исходного ZIP', day.metadata.source_sha256],
      ['SHA-256 протокола', day.metadata.integration_protocol_sha256],
      ['Модель', day.metadata.model_id],
    ],
    quality: `${day.evaluated_minutes} / ${day.calendar_minutes} минут оценено · RUNNING ${day.running_minutes ?? '—'} мин · непрерывно ${day.continuous_minutes} мин. Показаны исходные значения SAT на оценённых минутах. Прочие минуты отсутствуют на графике.`,
    applicability: `Stage02 · ${day.method} / ${day.metadata.arm} · ${day.metadata.policy_version} · ${day.status}${day.reason ? ' · ' + day.reason : ''}. Только архивная симуляция.`,
    anomaly: evaluated ? day.alert ?? 'NO_MODEL_ANOMALY' : 'UNAVAILABLE',
    cause: 'ABSTAIN',
    support: evaluated
      ? `Средний z остатка ${day.daily_score!.toFixed(4)} · порог > ${day.threshold}. Измеренный в симуляции SAT и прогноз относятся к одному прогону.`
      : 'Оценка суточного остатка недоступна.',
    conflict: 'UNAVAILABLE · подтверждённая инъекция SAT bias. Имя члена ZIP отличается от таблицы издателя (UNVERIFIED_PUBLISHER_ALIAS, G0/G1 D002).',
    missing: 'Однозначное сопоставление члена ZIP с инъекцией и независимое измерение SAT.',
    action: 'Запросить у LBNL таблицу соответствия или журнал инъекции. Для локализации смещения сравнить SAT с независимым калиброванным датчиком в том же сечении и режиме.',
    pilot: {
      method: `Stage02 · ${day.method} / ${day.metadata.arm} · ${day.metadata.policy_version} · ${day.status}`,
      observations: [
        evaluated ? `Средний z остатка ${day.daily_score!.toFixed(4)} · порог > ${day.threshold}.` : 'Суточный остаток недоступен.',
        `Член ZIP ${day.case.member} · статус соответствия таблице издателя: ${day.case.alias_status}.`,
        'Измеренный в симуляции SAT и прогноз относятся к одному прогону.',
      ],
    },
    clock: 'Минуты от начала дня по часам источника, смещение UTC неизвестно',
    channels: ['SAT источника, °F', 'Прогноз SAT, °F'],
    samples: day.points.map(point => ({
      time: point.timestamp,
      seconds: Number(point.timestamp.slice(11, 13)) * 3600 + Number(point.timestamp.slice(14, 16)) * 60,
      values: [point.actual, point.predicted],
      context: `Остаток ${point.absolute_residual.toFixed(4)} °F · z ${point.z.toFixed(4)}`,
    })),
  };
}

function g36(trace: TransferTrace, contract: TransferContract): DecisionTrace {
  if (trace.clock !== 'MODEL_SECONDS' || trace.gate !== 'STOP_OOD_HEALTHY' ||
      contract.transfer_normal_gate !== trace.gate ||
      contract.historical_normal_evidence.stage06_archive_sha256 !== trace.provenance.archive_sha256 ||
      trace.points.length !== 60 || trace.blocks.length !== 7 ||
      trace.points.some((point, index) => point.model_seconds !== 17645700 + index * 60)) {
    throw new Error('SOURCE_OR_CONTRACT_UNAVAILABLE');
  }
  const alertCount = trace.blocks.filter(block => block.decision === 'ALERT').length;
  return {
    source: 'G36-1wk · симуляция · BaselineSystem.csv',
    sourceUrl: 'https://doi.org/10.6084/m9.figshare.29297999',
    provenance: [
      ['SHA-256 BaselineSystem.csv', trace.provenance.source_sha256],
      ['SHA-256 модели LightGBM', trace.provenance.model_sha256],
      ['SHA-256 архива Stage06', trace.provenance.archive_sha256],
      ['SHA-256 минутной трассы', trace.provenance.trace_sha256],
      ['SHA-256 блочного CSV', trace.provenance.blocks_sha256],
      ['SHA-256 receipt', trace.provenance.receipt_sha256],
    ],
    quality: `${trace.eligible_minutes} / ${trace.calendar_minutes} минут допущено. Показан архивный срез из ${trace.points.length} минут; прогноз есть только на допущенных минутах.`,
    applicability: `Stage06 / Stage07 · ${contract.candidate} · ${trace.gate} · эксплуатационный допуск закрыт.`,
    anomaly: 'ABSTAIN',
    cause: 'ABSTAIN',
    support: `${alertCount} / ${trace.blocks.length} блоков дали ALERT (z > ${trace.threshold}) в ${trace.independent_normal_runs} симуляционном референсном прогоне. Трасса, блоки и результат используют этот же прогон.`,
    conflict: `Референсный прогон задан без инъекции. Активная уставка меняется, при обучении она составляла ${contract.training_setpoint_support.span[0]} °F. Прохождение одномерных диапазонов не подтверждает переносимость режима.`,
    missing: 'Независимые нормальные прогоны и подтверждённая карта режима, измерений и уставки на целевой установке.',
    action: 'Проверить по журналу контроллера активную уставку SAT и режим работы. Собрать независимые нормальные прогоны в этих режимах и проверить частоту ложных тревог перед эксплуатационным применением.',
    pilot: {
      method: `Stage06 / Stage07 · ${contract.candidate}`,
      observations: [
        `${alertCount} / ${trace.blocks.length} блоков с ALERT (z > ${trace.threshold}) · ${trace.independent_normal_runs} референсный симуляционный прогон без инъекции.`,
        `В обучающем источнике зарегистрировано одно значение активной уставки SAT: ${contract.training_setpoint_support.span[0]} °F.`,
        'Минутная трасса и блочные решения относятся к одному прогону.',
      ],
    },
    clock: 'Секунды модели (MODEL_SECONDS)',
    channels: ['SAT источника, °F', 'Активная уставка SAT, °F', 'Сохранённый прогноз SAT, °F'],
    samples: trace.points.map(point => ({
      time: String(point.model_seconds),
      seconds: point.model_seconds,
      values: [point.sat_deg_f, point.setpoint_deg_f, point.prediction_deg_f],
      context: `Строка ${point.source_row} · вентилятор ${point.fan_status} · режим ${point.plant_mode} · одномерный support ${point.source_support ? 'да' : 'нет'} · ${point.eligible ? 'ELIGIBLE' : point.abstain_reason}`,
    })),
    blocks: trace.blocks,
  };
}

function field(payload: FieldEvidence, ahu: 'AHU23' | 'AHU2'): DecisionTrace {
  const item = payload.cases.find(candidate => candidate.id === 'event-' + ahu);
  const origin = payload.provenance;
  if (!item || origin.version !== 1 || origin.dataset_doi !== '10.17632/jkw85sm4v4.1' ||
      origin.rule_version !== 'bas-fan-observation@1.0.0' ||
      origin.clock !== 'UNKNOWN_CLOCK_NAIVE_WORKBOOK_300S') {
    throw new Error('SOURCE_OR_CONTRACT_UNAVAILABLE');
  }
  const outcome = item.archived_outcome;
  if (outcome.physical_fault !== 'ABSTAIN' ||
      item.observations.length !== Number(outcome.pre_ticks) + Number(outcome.window_ticks) ||
      !item.observations.every(tick => basChannels.every(channel => [0, 1, null].includes(tick[channel])))) {
    throw new Error('SOURCE_OR_CONTRACT_UNAVAILABLE');
  }
  const observed = outcome.A_change === 'BAS_ON_TO_OFF_OBSERVED';
  return {
    source: `Mendeley V${origin.version} · ${item.ahu} · экспорт BMS`,
    sourceUrl: origin.dataset_url,
    provenance: [
      ['DOI', origin.dataset_doi],
      ['Файл', outcome.raw_file],
      ['SHA-256 книги', outcome.raw_sha256],
      ['SHA-256 трассы', outcome.trace_sha256],
      ['SHA-256 манифеста', origin.source_manifest_sha256],
      ['SHA-256 архива Stage09', origin.stage09_zip_sha256],
      ...basChannels.map((channel): [string, string] => [channel, origin.input_columns[channel]]),
    ],
    quality: `${outcome.window_ticks} отсчётов окна + ${outcome.pre_ticks} PRE · известно в окне: приток ${outcome.supply_available}, вытяжка ${outcome.exhaust_available}, нагрев ${outcome.heat_available}, охлаждение ${outcome.cool_available}.`,
    applicability: `Stage09 / Stage10 · ${origin.rule_version} · A: ${outcome.A_status} · B: ${outcome.B_status}. Отчётные состояния BAS.`,
    anomaly: outcome.A_change,
    cause: outcome.physical_fault,
    support: observed
      ? `A: ${outcome.A_change}. Первый OFF ${outcome.A_first_off_inclusive}, повторный OFF ${outcome.A_confirm_off}. Оба правила используют одну книгу BAS.`
      : `A: ${outcome.A_change} · B: ${outcome.B_change}. Оба правила используют одну книгу BAS.`,
    conflict: observed
      ? `B: ${outcome.B_change}. ${outcome.pair_01_ticks} отсчётов с притоком OFF и вытяжкой ON. Совместный переход двух статусов не наблюдался.`
      : 'При отсутствующих каналах согласие и расхождение состояний оценить невозможно.',
    missing: observed
      ? 'Независимое подтверждение вращения или расхода. Издатель указал неисправность датчика перепада давления в этом окне.'
      : 'Статусы притока и вытяжки, запросы нагрева и охлаждения, независимый признак работы и расход.',
    action: observed
      ? 'Сверить привязку тегов с приводами, снять обратную связь с каждого привода и измерить расход либо перепад давления исправным прибором.'
      : 'Восстановить тренды статусов обоих вентиляторов и запросов нагрева и охлаждения. Снять обратную связь с приводов и независимый расход, затем повторить проверку.',
    pilot: {
      method: `Stage09 / Stage10 · ${origin.rule_version} · A: ${outcome.A_status} · B: ${outcome.B_status}`,
      observations: [
        `Приток (A): ${outcome.A_change}. Пара тегов (B): ${outcome.B_change}.`,
        observed
          ? `Первый OFF притока: ${outcome.A_first_off_inclusive}, повтор: ${outcome.A_confirm_off}. Приток OFF / вытяжка ON: ${outcome.pair_01_ticks} отсчётов.`
          : 'Пустые ячейки сохранены при отображении.',
        observed
          ? 'Оба правила используют одну книгу BAS. В журнале издателя отмечена неисправность датчика перепада давления.'
          : 'Оба правила используют одну книгу BAS.',
      ],
    },
    clock: `Секунды от начала окна по часам книги, шаг ${origin.cadence_seconds} с. Смещение UTC неизвестно`,
    channels: ['Приток BAS', 'Вытяжка BAS', 'Запрос нагрева', 'Запрос охлаждения'],
    samples: item.observations.map(tick => ({
      time: tick.native_time,
      seconds: tick.relative_seconds,
      values: basChannels.map(channel => tick[channel]),
      context: tick.partition,
    })),
  };
}

export async function loadDecisionTrace(id: CaseId, signal: AbortSignal): Promise<DecisionTrace> {
  if (id === 'A') {
    return lbnl(await read<Day>('virtual-sensors/day?case=sa-plus-2&day=2018-10-20', signal));
  }
  if (id === 'B') {
    const [trace, contract] = await Promise.all([
      read<TransferTrace>('transfer-trace-15', signal),
      read<TransferContract>('domain-shift-07', signal),
    ]);
    return g36(trace, contract);
  }
  return field(await read<FieldEvidence>('field-evidence', signal), id === 'C' ? 'AHU23' : 'AHU2');
}
