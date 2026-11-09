import React, { useMemo, useRef } from 'react';
import ReactECharts from 'echarts-for-react';
import { TelemetrySeriesItem, MLPredictionResponse } from '../types/api';
import { Brain, AlertTriangle, CheckCircle, Info } from 'lucide-react';

interface TelemetryChartProps {
  series: TelemetrySeriesItem[];
  currentTimestamp?: string;
  onSeekToTimestamp?: (timestamp: string) => void;
  isLoading?: boolean;
  mlPredictions?: MLPredictionResponse | null;
  showVirtualSensor?: boolean;
}

const COLOR_PALETTE = [
  '#38bdf8', // Light Blue (SA_TEMP)
  '#f59e0b', // Amber (OA_TEMP)
  '#10b981', // Emerald (MA_TEMP)
  '#a855f7', // Purple (RA_TEMP)
  '#ec4899', // Pink (CHWC_VLV_DM)
  '#6366f1', // Indigo (OA_DMPR_DM)
  '#14b8a6', // Teal
  '#eab308'  // Yellow
];

export const TelemetryChart: React.FC<TelemetryChartProps> = ({
  series,
  currentTimestamp,
  onSeekToTimestamp,
  isLoading,
  mlPredictions,
  showVirtualSensor
}) => {
  const chartRef = useRef<any>(null);
  const residualChartRef = useRef<any>(null);

  // Check temperature unit of raw series (default °F in LBNL)
  const isFahrenheit = series.some(s => s.channel === 'SA_TEMP' && s.unit.includes('F'));

  // Cursor prediction details
  const cursorMLPoint = useMemo(() => {
    if (!mlPredictions || !currentTimestamp) return null;
    return mlPredictions.points.find(p => p.timestamp === currentTimestamp) || null;
  }, [mlPredictions, currentTimestamp]);

  const mainOption = useMemo(() => {
    if (!series || series.length === 0) {
      return {
        title: {
          text: 'Нет выбранных каналов для отображения',
          left: 'center',
          top: 'middle',
          textStyle: { color: '#64748b', fontSize: 14 }
        }
      };
    }

    const hasFractional = series.some(s => s.unit === '0-1' || s.unit === '0/1' || s.unit === '%');
    const hasPhysical = series.some(s => s.unit !== '0-1' && s.unit !== '0/1' && s.unit !== '%');

    const echartsSeries = series.map((s, idx) => {
      const isFraction = s.unit === '0-1' || s.unit === '0/1' || s.unit === '%';
      const color = COLOR_PALETTE[idx % COLOR_PALETTE.length];

      const item: any = {
        name: s.display_name_ru,
        type: 'line',
        showSymbol: false,
        smooth: false,
        data: s.points,
        yAxisIndex: (hasFractional && isFraction) ? 1 : 0,
        lineStyle: {
          width: 2,
          color: color
        },
        itemStyle: {
          color: color
        }
      };

      if (idx === 0 && currentTimestamp) {
        item.markLine = {
          symbol: ['none', 'none'],
          silent: true,
          label: {
            show: true,
            formatter: 'Курсор',
            position: 'end',
            color: '#fbbf24',
            fontSize: 10
          },
          lineStyle: {
            color: '#fbbf24',
            type: 'solid',
            width: 2
          },
          data: [{ xAxis: currentTimestamp }]
        };
      }

      return item;
    });

    // Add Virtual Sensor overlay if enabled
    if (showVirtualSensor && mlPredictions && mlPredictions.points.length > 0) {
      // Convert predicted °C to °F if raw chart is in °F
      const predPoints = mlPredictions.points.map(p => {
        if (p.predicted === null || p.predicted === undefined) return [p.timestamp, null];
        const val = isFahrenheit ? (p.predicted * 9 / 5 + 32) : p.predicted;
        return [p.timestamp, parseFloat(val.toFixed(2))];
      });

      echartsSeries.push({
        name: `SA_TEMP прогноз (${mlPredictions.model_id})`,
        type: 'line',
        showSymbol: false,
        smooth: false,
        data: predPoints,
        yAxisIndex: 0,
        lineStyle: {
          width: 2.5,
          color: '#f43f5e', // Rose / Red
          type: 'dashed'
        },
        itemStyle: {
          color: '#f43f5e'
        }
      });
    }

    const yAxes: any[] = [];
    if (hasPhysical || !hasFractional) {
      yAxes.push({
        type: 'value',
        name: isFahrenheit ? 'Температура (°F)' : 'Температура (°C)',
        nameTextStyle: { color: '#94a3b8', fontSize: 11 },
        position: 'left',
        splitLine: { lineStyle: { color: '#1e293b' } },
        axisLabel: { color: '#94a3b8' }
      });
    }

    if (hasFractional) {
      yAxes.push({
        type: 'value',
        name: 'Сигнал / Положение (0–1)',
        nameTextStyle: { color: '#94a3b8', fontSize: 11 },
        position: 'right',
        min: 0,
        max: 1.05,
        splitLine: { show: false },
        axisLabel: {
          color: '#94a3b8',
          formatter: (val: number) => `${(val * 100).toFixed(0)}%`
        }
      });
    }

    return {
      backgroundColor: 'transparent',
      animation: false,
      tooltip: {
        trigger: 'axis',
        axisPointer: {
          type: 'cross',
          label: { backgroundColor: '#334155' }
        },
        backgroundColor: 'rgba(15, 23, 42, 0.95)',
        borderColor: '#475569',
        textStyle: { color: '#f8fafc', fontSize: 12 }
      },
      legend: {
        top: 4,
        textStyle: { color: '#cbd5e1', fontSize: 11 },
        type: 'scroll'
      },
      grid: {
        top: 48,
        left: 55,
        right: hasFractional ? 55 : 20,
        bottom: 50
      },
      xAxis: {
        type: 'time',
        boundaryGap: false,
        splitLine: { lineStyle: { color: '#1e293b' } },
        axisLabel: { color: '#94a3b8' }
      },
      yAxis: yAxes,
      dataZoom: [
        {
          type: 'inside',
          xAxisIndex: [0]
        },
        {
          type: 'slider',
          xAxisIndex: [0],
          bottom: 4,
          height: 20,
          borderColor: '#334155',
          textStyle: { color: '#94a3b8' },
          handleStyle: { color: '#38bdf8' }
        }
      ],
      series: echartsSeries
    };
  }, [series, currentTimestamp, showVirtualSensor, mlPredictions, isFahrenheit]);

  // Secondary chart: Residual & Threshold
  const residualOption = useMemo(() => {
    if (!showVirtualSensor || !mlPredictions || mlPredictions.points.length === 0) {
      return null;
    }

    const residualAbsPoints = mlPredictions.points.map(p => [p.timestamp, p.residual_abs]);
    const thresholdPoints = mlPredictions.points.map(p => [p.timestamp, p.threshold]);

    return {
      backgroundColor: 'transparent',
      animation: false,
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'cross' },
        backgroundColor: 'rgba(15, 23, 42, 0.95)',
        borderColor: '#475569',
        textStyle: { color: '#f8fafc', fontSize: 12 }
      },
      legend: {
        top: 0,
        textStyle: { color: '#cbd5e1', fontSize: 11 }
      },
      grid: {
        top: 30,
        left: 55,
        right: 20,
        bottom: 25
      },
      xAxis: {
        type: 'time',
        boundaryGap: false,
        splitLine: { lineStyle: { color: '#1e293b' } },
        axisLabel: { color: '#94a3b8' }
      },
      yAxis: {
        type: 'value',
        name: '|r(t)| (°C)',
        nameTextStyle: { color: '#94a3b8', fontSize: 11 },
        splitLine: { lineStyle: { color: '#1e293b' } },
        axisLabel: { color: '#94a3b8' }
      },
      series: [
        {
          name: 'Невязка |r| = |SA_TEMP - прогноз| (°C)',
          type: 'line',
          showSymbol: false,
          data: residualAbsPoints,
          lineStyle: { width: 1.8, color: '#f59e0b' },
          areaStyle: {
            color: 'rgba(245, 158, 11, 0.12)'
          }
        },
        {
          name: `Порог (${mlPredictions.threshold_policy}: ${mlPredictions.threshold_value}°C)`,
          type: 'line',
          showSymbol: false,
          data: thresholdPoints,
          lineStyle: { width: 1.5, color: '#ef4444', type: 'dashed' }
        }
      ]
    };
  }, [showVirtualSensor, mlPredictions]);

  const onChartClick = (params: any) => {
    if (params && params.data && params.data[0] && onSeekToTimestamp) {
      onSeekToTimestamp(params.data[0]);
    }
  };

  return (
    <div className="space-y-3">
      {/* Main Telemetry Chart */}
      <div className="relative bg-slate-800/80 border border-slate-700/80 rounded-xl p-4 shadow-xl backdrop-blur-sm">
        {isLoading && (
          <div className="absolute inset-0 bg-slate-900/60 flex items-center justify-center z-10 rounded-xl backdrop-blur-[2px]">
            <div className="flex items-center space-x-2 text-emerald-400 text-sm">
              <span className="w-4 h-4 border-2 border-emerald-400 border-t-transparent rounded-full animate-spin" />
              <span>Загрузка данных временных рядов...</span>
            </div>
          </div>
        )}
        <ReactECharts
          ref={chartRef}
          option={mainOption}
          style={{ height: '360px', width: '100%' }}
          onEvents={{ click: onChartClick }}
          notMerge={true}
          lazyUpdate={true}
        />
      </div>

      {/* Virtual Sensor Residual & Threshold Panel */}
      {showVirtualSensor && mlPredictions && (
        <div className="bg-slate-800/80 border border-slate-700/80 rounded-xl p-4 shadow-xl backdrop-blur-sm">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 border-b border-slate-700/60 pb-2 mb-3">
            <div className="flex items-center space-x-2">
              <Brain className="w-4 h-4 text-rose-400" />
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-200">
                График невязки виртуального датчика SA_TEMP и порог тревоги
              </h3>
            </div>

            {/* Cursor status banner */}
            {cursorMLPoint && (
              <div className="flex items-center space-x-3 text-xs">
                <div>
                  <span className="text-slate-400">Факт: </span>
                  <span className="font-mono text-sky-300 font-semibold">
                    {cursorMLPoint.actual !== null ? `${cursorMLPoint.actual} °C` : 'N/A'}
                  </span>
                </div>
                <div>
                  <span className="text-slate-400">Прогноз: </span>
                  <span className="font-mono text-rose-300 font-semibold">
                    {cursorMLPoint.predicted !== null ? `${cursorMLPoint.predicted} °C` : 'N/A'}
                  </span>
                </div>
                <div>
                  <span className="text-slate-400">|r|: </span>
                  <span className="font-mono text-amber-300 font-semibold">
                    {cursorMLPoint.residual_abs !== null ? `${cursorMLPoint.residual_abs} °C` : 'N/A'}
                  </span>
                </div>
                <div>
                  {cursorMLPoint.is_alarm ? (
                    <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-rose-950 text-rose-300 border border-rose-700 animate-pulse">
                      ОТКЛОНЕНИЕ МОДЕЛИ
                    </span>
                  ) : !cursorMLPoint.is_operating ? (
                    <span className="px-2 py-0.5 rounded text-[10px] font-medium bg-slate-900 text-slate-400 border border-slate-700">
                      ВЕНТ ВЫКЛ (AHU_OFF)
                    </span>
                  ) : (
                    <span className="px-2 py-0.5 rounded text-[10px] font-medium bg-emerald-950 text-emerald-300 border border-emerald-800">
                      НОРМА
                    </span>
                  )}
                </div>
              </div>
            )}
          </div>

          {residualOption && (
            <ReactECharts
              ref={residualChartRef}
              option={residualOption}
              style={{ height: '180px', width: '100%' }}
              onEvents={{ click: onChartClick }}
              notMerge={true}
              lazyUpdate={true}
            />
          )}

          {/* Scientific Disclaimer Note */}
          <div className="flex items-start space-x-2 mt-2 pt-2 border-t border-slate-700/40 text-[11px] text-slate-400">
            <Info className="w-4 h-4 text-sky-400 shrink-0 mt-0.5" />
            <p>
              <strong className="text-slate-300">Научное ограничение:</strong> Невязка одномерного виртуального датчика фиксирует расхождение теплового баланса установки (<em className="text-sky-300">детектор аномалий</em>), но не локализует первопричину (заклинивание клапана, заслонки или смещение самого датчика одинаково искажают баланс).
            </p>
          </div>
        </div>
      )}
    </div>
  );
};
