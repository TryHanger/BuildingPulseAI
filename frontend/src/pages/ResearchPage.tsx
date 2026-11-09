import React, { useState, useEffect, useMemo } from 'react';
import ReactECharts from 'echarts-for-react';
import { api } from '../api/client';
import {
  Stage5RecommendationSummary,
  Stage5ExternalSummary,
  SensorRecommendationResponse,
  RecommendableChannelItem,
  AdaptationSummaryResponse,
  AdaptationModelCard,
  AdaptationPredictionsResponse
} from '../types/api';

interface ResearchPageProps {
  activeTab: 'monitoring' | 'diagnostics' | 'research';
  onTabChange: (tab: 'monitoring' | 'diagnostics' | 'research') => void;
  selectedScenarioId: string;
  onSelectScenarioId: (id: string) => void;
}

export function ResearchPage({
  activeTab,
  onTabChange,
  selectedScenarioId,
  onSelectScenarioId
}: ResearchPageProps) {
  const [internalTab, setInternalTab] = useState<'overview' | 'risk_coverage' | 'observability' | 'recommender' | 'real_building'>('overview');
  
  // Data states
  const [loading, setLoading] = useState<boolean>(true);
  const [stage4Data, setStage4Data] = useState<any>(null);
  const [recSummary, setRecSummary] = useState<Stage5RecommendationSummary | null>(null);
  const [extSummary, setExtSummary] = useState<Stage5ExternalSummary | null>(null);

  // Stage 6 Adaptation Data states
  const [realBuildingSubTab, setRealBuildingSubTab] = useState<'adaptation' | 'audit'>('adaptation');
  const [adaptSummary, setAdaptSummary] = useState<AdaptationSummaryResponse | null>(null);
  const [adaptModels, setAdaptModels] = useState<AdaptationModelCard[]>([]);
  const [selectedAdaptModelId, setSelectedAdaptModelId] = useState<string>('csiro-ahu9-affine-v1');
  const [adaptPredictions, setAdaptPredictions] = useState<AdaptationPredictionsResponse | null>(null);
  const [adaptLoading, setAdaptLoading] = useState<boolean>(false);
  const [allowUnvalidatedAdapt, setAllowUnvalidatedAdapt] = useState<boolean>(false);

  // Interactive Recommender State
  const [testProfile, setTestProfile] = useState<string>('BASIC');
  const [testCoverage, setTestCoverage] = useState<number>(0.60);
  const [recResult, setRecResult] = useState<SensorRecommendationResponse | null>(null);
  const [recLoading, setRecLoading] = useState<boolean>(false);

  // Risk Coverage view profile
  const [rcProfile, setRcProfile] = useState<'BASIC' | 'BASIC_PLUS_VALVE'>('BASIC');

  // Mark areas for documented fault injections on Held-Out Test
  const faultMarkAreas = useMemo(() => {
    if (!adaptPredictions || !adaptPredictions.points) return [];
    const areas: any[] = [];
    let startDt: string | null = null;
    adaptPredictions.points.forEach((p, idx) => {
      if (p.is_fault && !startDt) {
        startDt = p.datetime;
      } else if (!p.is_fault && startDt) {
        areas.push([{ xAxis: startDt }, { xAxis: adaptPredictions.points[idx - 1].datetime }]);
        startDt = null;
      }
    });
    if (startDt && adaptPredictions.points.length > 0) {
      areas.push([{ xAxis: startDt }, { xAxis: adaptPredictions.points[adaptPredictions.points.length - 1].datetime }]);
    }
    return areas;
  }, [adaptPredictions]);

  useEffect(() => {
    async function loadData() {
      setLoading(true);
      try {
        const [s4, s5r, s5e, aSum, aMods] = await Promise.all([
          api.getStage4ExperimentsSummary().catch(() => null),
          api.getStage5RecommendationSummary().catch(() => null),
          api.getStage5ExternalSummary().catch(() => null),
          api.getAdaptationSummary('CSIRO_AHU9').catch(() => null),
          api.getAdaptationModels('CSIRO_AHU9').catch(() => [])
        ]);
        setStage4Data(s4);
        setRecSummary(s5r);
        setExtSummary(s5e);
        setAdaptSummary(aSum);
        setAdaptModels(aMods);
      } catch (err) {
        console.error('Failed to load research data:', err);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  useEffect(() => {
    async function loadPredictions() {
      if (internalTab !== 'real_building') return;
      setAdaptLoading(true);
      try {
        const preds = await api.getAdaptationPredictions('CSIRO_AHU9', selectedAdaptModelId, 500);
        setAdaptPredictions(preds);
      } catch (err) {
        console.error('Failed to load adaptation predictions:', err);
      } finally {
        setAdaptLoading(false);
      }
    }
    loadPredictions();
  }, [internalTab, selectedAdaptModelId]);

  const handleRunRecommender = async () => {
    setRecLoading(true);
    try {
      const res = await api.getSensorRecommendation({
        scenario_id: selectedScenarioId || null,
        profile_id: testProfile,
        coverage_target: testCoverage,
        allow_unvalidated: false
      });
      setRecResult(res);
    } catch (err: any) {
      console.error('Recommender error:', err);
    } finally {
      setRecLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-900 text-slate-100 flex flex-col font-sans">
      {/* Header */}
      <header className="border-b border-slate-800 bg-slate-950/80 backdrop-blur sticky top-0 z-30 px-6 py-3.5 flex items-center justify-between">
        <div className="flex items-center space-x-4">
          <div className="h-9 w-9 rounded-lg bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400 font-bold text-lg">
            BP
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h1 className="text-base font-semibold text-slate-100 tracking-tight">BuildingPulse AI</h1>
              <span className="px-2 py-0.5 text-[11px] font-semibold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 rounded-full">
                v0.7.1-stage7.1
              </span>
            </div>
            <p className="text-xs text-slate-400">
              Научно-исследовательский протокол и экспериментальная валидация
            </p>
          </div>
        </div>

        {/* Global Navigation Tabs */}
        <div className="flex items-center bg-slate-900 border border-slate-800 rounded-lg p-1">
          <button
            onClick={() => onTabChange('monitoring')}
            className={`px-3.5 py-1.5 text-xs font-medium rounded-md transition-all ${
              activeTab === 'monitoring'
                ? 'bg-slate-800 text-slate-100 shadow-sm'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Мониторинг AHU
          </button>
          <button
            onClick={() => onTabChange('diagnostics')}
            className={`px-3.5 py-1.5 text-xs font-medium rounded-md transition-all ${
              activeTab === 'diagnostics'
                ? 'bg-indigo-600 text-white shadow-sm'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Диагностика
          </button>
          <button
            onClick={() => onTabChange('research')}
            className={`px-3.5 py-1.5 text-xs font-medium rounded-md transition-all ${
              activeTab === 'research'
                ? 'bg-emerald-600 text-white shadow-sm'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Исследования
          </button>
        </div>
      </header>

      {/* Sub-header Navigation */}
      <div className="border-b border-slate-800 bg-slate-950/40 px-6 py-2 flex items-center justify-between">
        <div className="flex space-x-2">
          {[
            { id: 'overview', label: '1. Обзор гипотез (H1–H4)' },
            { id: 'risk_coverage', label: '2. Селективный риск (Risk–Coverage)' },
            { id: 'observability', label: '3. Профили наблюдаемости' },
            { id: 'recommender', label: '4. Рекомендатель датчиков (H3)' },
            { id: 'real_building', label: '5. Реальное здание и адаптация (CSIRO)' }
          ].map(tab => (
            <button
              key={tab.id}
              onClick={() => setInternalTab(tab.id as any)}
              className={`px-3 py-1 text-xs font-medium rounded-md transition-colors ${
                internalTab === tab.id
                  ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
        <div className="text-[11px] text-slate-400">
          Независимых тестовых сценариев: <span className="font-semibold text-slate-200">N=7</span>
        </div>
      </div>

      {/* Main Content Area */}
      <main className="flex-1 p-6 max-w-7xl mx-auto w-full space-y-6">
        {loading ? (
          <div className="flex items-center justify-center p-20 text-slate-400 text-sm">
            Загрузка научных протоколов и манифестов запусков...
          </div>
        ) : (
          <>
            {/* TAB 1: OVERVIEW */}
            {internalTab === 'overview' && (
              <div className="space-y-6">
                <div className="bg-slate-950 border border-slate-800 rounded-xl p-5 space-y-4">
                  <h2 className="text-base font-semibold text-slate-100 flex items-center justify-between">
                    <span>Сводная матрица научных гипотез и результатов (Stage 1–5)</span>
                    <span className="text-xs font-normal text-slate-400">Воспроизводимые запуски research/runs/</span>
                  </h2>

                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs border-collapse">
                      <thead>
                        <tr className="border-b border-slate-800 text-slate-400">
                          <th className="py-2.5 px-3">Гипотеза</th>
                          <th className="py-2.5 px-3">Предмет исследования</th>
                          <th className="py-2.5 px-3">Методика проверки</th>
                          <th className="py-2.5 px-3">Ключевой числовой результат</th>
                          <th className="py-2.5 px-3">Статус</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-800/60">
                        <tr className="hover:bg-slate-900/50">
                          <td className="py-3 px-3 font-semibold text-slate-200">H1: Decision Layer</td>
                          <td className="py-3 px-3 text-slate-300">Снижение селективного риска при отказе от необоснованных одиночных диагнозов</td>
                          <td className="py-3 px-3 text-slate-400">Сравнение M с бейзлайнами B1/B2 на одинаковом Basic профиле</td>
                          <td className="py-3 px-3 text-emerald-400 font-mono">
                            При Coverage 0.40: Risk снижен с 0.556 до 0.294 (-47.1% ошибки)
                          </td>
                          <td className="py-3 px-3">
                            <span className="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 text-[10px] font-semibold">
                              SUPPORTED_WITH_LIMITATIONS
                            </span>
                          </td>
                        </tr>
                        <tr className="hover:bg-slate-900/50">
                          <td className="py-3 px-3 font-semibold text-slate-200">H2: Ценность канала</td>
                          <td className="py-3 px-3 text-slate-300">Прирост Macro F1 при добавлении обратной связи клапана охладителя</td>
                          <td className="py-3 px-3 text-slate-400">5 профилей наблюдаемости при одинаковом классификаторе</td>
                          <td className="py-3 px-3 text-emerald-400 font-mono">
                            Macro F1: 0.5196 → 0.6722 (+15.26 п.п., +29.4% к Basic)
                          </td>
                          <td className="py-3 px-3">
                            <span className="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 text-[10px] font-semibold">
                              SUPPORTED_WITH_LIMITATIONS
                            </span>
                          </td>
                        </tr>
                        <tr className="hover:bg-slate-900/50">
                          <td className="py-3 px-3 font-semibold text-slate-200">H3: Recommender</td>
                          <td className="py-3 px-3 text-slate-300">Выбор дополнительного канала на validation превосходит Random и Fixed</td>
                          <td className="py-3 px-3 text-slate-400">Отложенные сценарии N=7, одинаковый бюджет 1 канал</td>
                          <td className="py-3 px-3 text-emerald-400 font-mono">
                            Validation-based (0.6722) превосходит Random (0.5931, +7.91 п.п.)
                          </td>
                          <td className="py-3 px-3">
                            <span className="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 text-[10px] font-semibold">
                              SUPPORTED_WITH_LIMITATIONS
                            </span>
                          </td>
                        </tr>
                        <tr className="hover:bg-slate-900/50">
                          <td className="py-3 px-3 font-semibold text-slate-200">Внешний перенос</td>
                          <td className="py-3 px-3 text-slate-300">Прямой перенос тепловой модели со симуляции на реальное здание CSIRO</td>
                          <td className="py-3 px-3 text-slate-400">Zero-shot инференс на реальной BMS в Ньюкасле (Австралия)</td>
                          <td className="py-3 px-3 text-amber-400 font-mono">
                            MAE возрастает с 0.039°C до 4.47°C (98.6% ложных тревог)
                          </td>
                          <td className="py-3 px-3">
                            <span className="px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 text-[10px] font-semibold">
                              PROVED_NEGATIVE_RESULT
                            </span>
                          </td>
                        </tr>
                        <tr className="hover:bg-slate-900/50">
                          <td className="py-3 px-3 font-semibold text-slate-200">H4: Локальная адаптация</td>
                          <td className="py-3 px-3 text-slate-300">Адаптация модели LBNL на чистых данных CSIRO снижает MAE и ложные тревоги</td>
                          <td className="py-3 px-3 text-slate-400">Held-Out Test N=1,074 чистых точек, сравнение Z0 vs C1/C2/A1/L1/L2</td>
                          <td className="py-3 px-3 text-emerald-400 font-mono">
                            MAE: 4.46°C → 1.11°C (-75.2%), ложные тревоги: 100% → 2.8%
                          </td>
                          <td className="py-3 px-3">
                            <span className="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 text-[10px] font-semibold">
                              CONFIRMED_HELDOUT
                            </span>
                          </td>
                        </tr>
                      </tbody>
                    </table>
                  </div>

                  <div className="p-3.5 bg-slate-900/60 border border-slate-800 rounded-lg text-xs text-slate-400 space-y-1">
                    <div className="font-semibold text-slate-300">Академический дисклеймер протокола:</div>
                    <p>
                      Все численные значения получены исполняемыми раннерами на стандартизированных срезах отложенных сценариев (Held-Out Test).
                      Статус <span className="text-emerald-300 font-semibold">SUPPORTED_WITH_LIMITATIONS</span> отражает подтверждение эффекта
                      в контролируемых условиях симуляционного бенчмарка при явном указании ограниченного числа независимых сценариев (N=7).
                    </p>
                  </div>
                </div>
              </div>
            )}

            {/* TAB 2: RISK-COVERAGE */}
            {internalTab === 'risk_coverage' && (
              <div className="space-y-6">
                <div className="bg-slate-950 border border-slate-800 rounded-xl p-5 space-y-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <h2 className="text-base font-semibold text-slate-100">
                        Кривые селективного риска (Selective Risk vs. Coverage)
                      </h2>
                      <p className="text-xs text-slate-400">
                        Честное сравнение стратегий отказа на одинаковом профиле телеметрии
                      </p>
                    </div>
                    <div className="flex items-center space-x-2">
                      <span className="text-xs text-slate-400">Профиль:</span>
                      <button
                        onClick={() => setRcProfile('BASIC')}
                        className={`px-3 py-1 text-xs rounded font-medium transition-all ${
                          rcProfile === 'BASIC'
                            ? 'bg-emerald-600 text-white'
                            : 'bg-slate-900 text-slate-400 border border-slate-800'
                        }`}
                      >
                        Basic (19 каналов)
                      </button>
                      <button
                        onClick={() => setRcProfile('BASIC_PLUS_VALVE')}
                        className={`px-3 py-1 text-xs rounded font-medium transition-all ${
                          rcProfile === 'BASIC_PLUS_VALVE'
                            ? 'bg-indigo-600 text-white'
                            : 'bg-slate-900 text-slate-400 border border-slate-800'
                        }`}
                      >
                        Basic + Valve Feedback
                      </button>
                    </div>
                  </div>

                  {rcProfile === 'BASIC' ? (
                    <div className="space-y-4">
                      <div className="overflow-x-auto">
                        <table className="w-full text-left text-xs border-collapse">
                          <thead>
                            <tr className="border-b border-slate-800 text-slate-400">
                              <th className="py-2 px-3">Целевой Coverage c</th>
                              <th className="py-2 px-3">B1: Confidence-Only Risk</th>
                              <th className="py-2 px-3">B2: Margin/Entropy Risk</th>
                              <th className="py-2 px-3">M: Decision Layer Risk</th>
                              <th className="py-2 px-3">Снижение риска ошибки</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-slate-800/60 font-mono">
                            <tr>
                              <td className="py-2.5 px-3 text-slate-200">0.40</td>
                              <td className="py-2.5 px-3 text-slate-400">0.556 (cov=0.46)</td>
                              <td className="py-2.5 px-3 text-slate-400">0.554 (cov=0.61)</td>
                              <td className="py-2.5 px-3 text-emerald-400 font-bold">0.294 (cov=0.42)</td>
                              <td className="py-2.5 px-3 text-emerald-400">-47.1% риска</td>
                            </tr>
                            <tr>
                              <td className="py-2.5 px-3 text-slate-200">0.60</td>
                              <td className="py-2.5 px-3 text-slate-400">0.547 (cov=0.61)</td>
                              <td className="py-2.5 px-3 text-slate-400">0.554 (cov=0.61)</td>
                              <td className="py-2.5 px-3 text-emerald-400 font-bold">0.361 (cov=0.60)</td>
                              <td className="py-2.5 px-3 text-emerald-400">-34.0% риска</td>
                            </tr>
                            <tr>
                              <td className="py-2.5 px-3 text-slate-200">0.80</td>
                              <td className="py-2.5 px-3 text-slate-400">0.540 (cov=0.81)</td>
                              <td className="py-2.5 px-3 text-slate-400">0.518 (cov=0.80)</td>
                              <td className="py-2.5 px-3 text-amber-400">0.362 (cov=0.60)</td>
                              <td className="py-2.5 px-3 text-slate-400">Физический предел Basic</td>
                            </tr>
                          </tbody>
                        </table>
                      </div>
                      <div className="text-xs text-slate-400 p-3 bg-slate-900 border border-slate-800 rounded-lg">
                        <strong>Физический предел охвата на Basic (60.23%):</strong> При отсутствии датчика штока $CHWC\_VLV$ Decision Layer
                        отказывается принудительно угадывать класс между заклиниванием клапана и смещением датчика при близких скорах,
                        сохраняя 28.6% UNRESOLVED и 11.2% MULTIPLE_PLAUSIBLE.
                      </div>
                    </div>
                  ) : (
                    <div className="space-y-4">
                      <div className="overflow-x-auto">
                        <table className="w-full text-left text-xs border-collapse">
                          <thead>
                            <tr className="border-b border-slate-800 text-slate-400">
                              <th className="py-2 px-3">Целевой Coverage c</th>
                              <th className="py-2 px-3">B1: Confidence-Only (+Valve)</th>
                              <th className="py-2 px-3">B2: Margin/Entropy (+Valve)</th>
                              <th className="py-2 px-3">M: Decision Layer (+Valve)</th>
                              <th className="py-2 px-3">Снижение риска ошибки</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-slate-800/60 font-mono">
                            <tr>
                              <td className="py-2.5 px-3 text-slate-200">0.40</td>
                              <td className="py-2.5 px-3 text-slate-400">0.291 (cov=0.60)</td>
                              <td className="py-2.5 px-3 text-slate-400">0.363 (cov=0.85)</td>
                              <td className="py-2.5 px-3 text-emerald-400 font-bold">0.063 (cov=0.45)</td>
                              <td className="py-2.5 px-3 text-emerald-400">-78.4% риска</td>
                            </tr>
                            <tr>
                              <td className="py-2.5 px-3 text-slate-200">0.60</td>
                              <td className="py-2.5 px-3 text-slate-400">0.291 (cov=0.60)</td>
                              <td className="py-2.5 px-3 text-slate-400">0.363 (cov=0.85)</td>
                              <td className="py-2.5 px-3 text-emerald-400 font-bold">0.158 (cov=0.60)</td>
                              <td className="py-2.5 px-3 text-emerald-400">-45.7% риска</td>
                            </tr>
                            <tr>
                              <td className="py-2.5 px-3 text-slate-200">0.80</td>
                              <td className="py-2.5 px-3 text-slate-400">0.367 (cov=0.80)</td>
                              <td className="py-2.5 px-3 text-slate-400">0.363 (cov=0.85)</td>
                              <td className="py-2.5 px-3 text-emerald-400 font-bold">0.217 (cov=0.76)</td>
                              <td className="py-2.5 px-3 text-emerald-400">-40.9% риска</td>
                            </tr>
                          </tbody>
                        </table>
                      </div>
                      <div className="text-xs text-slate-400 p-3 bg-slate-900 border border-slate-800 rounded-lg">
                        <strong>Эффект устранения неоднозначности:</strong> При наличии $CHWC\_VLV$ Decision Layer безошибочно изолирует
                        заклинивание клапана, снижая риск ошибки при охвате 0.60 до 0.158 против 0.291 у бейзлайна доверия.
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* TAB 3: OBSERVABILITY PROFILES */}
            {internalTab === 'observability' && (
              <div className="space-y-6">
                <div className="bg-slate-950 border border-slate-800 rounded-xl p-5 space-y-4">
                  <h2 className="text-base font-semibold text-slate-100">
                    Сравнение 5 профилей наблюдаемости датчиков (E4.2)
                  </h2>
                  <p className="text-xs text-slate-400">
                    Оценка Macro F1 классификатора на отложенных независимых уровнях дефектов (Held-out Test)
                  </p>

                  <div className="grid grid-cols-1 md:grid-cols-5 gap-3">
                    {[
                      { id: 'BASIC', name: 'Basic BMS', feats: 11, f1: '0.5196', gain: '0.00', color: 'border-slate-700 bg-slate-900/50' },
                      { id: 'BASIC_PLUS_VALVE', name: '+ Valve Feedback', feats: 14, f1: '0.6722', gain: '+15.26 п.п.', color: 'border-emerald-500/40 bg-emerald-500/10 text-emerald-300' },
                      { id: 'BASIC_PLUS_DAMPER', name: '+ Damper Feedback', feats: 14, f1: '0.5123', gain: '-0.73 п.п.', color: 'border-slate-800 bg-slate-900/30' },
                      { id: 'BASIC_PLUS_BOTH', name: '+ Both Actuators', feats: 17, f1: '0.6755', gain: '+15.59 п.п.', color: 'border-indigo-500/40 bg-indigo-500/10' },
                      { id: 'FULL', name: 'Full Lab Observability', feats: 19, f1: '0.6766', gain: '+15.70 п.п.', color: 'border-cyan-500/40 bg-cyan-500/10' }
                    ].map(p => (
                      <div key={p.id} className={`p-4 rounded-xl border ${p.color} flex flex-col justify-between`}>
                        <div>
                          <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">{p.name}</div>
                          <div className="text-2xl font-bold font-mono mt-1 text-slate-100">{p.f1}</div>
                          <div className="text-[11px] text-slate-400 mt-1">{p.feats} признаков</div>
                        </div>
                        <div className="mt-3 pt-2 border-t border-slate-800 text-[11px] font-semibold">
                          ΔF1: <span className="font-mono">{p.gain}</span>
                        </div>
                      </div>
                    ))}
                  </div>

                  <div className="text-xs text-slate-400 p-4 bg-slate-900/60 border border-slate-800 rounded-xl space-y-2">
                    <div className="font-semibold text-slate-200">Научные выводы по наблюдаемости:</div>
                    <ul className="list-disc list-inside space-y-1 text-slate-400">
                      <li>
                        <strong>Датчик штока клапана охлаждения (CHWC_VLV)</strong> обеспечивает основной скачок качества:
                        Macro F1 возрастает с 0.5196 до 0.6722 (+15.26 процентных пунктов, +29.4% относительно Basic).
                        F1 заклинивания клапана достигает 0.9996, а F1 температурного смещения датчика притока вырастает в 2.86 раза.
                      </li>
                      <li>
                        <strong>Датчик заслонки (OA_DMPR)</strong> повышает детекцию дефектов заслонки (F1 до 0.7764),
                        но не устраняет основную неопределенность контура теплообмена, давая интегральный Macro F1 = 0.5123.
                      </li>
                      <li>
                        <strong>Полный лабораторный набор (FULL)</strong> даёт Macro F1 = 0.6766, что лишь незначительно превосходит
                        Basic + Valve (+0.44 п.п.), подтверждая принцип достаточности свидетельств: 1 ключевой датчик даёт 97% возможного эффекта.
                      </li>
                    </ul>
                  </div>
                </div>
              </div>
            )}

            {/* TAB 4: RECOMMENDER (H3) */}
            {internalTab === 'recommender' && (
              <div className="space-y-6">
                {/* Strategy Summary Table */}
                <div className="bg-slate-950 border border-slate-800 rounded-xl p-5 space-y-4">
                  <h2 className="text-base font-semibold text-slate-100 flex items-center justify-between">
                    <span>Сравнение стратегий выбора измерения (Эксперимент H3)</span>
                    <span className="text-xs font-normal text-slate-400 font-mono">Бюджет: 1 дополнительный канал</span>
                  </h2>

                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs border-collapse">
                      <thead>
                        <tr className="border-b border-slate-800 text-slate-400">
                          <th className="py-2.5 px-3">Стратегия выбора</th>
                          <th className="py-2.5 px-3">Выбранный канал</th>
                          <th className="py-2.5 px-3">Macro F1 на Held-Out</th>
                          <th className="py-2.5 px-3">Прирост к Basic</th>
                          <th className="py-2.5 px-3">Прирост к Random</th>
                          <th className="py-2.5 px-3">Статистическая оценка</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-800/60 font-mono">
                        <tr>
                          <td className="py-3 px-3 text-slate-300">0. Baseline (BASIC 19 ch)</td>
                          <td className="py-3 px-3 text-slate-400">—</td>
                          <td className="py-3 px-3 text-slate-200">0.5196</td>
                          <td className="py-3 px-3 text-slate-400">—</td>
                          <td className="py-3 px-3 text-slate-400">—</td>
                          <td className="py-3 px-3 text-slate-400">Исходная базовая линия</td>
                        </tr>
                        <tr>
                          <td className="py-3 px-3 text-slate-300">1. Random Strategy (p=0.5)</td>
                          <td className="py-3 px-3 text-slate-400">50% Valve, 50% Damper</td>
                          <td className="py-3 px-3 text-amber-300">0.5931 ± 0.0015</td>
                          <td className="py-3 px-3 text-amber-400">+7.35 п.п.</td>
                          <td className="py-3 px-3 text-slate-400">—</td>
                          <td className="py-3 px-3 text-slate-400">5 seeds (42, 123, 456, 789, 999)</td>
                        </tr>
                        <tr>
                          <td className="py-3 px-3 text-slate-300">2. Fixed Strategy</td>
                          <td className="py-3 px-3 text-indigo-300 font-semibold">CHWC_VLV</td>
                          <td className="py-3 px-3 text-emerald-400 font-bold">0.6722</td>
                          <td className="py-3 px-3 text-emerald-400">+15.26 п.п.</td>
                          <td className="py-3 px-3 text-emerald-400">+7.91 п.п.</td>
                          <td className="py-3 px-3 text-slate-400">Априорная эвристика</td>
                        </tr>
                        <tr className="bg-emerald-500/5">
                          <td className="py-3 px-3 font-semibold text-emerald-300">3. Validation-Based (Recommender)</td>
                          <td className="py-3 px-3 text-emerald-300 font-semibold">CHWC_VLV</td>
                          <td className="py-3 px-3 text-emerald-400 font-bold">0.6722</td>
                          <td className="py-3 px-3 text-emerald-400">+15.26 п.п.</td>
                          <td className="py-3 px-3 text-emerald-400 font-bold">+7.91 п.п.</td>
                          <td className="py-3 px-3 text-emerald-300 font-semibold">p &lt; 0.05 vs. Random</td>
                        </tr>
                        <tr className="text-slate-500">
                          <td className="py-3 px-3">4. Infeasible Oracle (Upper Bound)</td>
                          <td className="py-3 px-3">Best per scenario</td>
                          <td className="py-3 px-3">0.6969</td>
                          <td className="py-3 px-3">+17.73 п.п.</td>
                          <td className="py-3 px-3">+10.38 п.п.</td>
                          <td className="py-3 px-3 text-amber-500">Недостижимый чит (запрещён)</td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </div>

                {/* Interactive Simulator */}
                <div className="bg-slate-950 border border-slate-800 rounded-xl p-5 space-y-4">
                  <h3 className="text-sm font-semibold text-slate-100 flex items-center justify-between">
                    <span>Интерактивный симулятор Recommendation Engine</span>
                    <span className="text-xs text-slate-400 font-normal">Эмпирическая оценка на валидационных сценариях</span>
                  </h3>

                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div>
                      <label className="text-xs text-slate-400 block mb-1">Активный профиль наблюдаемости:</label>
                      <select
                        value={testProfile}
                        onChange={(e) => setTestProfile(e.target.value)}
                        className="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-emerald-500"
                      >
                        <option value="BASIC">BASIC (19 каналов BMS)</option>
                        <option value="BASIC_PLUS_VALVE">BASIC_PLUS_VALVE (с клапаном)</option>
                        <option value="BASIC_PLUS_DAMPER">BASIC_PLUS_DAMPER (с заслонкой)</option>
                        <option value="BASIC_PLUS_BOTH">BASIC_PLUS_BOTH (оба привода)</option>
                      </select>
                    </div>

                    <div>
                      <label className="text-xs text-slate-400 block mb-1">Целевой селективный охват (Coverage c):</label>
                      <select
                        value={testCoverage}
                        onChange={(e) => setTestCoverage(parseFloat(e.target.value))}
                        className="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-emerald-500"
                      >
                        <option value={0.40}>0.40 (консервативный режим)</option>
                        <option value={0.60}>0.60 (рекомендуемый предел Basic)</option>
                        <option value={0.80}>0.80 (расширенный охват)</option>
                      </select>
                    </div>

                    <div className="flex items-end">
                      <button
                        onClick={handleRunRecommender}
                        disabled={recLoading}
                        className="w-full bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white font-medium text-xs px-4 py-2.5 rounded-lg transition-all"
                      >
                        {recLoading ? 'Расчёт ценности каналов...' : 'Какое измерение поможет?'}
                      </button>
                    </div>
                  </div>

                  {recResult && (
                    <div className="mt-4 p-4 rounded-xl border border-slate-800 bg-slate-900/60 space-y-3">
                      <div className="flex items-center justify-between">
                        <div className="text-xs font-semibold text-slate-200 flex items-center space-x-2">
                          <span>Статус:</span>
                          <span className={`px-2 py-0.5 rounded text-[11px] font-bold ${
                            recResult.status === 'RECOMMENDED'
                              ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                              : 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                          }`}>
                            {recResult.status}
                          </span>
                        </div>
                        {recResult.recommended_channel && (
                          <div className="text-xs font-mono font-bold text-emerald-400">
                            Рекомендован: {recResult.recommended_channel}
                          </div>
                        )}
                      </div>

                      <p className="text-xs text-slate-300">{recResult.reason}</p>

                      {recResult.candidate_scores.length > 0 && (
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-2">
                          {recResult.candidate_scores.map(cand => (
                            <div key={cand.channel} className="p-3 bg-slate-950 border border-slate-800 rounded-lg space-y-1.5">
                              <div className="flex items-center justify-between">
                                <span className="font-semibold text-xs text-slate-200">{cand.channel}</span>
                                <span className="text-[10px] font-mono px-1.5 py-0.5 bg-slate-800 rounded text-slate-300">
                                  {cand.decision}
                                </span>
                              </div>
                              <div className="text-[11px] text-emerald-400 font-mono">
                                ΔSelectiveRisk: -{(cand.delta_selective_risk_validation || 0) * 100}% (при cov={cand.coverage_actual})
                              </div>
                              <p className="text-[11px] text-slate-400">{cand.reason}</p>
                            </div>
                          ))}
                        </div>
                      )}

                      {recResult.limitations.length > 0 && (
                        <div className="pt-2 text-[11px] text-slate-400 border-t border-slate-800/80 space-y-0.5">
                          <span className="font-semibold text-slate-300">Ограничения:</span>
                          {recResult.limitations.map((lim, i) => (
                            <div key={i}>• {lim}</div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* TAB 5: REAL BUILDING (CSIRO) & ADAPTATION */}
            {internalTab === 'real_building' && (
              <div className="space-y-6">
                {/* Sub-tab Navigation */}
                <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                  <div className="flex space-x-2">
                    <button
                      onClick={() => setRealBuildingSubTab('adaptation')}
                      className={`px-4 py-2 text-xs font-semibold rounded-lg transition-all ${
                        realBuildingSubTab === 'adaptation'
                          ? 'bg-emerald-600 text-white shadow-md'
                          : 'bg-slate-900 text-slate-400 hover:text-slate-200 border border-slate-800'
                      }`}
                    >
                      🚀 Локальная адаптация моделей (Stage 6)
                    </button>
                    <button
                      onClick={() => setRealBuildingSubTab('audit')}
                      className={`px-4 py-2 text-xs font-semibold rounded-lg transition-all ${
                        realBuildingSubTab === 'audit'
                          ? 'bg-slate-800 text-slate-100 shadow-md border border-slate-700'
                          : 'bg-slate-900 text-slate-400 hover:text-slate-200 border border-slate-800'
                      }`}
                    >
                      ⚠️ Исходный аудит прямого переноса (Stage 5)
                    </button>
                  </div>

                  <div className="flex items-center space-x-2">
                    <span className="text-[11px] text-slate-400 font-mono">Объект:</span>
                    <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                      CSIRO AHU9 (Energy Centre, Newcastle)
                    </span>
                  </div>
                </div>

                {/* SUBTAB 1: STAGE 6 ADAPTATION */}
                {realBuildingSubTab === 'adaptation' && (
                  <div className="space-y-6">
                    {/* Control & Model Selector Header */}
                    <div className="bg-slate-950 border border-slate-800 rounded-xl p-5 space-y-4">
                      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                        <div>
                          <div className="flex items-center space-x-2">
                            <h2 className="text-base font-semibold text-slate-100">
                              Результаты адаптации к реальному зданию CSIRO AHU9
                            </h2>
                            <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30">
                              REAL_FIELD_BMS
                            </span>
                            <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                              selectedAdaptModelId === 'vs-sa-temp-v2'
                                ? 'bg-rose-500/20 text-rose-300 border border-rose-500/30'
                                : 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                            }`}>
                              {selectedAdaptModelId === 'vs-sa-temp-v2' ? 'OUT_OF_DOMAIN_UNVALIDATED' : 'LOCALLY_EVALUATED'}
                            </span>
                          </div>
                          <p className="text-xs text-slate-400 mt-1">
                            Оценка выполнена на строго отложенном независимом тесте (2013-11-07 — 2013-11-12, 1 074 чистых точек)
                          </p>
                        </div>

                        {/* Model Dropdown */}
                        <div className="flex items-center space-x-3">
                          <label className="text-xs text-slate-400 font-medium whitespace-nowrap">Модель:</label>
                          <select
                            value={selectedAdaptModelId}
                            onChange={(e) => setSelectedAdaptModelId(e.target.value)}
                            className="bg-slate-900 border border-slate-700 text-xs text-slate-200 rounded-lg px-3 py-2 font-medium focus:outline-none focus:border-emerald-500"
                          >
                            {adaptModels && adaptModels.length > 0 ? (
                              adaptModels.map(m => (
                                <option key={m.model_id} value={m.model_id}>
                                  {m.strategy_code}: {m.name} {m.strategy_code === 'C2' ? '[Рекомендована, -75.2% MAE]' : ''}
                                </option>
                              ))
                            ) : (
                              <>
                                <option value="csiro-ahu9-affine-v1">C2: Affine Calibrator (y = 2.01x - 10.11) [Рекомендована, -75.2% MAE]</option>
                                <option value="csiro-ahu9-bias-v1">C1: Constant Bias (+4.59°C) [-73.0% MAE]</option>
                                <option value="csiro-ahu9-local-lgbm-v1">L2: Local LightGBM (depth=3) [-71.5% MAE]</option>
                                <option value="csiro-ahu9-residual-ridge-v1">A1: Residual Ridge (Source + Ridge) [-58.9% MAE]</option>
                                <option value="csiro-ahu9-local-ridge-v1">L1: Local Ridge (с нуля без LBNL) [-33.1% MAE]</option>
                                <option value="vs-sa-temp-v2">Z0: Исходная LBNL Zero-Shot (без адаптации)</option>
                              </>
                            )}
                          </select>
                        </div>
                      </div>

                      {/* Top 4 Metric Cards */}
                      {adaptSummary && (
                        <div className="grid grid-cols-1 md:grid-cols-4 gap-3 pt-2">
                          {(() => {
                            const curRow = adaptSummary.models_comparison.find(m => {
                              if (selectedAdaptModelId === 'vs-sa-temp-v2') return m.strategy_code === 'Z0';
                              if (selectedAdaptModelId === 'csiro-ahu9-bias-v1') return m.strategy_code === 'C1';
                              if (selectedAdaptModelId === 'csiro-ahu9-affine-v1') return m.strategy_code === 'C2';
                              if (selectedAdaptModelId === 'csiro-ahu9-residual-ridge-v1') return m.strategy_code === 'A1';
                              if (selectedAdaptModelId === 'csiro-ahu9-local-ridge-v1') return m.strategy_code === 'L1';
                              if (selectedAdaptModelId === 'csiro-ahu9-local-lgbm-v1') return m.strategy_code === 'L2';
                              return m.strategy_code === 'C2';
                            }) || adaptSummary.models_comparison[3];

                            const z0Row = adaptSummary.models_comparison.find(m => m.strategy_code === 'Z0')!;
                            const maeDelta = z0Row.mae_degC && curRow.mae_degC
                              ? (((curRow.mae_degC - z0Row.mae_degC) / z0Row.mae_degC) * 100).toFixed(1)
                              : '0';

                            return (
                              <>
                                <div className="p-4 bg-slate-900 border border-slate-800 rounded-xl space-y-1">
                                  <div className="text-[11px] text-slate-400 uppercase font-semibold">MAE ошибки теста</div>
                                  <div className="text-2xl font-bold font-mono text-emerald-400">
                                    {curRow.mae_degC?.toFixed(2)} °C
                                  </div>
                                  <div className="text-[11px] font-semibold text-emerald-400">
                                    {parseFloat(maeDelta) < 0 ? `${maeDelta}% к LBNL Z0` : 'Исходный бейзлайн'}
                                  </div>
                                </div>

                                <div className="p-4 bg-slate-900 border border-slate-800 rounded-xl space-y-1">
                                  <div className="text-[11px] text-slate-400 uppercase font-semibold">RMSE ошибки теста</div>
                                  <div className="text-2xl font-bold font-mono text-slate-200">
                                    {curRow.rmse_degC?.toFixed(2)} °C
                                  </div>
                                  <div className="text-[11px] text-slate-400">
                                    vs. {z0Row.rmse_degC?.toFixed(2)} °C на LBNL Z0
                                  </div>
                                </div>

                                <div className="p-4 bg-slate-900 border border-slate-800 rounded-xl space-y-1">
                                  <div className="text-[11px] text-slate-400 uppercase font-semibold">Систематический сдвиг (Bias)</div>
                                  <div className={`text-2xl font-bold font-mono ${
                                    Math.abs(curRow.mean_bias_degC || 0) < 0.5 ? 'text-emerald-400' : 'text-amber-400'
                                  }`}>
                                    {(curRow.mean_bias_degC ?? 0) > 0 ? '+' : ''}{curRow.mean_bias_degC?.toFixed(2)} °C
                                  </div>
                                  <div className="text-[11px] text-slate-400">
                                    vs. +{z0Row.mean_bias_degC?.toFixed(2)} °C на LBNL Z0
                                  </div>
                                </div>

                                <div className="p-4 bg-slate-900 border border-slate-800 rounded-xl space-y-1">
                                  <div className="text-[11px] text-slate-400 uppercase font-semibold">Ложные тревоги в норме (3σ)</div>
                                  <div className={`text-2xl font-bold font-mono ${
                                    (curRow.false_alarm_rate_pct || 0) <= 5.0 ? 'text-emerald-400' : 'text-rose-400'
                                  }`}>
                                    {curRow.false_alarm_rate_pct?.toFixed(1)}%
                                  </div>
                                  <div className="text-[11px] font-semibold text-emerald-400">
                                    {(curRow.false_alarm_rate_pct || 0) <= 5.0 ? '✓ Бюджет ≤ 5% соблюден' : 'Превышение бюджета'}
                                  </div>
                                </div>
                              </>
                            );
                          })()}
                        </div>
                      )}

                      {/* Domain Guard Notice Box */}
                      <div className="p-3.5 bg-slate-900/60 border border-slate-800 rounded-lg flex flex-col md:flex-row md:items-center justify-between text-xs text-slate-300 gap-3">
                        <div className="space-y-0.5">
                          <span className="font-semibold text-emerald-400 flex items-center space-x-1.5">
                            <span>🛡️ Доменный барьер Domain Guard активен:</span>
                          </span>
                          <p className="text-slate-400 text-[11px]">
                            Адаптированная модель допущена к регрессионной оценке температуры на AHU9 со статусом <code className="text-emerald-300">LOCALLY_EVALUATED</code>. Выдача автоматических аварийных диагнозов без подтверждения классификатора причин заблокирована.
                          </p>
                        </div>
                        <div className="flex items-center space-x-2 shrink-0">
                          <button
                            onClick={() => setAllowUnvalidatedAdapt(!allowUnvalidatedAdapt)}
                            className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-all ${
                              allowUnvalidatedAdapt
                                ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                                : 'bg-slate-800 text-slate-400 hover:text-slate-200 border border-slate-700'
                            }`}
                          >
                            {allowUnvalidatedAdapt ? 'Режим исследователя ВКЛ' : 'Включить режим исследователя'}
                          </button>
                        </div>
                      </div>
                    </div>

                    {/* Interactive Prediction Time Series Chart */}
                    <div className="bg-slate-950 border border-slate-800 rounded-xl p-5 space-y-3">
                      <div className="flex items-center justify-between">
                        <div>
                          <h3 className="text-sm font-semibold text-slate-100 flex items-center space-x-2">
                            <span>Временной ряд отложенного теста: Факт vs Zero-Shot vs Адаптация</span>
                            {adaptLoading && <span className="text-xs text-emerald-400 animate-pulse">(обновление...)</span>}
                          </h3>
                          <p className="text-xs text-slate-400">
                            Период независимого теста 07.11.2013 — 12.11.2013 (оранжевым выделены подтвержденные окна инъекций неисправностей)
                          </p>
                        </div>
                        <div className="flex items-center space-x-4 text-xs font-mono">
                          <span className="flex items-center space-x-1.5">
                            <span className="w-3 h-0.5 bg-[#38bdf8] inline-block"></span>
                            <span className="text-slate-300">Факт SA_TEMP</span>
                          </span>
                          <span className="flex items-center space-x-1.5">
                            <span className="w-3 h-0.5 bg-[#f43f5e] inline-block border-dashed"></span>
                            <span className="text-slate-300">LBNL Zero-Shot (Z0)</span>
                          </span>
                          <span className="flex items-center space-x-1.5">
                            <span className="w-3 h-0.5 bg-[#10b981] inline-block"></span>
                            <span className="text-emerald-400 font-semibold">Адаптированный прогноз</span>
                          </span>
                        </div>
                      </div>

                      {adaptPredictions && adaptPredictions.points.length > 0 ? (
                        <div className="h-80 w-full">
                          <ReactECharts
                            option={{
                              backgroundColor: 'transparent',
                              tooltip: {
                                trigger: 'axis',
                                backgroundColor: '#0f172a',
                                borderColor: '#334155',
                                textStyle: { color: '#e2e8f0', fontSize: 11 },
                                formatter: (params: any) => {
                                  if (!params || params.length === 0) return '';
                                  const p0 = params[0];
                                  let res = `<div class="font-bold text-slate-300 mb-1">${p0.axisValue}</div>`;
                                  params.forEach((item: any) => {
                                    res += `<div class="flex items-center justify-between space-x-3 text-xs">
                                      <span style="color:${item.color}">${item.seriesName}:</span>
                                      <span class="font-mono font-bold">${item.value !== null ? item.value.toFixed(2) + ' °C' : 'N/A'}</span>
                                    </div>`;
                                  });
                                  return res;
                                }
                              },
                              grid: {
                                top: 25,
                                right: 20,
                                bottom: 35,
                                left: 45
                              },
                              xAxis: {
                                type: 'category',
                                data: adaptPredictions.points.map(p => p.datetime),
                                axisLine: { lineStyle: { color: '#334155' } },
                                axisLabel: {
                                  color: '#94a3b8',
                                  fontSize: 10,
                                  formatter: (v: string) => v.split(' ')[0].slice(5) + ' ' + v.split(' ')[1]?.slice(0, 5)
                                }
                              },
                              yAxis: {
                                type: 'value',
                                name: '°C',
                                min: 10,
                                max: 26,
                                axisLine: { lineStyle: { color: '#334155' } },
                                axisLabel: { color: '#94a3b8', fontSize: 10 },
                                splitLine: { lineStyle: { color: '#1e293b' } }
                              },
                              series: [
                                {
                                  name: 'Факт SA_TEMP',
                                  type: 'line',
                                  data: adaptPredictions.points.map(p => p.actual_sa_temp),
                                  lineStyle: { color: '#38bdf8', width: 2 },
                                  itemStyle: { color: '#38bdf8' },
                                  connectNulls: false,
                                  showSymbol: false,
                                  markArea: faultMarkAreas.length > 0 ? {
                                    itemStyle: { color: 'rgba(249, 115, 22, 0.20)' },
                                    label: {
                                      show: true,
                                      position: 'insideTop',
                                      color: '#fb923c',
                                      fontSize: 9,
                                      formatter: 'Инъекция'
                                    },
                                    data: faultMarkAreas
                                  } : undefined
                                },
                                {
                                  name: 'LBNL Zero-Shot (Z0)',
                                  type: 'line',
                                  data: adaptPredictions.points.map(p => p.source_pred_sa_temp),
                                  lineStyle: { color: '#f43f5e', width: 1.5, type: 'dashed' },
                                  itemStyle: { color: '#f43f5e' },
                                  connectNulls: false,
                                  showSymbol: false
                                },
                                {
                                  name: 'Адаптированный прогноз',
                                  type: 'line',
                                  data: adaptPredictions.points.map(p => p.adapted_pred_sa_temp),
                                  lineStyle: { color: '#10b981', width: 2 },
                                  itemStyle: { color: '#10b981' },
                                  connectNulls: false,
                                  showSymbol: false
                                }
                              ]
                            }}
                            style={{ height: '100%', width: '100%' }}
                            notMerge={true}
                          />
                        </div>
                      ) : (
                        <div className="h-80 flex items-center justify-center text-slate-500 text-xs">
                          Загрузка временных рядов отложенного теста...
                        </div>
                      )}

                      {/* Explanation Note for Night Gaps & Fault Bands */}
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between text-[11px] text-slate-400 border-t border-slate-900 pt-2 gap-2">
                        <span className="flex items-center space-x-1.5">
                          <span className="w-2 h-2 rounded-full bg-slate-600 shrink-0"></span>
                          <span>Разрывы линий: ночные периоды (18:00–06:00, вентилятор OFF) и выходные дни не сшиваются фиктивными прямыми отрезками.</span>
                        </span>
                        <span className="text-amber-400/90 font-mono text-[10px] shrink-0">
                          Оранжевые зоны: 34 окна документированных инъекций дефектов
                        </span>
                      </div>
                    </div>

                    {/* Scientific Table: Strategy Comparison */}
                    {adaptSummary && (
                      <div className="bg-slate-950 border border-slate-800 rounded-xl p-5 space-y-3">
                        <div className="flex items-center justify-between">
                          <h3 className="text-sm font-semibold text-slate-100">
                            Таблица 1. Сравнение стратегий адаптации на отложенном независимом тесте (Held-Out Test, N=1,074)
                          </h3>
                          <span className="text-xs text-slate-400 font-mono">Единая тестовая выборка, SF_SPD_DM ≥ 0.5</span>
                        </div>

                        <div className="overflow-x-auto">
                          <table className="w-full text-left text-xs text-slate-300">
                            <thead className="bg-slate-900/80 text-slate-400 text-[11px] uppercase font-mono border-b border-slate-800">
                              <tr>
                                <th className="py-2.5 px-3">Код</th>
                                <th className="py-2.5 px-3">Стратегия / Модель</th>
                                <th className="py-2.5 px-3">Статус домена</th>
                                <th className="py-2.5 px-3">MAE [°C]</th>
                                <th className="py-2.5 px-3">RMSE [°C]</th>
                                <th className="py-2.5 px-3">Bias [°C]</th>
                                <th className="py-2.5 px-3">Коэфф. R²</th>
                                <th className="py-2.5 px-3">Ложные тревоги (3σ)</th>
                                <th className="py-2.5 px-3">CHW Valve Recall</th>
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-800/60 font-mono text-xs">
                              {adaptSummary.models_comparison.map(row => (
                                <tr
                                  key={row.strategy_code}
                                  className={`hover:bg-slate-900/60 transition-colors ${
                                    (row.strategy_code === 'C2' && selectedAdaptModelId === 'csiro-ahu9-affine-v1') ||
                                    (row.strategy_code === 'C1' && selectedAdaptModelId === 'csiro-ahu9-bias-v1') ||
                                    (row.strategy_code === 'L2' && selectedAdaptModelId === 'csiro-ahu9-local-lgbm-v1') ||
                                    (row.strategy_code === 'Z0' && selectedAdaptModelId === 'vs-sa-temp-v2')
                                      ? 'bg-emerald-500/10'
                                      : ''
                                  }`}
                                >
                                  <td className="py-2.5 px-3 font-bold text-slate-200">{row.strategy_code}</td>
                                  <td className="py-2.5 px-3 font-sans text-slate-200">{row.model_name}</td>
                                  <td className="py-2.5 px-3">
                                    <span className={`px-2 py-0.5 rounded text-[10px] font-semibold ${
                                      row.status === 'LOCALLY_EVALUATED'
                                        ? 'bg-emerald-500/20 text-emerald-300'
                                        : 'bg-rose-500/20 text-rose-300'
                                    }`}>
                                      {row.status}
                                    </span>
                                  </td>
                                  <td className={`py-2.5 px-3 font-bold ${
                                    (row.mae_degC || 0) <= 1.25 ? 'text-emerald-400' : (row.mae_degC || 0) <= 2.0 ? 'text-amber-400' : 'text-rose-400'
                                  }`}>
                                    {row.mae_degC?.toFixed(4)} °C
                                  </td>
                                  <td className="py-2.5 px-3 text-slate-300">{row.rmse_degC?.toFixed(4)} °C</td>
                                  <td className="py-2.5 px-3 text-slate-300">
                                    {(row.mean_bias_degC ?? 0) > 0 ? '+' : ''}{row.mean_bias_degC?.toFixed(4)} °C
                                  </td>
                                  <td className="py-2.5 px-3 text-slate-300">{row.r2_score !== null ? row.r2_score.toFixed(4) : 'N/A'}</td>
                                  <td className={`py-2.5 px-3 ${
                                    (row.false_alarm_rate_pct || 0) <= 5.0 ? 'text-emerald-400' : 'text-rose-400 font-bold'
                                  }`}>
                                    {row.false_alarm_rate_pct?.toFixed(1)}%
                                  </td>
                                  <td className="py-2.5 px-3 text-emerald-400">
                                    {row.chw_valve_recall_pct !== null ? `${row.chw_valve_recall_pct.toFixed(0)}%` : 'N/A'}
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    )}

                    {/* Scientific Limitations Card */}
                    <div className="bg-slate-950 border border-slate-800 rounded-xl p-5 space-y-2 text-xs text-slate-300">
                      <h4 className="font-semibold text-slate-100 flex items-center space-x-2">
                        <span>📋 Научные выводы и ограничения адаптации (Gate 1 & Gate 3):</span>
                      </h4>
                      <ul className="list-disc list-inside space-y-1.5 text-slate-400 pl-1 text-[11px]">
                        <li>
                          <strong className="text-emerald-400">H4a ПОДТВЕРЖДЕНА (SUPPORTED_ON_THIS_TEST):</strong> Аффинная калибровка (C2) и константное смещение (C1) снизили MAE на независимом тесте с 4.46 °C до 1.11 °C (-75.2%) и 1.20 °C (-73.0%), превысив целевой порог снижения 50%.
                        </li>
                        <li>
                          <strong className="text-rose-400">H4b ОПРОВЕРГНУТА (REFUTED_ON_TEST):</strong> Ни одна локальная модель (L1 Ridge: 2.98 °C, A1 Residual: 1.83 °C, L2 LightGBM: 1.27 °C) не превзошла константный сдвиг предобученной модели симулятора (C1: 1.20 °C). Сохранение нелинейной структуры симулятора надёжнее обучения с нуля на недельной телеметрии.
                        </li>
                        <li>
                          <strong className="text-amber-400">H4c ЧАСТИЧНО ПОДТВЕРЖДЕНА (PARTIALLY_SUPPORTED_WITH_LOW_SENSITIVITY):</strong> Локальный порог 3σ уложился в норматив ложных тревог (2.8% ≤ 5.0%, 1.79 эп/день), однако полнота детекции дефектов клапана составила лишь 25.0% (1 из 4: обнаружен только аварийный режим 88% stuck), а общий recall — 17.6% (6 из 34 эпизодов). Высокий порог, необходимый для фильтрации шума реальной BMS, подавляет чувствительность к умеренным дефектам.
                        </li>
                      </ul>
                    </div>
                  </div>
                )}

                {/* SUBTAB 2: STAGE 5 AUDIT ZERO-SHOT */}
                {realBuildingSubTab === 'audit' && (
                  <div className="space-y-6">
                    <div className="bg-slate-950 border border-slate-800 rounded-xl p-5 space-y-4">
                      <div className="flex items-center justify-between">
                        <div>
                          <div className="flex items-center space-x-2">
                            <h2 className="text-base font-semibold text-slate-100">
                              Аудит исходного переноса: CSIRO Operational AHU (Zero-Shot)
                            </h2>
                            <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30">
                              REAL_FIELD_BMS
                            </span>
                          </div>
                          <p className="text-xs text-slate-400">
                            Офисный центр CSIRO Energy Centre, Ньюкасл, Австралия (BMS Schneider Electric TAC Vista)
                          </p>
                        </div>
                        <div className="px-2.5 py-1 rounded bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs font-semibold">
                          Domain Guard: OUT_OF_DOMAIN_UNVALIDATED
                        </div>
                      </div>

                      {/* Transfer Metrics Grid */}
                      <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
                        <div className="p-4 bg-slate-900 border border-slate-800 rounded-xl">
                          <div className="text-[11px] text-slate-400 uppercase font-semibold">MAE невязки</div>
                          <div className="text-2xl font-bold font-mono text-amber-400 mt-1">4.47 °C</div>
                          <div className="text-[11px] text-slate-400 mt-1">vs. 0.039 °C на симуляторе</div>
                        </div>
                        <div className="p-4 bg-slate-900 border border-slate-800 rounded-xl">
                          <div className="text-[11px] text-slate-400 uppercase font-semibold">RMSE невязки</div>
                          <div className="text-2xl font-bold font-mono text-amber-400 mt-1">4.85 °C</div>
                          <div className="text-[11px] text-slate-400 mt-1">vs. 0.174 °C на симуляторе</div>
                        </div>
                        <div className="p-4 bg-slate-900 border border-slate-800 rounded-xl">
                          <div className="text-[11px] text-slate-400 uppercase font-semibold">Коэффициент R²</div>
                          <div className="text-2xl font-bold font-mono text-rose-400 mt-1">-1.92</div>
                          <div className="text-[11px] text-slate-400 mt-1">Полный распад корреляции</div>
                        </div>
                        <div className="p-4 bg-slate-900 border border-slate-800 rounded-xl">
                          <div className="text-[11px] text-slate-400 uppercase font-semibold">Ложные тревоги</div>
                          <div className="text-2xl font-bold font-mono text-rose-400 mt-1">98.6%</div>
                          <div className="text-[11px] text-slate-400 mt-1">При пороге 3σ нормы</div>
                        </div>
                      </div>

                      {/* Scientific Finding Alert */}
                      <div className="p-4 bg-amber-500/10 border border-amber-500/30 rounded-xl text-xs text-amber-200/90 space-y-2">
                        <div className="font-semibold text-amber-300 text-sm flex items-center space-x-2">
                          <span>⚠️ Доказанный отрицательный результат прямого ML-переноса:</span>
                        </div>
                        <p>
                          Прямой перенос модели виртуального датчика, обученной на симуляторе EnergyPlus (Chicago TMY),
                          на реальное коммерческое здание в Ньюкасле (Австралия) без локальной калибровки приводит к систематической
                          физической ошибке в 4.47°C. Это вызывает ложные тревоги на 98.6% рабочего времени при исправном оборудовании.
                        </p>
                      </div>

                      {/* Documented Field Injected Faults */}
                      <div className="space-y-2 pt-2">
                        <h3 className="text-xs font-semibold text-slate-200">
                          Документированные эпизоды экспериментальных дефектов (Ground Truth):
                        </h3>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-xs font-mono">
                          {[
                            { time: '2013-10-31 09:30–10:30', fault: 'CHW Valve Proxy Stuck Open', sev: '40%' },
                            { time: '2013-10-31 10:31–11:31', fault: 'CHW Valve Proxy Stuck Open', sev: '28%' },
                            { time: '2013-10-31 11:31–12:31', fault: 'CHW Valve Proxy Stuck Open', sev: '89%' },
                            { time: '2013-11-11 08:30–09:30', fault: 'CHW Valve Proxy Stuck Open', sev: '45%' },
                            { time: '2013-11-11 10:30–11:30', fault: 'CHW Valve Proxy Stuck Open', sev: '88%' },
                            { time: '2013-11-11 12:31–13:31', fault: 'CHW Valve Proxy Stuck Open', sev: '79%' },
                            { time: '2013-11-11 14:31–15:31', fault: 'CHW Valve Proxy Stuck Open', sev: '52%' }
                          ].map((ef, idx) => (
                            <div key={idx} className="p-2.5 bg-slate-900 border border-slate-800 rounded-lg flex items-center justify-between">
                              <span className="text-slate-400">{ef.time}</span>
                              <span className="text-emerald-400 font-semibold">{ef.fault} ({ef.sev})</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}
export default ResearchPage;
