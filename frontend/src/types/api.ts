export type SourceKind = 'PUBLIC_REAL' | 'SIMULATED_BENCHMARK' | 'SYNTHETIC_DEMO' | 'REAL_FIELD_BMS' | 'USER_UPLOADED' | 'UNKNOWN';

export interface DatasetItem {
  id: string;
  name: string;
  source_kind: SourceKind;
  source_url?: string;
  license_note?: string;
  sha256?: string;
  size_bytes?: number;
  imported_at?: string;
  processing_version: string;
  status: string;
  provenance_note?: string;
}

export interface ScenarioItem {
  id: string;
  dataset_id: string;
  name: string;
  start_at?: string;
  end_at?: string;
  sample_interval_seconds: number;
  timezone_status: string;
  source_fault_label?: string;
  source_fault_label_type?: string;
  description?: string;
  total_rows: number;
}

export interface SensorItem {
  id: number;
  scenario_id: string;
  canonical_key: string;
  original_column: string;
  display_name_ru: string;
  unit_raw?: string;
  unit_normalized?: string;
  component: string;
  signal_kind: 'MEASUREMENT' | 'COMMAND' | 'FEEDBACK';
  is_basic: boolean;
  is_available: boolean;
}

export interface TelemetrySeriesItem {
  channel: string;
  display_name_ru: string;
  unit: string;
  component: string;
  signal_kind: string;
  points: [string, number | null][];
}

export interface TelemetryResponse {
  scenario_id: string;
  range: {
    start?: string;
    end?: string;
    timezone_status: string;
  };
  series: TelemetrySeriesItem[];
  sampling: {
    aggregated: boolean;
    method: string;
    returned_points: number;
    total_source_points: number;
  };
  source_kind: SourceKind;
}

export interface QualityMetric {
  name: string;
  description: string;
  status: 'OK' | 'WARNING' | 'ERROR';
  value: string | number;
}

export interface MissingInterval {
  start: string;
  end: string;
  duration_minutes: number;
}

export interface DataQualityReport {
  scenario_id: string;
  total_records: number;
  time_monotonic: boolean;
  duplicate_timestamps_count: number;
  missing_intervals: MissingInterval[];
  missing_ratio: number;
  stuck_channels: {
    channel: string;
    consecutive_constant_points: number;
    constant_value: number;
  }[];
  metrics: QualityMetric[];
}

export interface DiagnosticEventItem {
  id: string;
  scenario_id: string;
  started_at: string;
  ended_at: string;
  rule_id: string;
  severity: 'INFO' | 'WARNING' | 'CRITICAL';
  evidence_json?: Record<string, any>;
  conclusion_type: string;
  generated_by_version: string;
}

export interface DetectionSummary {
  status: 'NORMAL' | 'ANOMALY' | 'INSUFFICIENT_DATA' | 'OUT_OF_DOMAIN';
  method: string;
  observed_at?: string | null;
  score?: number | null;
  threshold?: number | null;
  unit: string;
  alarm_minutes: number;
  alarm_episodes_count: number;
  operating_minutes: number;
}

export interface SensorProfileItem {
  id: string;
  display_name: string;
  description: string;
  allowed_channels: string[];
  has_valve_feedback: boolean;
  has_damper_feedback: boolean;
  version: string;
  channel_count: number;
}

export interface StructuredEvidenceItem {
  evidence_id: string;
  component: string;
  measured_channels: string[];
  available: boolean;
  applicable: boolean;
  value: number | null;
  unit: string;
  threshold: number | null;
  direction: string | null;
  supports: string[];
  contradicts: string[];
  reason_if_unavailable?: string | null;
  source: string;
}

export interface LocalizationSummary {
  status: 'PRELIMINARY_CLASS' | 'UNRESOLVED' | 'FAULT_FREE' | 'NOT_EVALUATED' | 'SINGLE_CAUSE' | 'MULTIPLE_PLAUSIBLE' | 'CAUSE_UNRESOLVED' | 'NO_ANOMALY' | 'AHU_OFF' | 'INSUFFICIENT_DATA' | 'OUT_OF_DOMAIN';
  candidate_class?: string | null;
  candidate_class_ru?: string | null;
  score?: number | null;
  score_type: string;
  supporting_evidence: string[];
  missing_evidence: string[];
  limitations: string[];
  // Stage 4 Decision Layer additions:
  decision_status?: string | null;
  single_cause?: string | null;
  single_cause_ru?: string | null;
  candidate_causes?: string[];
  reason_codes?: string[];
  structured_evidence?: StructuredEvidenceItem[];
  missing_measurements?: string[];
}

export interface DiagnosticProvenance {
  dataset_version: string;
  model_id: string;
  model_version: string;
  threshold_policy: string;
  feature_profile: string;
  scientific_disclaimer: string;
}

export interface GroundTruthEvaluationInfo {
  source_fault_label?: string | null;
  source_fault_label_type?: string | null;
  description?: string | null;
  is_benchmark_evaluation: boolean;
}

export interface ScenarioDiagnosticSummary {
  scenario_id: string;
  scenario_name: string;
  source_kind: SourceKind;
  model_domain_status: 'VALIDATED_ON_LBNL' | 'OUT_OF_DOMAIN_UNVALIDATED' | 'NOT_VALIDATED';
  domain_warning?: string | null;
  profile_id: string;
  profile_info?: SensorProfileItem | null;
  detection: DetectionSummary;
  localization: LocalizationSummary;
  provenance: DiagnosticProvenance;
  ground_truth?: GroundTruthEvaluationInfo | null;
}

export interface HealthResponse {
  status: string;
  service: string;
  database: string;
}

export interface MLModelItem {
  model_id: string;
  name: string;
  description: string;
  model_type: string;
  target: string;
  target_unit: string;
  features: string[];
  train_scenario_id: string;
  validation_metrics: Record<string, number>;
  thresholds: Record<string, number>;
  created_at: string;
  target_domain?: string;
  source_kind?: string;
  is_adaptation?: boolean;
}

export interface MLPredictionPoint {
  timestamp: string;
  actual: number | null;
  predicted: number | null;
  residual_signed: number | null;
  residual_abs: number | null;
  threshold: number | null;
  is_operating: boolean;
  is_alarm: boolean;
  status: string;
}

export interface MLPredictionResponse {
  scenario_id: string;
  model_id: string;
  target: string;
  unit: string;
  total_points: number;
  operating_points: number;
  alarm_points: number;
  alarm_episodes_count: number;
  threshold_policy: string;
  threshold_value: number;
  metrics?: {
    mae_degC: number;
    rmse_degC: number;
    r2: number;
  };
  points: MLPredictionPoint[];
}

export interface RecommendableChannelItem {
  channel: string;
  display_name: string;
  component: string;
  already_present: boolean;
  is_recommendable: boolean;
  reason: string;
}

export interface CandidateScoreRead {
  channel: string;
  channel_name_ru: string;
  component: string;
  delta_selective_risk_validation: number | null;
  coverage_target: number;
  coverage_actual: number | null;
  eligible_groups: number | null;
  decision: 'RECOMMENDED' | 'ALTERNATIVE' | 'INSUFFICIENT_EVIDENCE' | 'NEGATIVE_IMPACT' | 'UNAVAILABLE';
  reason: string;
}

export interface SensorRecommendationRequest {
  scenario_id?: string | null;
  profile_id: string;
  coverage_target?: number;
  policy_id?: string;
  allow_unvalidated?: boolean;
}

export interface SensorRecommendationResponse {
  scenario_id?: string | null;
  profile_id: string;
  status: 'RECOMMENDED' | 'NO_RELIABLE_RECOMMENDATION' | 'OUT_OF_DOMAIN' | 'PROFILES_EXHAUSTED' | 'INSUFFICIENT_EXCITATION';
  recommended_channel?: string | null;
  recommended_channel_name_ru?: string | null;
  reason: string;
  candidate_scores: CandidateScoreRead[];
  evidence_source: string;
  training_domain: string;
  model_version: string;
  policy_version: string;
  limitations: string[];
}

export interface Stage5RecommendationSummary {
  run_id: string;
  created_at: string;
  hypothesis: string;
  budget_additional_channels: number;
  independent_test_scenarios_count: number;
  total_test_data_points: number;
  candidate_channels_evaluated: string[];
  validation_empirical_values: Record<string, { delta_risk: number; coverage: number }>;
  held_out_strategy_comparison: {
    baseline_basic_f1: number;
    random_strategy: {
      mean_macro_f1: number;
      std_macro_f1: number;
      seeds_evaluated: number[];
    };
    fixed_strategy: {
      selected_channel: string;
      macro_f1: number;
      gain_over_basic_pp: number;
    };
    validation_based_strategy: {
      selected_channel: string;
      macro_f1: number;
      gain_over_basic_pp: number;
      gain_over_random_pp: number;
    };
    infeasible_oracle_upper_bound: {
      macro_f1: number;
      gain_over_basic_pp: number;
    };
  };
  per_scenario_results: {
    scenario_id: string;
    scenario_name: string;
    ground_truth_class: string;
    points_count: number;
    accuracy_basic: number;
    accuracy_plus_valve: number;
    accuracy_plus_damper: number;
    delta_valve: number;
    delta_damper: number;
    oracle_choice: string;
    oracle_accuracy: number;
  }[];
  conclusions: {
    h3_status: string;
    summary: string;
  };
}

export interface TargetDatasetInfo {
  target_id: string;
  name: string;
  building_location: string;
  facility_type: string;
  source_kind: string;
  scenario_id: string;
  available_channels: string[];
  normal_operating_minutes: number;
  fault_episodes_count: number;
  domain_guard_default: boolean;
  status: string;
}

export interface AdaptationModelCard {
  model_id: string;
  name: string;
  strategy_code: string;
  description: string;
  target_domain: string;
  status: string;
  prediction_validity: string;
  fault_localization_validity: string;
  features: string[];
  training_sample_count: number;
  validation_metrics?: Record<string, any>;
  calibrated_thresholds?: Record<string, number>;
}

export interface ModelComparisonRow {
  strategy_code: string;
  model_name: string;
  status: string;
  mae_degC: number | null;
  rmse_degC: number | null;
  mean_bias_degC: number | null;
  r2_score: number | null;
  false_alarm_rate_pct: number | null;
  event_recall_pct: number | null;
  chw_valve_recall_pct: number | null;
}

export interface AdaptationSummaryResponse {
  target_domain: string;
  scenario_id: string;
  dataset_sha256: string;
  split_info: Record<string, any>;
  models_comparison: ModelComparisonRow[];
  best_adapted_model_id: string;
  mae_reduction_pct: number;
  limitations: string[];
  provenance_note: string;
}

export interface PredictionPoint {
  datetime: string;
  actual_sa_temp: number | null;
  source_pred_sa_temp: number | null;
  adapted_pred_sa_temp: number | null;
  source_residual: number | null;
  adapted_residual: number | null;
  is_fault: boolean;
  fault_label?: string | null;
}

export interface AdaptationPredictionsResponse {
  target_domain: string;
  model_id: string;
  status: string;
  total_points: number;
  downsampled_points: number;
  points: PredictionPoint[];
}

export interface Stage5ExternalSummary {
  dataset_name: string;
  building_location: string;
  facility_type: string;
  source_kind: string;
  scenario_id: string;
  sample_points_count: number;
  operating_points_count: number;
  sampling_resolution: string;
  domain_guard_status: string;
  zero_shot_transfer_metrics: {
    mae_degC: number;
    rmse_degC: number;
    mean_bias_degC: number;
    r2_score: number;
    threshold_breach_rate: number;
    lbnl_benchmark_mae_degC: number;
  };
  injected_fault_episodes: {
    fault_type: string;
    severity: string;
    datetime: string;
  }[];
  scientific_finding: string;
  transferable_mechanisms: string[];
  created_at: string;
}
