import React, { useState, useEffect, useRef, useMemo } from 'react';
import {
  Layers,
  Sliders,
  Activity,
  ShieldCheck,
  FileText,
  AlertTriangle,
  Building,
  CheckCircle2,
  Lock,
  Download,
  Info
} from 'lucide-react';
import { ReplayClockBar, AHUOperatingMode } from '../components/ReplayClockBar';
import { AHUIndustrialSchematic } from '../components/AHUIndustrialSchematic';
import { SynchronousTelemetryCharts } from '../components/SynchronousTelemetryCharts';
import { EvidenceInspectorCard } from '../components/EvidenceInspectorCard';
import { SensorLabPanel } from '../components/SensorLabPanel';
import { NormalFaultOverlayPanel } from '../components/NormalFaultOverlayPanel';

import datasetsFixtureData from '../fixtures/datasets_fixture.json';
import investigatorFixtureData from '../fixtures/investigator_ahu_fixture.json';
import evidenceFixtureData from '../fixtures/evidence_fixture.json';
import sensorLabFixtureData from '../fixtures/sensor_lab_fixture.json';
import matchedPairsFixtureData from '../fixtures/matched_pairs_fixture.json';

interface AHUInvestigatorPageProps {
  assetId?: string;
  initialTimestamp?: string;
  onSelectAsset?: (assetId: string) => void;
  onNavigateToIncidents?: () => void;
}

export const AHUInvestigatorPage: React.FC<AHUInvestigatorPageProps> = ({
  assetId = 'ahu-sd',
  initialTimestamp,
  onSelectAsset,
  onNavigateToIncidents
}) => {
  // Contextual tabs inside Investigator workspace
  const [activeWorkspaceTab, setActiveWorkspaceTab] = useState<
    'schematic_telemetry' | 'sensor_lab' | 'normal_fault' | 'quality_modes' | 'audit_report'
  >('schematic_telemetry');

  // Mobile / Narrow layout tab switch (when width < 1024px)
  const [mobileSplitTab, setMobileSplitTab] = useState<'schematic' | 'inspector'>('schematic');

  // Active Profile for Sensor Lab (BASIC, BASIC_PLUS_VALVE, etc.)
  const [activeProfile, setActiveProfile] = useState<'BASIC' | 'BASIC_PLUS_VALVE' | 'BASIC_PLUS_DAMPER' | 'FULL'>('BASIC');
  const [isRecomputing, setIsRecomputing] = useState<boolean>(false);

  // Replay Clock State
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [playbackSpeed, setPlaybackSpeed] = useState<number>(5);
  const [currentIndex, setCurrentIndex] = useState<number>(0);

  // Playback timer ref
  const playbackTimerRef = useRef<any>(null);

  // Telemetry time points
  const timePoints: string[] = useMemo(() => {
    const satSeries = investigatorFixtureData.series.find(s => s.channel === 'SA_TEMP');
    return satSeries ? satSeries.points.map(p => String(p[0])) : [];
  }, []);

  const totalPoints = timePoints.length;

  // Initialize cursor on initialTimestamp if given
  useEffect(() => {
    if (initialTimestamp && timePoints.length > 0) {
      const idx = timePoints.indexOf(initialTimestamp);
      if (idx !== -1) {
        setCurrentIndex(idx);
      }
    }
  }, [initialTimestamp, timePoints]);

  const currentTimestamp: string = timePoints[currentIndex] || String(investigatorFixtureData.default_cursor_timestamp);

  // Derive Current Values at currentTimestamp for schematic
  const currentValues = useMemo(() => {
    const vals: Record<string, number | null> = {};
    investigatorFixtureData.series.forEach(s => {
      const point = s.points.find(p => String(p[0]) === currentTimestamp);
      vals[s.channel] = point && point[1] !== null ? Number(point[1]) : null;
    });

    // If profile has physical feedback, populate it
    if (activeProfile === 'BASIC_PLUS_VALVE' || activeProfile === 'FULL') {
      const chwcCmd = vals['CHWC_VLV_DM'];
      vals['CHWC_VLV'] = chwcCmd !== null && chwcCmd !== undefined ? chwcCmd * 0.98 : null;
    }
    if (activeProfile === 'BASIC_PLUS_DAMPER' || activeProfile === 'FULL') {
      const oaCmd = vals['OA_DMPR_DM'];
      vals['OA_DMPR'] = oaCmd !== null && oaCmd !== undefined ? oaCmd : null;
    }

    return vals;
  }, [currentTimestamp, activeProfile]);

  // Derive Current Operating Mode and Fan state from mode_segments
  const { currentMode, fanOn } = useMemo(() => {
    const seg = investigatorFixtureData.mode_segments.find(m => {
      return currentTimestamp >= m.start && currentTimestamp <= m.end;
    });
    if (seg) {
      return {
        currentMode: seg.mode as AHUOperatingMode,
        fanOn: seg.fan_on
      };
    }
    return {
      currentMode: 'UNKNOWN' as AHUOperatingMode,
      fanOn: false
    };
  }, [currentTimestamp]);

  // Replay playback effect
  useEffect(() => {
    if (isPlaying && totalPoints > 0) {
      const intervalMs = Math.max(100, Math.floor(1000 / playbackSpeed));
      playbackTimerRef.current = setInterval(() => {
        setCurrentIndex(prev => {
          if (prev >= totalPoints - 1) {
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
  }, [isPlaying, playbackSpeed, totalPoints]);

  const handleSeekTimestamp = (ts: string) => {
    const idx = timePoints.indexOf(ts);
    if (idx !== -1) {
      setCurrentIndex(idx);
    }
  };

  const handleRecompute = () => {
    setIsRecomputing(true);
    setTimeout(() => {
      setIsRecomputing(false);
    }, 800);
  };

  // Assets list from datasets fixture
  const assetsList = useMemo(() => {
    const list: Array<{ id: string; name: string; building: string; dataset_name: string }> = [];
    datasetsFixtureData.items.forEach(ds => {
      ds.equipment_list.forEach(eq => {
        list.push({
          id: eq.id,
          name: eq.name,
          building: eq.building,
          dataset_name: ds.name
        });
      });
    });
    return list;
  }, []);

  return (
    <div className="max-w-[1920px] mx-auto p-3 sm:p-4 space-y-4 select-none">
      {/* Upper Navigation Replay Clock Bar */}
      <ReplayClockBar
        isPlaying={isPlaying}
        onTogglePlay={() => setIsPlaying(!isPlaying)}
        onReset={() => {
          setIsPlaying(false);
          setCurrentIndex(0);
        }}
        currentIndex={currentIndex}
        totalPoints={totalPoints}
        onSeekIndex={setCurrentIndex}
        currentTimestamp={currentTimestamp}
        playbackSpeed={playbackSpeed}
        onChangeSpeed={setPlaybackSpeed}
        currentMode={currentMode}
        fanOn={fanOn}
        hasDataGap={currentTimestamp >= '2026-07-15T13:45:00Z' && currentTimestamp <= '2026-07-15T14:15:00Z'}
      />

      {/* Main Workspace Layout with Left Sidebar */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* Left Sidebar: Equipment Hierarchy (3 cols on 1280+) */}
        <aside className="lg:col-span-3 xl:col-span-2 space-y-3">
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-3 shadow-md space-y-2">
            <div className="flex items-center justify-between text-xs font-bold text-slate-300 pb-2 border-b border-slate-800">
              <span className="flex items-center space-x-1.5">
                <Building className="w-4 h-4 text-emerald-400" />
                <span>Оборудование AHU</span>
              </span>
              <span className="text-[10px] font-mono text-slate-500">{assetsList.length} уст.</span>
            </div>

            <div className="space-y-1">
              {assetsList.map(item => {
                const isSelected = item.id === assetId;
                return (
                  <button
                    key={item.id}
                    onClick={() => onSelectAsset && onSelectAsset(item.id)}
                    className={`w-full text-left p-2 rounded-lg text-xs transition-all ${
                      isSelected
                        ? 'bg-emerald-950/80 text-emerald-300 border border-emerald-700/80 font-bold shadow-sm'
                        : 'text-slate-300 hover:bg-slate-800 border border-transparent'
                    }`}
                  >
                    <div className="truncate">{item.name}</div>
                    <div className="text-[10px] text-slate-400 truncate mt-0.5">{item.building}</div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Quick Contextual Navigation Tabs */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-3 shadow-md space-y-1">
            <div className="text-[10px] font-mono uppercase tracking-wider text-slate-500 mb-2 px-1">
              Контекстные разделы
            </div>

            <button
              onClick={() => setActiveWorkspaceTab('schematic_telemetry')}
              className={`w-full text-left px-2.5 py-1.5 rounded-lg text-xs font-medium flex items-center space-x-2 transition-colors ${
                activeWorkspaceTab === 'schematic_telemetry'
                  ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 font-semibold'
                  : 'text-slate-400 hover:bg-slate-800 hover:text-slate-200'
              }`}
            >
              <Activity className="w-4 h-4 text-emerald-400" />
              <span>Мнемосхема и Телеметрия</span>
            </button>

            <button
              onClick={() => setActiveWorkspaceTab('sensor_lab')}
              className={`w-full text-left px-2.5 py-1.5 rounded-lg text-xs font-medium flex items-center space-x-2 transition-colors ${
                activeWorkspaceTab === 'sensor_lab'
                  ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 font-semibold'
                  : 'text-slate-400 hover:bg-slate-800 hover:text-slate-200'
              }`}
            >
              <Sliders className="w-4 h-4 text-cyan-400" />
              <span>Sensor Lab (BASIC/EXTRA)</span>
            </button>

            <button
              onClick={() => setActiveWorkspaceTab('normal_fault')}
              className={`w-full text-left px-2.5 py-1.5 rounded-lg text-xs font-medium flex items-center space-x-2 transition-colors ${
                activeWorkspaceTab === 'normal_fault'
                  ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 font-semibold'
                  : 'text-slate-400 hover:bg-slate-800 hover:text-slate-200'
              }`}
            >
              <Layers className="w-4 h-4 text-purple-400" />
              <span>Сравнение Норма / Авария</span>
            </button>

            <button
              onClick={() => setActiveWorkspaceTab('quality_modes')}
              className={`w-full text-left px-2.5 py-1.5 rounded-lg text-xs font-medium flex items-center space-x-2 transition-colors ${
                activeWorkspaceTab === 'quality_modes'
                  ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 font-semibold'
                  : 'text-slate-400 hover:bg-slate-800 hover:text-slate-200'
              }`}
            >
              <ShieldCheck className="w-4 h-4 text-amber-400" />
              <span>Качество и Режимы</span>
            </button>

            <button
              onClick={() => setActiveWorkspaceTab('audit_report')}
              className={`w-full text-left px-2.5 py-1.5 rounded-lg text-xs font-medium flex items-center space-x-2 transition-colors ${
                activeWorkspaceTab === 'audit_report'
                  ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 font-semibold'
                  : 'text-slate-400 hover:bg-slate-800 hover:text-slate-200'
              }`}
            >
              <FileText className="w-4 h-4 text-blue-400" />
              <span>Инженерный Аудит и Отчет</span>
            </button>
          </div>
        </aside>

        {/* Central & Right Content Area (10 cols on 1280+) */}
        <main className="lg:col-span-9 xl:col-span-10 space-y-4">
          {/* TAB 1: SCHEMATIC + EVIDENCE INSPECTOR + 3 SYNCHRONOUS CHARTS */}
          {activeWorkspaceTab === 'schematic_telemetry' && (
            <div className="space-y-4">
              {/* Responsive Tab Switcher for Viewports < 1024px */}
              <div className="flex sm:hidden bg-slate-900 p-1 rounded-lg border border-slate-800 text-xs">
                <button
                  onClick={() => setMobileSplitTab('schematic')}
                  className={`flex-1 py-1.5 rounded-md font-semibold text-center ${
                    mobileSplitTab === 'schematic' ? 'bg-emerald-600 text-white' : 'text-slate-400'
                  }`}
                >
                  Мнемосхема AHU
                </button>
                <button
                  onClick={() => setMobileSplitTab('inspector')}
                  className={`flex-1 py-1.5 rounded-md font-semibold text-center ${
                    mobileSplitTab === 'inspector' ? 'bg-emerald-600 text-white' : 'text-slate-400'
                  }`}
                >
                  Свидетельства и Факты
                </button>
              </div>

              {/* Upper Split: Central SVG Schematic & Right Evidence Card */}
              <div className="grid grid-cols-1 xl:grid-cols-12 gap-4">
                {/* Central Schematic (7 cols on XL) */}
                <div className={`xl:col-span-7 ${mobileSplitTab === 'inspector' ? 'hidden sm:block' : ''}`}>
                  <AHUIndustrialSchematic
                    currentValues={currentValues}
                    currentTimestamp={currentTimestamp}
                    hasCoolingAlert={currentValues['SA_TEMP'] !== null && (currentValues['SA_TEMP'] || 0) > 17.5}
                    hasFreezeAlert={false}
                    fanOn={fanOn}
                    activeProfile={activeProfile}
                  />
                </div>

                {/* Right Facts / Evidence Inspector Card (5 cols on XL) */}
                <div className={`xl:col-span-5 ${mobileSplitTab === 'schematic' ? 'hidden sm:block' : ''}`}>
                  <EvidenceInspectorCard
                    detectionState="DETECTED"
                    causeState="AMBIGUOUS"
                    dataState="VALID"
                    modelScope="IN_SCOPE"
                    ruleEvaluation={evidenceFixtureData.rule_evaluation}
                    hypotheses={evidenceFixtureData.hypotheses}
                    unexecutableChecks={evidenceFixtureData.unexecutable_checks}
                    recommendedActions={evidenceFixtureData.recommended_actions_whitelist as any}
                    causalityGraph={evidenceFixtureData.causality_graph}
                  />
                </div>
              </div>

              {/* Lower Section: 3 Synchronous Telemetry Charts */}
              <div className="space-y-2">
                <div className="flex items-center justify-between text-xs text-slate-400 px-1">
                  <span className="font-semibold text-slate-300">
                    Синхронные временные графики (Связанный курсор, Min/Max Envelope, Сырой зум)
                  </span>
                  <span className="font-mono text-[11px]">Шаг сетки: 5 минут (Без искусственного сглаживания)</span>
                </div>

                <SynchronousTelemetryCharts
                  currentTimestamp={currentTimestamp}
                  onSeekTimestamp={handleSeekTimestamp}
                  series={investigatorFixtureData.series as any}
                  isModelAvailable={true}
                />
              </div>
            </div>
          )}

          {/* TAB 2: SENSOR LAB */}
          {activeWorkspaceTab === 'sensor_lab' && (
            <SensorLabPanel
              profiles={sensorLabFixtureData.profiles as any}
              channelMatrix={sensorLabFixtureData.channel_matrix as any}
              activeProfileId={activeProfile}
              onSelectProfile={(pId: string) => setActiveProfile(pId as any)}
              onRequestRecomputation={handleRecompute}
              isRecomputing={isRecomputing}
            />
          )}

          {/* TAB 3: NORMAL VS FAULT OVERLAY */}
          {activeWorkspaceTab === 'normal_fault' && (
            <NormalFaultOverlayPanel
              pairs={matchedPairsFixtureData.pairs as any}
            />
          )}

          {/* TAB 4: DATA QUALITY & MODES */}
          {activeWorkspaceTab === 'quality_modes' && (
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 shadow-xl space-y-4">
              <div className="flex items-center space-x-2 pb-2 border-b border-slate-800">
                <ShieldCheck className="w-5 h-5 text-amber-400" />
                <h3 className="text-xs font-bold tracking-wider uppercase text-slate-200">
                  Аудит качества данных и эксплуатационных режимов
                </h3>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-4 gap-3 text-xs">
                <div className="p-3 bg-slate-950/80 rounded-lg border border-slate-800">
                  <span className="text-slate-500 block text-[10px] uppercase font-mono">Монотонность времени</span>
                  <span className="text-emerald-400 font-bold text-sm flex items-center space-x-1 mt-1">
                    <CheckCircle2 className="w-4 h-4" />
                    <span>Строго монотонно (0 сбоев)</span>
                  </span>
                </div>
                <div className="p-3 bg-slate-950/80 rounded-lg border border-slate-800">
                  <span className="text-slate-500 block text-[10px] uppercase font-mono">Пропуски (Data Gaps)</span>
                  <span className="text-amber-400 font-bold text-sm flex items-center space-x-1 mt-1">
                    <AlertTriangle className="w-4 h-4" />
                    <span>1 интервал (30 мин)</span>
                  </span>
                </div>
                <div className="p-3 bg-slate-950/80 rounded-lg border border-slate-800">
                  <span className="text-slate-500 block text-[10px] uppercase font-mono">Замирание (Stuck Signal)</span>
                  <span className="text-emerald-400 font-bold text-sm flex items-center space-x-1 mt-1">
                    <CheckCircle2 className="w-4 h-4" />
                    <span>Не обнаружено</span>
                  </span>
                </div>
                <div className="p-3 bg-slate-950/80 rounded-lg border border-slate-800">
                  <span className="text-slate-500 block text-[10px] uppercase font-mono">Выход за физические пределы</span>
                  <span className="text-emerald-400 font-bold text-sm flex items-center space-x-1 mt-1">
                    <CheckCircle2 className="w-4 h-4" />
                    <span>0 точек OOR</span>
                  </span>
                </div>
              </div>

              <div className="p-3 bg-slate-950/70 rounded-lg border border-slate-800 text-xs text-slate-300 space-y-2">
                <div className="font-semibold text-slate-200">Журнал режимных переходов LBNL State Machine:</div>
                <div className="space-y-1 font-mono text-[11px] text-slate-400">
                  {investigatorFixtureData.mode_segments.map((seg, idx) => (
                    <div key={idx} className="flex justify-between py-1 border-b border-slate-850">
                      <span>{seg.start.substring(11, 16)} – {seg.end.substring(11, 16)} UTC</span>
                      <span className="text-emerald-400 font-bold">{seg.mode}</span>
                      <span>Вентилятор: {seg.fan_on ? 'ВКЛ' : 'ВЫКЛ'}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* TAB 5: AUDIT & REPORT */}
          {activeWorkspaceTab === 'audit_report' && (
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 shadow-xl space-y-4">
              <div className="flex items-center justify-between pb-2 border-b border-slate-800">
                <div className="flex items-center space-x-2">
                  <FileText className="w-5 h-5 text-blue-400" />
                  <h3 className="text-xs font-bold tracking-wider uppercase text-slate-200">
                    Инженерный паспорт и Аудиторский отчет
                  </h3>
                </div>
                <button
                  onClick={() => alert('Экспорт отчета доступен при наличии связи с backend API v1.')}
                  className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-blue-600/30 text-blue-300 border border-blue-500 hover:bg-blue-600/40 transition-colors flex items-center space-x-1.5"
                >
                  <Download className="w-3.5 h-3.5" />
                  <span>Экспорт отчета (JSON / Markdown)</span>
                </button>
              </div>

              <div className="p-3 bg-slate-950/80 rounded-lg border border-slate-800 text-xs space-y-2 text-slate-300">
                <div className="font-bold text-slate-200">Метаданные сессии и происхождения:</div>
                <div className="grid grid-cols-2 gap-2 font-mono text-[11px]">
                  <div><span className="text-slate-500">Dataset ID:</span> ds-lbnl-sdahu</div>
                  <div><span className="text-slate-500">Equipment:</span> LBNL SD-AHU 01</div>
                  <div><span className="text-slate-500">Provenance:</span> SYNTHETIC_UI_ONLY (UI_MOCK_V0)</div>
                  <div><span className="text-slate-500">Run ID:</span> ui-demo-investigator-v0</div>
                  <div><span className="text-slate-500">Data Hash:</span> sha256:d11cbb117b57...</div>
                  <div><span className="text-slate-500">Ground Truth Status:</span> NO_GROUND_TRUTH</div>
                </div>
                <div className="pt-2 text-[11px] text-amber-300/80 italic border-t border-slate-800">
                  *Внимание: фикстурные данные используются исключительно для автономной верстки интерфейса. В научном отчете или экспорте реальных испытаний данные фикстур не участвуют.
                </div>
              </div>
            </div>
          )}
        </main>
      </div>
    </div>
  );
};
