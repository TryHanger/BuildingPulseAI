import type { paths } from '../types/openapi-v1.generated';

type GetPath = keyof paths;
type Result<P extends GetPath> = paths[P]['get']['responses'][200]['content']['application/json'];
type Query<P extends GetPath> = [NonNullable<paths[P]['get']['parameters']['query']>] extends [never]
  ? Record<string, never> : NonNullable<paths[P]['get']['parameters']['query']>;

async function get<P extends GetPath>(
  path: P,
  query: Query<P>,
  signal: AbortSignal,
  datasetId?: string,
): Promise<Result<P>> {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value === undefined) continue;
    for (const item of Array.isArray(value) ? value : [value]) params.append(key, String(item));
  }
  const url = datasetId ? path.replace('{dataset_id}', encodeURIComponent(datasetId)) : path;
  const response = await fetch(`${url}?${params}`, { signal });
  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new Error(`HTTP ${response.status}${error?.detail?.code ? ` · ${error.detail.code}` : ''}`);
  }
  return response.json();
}

export const investigatorV1 = {
  datasets: (signal: AbortSignal, demo = false) => get('/api/v1/datasets', demo ? { demo: true } : {}, signal),
  signals: (id: string, query: Query<'/api/v1/datasets/{dataset_id}/signals'>, signal: AbortSignal) =>
    get('/api/v1/datasets/{dataset_id}/signals', query, signal, id),
  series: (query: Query<'/api/v1/series'>, signal: AbortSignal) =>
    get('/api/v1/series', query, signal),
  modes: (query: Query<'/api/v1/modes'>, signal: AbortSignal) =>
    get('/api/v1/modes', query, signal),
  incidents: (query: Query<'/api/v1/incidents'>, signal: AbortSignal) =>
    get('/api/v1/incidents', query, signal),
  investigation: (query: Query<'/api/v1/investigation'>, signal: AbortSignal) =>
    get('/api/v1/investigation', query, signal),
  g36Comparison: (signal: AbortSignal) => get('/api/v1/g36-benchmark/comparison', {}, signal),
  g36Benchmark: (query: Query<'/api/v1/g36-benchmark'>, signal: AbortSignal) =>
    get('/api/v1/g36-benchmark', query, signal),
  diagnostics: (query: Query<'/api/v1/diagnostics'>, signal: AbortSignal) =>
    get('/api/v1/diagnostics', query, signal),
};
