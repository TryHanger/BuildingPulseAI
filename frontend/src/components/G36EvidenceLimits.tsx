import sensorEvidence from '../fixtures/g56_sensor_evidence.json';

const sources = [
  {
    id: 'G36',
    heading: 'SIMULATION · G36',
    context: 'Текущий источник · модельные величины и издательский oracle. Установленные датчики AHU здесь отсутствуют.',
  },
  {
    id: 'RBC_NESBITT',
    heading: 'FIELD · RBC-Nesbitt',
    context: 'Другой источник · опубликованные полевые колонки за пределами текущего прогона G36.',
  },
];

export function G36EvidenceLimits({ coolingEnable, confirmed }: {
  coolingEnable: string;
  confirmed: boolean;
}) {
  return (
    <details className="mt-3 space-y-3 rounded border border-slate-700 p-3 text-sm text-slate-300">
      <summary className="cursor-pointer font-semibold text-slate-100">Sensor Lab · границы наблюдаемости</summary>
      {coolingEnable === 'UNKNOWN' && <p className="text-amber-200">
        Физическое охлаждение неизвестно (UNKNOWN). Причина не установлена.
      </p>}
      <p>{confirmed ? 'Температурный симптом SAT подтверждён на выбранном отсчёте.' :
        'Для выбранного отсчёта подтверждение симптома SAT отсутствует.'} Возможные объяснения и измерения для их проверки:</p>
      <ul className="list-disc space-y-1 pl-5">
        <li>Недостаточная подача холода · расход на ветви и перепад давления помогают проверить поступление воды.</li>
        <li>Наружная заслонка · измеренная доля наружного воздуха помогает проверить смешение.</li>
        <li>Утечка воздуховода · синхронные расходы по обе стороны участка помогают проверить баланс.</li>
        <li>Ошибка SAT · независимый термометр помогает проверить показание штатного датчика.</li>
      </ul>
      <p>Для пары Between-coil / SAT нужно установить места и физические входы обоих датчиков. Схема
        допускает расположение Between-coil перед охладителем. MAT − Between-coil нельзя считать
        перепадом через охладитель.</p>
      <p>Подтверждённые физические входы (FIELD_IO_VERIFIED) для этих кандидатов отсутствуют в проверенных источниках.</p>
      <aside aria-label="SIM_ONLY_SECTION_CONTEXT" className="rounded border border-slate-700 p-2">
        <p className="font-semibold text-slate-100">SIM_ONLY_SECTION_CONTEXT</p>
        <p>В проверенных симуляциях превышение уставки SAT уже наблюдалось на выходе охладителя.
          Точки относятся к одному модельному контуру. Независимое подтверждение, причина и польза для диагностики не установлены.</p>
      </aside>
      {sources.map(({ id, heading, context }) => (
        <section key={id} aria-label={heading} className="space-y-2">
          <h4 className="font-semibold text-slate-100">{heading}</h4>
          <p className="text-xs">{context}</p>
          <dl className="grid gap-2 sm:grid-cols-2">
            {sensorEvidence.channels.filter(channel => channel.source === id)
              .map(({ id: channelId, label, status, detail }) => (
                <div key={channelId} className="rounded bg-slate-800 p-2">
                  <dt className="font-medium text-slate-100">{label}</dt>
                  <dd className="break-words text-xs text-sky-200">{status}</dd>
                  <dd className="mt-1 text-xs">{detail}</dd>
                </div>
              ))}
          </dl>
        </section>
      ))}
    </details>
  );
}
