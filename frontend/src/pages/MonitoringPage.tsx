import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Activity,
  AlertCircle,
  Database,
  Upload,
  RefreshCw,
  CheckCircle2,
  XCircle,
  FlaskConical,
  HelpCircle,
  Brain,
  Sliders,
  Check
} from 'lucide-react';
import { apiClient } from '../api/client';
import {
  DatasetItem,
  ScenarioItem,
  SensorItem,
  TelemetryResponse,
  DataQualityReport,
  DiagnosticEventItem,
  HealthResponse,
  MLModelItem,
  MLPredictionResponse
} from '../types/api';
import { AHUSchematic } from '../components/AHUSchematic';
import { TelemetryChart } from '../components/TelemetryChart';
import { PlaybackControls } from '../components/PlaybackControls';
import { SensorSelector } from '../components/SensorSelector';
import { DataQualityPanel } from '../components/DataQualityPanel';

interface MonitoringPageProps {
  activeTab?: 'monitoring' | 'diagnostics' | 'research';
  onTabChange?: (tab: 'monitoring' | 'diagnostics' | 'research') => void;
  selectedScenarioId?: string;
  onSelectScenarioId?: (id: string) => void;
}

export const MonitoringPage: React.FC<MonitoringPageProps> = ({
  activeTab = 'monitoring',
  onTabChange,
  selectedScenarioId: propScenarioId,
  onSelectScenarioId: propOnSelectScenarioId
}) => {
  // Global States
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);

  const [datasets, setDatasets] = useState<DatasetItem[]>([]);
  const [scenarios, setScenarios] = useState<ScenarioItem[]>([]);
  const [localScenarioId, setLocalScenarioId] = useState<string>('');
  const selectedScenarioId = propScenarioId || localScenarioId;
  const setSelectedScenarioId = (id: string) => {
    if (propOnSelectScenarioId) {
      propOnSelectScenarioId(id);
    }
    setLocalScenarioId(id);
  };

  const [sensors, setSensors] = useState<SensorItem[]>([]);
  const [selectedChannels, setSelectedChannels] = useState<string[]>([
    'OA_TEMP',
    'MA_TEMP',
    'SA_TEMP',
    'CHWC_VLV_DM'
  ]);

  const [telemetry, setTelemetry] = useState<TelemetryResponse | null>(null);
  const [qualityReport, setQualityReport] = useState<DataQualityReport | null>(null);
  const [events, setEvents] = useState<DiagnosticEventItem[]>([]);

  // ML Virtual Sensor States
  const [mlModels, setMlModels] = useState<MLModelItem[]>([]);
  const [selectedModelId, setSelectedModelId] = useState<string>('vs-sa-temp-v1');
  const [isVirtualSensorEnabled, setIsVirtualSensorEnabled] = useState<boolean>(true);
  const [thresholdPolicy, setThresholdPolicy] = useState<string>('three_sigma');
  const [mlPredictions, setMlPredictions] = useState<MLPredictionResponse | null>(null);
  const [isLoadingML, setIsLoadingML] = useState<boolean>(false);
  const [isRunningMLDetect, setIsRunningMLDetect] = useState<boolean>(false);
  const [mlError, setMlError] = useState<string | null>(null);

  // Playback state
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [playbackIndex, setPlaybackIndex] = useState<number>(0);
  const [playbackSpeed, setPlaybackSpeed] = useState<number>(5);

  const [isLoadingTelemetry, setIsLoadingTelemetry] = useState<boolean>(false);
  const [isRunningRules, setIsRunningRules] = useState<boolean>(false);
  const [uploadModalOpen, setUploadModalOpen] = useState<boolean>(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState<boolean>(false);

  // Interval timer ref for playback
  const playbackTimerRef = useRef<any>(null);

  // 1. Initial Health and Datasets Check
  const loadInitialData = async () => {
    try {
      const h = await apiClient.getHealth();
      setHealth(h);
      setHealthError(null);
    } catch (e: any) {
      setHealthError(e.message || 'Ошибка подключения к API');
    }

    try {
      const dsList = await apiClient.getDatasets();
      setDatasets(dsList);

      const scList = await apiClient.getScenarios();
      setScenarios(scList);

      if (scList.length > 0 && !selectedScenarioId) {
        setSelectedScenarioId(scList[0].id);
      }

      const models = await apiClient.getMLModels().catch(() => []);
      setMlModels(models);
      if (models.length > 0) {
        const defaultModel = models.find(m => !m.is_adaptation && !m.model_id.startsWith('csiro-'))?.model_id || models[0].model_id;
        setSelectedModelId(prev => (prev && models.some(m => m.model_id === prev)) ? prev : defaultModel);
      }
    } catch (e: any) {
      console.error('Error fetching scenarios/models:', e);
    }
  };

  useEffect(() => {
    loadInitialData();
  }, []);

  // 2. Load scenario metadata when selectedScenarioId changes
  useEffect(() => {
    if (!selectedScenarioId) return;

    let isCancelled = false;

    const loadScenarioDetails = async () => {
      try {
        const sList = await apiClient.getSensors(selectedScenarioId);
        if (isCancelled) return;
        setSensors(sList);

        // Filter default channels to only those available
        const availKeys = sList.map(s => s.canonical_key);
        setSelectedChannels(prev => {
          const valid = prev.filter(k => availKeys.includes(k));
          if (valid.length === 0 && availKeys.length > 0) {
            return availKeys.slice(0, 4);
          }
          return valid;
        });

        // Load Quality Report, Rule Events and ML Events
        const [q, ruleEvs, mlEvs] = await Promise.all([
          apiClient.getDataQuality(selectedScenarioId).catch(() => null),
          apiClient.getDiagnosticEvents(selectedScenarioId).catch(() => []),
          apiClient.getMLEvents(selectedScenarioId).catch(() => [])
        ]);

        if (isCancelled) return;
        setQualityReport(q);
        // Deduplicate events by id
        const uniqueEventsMap = new Map();
        for (const ev of [...ruleEvs, ...mlEvs]) {
          if (!uniqueEventsMap.has(ev.id)) {
            uniqueEventsMap.set(ev.id, ev);
          }
        }
        setEvents(Array.from(uniqueEventsMap.values()));

        // Reset playback position
        setIsPlaying(false);
        setPlaybackIndex(0);
      } catch (err) {
        console.error('Error loading scenario sensors:', err);
      }
    };

    loadScenarioDetails();

    return () => {
      isCancelled = true;
    };
  }, [selectedScenarioId]);

  const currentScenario = scenarios.find(s => s.id === selectedScenarioId);
  const currentDataset = datasets.find(d => d.id === currentScenario?.dataset_id);
  const selectedModel = mlModels.find(m => m.model_id === selectedModelId);
  const isCsiroModel = Boolean(
    selectedModel?.is_adaptation ||
    selectedModelId.startsWith('csiro-') ||
    selectedModel?.target_domain === 'CSIRO_AHU9'
  );
  const isCsiroScenario =
    currentDataset?.source_kind === 'REAL_FIELD_BMS' ||
    (currentScenario?.name?.toLowerCase().includes('csiro') ?? false);
  const isModelIncompatible = isCsiroModel && !isCsiroScenario;

  // Fetch ML predictions
  const fetchMLPredictions = useCallback(async () => {
    if (!selectedScenarioId || !isVirtualSensorEnabled) {
      setMlPredictions(null);
      setMlError(null);
      return;
    }

    if (isModelIncompatible) {
      setMlPredictions(null);
      setMlError(
        `Модель «${selectedModel?.name || selectedModelId}» откалибрована для натурного датасета CSIRO AHU9 (REAL_FIELD_BMS) и несовместима со сценарием «${currentScenario?.name || selectedScenarioId}» (${currentDataset?.source_kind || 'UNKNOWN'}). Для анализа выберите модель симулятора LBNL (vs-sa-temp-v1 / vs-sa-temp-v2) или откройте сценарий CSIRO на вкладке «Исследования».`
      );
      setIsLoadingML(false);
      return;
    }

    setIsLoadingML(true);
    setMlError(null);
    try {
      const pred = await apiClient.getMLPredictions(
        selectedScenarioId,
        selectedModelId,
        thresholdPolicy,
        1500
      );
      setMlPredictions(pred);
    } catch (err: any) {
      setMlError(err.message || 'Ошибка загрузки виртуального датчика');
      setMlPredictions(null);
    } finally {
      setIsLoadingML(false);
    }
  }, [selectedScenarioId, selectedModelId, thresholdPolicy, isVirtualSensorEnabled, isModelIncompatible, selectedModel, currentScenario, currentDataset]);

  useEffect(() => {
    fetchMLPredictions();
  }, [fetchMLPredictions]);

  // 3. Load Telemetry Series
  const fetchTelemetryData = useCallback(async () => {
    if (!selectedScenarioId || selectedChannels.length === 0) return;

    setIsLoadingTelemetry(true);
    try {
      const tel = await apiClient.getTelemetry(
        selectedScenarioId,
        selectedChannels,
        undefined,
        undefined,
        1500
      );
      setTelemetry(tel);
    } catch (e) {
      console.error('Error fetching telemetry:', e);
    } finally {
      setIsLoadingTelemetry(false);
    }
  }, [selectedScenarioId, selectedChannels]);

  useEffect(() => {
    fetchTelemetryData();
  }, [fetchTelemetryData]);

  // 4. Time points and live telemetry values mapped to cursor index
  const availableTimestamps = React.useMemo(() => {
    if (!telemetry || telemetry.series.length === 0) return [];
    return telemetry.series[0].points.map(pt => pt[0]);
  }, [telemetry]);

  const currentTimestamp = availableTimestamps[playbackIndex] || '';

  const currentValues = React.useMemo(() => {
    const vals: Record<string, number | null> = {};
    if (!telemetry) return vals;

    for (const s of telemetry.series) {
      if (playbackIndex < s.points.length) {
        vals[s.channel] = s.points[playbackIndex][1];
      } else {
        vals[s.channel] = null;
      }
    }
    return vals;
  }, [telemetry, playbackIndex]);

  // 5. Playback loop
  useEffect(() => {
    if (isPlaying && availableTimestamps.length > 0) {
      // Advance playbackIndex based on speed (interval 300ms / speed)
      const intervalMs = Math.max(50, Math.floor(600 / playbackSpeed));
      playbackTimerRef.current = setInterval(() => {
        setPlaybackIndex(prev => {
          if (prev >= availableTimestamps.length - 1) {
            setIsPlaying(false);
            return prev;
          }
          return prev + 1;
        });
      }, intervalMs);
    } else {
      if (playbackTimerRef.current) {
        clearInterval(playbackTimerRef.current);
        playbackTimerRef.current = null;
      }
    }

    return () => {
      if (playbackTimerRef.current) {
        clearInterval(playbackTimerRef.current);
      }
    };
  }, [isPlaying, playbackSpeed, availableTimestamps.length]);

  // Handle Playback Actions
  const handleTogglePlay = () => {
    if (playbackIndex >= availableTimestamps.length - 1) {
      setPlaybackIndex(0);
      setIsPlaying(true);
    } else {
      setIsPlaying(!isPlaying);
    }
  };

  const handleRewind = () => {
    setIsPlaying(false);
    setPlaybackIndex(0);
  };

  const handleStep = (delta: number) => {
    setIsPlaying(false);
    setPlaybackIndex(prev => {
      const next = prev + delta;
      return Math.max(0, Math.min(availableTimestamps.length - 1, next));
    });
  };

  const handleSeekIndex = (index: number) => {
    setIsPlaying(false);
    setPlaybackIndex(Math.max(0, Math.min(availableTimestamps.length - 1, index)));
  };

  const handleSeekToTimestamp = (timestamp: string) => {
    setIsPlaying(false);
    const idx = availableTimestamps.indexOf(timestamp);
    if (idx !== -1) {
      setPlaybackIndex(idx);
    }
  };

  // Channel toggling
  const handleToggleChannel = (channel: string) => {
    if (selectedChannels.includes(channel)) {
      if (selectedChannels.length > 1) {
        setSelectedChannels(selectedChannels.filter(c => c !== channel));
      }
    } else {
      if (selectedChannels.length < 5) {
        setSelectedChannels([...selectedChannels, channel]);
      }
    }
  };

  const handleSelectPreset = (channels: string[]) => {
    const avail = sensors.map(s => s.canonical_key);
    const valid = channels.filter(c => avail.includes(c));
    if (valid.length > 0) {
      setSelectedChannels(valid.slice(0, 5));
    }
  };

  // Run Rules
  const handleRunRules = async () => {
    if (!selectedScenarioId) return;
    setIsRunningRules(true);
    try {
      const res = await apiClient.runDiagnosticRules(selectedScenarioId);
      const mlEvs = await apiClient.getMLEvents(selectedScenarioId).catch(() => []);
      setEvents([...res.events, ...mlEvs]);
      const q = await apiClient.getDataQuality(selectedScenarioId);
      setQualityReport(q);
    } catch (e: any) {
      alert(`Ошибка выполнения правил: ${e.message}`);
    } finally {
      setIsRunningRules(false);
    }
  };

  // Run ML Detect
  const handleRunMLDetect = async () => {
    if (!selectedScenarioId) return;

    if (isModelIncompatible) {
      alert(`Запуск заблокирован (Domain Guard): Модель «${selectedModel?.name || selectedModelId}» предназначена для натурного датасета CSIRO AHU9 (REAL_FIELD_BMS) и несовместима с текущим сценарием.`);
      return;
    }

    if (currentDataset?.source_kind === 'SYNTHETIC_DEMO') {
      const confirmRun = window.confirm(
        'Внимание (Domain Guard): Модель обучена на симуляции LBNL SD-AHU. ' +
        'Сценарий относится к Synthetic Demo, поэтому детекция не является научно валидированной для этого источника. ' +
        'Запустить в ознакомительном режиме UNVALIDATED?'
      );
      if (!confirmRun) return;
    }

    setIsRunningMLDetect(true);
    try {
      const newEvs = await apiClient.runMLDetect(selectedScenarioId, selectedModelId, thresholdPolicy);
      const ruleEvs = await apiClient.getDiagnosticEvents(selectedScenarioId).catch(() => []);
      setEvents([...ruleEvs, ...newEvs]);
    } catch (e: any) {
      alert(`Ошибка выполнения ML-детекции: ${e.message}`);
    } finally {
      setIsRunningMLDetect(false);
    }
  };

  // CSV Upload
  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setIsUploading(true);
    setUploadError(null);
    try {
      const res = await apiClient.uploadCsv(file, 'USER_UPLOADED');
      setUploadModalOpen(false);
      await loadInitialData();
      if (res.scenario_id) {
        setSelectedScenarioId(res.scenario_id);
      }
    } catch (err: any) {
      setUploadError(err.message || 'Ошибка загрузки файла');
    } finally {
      setIsUploading(false);
    }
  };

  // Source Badge Styling
  const getSourceBadge = (kind?: string) => {
    switch (kind) {
      case 'SIMULATED_BENCHMARK':
        return (
          <span className="px-2 py-0.5 rounded text-xs font-semibold bg-sky-950 text-sky-300 border border-sky-700">
            Симуляция LBNL SD-AHU
          </span>
        );
      case 'SYNTHETIC_DEMO':
        return (
          <span className="px-2 py-0.5 rounded text-xs font-semibold bg-amber-950 text-amber-300 border border-amber-700">
            Синтетическое демо
          </span>
        );
      case 'PUBLIC_REAL':
        return (
          <span className="px-2 py-0.5 rounded text-xs font-semibold bg-emerald-950 text-emerald-300 border border-emerald-700">
            Реальные измерения здания
          </span>
        );
      case 'USER_UPLOADED':
        return (
          <span className="px-2 py-0.5 rounded text-xs font-semibold bg-purple-950 text-purple-300 border border-purple-700">
            Пользовательский CSV
          </span>
        );
      default:
        return (
          <span className="px-2 py-0.5 rounded text-xs bg-slate-800 text-slate-300 border border-slate-700">
            {kind || 'Неизвестно'}
          </span>
        );
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
      {/* Top Header */}
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

          {/* Navigation & API Health */}
          <div className="flex items-center space-x-3 self-end sm:self-auto">
            {/* Nav Tabs */}
            <nav className="flex items-center space-x-1 bg-slate-800/80 p-1 rounded-lg border border-slate-700 text-xs">
              <button
                onClick={() => onTabChange?.('monitoring')}
                className={`px-3 py-1 rounded-md font-semibold transition-all ${
                  activeTab === 'monitoring'
                    ? 'bg-emerald-600 text-slate-950 shadow-sm'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Мониторинг AHU
              </button>
              <button
                onClick={() => onTabChange?.('diagnostics')}
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
                onClick={() => onTabChange?.('research')}
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

            {/* Health Status Pill */}
            <div className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg border text-xs bg-slate-900/80 border-slate-700">
              {health && health.status === 'ok' ? (
                <>
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                  <span className="text-emerald-300 font-medium hidden md:inline">API: Подключено</span>
                </>
              ) : (
                <>
                  <XCircle className="w-3.5 h-3.5 text-rose-400" />
                  <span className="text-rose-300 font-medium">{healthError || 'Ошибка API'}</span>
                </>
              )}
            </div>

            {/* CSV Import Button */}
            <button
              onClick={() => setUploadModalOpen(true)}
              className="flex items-center space-x-1.5 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-200 text-xs font-semibold rounded-lg transition-colors"
            >
              <Upload className="w-3.5 h-3.5 text-sky-400" />
              <span>Импорт CSV</span>
            </button>
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 max-w-[1440px] w-full mx-auto p-4 space-y-4">
        {/* Scenario & Provenance Header Bar */}
        <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-3.5 flex flex-col md:flex-row md:items-center justify-between gap-3 shadow-md">
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center space-x-2">
              <Database className="w-4 h-4 text-emerald-400 shrink-0" />
              <span className="text-xs text-slate-400 font-medium">Сценарий данных:</span>
              <select
                value={selectedScenarioId}
                onChange={e => setSelectedScenarioId(e.target.value)}
                className="bg-slate-800 border border-slate-700 rounded-lg px-3 py-1 text-xs text-slate-100 font-medium focus:outline-none focus:ring-1 focus:ring-emerald-500"
              >
                {scenarios.map(sc => (
                  <option key={sc.id} value={sc.id}>
                    {sc.name} ({sc.total_rows.toLocaleString()} строк)
                  </option>
                ))}
              </select>
            </div>

            {getSourceBadge(currentDataset?.source_kind)}
          </div>

          <div className="flex items-center space-x-4 text-xs text-slate-400">
            {currentScenario && (
              <div>
                Временной охват:{' '}
                <span className="text-slate-200 font-mono">
                  {currentScenario.start_at} → {currentScenario.end_at}
                </span>
              </div>
            )}
            {telemetry?.sampling && (
              <div className="hidden sm:block">
                Точек на график:{' '}
                <span className="text-emerald-400 font-mono">
                  {telemetry.sampling.returned_points} / {telemetry.sampling.total_source_points}
                </span>
                {telemetry.sampling.aggregated && (
                  <span className="text-[10px] text-slate-500 ml-1">
                    ({telemetry.sampling.method})
                  </span>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Empty State warning if no scenarios exist */}
        {scenarios.length === 0 && (
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-12 text-center max-w-lg mx-auto">
            <AlertCircle className="w-12 h-12 text-amber-400 mx-auto mb-3" />
            <h3 className="text-base font-bold text-slate-200 mb-1">Нет загруженных сценариев</h3>
            <p className="text-xs text-slate-400 mb-4">
              Запустите генерацию демонстрационного сценария или импортируйте свой CSV-файл.
            </p>
            <button
              onClick={() => setUploadModalOpen(true)}
              className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-slate-950 font-semibold rounded-lg text-xs"
            >
              Загрузить первый CSV
            </button>
          </div>
        )}

        {scenarios.length > 0 && (
          <>
            {/* Top Row: AHU Schematic */}
            <AHUSchematic
              currentValues={currentValues}
              currentTimestamp={currentTimestamp}
              hasFreezeAlert={events.some(e => e.rule_id === 'RULE_PHYS_FREEZE_RISK')}
              hasCoolingAlert={events.some(e => e.rule_id === 'RULE_PHYS_COOLING_INEFFECTIVE')}
            />

            {/* Playback Controls Bar */}
            <PlaybackControls
              isPlaying={isPlaying}
              onTogglePlay={handleTogglePlay}
              onRewind={handleRewind}
              onStep={handleStep}
              currentIndex={playbackIndex}
              totalPoints={availableTimestamps.length}
              currentTimestamp={currentTimestamp}
              speed={playbackSpeed}
              onSetSpeed={setPlaybackSpeed}
              onSeekIndex={handleSeekIndex}
            />

            {/* Sensor Selector Bar */}
            <SensorSelector
              sensors={sensors}
              selectedChannels={selectedChannels}
              onToggleChannel={handleToggleChannel}
              onSelectPreset={handleSelectPreset}
              currentValues={currentValues}
            />

            {/* Virtual Sensor ML Control Bar */}
            <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-3.5 shadow-md flex flex-col md:flex-row md:items-center justify-between gap-3">
              <div className="flex flex-wrap items-center gap-3">
                <button
                  onClick={() => setIsVirtualSensorEnabled(!isVirtualSensorEnabled)}
                  className={`flex items-center space-x-2 px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all ${
                    isVirtualSensorEnabled
                      ? 'bg-rose-950/80 border-rose-500 text-rose-300 shadow-sm shadow-rose-950/50'
                      : 'bg-slate-800 border-slate-700 text-slate-400 hover:text-slate-200'
                  }`}
                >
                  <Brain className="w-4 h-4 text-rose-400" />
                  <span>Виртуальный датчик SA_TEMP</span>
                  <span className={`text-[10px] px-1.5 py-0.2 rounded font-mono ${
                    isVirtualSensorEnabled ? 'bg-rose-900/80 text-rose-200' : 'bg-slate-700 text-slate-400'
                  }`}>
                    {isVirtualSensorEnabled ? 'ВКЛ' : 'ВЫКЛ'}
                  </span>
                </button>

                {isVirtualSensorEnabled && (
                  <>
                    <div className="flex items-center space-x-1.5 text-xs text-slate-400">
                      <span>Модель:</span>
                      <select
                        value={selectedModelId}
                        onChange={e => setSelectedModelId(e.target.value)}
                        className="bg-slate-800 border border-slate-700 rounded-lg px-2.5 py-1 text-xs text-slate-200 font-medium focus:outline-none focus:ring-1 focus:ring-rose-500"
                      >
                        <optgroup label="Модели симулятора LBNL (Этапы 2–3)">
                          {mlModels.filter(m => !m.is_adaptation && !m.model_id.startsWith('csiro-')).map(m => (
                            <option key={m.model_id} value={m.model_id}>
                              [LBNL] {m.name} (MAE: {m.validation_metrics?.mae_degC?.toFixed(3) ?? 'N/A'} °C)
                            </option>
                          ))}
                        </optgroup>
                        <optgroup label="Адаптивные калибраторы CSIRO AHU9 (Этап 6)">
                          {mlModels.filter(m => m.is_adaptation || m.model_id.startsWith('csiro-')).map(m => (
                            <option key={m.model_id} value={m.model_id}>
                              [CSIRO] {m.name} (MAE: {m.validation_metrics?.mae_degC?.toFixed(3) ?? 'N/A'} °C)
                            </option>
                          ))}
                        </optgroup>
                      </select>
                    </div>

                    <div className="flex items-center space-x-1.5 text-xs text-slate-400">
                      <span>Порог:</span>
                      <select
                        value={thresholdPolicy}
                        onChange={e => setThresholdPolicy(e.target.value)}
                        className="bg-slate-800 border border-slate-700 rounded-lg px-2.5 py-1 text-xs text-slate-200 font-medium focus:outline-none focus:ring-1 focus:ring-rose-500"
                      >
                        <option value="three_sigma">3-Sigma (консервативный, 0% FA)</option>
                        <option value="q95">Q95 (чувствительный к дрейфу)</option>
                        <option value="mad">MAD (робастный)</option>
                        <option value="q99">Q99 (экстремальные отклонения)</option>
                      </select>
                    </div>
                  </>
                )}
              </div>

              {isVirtualSensorEnabled && (
                <div className="flex items-center space-x-3">
                  {mlPredictions && (
                    <div className="text-xs text-slate-400 hidden lg:flex items-center space-x-2">
                      <span>Порог: <strong className="text-rose-400 font-mono">{mlPredictions.threshold_value} °C</strong></span>
                      <span>•</span>
                      <span>Аномалий: <strong className="text-amber-400 font-mono">{mlPredictions.alarm_points}</strong> ({mlPredictions.alarm_episodes_count} эп.)</span>
                    </div>
                  )}

                  <button
                    onClick={handleRunMLDetect}
                    disabled={isRunningMLDetect || isLoadingML || isModelIncompatible}
                    className="flex items-center space-x-1.5 px-3 py-1.5 bg-rose-600 hover:bg-rose-500 disabled:opacity-50 text-white font-semibold text-xs rounded-lg transition-colors shadow-sm"
                  >
                    {isRunningMLDetect ? (
                      <>
                        <span className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                        <span>Детекция...</span>
                      </>
                    ) : (
                      <>
                        <Brain className="w-3.5 h-3.5" />
                        <span>Запуск ML-детекции</span>
                      </>
                    )}
                  </button>
                </div>
              )}
            </div>

            {/* Domain Incompatibility / Error Banner */}
            {isModelIncompatible && (
              <div className="p-3.5 bg-amber-950/70 border border-amber-500/60 rounded-xl text-xs text-amber-200 flex flex-col md:flex-row md:items-center justify-between gap-3 shadow-lg">
                <div className="flex items-start md:items-center space-x-2.5">
                  <AlertCircle className="w-5 h-5 text-amber-400 shrink-0 mt-0.5 md:mt-0" />
                  <div>
                    <span className="font-bold text-amber-300">Несовместимость домена данных (Domain Guard): </span>
                    <span>
                      Модель «{selectedModel?.name || selectedModelId}» откалибрована для натурного здания CSIRO AHU9 (REAL_FIELD_BMS) и не может применяться к сценарию «{currentScenario?.name}» ({currentDataset?.source_kind}).
                    </span>
                  </div>
                </div>
                <div className="flex items-center space-x-2 shrink-0 self-end md:self-auto">
                  <button
                    onClick={() => setSelectedModelId('vs-sa-temp-v2')}
                    className="px-3 py-1 bg-amber-600 hover:bg-amber-500 text-slate-950 font-bold rounded-lg text-xs transition-colors"
                  >
                    Выбрать vs-sa-temp-v2
                  </button>
                  {onTabChange && (
                    <button
                      onClick={() => onTabChange('research')}
                      className="px-3 py-1 bg-slate-800 hover:bg-slate-700 text-amber-300 font-semibold rounded-lg text-xs border border-amber-500/40 transition-colors"
                    >
                      К CSIRO в «Исследования»
                    </button>
                  )}
                </div>
              </div>
            )}

            {!isModelIncompatible && mlError && (
              <div className="p-3 bg-amber-950/40 border border-amber-500/40 rounded-xl text-xs text-amber-200 flex items-center space-x-2">
                <AlertCircle className="w-4 h-4 text-amber-400 shrink-0" />
                <span>{mlError}</span>
              </div>
            )}

            {/* Middle Row: Telemetry ECharts Chart & Virtual Sensor Residuals */}
            <TelemetryChart
              series={telemetry?.series || []}
              currentTimestamp={currentTimestamp}
              onSeekToTimestamp={handleSeekToTimestamp}
              isLoading={isLoadingTelemetry}
              mlPredictions={mlPredictions}
              showVirtualSensor={isVirtualSensorEnabled}
            />

            {/* Bottom Row: Data Quality & Diagnostics Baseline Panel */}
            <DataQualityPanel
              qualityReport={qualityReport}
              events={events}
              onRunRules={handleRunRules}
              isRunningRules={isRunningRules}
              sourceFaultLabel={currentScenario?.source_fault_label}
              sourceFaultLabelType={currentScenario?.source_fault_label_type}
            />
          </>
        )}
      </main>

      {/* CSV Upload Modal */}
      {uploadModalOpen && (
        <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-md w-full p-6 shadow-2xl">
            <h3 className="text-base font-bold text-white mb-2">Импорт локального CSV-файла</h3>
            <p className="text-xs text-slate-400 mb-4">
              Поддерживается любой CSV с колонкой времени (Datetime) и показаниями AHU. Каналы будут автоматически сопоставлены со словарем.
            </p>

            {uploadError && (
              <div className="mb-4 p-3 rounded-lg bg-rose-950/40 border border-rose-500/40 text-xs text-rose-200">
                {uploadError}
              </div>
            )}

            <div className="mb-4">
              <label className="block text-xs font-medium text-slate-300 mb-2">
                Выберите файл .csv:
              </label>
              <input
                type="file"
                accept=".csv"
                onChange={handleFileUpload}
                disabled={isUploading}
                className="w-full text-xs text-slate-400 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-emerald-600 file:text-slate-950 hover:file:bg-emerald-500 cursor-pointer"
              />
            </div>

            {isUploading && (
              <div className="text-xs text-emerald-400 flex items-center space-x-2 my-2">
                <span className="w-3.5 h-3.5 border-2 border-emerald-400 border-t-transparent rounded-full animate-spin" />
                <span>Обработка и конвертация в Parquet...</span>
              </div>
            )}

            <div className="flex justify-end space-x-2 mt-6">
              <button
                onClick={() => setUploadModalOpen(false)}
                disabled={isUploading}
                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-xs font-semibold"
              >
                Отмена
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
