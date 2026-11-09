'use strict';

const data = JSON.parse(document.getElementById('study-data').textContent);
const table = document.getElementById('signals');
const header = table.createTHead().insertRow();
for (const title of ['Модельные s', ...data.channels.map(([name, unit]) => `${name} · ${unit}`)]) {
  const cell = document.createElement('th');
  cell.scope = 'col';
  cell.textContent = title;
  header.append(cell);
}
const body = table.createTBody();
for (const [time, ...values] of data.points) {
  const row = body.insertRow();
  const timeCell = document.createElement('th');
  timeCell.scope = 'row';
  timeCell.textContent = time;
  row.append(timeCell);
  for (const value of values) row.insertCell().textContent = Number(value.toFixed(3));
}
const cursor = document.getElementById('cursor');
const cursorValue = document.getElementById('cursor-value');
function highlight() {
  cursorValue.textContent = cursor.value;
  for (const row of body.rows) {
    if (row.cells[0].textContent === cursor.value) row.setAttribute('aria-current', 'true');
    else row.removeAttribute('aria-current');
  }
}
cursor.addEventListener('input', highlight);
highlight();

const captions = {
  instant: 'Мгновенный флаг', applicability: 'Применимость', temporal: 'Временной статус',
  rule: 'Правило', total_ticks: 'Отсчёты окна', evaluated_ticks: 'Оценённые отсчёты', missing_ticks: 'Пропуски сетки',
};
const translations = {
  EXCEEDS: 'Превышение', NO_ALARM: 'Превышения нет', NOT_EVALUATED: 'Не оценено',
  CONFIRMED: 'Подтверждено', NOT_CONFIRMED: 'Не подтверждено',
  APPLICABLE: 'Применимо', FAN_OFF: 'Вентилятор выключен',
};
const decision = document.getElementById('decision');
for (const [key, value] of Object.entries(data.detector)) {
  const term = document.createElement('dt');
  const description = document.createElement('dd');
  term.textContent = captions[key];
  description.textContent = translations[value] ?? value;
  decision.append(term, description);
}

const form = document.getElementById('response');
const download = document.getElementById('download');
const timer = document.getElementById('timer');
const responseState = document.getElementById('response-state');
const start = performance.now();
const limit = 180000;
let response;
function finish(status) {
  if (response) return;
  const elapsed = performance.now() - start;
  const fields = Object.fromEntries(new FormData(form));
  response = {
    protocol: data.protocol, panel_version: data.panel_version,
    response_id: crypto.randomUUID(), case_id: data.case_id, presentation_id: data.presentation_id,
    collection_mode: new URLSearchParams(location.search).get('qa') === '1' ? 'QA_ONLY' : 'REVIEW_ONLY',
    status, elapsed_ms: Math.round(Math.min(elapsed, limit)), fields,
  };
  for (const field of form.elements) field.disabled = true;
  download.disabled = false;
  responseState.textContent = status === 'TIMEOUT' ? 'Время истекло.' : 'Ответ зафиксирован.';
  clearInterval(tick);
}
const tick = setInterval(() => {
  const remaining = Math.max(0, limit - (performance.now() - start));
  timer.textContent = Math.ceil(remaining / 1000);
  if (remaining === 0) finish('TIMEOUT');
}, 200);
form.addEventListener('submit', event => {
  event.preventDefault();
  finish(performance.now() - start >= limit ? 'TIMEOUT' : 'COMPLETE');
});
download.addEventListener('click', () => {
  const url = URL.createObjectURL(new Blob([JSON.stringify(response)], { type: 'application/json' }));
  const link = document.createElement('a');
  link.href = url;
  link.download = 'study-response.json';
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
});
