import React from 'react';
import ReactECharts from 'echarts-for-react';
import { Layers, ShieldAlert, CheckCircle2, Lock, AlertTriangle } from 'lucide-react';

export interface MatchedScenarioPair {
  pair_id: string;
  status: 'CONFIRMED_MATCHED' | 'BLOCKED_INCOMPARABLE';
  label: string;
  baseline_scenario_id: string;
  baseline_scenario_name: string;
  fault_scenario_id: string;
  fault_scenario_name: string;
  justification: string;
  series_overlay: {
    channel: string;
    unit: string;
    points_baseline: Array<[string, number | null]>;
    points_fault: Array<[string, number | null]>;
  } | null;
}

interface NormalFaultOverlayPanelProps {
  pairs: MatchedScenarioPair[];
  selectedPairId?: string;
  onSelectPair?: (pairId: string) => void;
}

export const NormalFaultOverlayPanel: React.FC<NormalFaultOverlayPanelProps> = ({
  pairs,
  selectedPairId,
  onSelectPair
}) => {
  const currentPair = pairs.find(p => p.pair_id === selectedPairId) || pairs[0];

  const chartOption = React.useMemo(() => {
    if (!currentPair || currentPair.status !== 'CONFIRMED_MATCHED' || !currentPair.series_overlay) {
      return null;
    }

    const overlay = currentPair.series_overlay;

    return {
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'axis',
        backgroundColor: '#0f172a',
        borderColor: '#334155',
        textStyle: { color: '#f8fafc', fontSize: 11 }
      },
      legend: {
        top: 0,
        textStyle: { color: '#cbd5e1', fontSize: 11 }
      },
      grid: {
        left: '4%',
        right: '4%',
        top: '18%',
        bottom: '12%',
        containLabel: true
      },
      xAxis: {
        type: 'category',
        data: overlay.points_baseline.map(pt => pt[0]),
        axisLine: { lineStyle: { color: '#475569' } },
        axisLabel: { color: '#94a3b8', fontSize: 10 }
      },
      yAxis: {
        type: 'value',
        name: overlay.unit,
        axisLine: { lineStyle: { color: '#475569' } },
        splitLine: { lineStyle: { color: '#1e293b' } },
        axisLabel: { color: '#94a3b8', fontSize: 10 }
      },
      series: [
        {
          name: `Норма (${currentPair.baseline_scenario_name})`,
          type: 'line',
          data: overlay.points_baseline.map(pt => pt[1]),
          showSymbol: true,
          smooth: false,
          lineStyle: { color: '#10b981', width: 2 },
          itemStyle: { color: '#10b981' }
        },
        {
          name: `Авария (${currentPair.fault_scenario_name})`,
          type: 'line',
          data: overlay.points_fault.map(pt => pt[1]),
          showSymbol: true,
          smooth: false,
          lineStyle: { color: '#ef4444', width: 2.5 },
          itemStyle: { color: '#ef4444' }
        }
      ]
    };
  }, [currentPair]);

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 shadow-xl select-none space-y-4">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between pb-3 border-b border-slate-800 gap-2">
        <div className="flex items-center space-x-2">
          <Layers className="w-4 h-4 text-emerald-400" />
          <h3 className="text-xs font-bold tracking-wider uppercase text-slate-200">
            Сравнение Норма vs Авария (Matched Scenario Pairs)
          </h3>
        </div>
        <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-blue-950 text-blue-300 border border-blue-800">
          Синтетический пример наложения · DEMO_FIXTURE
        </span>
      </div>

      {/* Scenario Pair Selectors */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {pairs.map(pair => {
          const isSelected = currentPair?.pair_id === pair.pair_id;
          const isMatched = pair.status === 'CONFIRMED_MATCHED';

          return (
            <div
              key={pair.pair_id}
              onClick={() => onSelectPair && onSelectPair(pair.pair_id)}
              className={`p-3 rounded-lg border cursor-pointer transition-all ${
                isSelected
                  ? 'bg-slate-950/80 border-emerald-500 shadow-md ring-1 ring-emerald-500/40'
                  : 'bg-slate-950/50 border-slate-800 hover:border-slate-700'
              }`}
            >
              <div className="flex items-center justify-between mb-1.5">
                <span className="font-mono text-xs font-bold text-slate-200">{pair.pair_id}</span>
                {isMatched ? (
                  <span className="inline-flex items-center text-[10px] font-semibold text-emerald-400 bg-emerald-950/80 px-2 py-0.5 rounded border border-emerald-800">
                    <CheckCircle2 className="w-3 h-3 mr-1" />
                    DEMO PAIR
                  </span>
                ) : (
                  <span className="inline-flex items-center text-[10px] font-semibold text-rose-400 bg-rose-950/80 px-2 py-0.5 rounded border border-rose-800">
                    <Lock className="w-3 h-3 mr-1" />
                    BLOCKED
                  </span>
                )}
              </div>

              <div className="text-xs text-slate-300 mb-1">
                <span className="text-slate-500">Норма:</span> {pair.baseline_scenario_name}
              </div>
              <div className="text-xs text-slate-300 mb-2">
                <span className="text-slate-500">Авария:</span> {pair.fault_scenario_name}
              </div>

              <div className="text-[11px] text-slate-400 italic pt-1.5 border-t border-slate-800/80">
                {pair.justification}
              </div>
            </div>
          );
        })}
      </div>

      {/* Visualization Canvas or Blocked Banner */}
      {currentPair?.status === 'CONFIRMED_MATCHED' && chartOption ? (
        <div className="bg-slate-950/80 p-3 rounded-lg border border-slate-800">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-semibold text-slate-300">
              Наложение траекторий приточного воздуха (SAT) при идентичных внешних условиях
            </span>
            <span className="text-[10px] font-mono text-cyan-400">
              Метка: {currentPair.label}
            </span>
          </div>
          <ReactECharts option={chartOption} style={{ height: '240px', width: '100%' }} />
        </div>
      ) : (
        <div className="bg-rose-950/30 border border-rose-800/60 rounded-lg p-4 text-center">
          <AlertTriangle className="w-8 h-8 text-rose-400 mx-auto mb-2" />
          <h4 className="text-xs font-bold text-rose-300 uppercase tracking-wide">
            Наложение заблокировано: Физическая несопоставимость сценариев
          </h4>
          <p className="text-xs text-slate-300 max-w-xl mx-auto mt-1">
            {currentPair?.justification || 'Данные сценарии имеют несогласованный профиль погодных условий или разные сезоны работы.'}
          </p>
        </div>
      )}
    </div>
  );
};
