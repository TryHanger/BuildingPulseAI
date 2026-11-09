import React, { useState, useEffect, useRef } from 'react';
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  HelpCircle,
  ShieldAlert,
  Sliders,
  ChevronDown,
  ChevronUp,
  Flame,
  Wind,
  Gauge,
  Cpu,
  Info,
  RefreshCw,
  ExternalLink,
  Layers,
  BarChart3,
  CheckSquare,
  Sparkles
} from 'lucide-react';
import * as echarts from 'echarts';
import { apiClient } from '../api/client';
import {
  DatasetItem,
  ScenarioItem,
  ScenarioDiagnosticSummary,
  DiagnosticEventItem,
  TelemetryResponse,
  SensorProfileItem,
  SensorRecommendationResponse
} from '../types/api';

interface DiagnosticsPageProps {
  activeTab: 'monitoring' | 'diagnostics' | 'research';
  onTabChange: (tab: 'monitoring' | 'diagnostics' | 'research') => void;
  selectedScenarioId: string;
  onSelectScenarioId: (id: string) => void;
}

export const DiagnosticsPage: React.FC<DiagnosticsPageProps> = ({
  activeTab,
  onTabChange,
  selectedScenarioId,
  onSelectScenarioId
}) => {
  const [datasets, setDatasets] = useState<DatasetItem[]>([]);
  const [scenarios, setScenarios] = useState<ScenarioItem[]>([]);
  const [sensorProfiles, setSensorProfiles] = useState<SensorProfileItem[]>([]);
  const [selectedProfileId, setSelectedProfileId] = useState<string>('BASIC');
  const [selectedModelId, setSelectedModelId] = useState<string>('vs-sa-temp-v2');
  const [thresholdPolicy, setThresholdPolicy] = useState<string>('three_sigma');
  const [allowUnvalidated, setAllowUnvalidated] = useState<boolean>(false);

  const [summary, setSummary] = useState<ScenarioDiagnosticSummary | null>(null);
  const [events, setEvents] = useState<DiagnosticEventItem[]>([]);
  const [telemetry, setTelemetry] = useState<TelemetryResponse | null>(null);
  const [selectedEventId, setSelectedEventId] = useState<string | null>(null);
  const [experimentsData, setExperimentsData] = useState<any | null>(null);
  const [recommendation, setRecommendation] = useState<SensorRecommendationResponse | null>(null);
  const [isLoadingRec, setIsLoadingRec] = useState<boolean>(false);

  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [showGroundTruth, setShowGroundTruth] = useState<boolean>(false);
  const [showExperiments, setShowExperiments] = useState<boolean>(true);

  const chartRef = useRef<HTMLDivElement>(null);
  const chartInstance = useRef<echarts.ECharts | null>(null);

  // 1. Initial Load of Metadata & Profiles
  useEffect(() => {
    const loadMetadata = async () => {
      try {
        const [dsList, scList, profList, expData] = await Promise.all([
          apiClient.getDatasets(),
          apiClient.getScenarios(),
          apiClient.getSensorProfiles().catch(() => []),
          apiClient.getStage4ExperimentsSummary().catch(() => null)
        ]);
        setDatasets(dsList);
        setScenarios(scList);
        setSensorProfiles(profList);
        setExperimentsData(expData);

        if (!selectedScenarioId && scList.length > 0) {
          onSelectScenarioId(scList[0].id);
        }
      } catch (err: any) {
        setError(err.message || 'Ошибка загрузки метаданных');
      }
    };
    loadMetadata();
  }, []);

  // 2. Load Diagnostic Data on parameters change
  const fetchDiagnostics = async () => {
    if (!selectedScenarioId) return;
    setIsLoading(true);
    setError(null);
    try {
      const [sumRes, evRes] = await Promise.all([
        apiClient.getDiagnosticSummary(
          selectedScenarioId,
          selectedModelId,
          thresholdPolicy,
          allowUnvalidated,
          selectedProfileId
        ),
        apiClient.getDiagnosticEvents(selectedScenarioId).catch(() => [])
      ]);
      setSummary(sumRes);
      setEvents(evRes);

      // Determine allowed telemetry channels based on profile
      const channels = ['SA_TEMP', 'MA_TEMP', 'CHWC_VLV_DM', 'OA_DMPR_DM'];
      if (selectedProfileId.includes('VALVE') || selectedProfileId.includes('BOTH') || selectedProfileId === 'FULL') {
        channels.push('CHWC_VLV');
      }
      if (selectedProfileId.includes('DAMPER') || selectedProfileId.includes('BOTH') || selectedProfileId === 'FULL') {
        channels.push('OA_DMPR');
      }

      const telem = await apiClient.getTelemetry(
        selectedScenarioId,
        channels,
        undefined,
        undefined,
        1200
      ).catch(() => null);
      setTelemetry(telem);
    } catch (err: any) {
      setError(err.message || 'Ошибка загрузки диагностики');
    } finally {
      setIsLoading(false);
    }
  };

  const handleFetchRecommendation = async () => {
    if (!selectedScenarioId) return;
    setIsLoadingRec(true);
    try {
      const res = await apiClient.recommendSensors({
        scenario_id: selectedScenarioId,
        profile_id: selectedProfileId
      });
      setRecommendation(res);
    } catch (err: any) {
      console.error('Failed to get sensor recommendation:', err);
    } finally {
      setIsLoadingRec(false);
    }
  };

  useEffect(() => {
    setRecommendation(null);
    fetchDiagnostics();
  }, [selectedScenarioId, selectedModelId, thresholdPolicy, allowUnvalidated, selectedProfileId]);

  // 3. Render ECharts Telemetry Preview
  useEffect(() => {
    if (!chartRef.current || !telemetry) return;

    if (!chartInstance.current) {
      chartInstance.current = echarts.init(chartRef.current, 'dark');
    }

    const saSeries = telemetry.series.find(s => s.channel === 'SA_TEMP');
    const maSeries = telemetry.series.find(s => s.channel === 'MA_TEMP');
    const vlvDmSeries = telemetry.series.find(s => s.channel === 'CHWC_VLV_DM');
    const vlvFbSeries = telemetry.series.find(s => s.channel === 'CHWC_VLV');

    const times = saSeries?.points.map(p => p[0]) || [];

    const legendData = ['SA_TEMP (°C)', 'MA_TEMP (°C)', 'Клапан команда (CHWC_VLV_DM)'];
    if (vlvFbSeries) {
      legendData.push('Клапан датчик штока (CHWC_VLV)');
    }

    const seriesList: any[] = [
      {
        name: 'SA_TEMP (°C)',
        type: 'line',
        showSymbol: false,
        data: saSeries?.points.map(p => p[1]) || [],
        lineStyle: { color: '#38bdf8', width: 2 }
      },
      {
        name: 'MA_TEMP (°C)',
        type: 'line',
        showSymbol: false,
        data: maSeries?.points.map(p => p[1]) || [],
        lineStyle: { color: '#a855f7', width: 1.5, type: 'dashed' }
      },
      {
        name: 'Клапан команда (CHWC_VLV_DM)',
        type: 'line',
        yAxisIndex: 1,
        showSymbol: false,
        data: vlvDmSeries?.points.map(p => p[1]) || [],
        lineStyle: { color: '#34d399', width: 1.5 }
      }
    ];

    if (vlvFbSeries) {
      seriesList.push({
        name: 'Клапан датчик штока (CHWC_VLV)',
        type: 'line',
        yAxisIndex: 1,
        showSymbol: false,
        data: vlvFbSeries?.points.map(p => p[1]) || [],
        lineStyle: { color: '#f59e0b', width: 2, type: 'dotted' }
      });
    }

    const option: echarts.EChartsOption = {
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'cross' }
      },
      legend: {
        data: legendData,
        textStyle: { color: '#94a3b8', fontSize: 11 },
        top: 0
      },
      grid: {
        top: 35,
        left: 45,
        right: 45,
        bottom: 25
      },
      xAxis: {
        type: 'category',
        data: times,
        axisLine: { lineStyle: { color: '#334155' } },
        axisLabel: {
          color: '#64748b',
          fontSize: 10,
          formatter: (val: string) => val ? val.substring(11, 16) : ''
        }
      },
      yAxis: [
        {
          type: 'value',
          name: '°C',
          axisLine: { lineStyle: { color: '#334155' } },
          splitLine: { lineStyle: { color: '#1e293b' } },
          axisLabel: { color: '#94a3b8', fontSize: 10 }
        },
        {
          type: 'value',
          name: 'Доля 0..1',
          max: 1.0,
          min: 0.0,
          axisLine: { lineStyle: { color: '#334155' } },
          splitLine: { show: false },
          axisLabel: { color: '#94a3b8', fontSize: 10 }
        }
      ],
      series: seriesList
    };

    chartInstance.current.setOption(option);

    const handleResize = () => chartInstance.current?.resize();
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [telemetry, selectedProfileId]);

  const currentScenario = scenarios.find(s => s.id === selectedScenarioId);
  const isSynthetic = summary?.source_kind === 'SYNTHETIC_DEMO';

  // Helper translations for Decision Layer statuses
  const decisionStatus = summary?.localization.decision_status || summary?.localization.status;

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
      {/* Header */}
      <header className="border-b border-slate-800 bg-slate-900/90 backdrop-blur-md sticky top-0 z-30 px-4 py-3">
        <div className="max-w-[1440px] mx-auto flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-emerald-600 to-teal-400 flex items-center justify-center shadow-lg shadow-emerald-950/50">
              <Activity className="w-6 h-6 text-slate-950 stroke-[2.5]" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h1 className="text-lg font-black tracking-tight text-white">BuildingPulse AI</h1>
                <span className="text-[10px] px-1.5 py-0.2 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 font-mono">
                  v0.7.1-stage7.1
                </span>
              </div>
              <p className="text-xs text-slate-400">
                Интеллектуальная система анализа данных вентиляционных установок AHU
              </p>
            </div>
          </div>

          {/* Navigation Tabs */}
          <div className="flex items-center space-x-3 self-end sm:self-auto">
            <nav className="flex items-center space-x-1 bg-slate-800/80 p-1 rounded-lg border border-slate-700 text-xs">
              <button
                onClick={() => onTabChange('monitoring')}
                className={`px-3 py-1 rounded-md font-semibold transition-all ${
                  activeTab === 'monitoring'
                    ? 'bg-emerald-600 text-slate-950 shadow-sm'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Мониторинг AHU
              </button>
              <button
                onClick={() => onTabChange('diagnostics')}
                className={`px-3 py-1 rounded-md font-semibold transition-all flex items-center space-x-1.5 ${
                  activeTab === 'diagnostics'
                    ? 'bg-emerald-600 text-slate-950 shadow-sm'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                <span>Диагностика</span>
                <span className="text-[9px] px-1 py-0.2 rounded bg-slate-900 text-emerald-300 border border-emerald-800/50">
                  Этап 4
                </span>
              </button>
              <button
                onClick={() => onTabChange('research')}
                className={`px-3 py-1 rounded-md font-semibold transition-all flex items-center space-x-1.5 ${
                  activeTab === 'research'
                    ? 'bg-emerald-600 text-slate-950 shadow-sm'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                <span>Исследования</span>
                <span className="text-[9px] px-1 py-0.2 rounded bg-purple-900/60 text-purple-300 border border-purple-700/50">
                  Этап 5
                </span>
              </button>
            </nav>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-[1440px] mx-auto p-4 flex-1 w-full space-y-4">
        {/* Controls Context Bar */}
        <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-4 shadow-sm flex flex-wrap items-center justify-between gap-4">
          <div className="flex flex-wrap items-center gap-3">
            {/* Scenario Selector */}
            <div>
              <label className="block text-[11px] text-slate-400 uppercase font-semibold mb-1">
                Сценарий AHU
              </label>
              <select
                value={selectedScenarioId}
                onChange={e => onSelectScenarioId(e.target.value)}
                className="bg-slate-950 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-white focus:outline-none focus:border-emerald-500 font-medium max-w-xs"
              >
                {scenarios.map(s => (
                  <option key={s.id} value={s.id}>
                    {s.name} ({s.source_fault_label_type || 'NORMAL'})
                  </option>
                ))}
              </select>
            </div>

            {/* Observability Profile Selector (Gate 3 requirement) */}
            <div>
              <label className="block text-[11px] text-slate-400 uppercase font-semibold mb-1 flex items-center gap-1">
                <Layers className="w-3.5 h-3.5 text-emerald-400" />
                <span>Профиль измерений</span>
              </label>
              <select
                value={selectedProfileId}
                onChange={e => setSelectedProfileId(e.target.value)}
                className="bg-slate-950 border border-emerald-700/80 rounded-lg px-3 py-1.5 text-xs text-emerald-300 font-bold focus:outline-none focus:border-emerald-500"
              >
                <option value="BASIC">BASIC (Базовый BMS, 19 каналов)</option>
                <option value="BASIC_PLUS_VALVE">BASIC + Valve Feedback (+CHWC_VLV)</option>
                <option value="BASIC_PLUS_DAMPER">BASIC + Damper Feedback (+OA_DMPR)</option>
                <option value="BASIC_PLUS_BOTH">BASIC + Both Actuators (Клапан + Заслонка)</option>
                <option value="FULL">FULL (Полная лабораторная наблюдаемость)</option>
              </select>
            </div>

            {/* Model Selector */}
            <div>
              <label className="block text-[11px] text-slate-400 uppercase font-semibold mb-1">
                Виртуальный датчик
              </label>
              <select
                value={selectedModelId}
                onChange={e => setSelectedModelId(e.target.value)}
                className="bg-slate-950 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-white focus:outline-none focus:border-emerald-500 font-medium"
              >
                <option value="vs-sa-temp-v2">vs-sa-temp-v2 (Многосезонный LightGBM)</option>
                <option value="vs-sa-temp-baseline-ridge-v2">vs-sa-temp-baseline-ridge-v2 (Ridge Baseline)</option>
                <option value="vs-sa-temp-v1">vs-sa-temp-v1 (Зимний срез Stage 2)</option>
              </select>
            </div>

            {/* Threshold Policy */}
            <div>
              <label className="block text-[11px] text-slate-400 uppercase font-semibold mb-1">
                Политика порога
              </label>
              <select
                value={thresholdPolicy}
                onChange={e => setThresholdPolicy(e.target.value)}
                className="bg-slate-950 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-white focus:outline-none focus:border-emerald-500 font-medium"
              >
                <option value="three_sigma">3-Sigma (Консервативный, 0 ложных)</option>
                <option value="q95">Q95 (Чувствительный к bias)</option>
                <option value="mad">MAD (Робастный медианный)</option>
                <option value="q99">Q99 (Критические выбросы)</option>
              </select>
            </div>
          </div>

          {/* Badges / Actions */}
          <div className="flex items-center gap-2">
            {summary?.model_domain_status === 'VALIDATED_ON_LBNL' ? (
              <span className="px-2.5 py-1 rounded-md text-xs font-semibold bg-emerald-950 text-emerald-300 border border-emerald-800 flex items-center gap-1">
                <CheckCircle2 className="w-3.5 h-3.5" />
                LBNL SD-AHU
              </span>
            ) : (
              <span className="px-2.5 py-1 rounded-md text-xs font-semibold bg-amber-950 text-amber-300 border border-amber-800 flex items-center gap-1">
                <AlertTriangle className="w-3.5 h-3.5" />
                Вне домена
              </span>
            )}
            <button
              onClick={fetchDiagnostics}
              disabled={isLoading}
              className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 transition-colors"
              title="Пересчитать диагностику"
            >
              <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
            </button>
          </div>
        </div>

        {/* Domain Guard Banner for Synthetic Demo */}
        {isSynthetic && (
          <div className="bg-amber-950/40 border border-amber-600/50 rounded-xl p-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 shadow-lg">
            <div className="flex items-start space-x-3">
              <ShieldAlert className="w-6 h-6 text-amber-400 flex-shrink-0 mt-0.5" />
              <div>
                <h3 className="text-sm font-bold text-amber-200">
                  Защитный барьер домена (Domain Guard)
                </h3>
                <p className="text-xs text-amber-300/90 mt-0.5 max-w-3xl">
                  {summary?.domain_warning ||
                    'Выбранный сценарий относится к синтетическому набору (SYNTHETIC_DEMO). ML-модель обучалась на симуляции LBNL EnergyPlus. Детекция модели по умолчанию отключена во избежание недостоверных выводов.'}
                </p>
              </div>
            </div>
            <label className="flex items-center space-x-2 bg-amber-900/60 hover:bg-amber-900 px-3 py-1.5 rounded-lg border border-amber-600/70 cursor-pointer text-xs font-medium text-amber-100 transition-colors">
              <input
                type="checkbox"
                checked={allowUnvalidated}
                onChange={e => setAllowUnvalidated(e.target.checked)}
                className="rounded border-amber-400 text-amber-600 focus:ring-0"
              />
              <span>Включить режим UNVALIDATED</span>
            </label>
          </div>
        )}

        {/* Diagnostic Status Card Grid (Gate 5) */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {/* Card 1: Anomaly Detection */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-slate-400 uppercase tracking-wider">
                  Детектор аномалий
                </span>
                <span
                  className={`px-2 py-0.5 rounded text-xs font-bold ${
                    summary?.detection.status === 'NORMAL'
                      ? 'bg-emerald-950 text-emerald-400 border border-emerald-700'
                      : summary?.detection.status === 'ANOMALY'
                      ? 'bg-rose-950 text-rose-300 border border-rose-700 animate-pulse'
                      : 'bg-amber-950 text-amber-300 border border-amber-700'
                  }`}
                >
                  {summary?.detection.status === 'NORMAL' && 'Норма'}
                  {summary?.detection.status === 'ANOMALY' && 'Аномалия обнаружена'}
                  {summary?.detection.status === 'OUT_OF_DOMAIN' && 'Вне домена'}
                  {summary?.detection.status === 'INSUFFICIENT_DATA' && 'Нет данных'}
                </span>
              </div>
              <div className="mt-3">
                <div className="text-2xl font-black text-white">
                  {summary?.detection.status === 'ANOMALY'
                    ? `${summary.detection.alarm_minutes} мин тревоги`
                    : summary?.detection.status === 'NORMAL'
                    ? '0 мин тревоги'
                    : 'Отключено'}
                </div>
                <p className="text-xs text-slate-400 mt-1">
                  Эпизодов превышения порога: {summary?.detection.alarm_episodes_count || 0}.
                </p>
              </div>
            </div>

            <div className="border-t border-slate-800/80 pt-3 mt-4 text-xs space-y-1 text-slate-400">
              <div className="flex justify-between">
                <span>Порог невязки ({summary?.provenance.threshold_policy}):</span>
                <strong className="text-slate-200">
                  {summary?.detection.threshold ? `${summary.detection.threshold.toFixed(2)} °C` : 'Н/Д'}
                </strong>
              </div>
              <div className="flex justify-between">
                <span>Максимальная невязка |r|:</span>
                <strong className="text-slate-200">
                  {summary?.detection.score ? `${summary.detection.score.toFixed(2)} °C` : 'Н/Д'}
                </strong>
              </div>
            </div>
          </div>

          {/* Card 2: Decision Layer Outcome */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-slate-400 uppercase tracking-wider">
                  Заключение Decision Layer
                </span>
                <span
                  className={`text-[10px] px-2 py-0.5 rounded font-bold uppercase tracking-wider ${
                    decisionStatus === 'SINGLE_CAUSE'
                      ? 'bg-emerald-950 text-emerald-300 border border-emerald-700'
                      : decisionStatus === 'MULTIPLE_PLAUSIBLE'
                      ? 'bg-amber-950 text-amber-300 border border-amber-700'
                      : decisionStatus === 'CAUSE_UNRESOLVED'
                      ? 'bg-slate-800 text-slate-300 border border-slate-700'
                      : 'bg-slate-800 text-slate-400 border border-slate-700'
                  }`}
                >
                  {decisionStatus === 'SINGLE_CAUSE' && 'Одиночный диагноз'}
                  {decisionStatus === 'MULTIPLE_PLAUSIBLE' && 'Несколько кандидатов'}
                  {decisionStatus === 'CAUSE_UNRESOLVED' && 'Причина не установлена'}
                  {decisionStatus === 'NO_ANOMALY' && 'Норма'}
                  {decisionStatus === 'AHU_OFF' && 'AHU выключен'}
                  {(!decisionStatus || decisionStatus === 'NOT_EVALUATED') && 'Не оценено'}
                </span>
              </div>

              <div className="mt-3">
                {decisionStatus === 'SINGLE_CAUSE' ? (
                  <div>
                    <div className="text-base font-extrabold text-emerald-300 leading-tight">
                      {summary?.localization.single_cause_ru || summary?.localization.candidate_class_ru}
                    </div>
                    <div className="text-[11px] text-slate-400 font-mono mt-1">
                      {summary?.localization.single_cause}
                    </div>
                  </div>
                ) : decisionStatus === 'MULTIPLE_PLAUSIBLE' ? (
                  <div>
                    <div className="text-sm font-bold text-amber-300">
                      Структурная неоднозначность ({summary?.localization.candidate_causes?.length || 2} кандидата):
                    </div>
                    <ul className="mt-1.5 space-y-1">
                      {summary?.localization.candidate_causes?.map((c, i) => (
                        <li key={i} className="text-xs text-slate-200 flex items-center gap-1.5">
                          <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />
                          <span className="font-mono text-[11px]">{c}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : (
                  <div>
                    <div className="text-sm font-bold text-slate-300">
                      {summary?.localization.candidate_class_ru || 'Причина не установлена'}
                    </div>
                    <p className="text-xs text-slate-500 mt-1">
                      Доступных свидетельств недостаточно для надежной изоляции дефекта.
                    </p>
                  </div>
                )}

                {/* Reason Codes Badges */}
                {summary?.localization.reason_codes && summary.localization.reason_codes.length > 0 && (
                  <div className="flex flex-wrap gap-1 mt-2.5">
                    {summary.localization.reason_codes.map((rc, i) => (
                      <span key={i} className="text-[9px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-300 font-mono border border-slate-700">
                        {rc}
                      </span>
                    ))}
                  </div>
                )}

                {/* Stage 5: Sensor Recommendation Engine Action */}
                {(decisionStatus === 'MULTIPLE_PLAUSIBLE' || selectedProfileId === 'BASIC') && (
                  <div className="mt-3 pt-3 border-t border-slate-800/80">
                    {!recommendation ? (
                      <button
                        onClick={handleFetchRecommendation}
                        disabled={isLoadingRec}
                        className="w-full flex items-center justify-center gap-2 py-1.5 px-3 rounded-lg bg-emerald-950/70 hover:bg-emerald-900 border border-emerald-600/60 text-emerald-300 text-xs font-semibold transition-colors"
                      >
                        <Sparkles className="w-3.5 h-3.5 text-emerald-400" />
                        <span>{isLoadingRec ? 'Расчет информационной ценности...' : 'Какое измерение поможет?'}</span>
                      </button>
                    ) : (
                      <div className="bg-slate-950 p-2.5 rounded-lg border border-emerald-700/60 space-y-2">
                        <div className="flex items-center justify-between text-xs">
                          <span className="text-slate-400 font-medium">Рекомендация H3:</span>
                          <span className="font-mono font-bold text-emerald-300 bg-emerald-950/80 px-2 py-0.5 rounded border border-emerald-800">
                            +{recommendation.recommended_channel || 'CHWC_VLV'}
                          </span>
                        </div>
                        <p className="text-[11px] text-slate-300 leading-snug">
                          {recommendation.reason ||
                            'Канал обратной связи штока клапана разрывает эквивалентность между заклиниванием и смещением.'}
                        </p>
                        {selectedProfileId === 'BASIC' && (
                          <button
                            onClick={() => setSelectedProfileId('BASIC_PLUS_VALVE')}
                            className="w-full py-1 px-2 rounded bg-emerald-600 hover:bg-emerald-500 text-slate-950 text-xs font-bold transition-colors"
                          >
                            Подключить канал (перейти на BASIC + Valve) →
                          </button>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>

            <div className="border-t border-slate-800/80 pt-3 mt-4 text-xs text-slate-400 flex items-center justify-between">
              <span>Скор модели:</span>
              <span className="text-slate-200 font-mono font-bold">
                {summary?.localization.score !== null && summary?.localization.score !== undefined
                  ? `${(summary.localization.score * 100).toFixed(1)}%`
                  : 'Н/Д'}
              </span>
            </div>
          </div>

          {/* Card 3: Observability Profile State */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-slate-400 uppercase tracking-wider">
                  Профиль наблюдаемости
                </span>
                <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-sky-950 text-sky-300 border border-sky-800">
                  {summary?.profile_id || selectedProfileId}
                </span>
              </div>
              <div className="mt-3 space-y-2 text-xs">
                <div className="flex items-center justify-between text-slate-300">
                  <span>Доступно каналов профиля:</span>
                  <strong className="font-mono text-white">
                    {summary?.profile_info?.channel_count || 19}
                  </strong>
                </div>
                <div className="flex items-center justify-between text-slate-300">
                  <span>Обратная связь клапана (CHWC_VLV):</span>
                  {summary?.profile_info?.has_valve_feedback ? (
                    <span className="text-emerald-400 font-medium flex items-center gap-1">
                      <CheckCircle2 className="w-3.5 h-3.5" /> Включена
                    </span>
                  ) : (
                    <span className="text-rose-400 font-medium flex items-center gap-1">
                      <XCircle className="w-3.5 h-3.5" /> Отсутствует
                    </span>
                  )}
                </div>
                <div className="flex items-center justify-between text-slate-300">
                  <span>Обратная связь заслонки (OA_DMPR):</span>
                  {summary?.profile_info?.has_damper_feedback ? (
                    <span className="text-emerald-400 font-medium flex items-center gap-1">
                      <CheckCircle2 className="w-3.5 h-3.5" /> Включена
                    </span>
                  ) : (
                    <span className="text-rose-400 font-medium flex items-center gap-1">
                      <XCircle className="w-3.5 h-3.5" /> Отсутствует
                    </span>
                  )}
                </div>
                <div className="flex items-center justify-between text-slate-300">
                  <span>Режим вентилятора:</span>
                  <span className="text-emerald-400 font-medium">SF_SPD_DM = 1 (включен)</span>
                </div>
              </div>
            </div>

            <div className="border-t border-slate-800/80 pt-3 mt-4 text-[11px] text-slate-400">
              {summary?.profile_info?.description || 'Стандартная автоматизация AHU'}
            </div>
          </div>
        </div>

        {/* Detailed Evidence & Telemetry Excerpt */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {/* Diagnostic Evidence Panel */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-4">
            <h3 className="text-sm font-bold text-white flex items-center space-x-2">
              <Cpu className="w-4 h-4 text-emerald-400" />
              <span>Физические свидетельства и ограничения профиля</span>
            </h3>

            {/* Supporting Evidence */}
            <div>
              <h4 className="text-xs font-semibold text-emerald-400 uppercase tracking-wider mb-2 flex items-center space-x-1.5">
                <CheckCircle2 className="w-3.5 h-3.5" />
                <span>Подтверждающие свидетельства</span>
              </h4>
              <ul className="space-y-1.5">
                {summary?.localization.supporting_evidence.map((ev, i) => (
                  <li key={i} className="text-xs text-slate-300 bg-slate-950 p-2 rounded border border-slate-800/70">
                    {ev}
                  </li>
                ))}
                {(!summary?.localization.supporting_evidence || summary.localization.supporting_evidence.length === 0) && (
                  <li className="text-xs text-slate-500 italic">Свидетельств не зафиксировано</li>
                )}
              </ul>
            </div>

            {/* Missing Evidence / Measurements */}
            <div>
              <h4 className="text-xs font-semibold text-amber-400 uppercase tracking-wider mb-2 flex items-center space-x-1.5">
                <AlertTriangle className="w-3.5 h-3.5" />
                <span>Недостающие каналы измерений ({summary?.profile_id})</span>
              </h4>
              <ul className="space-y-1.5">
                {summary?.localization.missing_measurements && summary.localization.missing_measurements.length > 0 ? (
                  summary.localization.missing_measurements.map((me, i) => (
                    <li key={i} className="text-xs text-slate-300 bg-slate-950 p-2 rounded border border-slate-800/70 font-mono">
                      {me}
                    </li>
                  ))
                ) : (
                  <li className="text-xs text-emerald-400/90 italic">Все требуемые каналы профиля доступны</li>
                )}
              </ul>
            </div>

            {/* Limitations */}
            <div>
              <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2 flex items-center space-x-1.5">
                <Info className="w-3.5 h-3.5" />
                <span>Ограничения интерпретации</span>
              </h4>
              <ul className="space-y-1">
                {summary?.localization.limitations.map((lim, i) => (
                  <li key={i} className="text-[11px] text-slate-400">
                    • {lim}
                  </li>
                ))}
              </ul>
            </div>
          </div>

          {/* Telemetry Excerpt Chart */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 flex flex-col">
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-sm font-bold text-white flex items-center space-x-2">
                <Activity className="w-4 h-4 text-sky-400" />
                <span>Телеметрия разрешенных каналов ({summary?.profile_id})</span>
              </h3>
              <span className="text-[11px] text-slate-400">
                Синхронизировано по времени
              </span>
            </div>
            <div ref={chartRef} className="w-full h-72 flex-1" />
          </div>
        </div>

        {/* Stage 4 Research Benchmark & Observability Value Panel (Gate 5) */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-sm">
          <button
            onClick={() => setShowExperiments(!showExperiments)}
            className="w-full p-4 flex items-center justify-between text-left hover:bg-slate-800/40 transition-colors"
          >
            <div className="flex items-center space-x-2">
              <BarChart3 className="w-4 h-4 text-emerald-400" />
              <span className="text-xs font-bold uppercase tracking-wider text-white">
                Научные эксперименты Stage 4: Risk–Coverage и ценность каналов наблюдаемости
              </span>
              <span className="text-[10px] px-1.5 py-0.2 rounded bg-emerald-950 text-emerald-300 border border-emerald-800 font-mono">
                Holdout Test
              </span>
            </div>
            {showExperiments ? (
              <ChevronUp className="w-4 h-4 text-slate-400" />
            ) : (
              <ChevronDown className="w-4 h-4 text-slate-400" />
            )}
          </button>

          {showExperiments && (
            <div className="p-4 border-t border-slate-800 bg-slate-950/70 space-y-4">
              <p className="text-xs text-slate-400">
                Результаты экспериментального прогона на 7 независимых тестовых сценариях LBNL SD-AHU (18 480 минутных точек).
                Сравнение качества локализации Decision Layer с классическими baseline-стратегиями отказа.
              </p>

              {/* Table 1: Comparative Risk-Coverage */}
              <div>
                <h4 className="text-xs font-bold text-slate-200 uppercase tracking-wider mb-2">
                  Таблица 1: Сравнение Selective Risk при фиксированном охвате (Coverage)
                </h4>
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs border-collapse border border-slate-800">
                    <thead>
                      <tr className="bg-slate-900 text-slate-400 border-b border-slate-800">
                        <th className="py-2 px-3">Целевой охват (Coverage)</th>
                        <th className="py-2 px-3">B1 (Confidence-Only) Risk</th>
                        <th className="py-2 px-3">B2 (Margin/Entropy) Risk</th>
                        <th className="py-2 px-3 text-emerald-400">Decision Layer M (BASIC) Risk</th>
                        <th className="py-2 px-3 text-purple-400">Decision Layer M (+VALVE) Risk</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800 font-mono text-[11px]">
                      <tr>
                        <td className="py-2 px-3 text-slate-300 font-bold">40%</td>
                        <td className="py-2 px-3">0.556 (cov=0.46)</td>
                        <td className="py-2 px-3">0.554 (cov=0.61)</td>
                        <td className="py-2 px-3 text-emerald-300 font-bold">0.294 (cov=0.42)</td>
                        <td className="py-2 px-3 text-purple-300 font-bold">0.156 (cov=0.39)</td>
                      </tr>
                      <tr>
                        <td className="py-2 px-3 text-slate-300 font-bold">60%</td>
                        <td className="py-2 px-3">0.547 (cov=0.61)</td>
                        <td className="py-2 px-3">0.554 (cov=0.61)</td>
                        <td className="py-2 px-3 text-emerald-300 font-bold">0.361 (cov=0.60)</td>
                        <td className="py-2 px-3 text-purple-300 font-bold">0.195 (cov=0.59)</td>
                      </tr>
                      <tr>
                        <td className="py-2 px-3 text-slate-300 font-bold">80%</td>
                        <td className="py-2 px-3">0.540 (cov=0.81)</td>
                        <td className="py-2 px-3">0.518 (cov=0.80)</td>
                        <td className="py-2 px-3 text-slate-500 italic">Предел охвата (60.2%)</td>
                        <td className="py-2 px-3 text-purple-300 font-bold">0.217 (cov=0.76)</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Table 2: Observability Profile Comparison */}
              <div>
                <h4 className="text-xs font-bold text-slate-200 uppercase tracking-wider mb-2">
                  Таблица 2: Сравнение качества классификации по профилям наблюдаемости (Macro F1)
                </h4>
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs border-collapse border border-slate-800">
                    <thead>
                      <tr className="bg-slate-900 text-slate-400 border-b border-slate-800">
                        <th className="py-2 px-3">Профиль наблюдаемости</th>
                        <th className="py-2 px-3">Признаков</th>
                        <th className="py-2 px-3">Macro F1</th>
                        <th className="py-2 px-3">Клапан (VALVE) F1</th>
                        <th className="py-2 px-3">Смещение (SENSOR) F1</th>
                        <th className="py-2 px-3">Заслонка (DAMPER) F1</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800 font-mono text-[11px]">
                      <tr className={selectedProfileId === 'BASIC' ? 'bg-emerald-950/30' : ''}>
                        <td className="py-2 px-3 font-sans font-bold text-slate-200">BASIC (Базовый)</td>
                        <td className="py-2 px-3">11</td>
                        <td className="py-2 px-3 font-bold text-slate-300">0.5196</td>
                        <td className="py-2 px-3">0.7672</td>
                        <td className="py-2 px-3">0.1886</td>
                        <td className="py-2 px-3">0.6547</td>
                      </tr>
                      <tr className={selectedProfileId === 'BASIC_PLUS_VALVE' ? 'bg-emerald-950/30' : ''}>
                        <td className="py-2 px-3 font-sans font-bold text-emerald-300">BASIC + Valve Feedback</td>
                        <td className="py-2 px-3">14</td>
                        <td className="py-2 px-3 font-bold text-emerald-300">0.6722 (+15.3%)</td>
                        <td className="py-2 px-3 text-emerald-400 font-bold">0.9996</td>
                        <td className="py-2 px-3 text-emerald-400 font-bold">0.5396</td>
                        <td className="py-2 px-3">0.6253</td>
                      </tr>
                      <tr className={selectedProfileId === 'BASIC_PLUS_DAMPER' ? 'bg-emerald-950/30' : ''}>
                        <td className="py-2 px-3 font-sans font-bold text-slate-200">BASIC + Damper Feedback</td>
                        <td className="py-2 px-3">14</td>
                        <td className="py-2 px-3">0.5123</td>
                        <td className="py-2 px-3">0.7590</td>
                        <td className="py-2 px-3">0.0662</td>
                        <td className="py-2 px-3 text-cyan-400 font-bold">0.7764</td>
                      </tr>
                      <tr className={selectedProfileId === 'BASIC_PLUS_BOTH' ? 'bg-emerald-950/30' : ''}>
                        <td className="py-2 px-3 font-sans font-bold text-purple-300">BASIC + Both Actuators</td>
                        <td className="py-2 px-3">17</td>
                        <td className="py-2 px-3 font-bold text-purple-300">0.6755 (+15.6%)</td>
                        <td className="py-2 px-3 text-emerald-400 font-bold">0.9995</td>
                        <td className="py-2 px-3">0.4454</td>
                        <td className="py-2 px-3 text-cyan-400 font-bold">0.7764</td>
                      </tr>
                      <tr className={selectedProfileId === 'FULL' ? 'bg-emerald-950/30' : ''}>
                        <td className="py-2 px-3 font-sans font-bold text-slate-200">FULL (Полная наблюдаемость)</td>
                        <td className="py-2 px-3">19</td>
                        <td className="py-2 px-3 font-bold text-white">0.6766 (+15.7%)</td>
                        <td className="py-2 px-3 text-emerald-400 font-bold">0.9995</td>
                        <td className="py-2 px-3">0.4490</td>
                        <td className="py-2 px-3 text-cyan-400 font-bold">0.7764</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Events Table */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-bold text-white">
              Зафиксированные события сценария ({events.length})
            </h3>
            <span className="text-xs text-slate-400">
              Хранятся в реляционной БД
            </span>
          </div>

          <div className="overflow-x-auto max-h-60 overflow-y-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-slate-800 text-slate-400">
                  <th className="py-2 px-3">Интервал времени</th>
                  <th className="py-2 px-3">Правило / Метод</th>
                  <th className="py-2 px-3">Важность</th>
                  <th className="py-2 px-3">Тип заключения</th>
                  <th className="py-2 px-3">Версия модели</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {events.map(ev => (
                  <tr
                    key={ev.id}
                    onClick={() => setSelectedEventId(ev.id)}
                    className={`cursor-pointer transition-colors ${
                      selectedEventId === ev.id ? 'bg-slate-800/80' : 'hover:bg-slate-800/40'
                    }`}
                  >
                    <td className="py-2 px-3 font-mono text-[11px]">
                      {ev.started_at.substring(5, 16)} — {ev.ended_at.substring(11, 16)}
                    </td>
                    <td className="py-2 px-3 font-semibold text-slate-200">
                      {ev.rule_id}
                    </td>
                    <td className="py-2 px-3">
                      <span
                        className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                          ev.severity === 'CRITICAL'
                            ? 'bg-rose-950 text-rose-300'
                            : 'bg-amber-950 text-amber-300'
                        }`}
                      >
                        {ev.severity}
                      </span>
                    </td>
                    <td className="py-2 px-3 text-slate-400">
                      {ev.conclusion_type}
                    </td>
                    <td className="py-2 px-3 font-mono text-[11px] text-slate-400">
                      {ev.generated_by_version}
                    </td>
                  </tr>
                ))}
                {events.length === 0 && (
                  <tr>
                    <td colSpan={5} className="py-4 text-center text-slate-500 italic">
                      Событий не зафиксировано
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Ground Truth Evaluation Panel (Strictly Separated) */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-sm">
          <button
            onClick={() => setShowGroundTruth(!showGroundTruth)}
            className="w-full p-4 flex items-center justify-between text-left hover:bg-slate-800/40 transition-colors"
          >
            <div className="flex items-center space-x-2">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-400">
                Разметка бенчмарка (Ground Truth для исследовательской верификации)
              </span>
              <span className="text-[10px] px-1.5 py-0.2 rounded bg-purple-950 text-purple-300 border border-purple-800">
                Научный аудит
              </span>
            </div>
            {showGroundTruth ? (
              <ChevronUp className="w-4 h-4 text-slate-400" />
            ) : (
              <ChevronDown className="w-4 h-4 text-slate-400" />
            )}
          </button>

          {showGroundTruth && (
            <div className="p-4 border-t border-slate-800 bg-slate-950 space-y-3">
              <p className="text-xs text-slate-400">
                В соответствии с протоколом исследования, истинная метка датасета категорически изолирована от диагностического классификатора и доступна исключительно для внешней валидации.
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
                <div className="bg-slate-900 p-3 rounded-lg border border-slate-800">
                  <div className="text-slate-500 text-[10px] uppercase font-bold">Истинная метка (Ground Truth)</div>
                  <div className="text-sm font-bold text-white mt-1">
                    {summary?.ground_truth?.source_fault_label || 'FAULT_FREE'}
                  </div>
                </div>
                <div className="bg-slate-900 p-3 rounded-lg border border-slate-800">
                  <div className="text-slate-500 text-[10px] uppercase font-bold">Тип дефекта в датасете</div>
                  <div className="text-sm font-bold text-white mt-1">
                    {summary?.ground_truth?.source_fault_label_type || 'FAULT_FREE'}
                  </div>
                </div>
                <div className="bg-slate-900 p-3 rounded-lg border border-slate-800">
                  <div className="text-slate-500 text-[10px] uppercase font-bold">Сравнение с моделью</div>
                  <div className="text-sm font-bold mt-1 text-emerald-400">
                    {summary?.ground_truth?.source_fault_label_type === summary?.localization.candidate_class
                      ? '✓ Точное совпадение семейства'
                      : 'Различие / Неопределено'}
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
};
