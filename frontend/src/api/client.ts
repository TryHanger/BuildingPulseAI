import {
  HealthResponse,
  DatasetItem,
  ScenarioItem,
  SensorItem,
  TelemetryResponse,
  DataQualityReport,
  DiagnosticEventItem
} from '../types/api';

const API_BASE = '/api';

export const apiClient = {
  async getHealth(): Promise<HealthResponse> {
    const res = await fetch(`${API_BASE}/health`);
    if (!res.ok) throw new Error(`Health check failed: HTTP ${res.status}`);
    return res.json();
  },

  async getDatasets(): Promise<DatasetItem[]> {
    const res = await fetch(`${API_BASE}/datasets`);
    if (!res.ok) throw new Error(`Failed to load datasets: HTTP ${res.status}`);
    const data = await res.json();
    return data.items || [];
  },

  async getScenarios(datasetId?: string): Promise<ScenarioItem[]> {
    const url = datasetId
      ? `${API_BASE}/scenarios?dataset_id=${encodeURIComponent(datasetId)}`
      : `${API_BASE}/scenarios`;
    const res = await fetch(url);
    if (!res.ok) throw new Error(`Failed to load scenarios: HTTP ${res.status}`);
    const data = await res.json();
    return data.items || [];
  },

  async getSensors(scenarioId: string): Promise<SensorItem[]> {
    const res = await fetch(`${API_BASE}/sensors?scenario_id=${encodeURIComponent(scenarioId)}`);
    if (!res.ok) throw new Error(`Failed to load sensors: HTTP ${res.status}`);
    const data = await res.json();
    return data.items || [];
  },

  async getTelemetry(
    scenarioId: string,
    channels: string[],
    start?: string,
    end?: string,
    maxPoints: number = 1500
  ): Promise<TelemetryResponse> {
    const params = new URLSearchParams({
      scenario_id: scenarioId,
      channels: channels.join(','),
      max_points: maxPoints.toString()
    });
    if (start) params.append('start', start);
    if (end) params.append('end', end);

    const res = await fetch(`${API_BASE}/telemetry?${params.toString()}`);
    if (!res.ok) throw new Error(`Telemetry request failed: HTTP ${res.status}`);
    return res.json();
  },

  async getDataQuality(scenarioId: string): Promise<DataQualityReport> {
    const res = await fetch(`${API_BASE}/data-quality?scenario_id=${encodeURIComponent(scenarioId)}`);
    if (!res.ok) throw new Error(`Data quality request failed: HTTP ${res.status}`);
    return res.json();
  },

  async runDiagnosticRules(scenarioId: string): Promise<{ events: DiagnosticEventItem[] }> {
    const res = await fetch(`${API_BASE}/diagnostics/run-rules`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ scenario_id: scenarioId })
    });
    if (!res.ok) throw new Error(`Diagnostic rules run failed: HTTP ${res.status}`);
    return res.json();
  },

  async getDiagnosticEvents(scenarioId: string): Promise<DiagnosticEventItem[]> {
    const res = await fetch(`${API_BASE}/diagnostics/events?scenario_id=${encodeURIComponent(scenarioId)}`);
    if (!res.ok) throw new Error(`Failed to load events: HTTP ${res.status}`);
    return res.json();
  },

  async uploadCsv(file: File, sourceKind: string = 'USER_UPLOADED'): Promise<any> {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('source_kind', sourceKind);

    const res = await fetch(`${API_BASE}/datasets/import`, {
      method: 'POST',
      body: formData
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
      throw new Error(err.detail || 'Upload failed');
    }
    return res.json();
  },

  async getMLModels(): Promise<import('../types/api').MLModelItem[]> {
    const res = await fetch(`${API_BASE}/ml/models`);
    if (!res.ok) throw new Error(`Failed to load ML models: HTTP ${res.status}`);
    return res.json();
  },

  async getMLPredictions(
    scenarioId: string,
    modelId: string = 'vs-sa-temp-v1',
    thresholdPolicy: string = 'three_sigma',
    maxPoints: number = 1500
  ): Promise<import('../types/api').MLPredictionResponse> {
    const params = new URLSearchParams({
      scenario_id: scenarioId,
      model_id: modelId,
      threshold_policy: thresholdPolicy,
      max_points: maxPoints.toString()
    });
    const res = await fetch(`${API_BASE}/ml/predictions?${params.toString()}`);
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
      throw new Error(err.detail || 'ML prediction request failed');
    }
    return res.json();
  },

  async runMLDetect(
    scenarioId: string,
    modelId: string = 'vs-sa-temp-v1',
    thresholdPolicy: string = 'three_sigma'
  ): Promise<DiagnosticEventItem[]> {
    const res = await fetch(`${API_BASE}/ml/detect`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        scenario_id: scenarioId,
        model_id: modelId,
        threshold_policy: thresholdPolicy
      })
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
      throw new Error(err.detail || 'ML detection failed');
    }
    return res.json();
  },

  async getMLEvents(scenarioId: string): Promise<DiagnosticEventItem[]> {
    const res = await fetch(`${API_BASE}/ml/events?scenario_id=${encodeURIComponent(scenarioId)}`);
    if (!res.ok) throw new Error(`Failed to load ML events: HTTP ${res.status}`);
    return res.json();
  },

  async getDiagnosticSummary(
    scenarioId: string,
    modelId: string = 'vs-sa-temp-v2',
    thresholdPolicy: string = 'three_sigma',
    allowUnvalidated: boolean = false,
    profileId: string = 'BASIC'
  ): Promise<import('../types/api').ScenarioDiagnosticSummary> {
    const params = new URLSearchParams({
      scenario_id: scenarioId,
      model_id: modelId,
      threshold_policy: thresholdPolicy,
      allow_unvalidated: allowUnvalidated ? 'true' : 'false',
      profile_id: profileId
    });
    const res = await fetch(`${API_BASE}/diagnostics/summary?${params.toString()}`);
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
      throw new Error(err.detail || 'Diagnostic summary request failed');
    }
    return res.json();
  },

  async getSensorProfiles(): Promise<import('../types/api').SensorProfileItem[]> {
    const res = await fetch(`${API_BASE}/diagnostics/profiles`);
    if (!res.ok) throw new Error(`Failed to load sensor profiles: HTTP ${res.status}`);
    return res.json();
  },

  async getStage4ExperimentsSummary(): Promise<any> {
    const res = await fetch(`${API_BASE}/experiments/stage4/summary`);
    if (!res.ok) throw new Error(`Failed to load Stage 4 experiments: HTTP ${res.status}`);
    return res.json();
  },

  async getRecommendableChannels(profileId: string = 'BASIC'): Promise<import('../types/api').RecommendableChannelItem[]> {
    const res = await fetch(`${API_BASE}/diagnostics/recommendable-channels?profile_id=${encodeURIComponent(profileId)}`);
    if (!res.ok) throw new Error(`Failed to load recommendable channels: HTTP ${res.status}`);
    return res.json();
  },

  async getSensorRecommendation(
    req: import('../types/api').SensorRecommendationRequest
  ): Promise<import('../types/api').SensorRecommendationResponse> {
    const res = await fetch(`${API_BASE}/sensors/recommend`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req)
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
      throw new Error(err.detail || 'Sensor recommendation request failed');
    }
    return res.json();
  },

  async getStage5RecommendationSummary(): Promise<import('../types/api').Stage5RecommendationSummary> {
    const res = await fetch(`${API_BASE}/experiments/stage5/recommendation-summary`);
    if (!res.ok) throw new Error(`Failed to load Stage 5 recommendation summary: HTTP ${res.status}`);
    return res.json();
  },

  async getStage5ExternalSummary(): Promise<import('../types/api').Stage5ExternalSummary> {
    const res = await fetch(`${API_BASE}/experiments/stage5/external-summary`);
    if (!res.ok) throw new Error(`Failed to load Stage 5 external summary: HTTP ${res.status}`);
    return res.json();
  },

  async recommendSensors(req: import('../types/api').SensorRecommendationRequest): Promise<import('../types/api').SensorRecommendationResponse> {
    return this.getSensorRecommendation(req);
  },

  async getAdaptationDatasets(): Promise<import('../types/api').TargetDatasetInfo[]> {
    const res = await fetch(`${API_BASE}/adaptation/datasets`);
    if (!res.ok) throw new Error(`Failed to load adaptation datasets: HTTP ${res.status}`);
    return res.json();
  },

  async getAdaptationModels(target: string = 'CSIRO_AHU9'): Promise<import('../types/api').AdaptationModelCard[]> {
    const res = await fetch(`${API_BASE}/adaptation/models?target=${encodeURIComponent(target)}`);
    if (!res.ok) throw new Error(`Failed to load adaptation models: HTTP ${res.status}`);
    return res.json();
  },

  async getAdaptationSummary(target: string = 'CSIRO_AHU9'): Promise<import('../types/api').AdaptationSummaryResponse> {
    const res = await fetch(`${API_BASE}/adaptation/summary?target=${encodeURIComponent(target)}`);
    if (!res.ok) throw new Error(`Failed to load adaptation summary: HTTP ${res.status}`);
    return res.json();
  },

  async getAdaptationPredictions(
    target: string = 'CSIRO_AHU9',
    modelId: string = 'csiro-ahu9-affine-v1',
    maxPoints: number = 600
  ): Promise<import('../types/api').AdaptationPredictionsResponse> {
    const res = await fetch(`${API_BASE}/adaptation/predictions?target=${encodeURIComponent(target)}&model_id=${encodeURIComponent(modelId)}&max_points=${maxPoints}`);
    if (!res.ok) throw new Error(`Failed to load adaptation predictions: HTTP ${res.status}`);
    return res.json();
  }
};

export const api = apiClient;
