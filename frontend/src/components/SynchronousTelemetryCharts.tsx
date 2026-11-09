import React, { useMemo, useRef } from 'react';
import ReactECharts from 'echarts-for-react';
import { Activity, Sliders, Thermometer } from 'lucide-react';

interface SynchronousTelemetryChartsProps {
  currentTimestamp: string;
  onSeekTimestamp?: (timestamp: string) => void;
  series: Array<{
    channel: string;
    display_name_ru: string;
    unit: string;
    chart_group: string;
    role?: string;
    points: Array<[string, number | null]>;
    model_available?: boolean;
  }>;
  isModelAvailable?: boolean;
  sourceTimestamps?: readonly string[];
  sourceGapBefore?: readonly boolean[];
}

// Gregorian calendar arithmetic on the source labels, independent of the browser clock.
export function sourceSeconds(timestamp: string): number {
  const [year, month, day, hour, minute, second] = timestamp.split(/[-T:]/).map(Number);
  const past = year - 1;
  const leap = year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0);
  const days = past * 365 + Math.floor(past / 4) - Math.floor(past / 100) + Math.floor(past / 400)
    + [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334][month - 1]
    + (month > 2 && leap ? 1 : 0) + day - 1;
  return days * 86400 + hour * 3600 + minute * 60 + second;
}

function elapsedLabel(seconds: number): string {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor(seconds / 60) % 60;
  const remainder = Math.round(seconds) % 60;
  const clock = `+${hours}:${String(minutes).padStart(2, '0')}`;
  return remainder ? `${clock}:${String(remainder).padStart(2, '0')}` : clock;
}

export const SynchronousTelemetryCharts: React.FC<SynchronousTelemetryChartsProps> = ({
  currentTimestamp,
  onSeekTimestamp,
  series,
  isModelAvailable = true,
  sourceTimestamps,
  sourceGapBefore
}) => {
  const chart1Ref = useRef<any>(null);
  const chart2Ref = useRef<any>(null);
  const chart3Ref = useRef<any>(null);

  const sourceClock = sourceTimestamps !== undefined;
  const sourceTime = useMemo(() => {
    if (!sourceTimestamps?.length) return undefined;
    const origin = sourceSeconds(sourceTimestamps[0]);
    const offsets = sourceTimestamps.map(stamp => sourceSeconds(stamp) - origin);
    return { origin, offsets, labels: new Map(offsets.map((x, i) => [x, sourceTimestamps[i]])) };
  }, [sourceTimestamps]);
  const plotted = useMemo(() => {
    if (!sourceTime) return series;
    return series.map(signal => {
      const points: Array<[number, number | null]> = [];
      signal.points.forEach(([, value], index) => {
        const x = sourceTime.offsets[index];
        if (index > 0 && sourceGapBefore?.[index]) {
          points.push([(sourceTime.offsets[index - 1] + x) / 2, null]);
        }
        points.push([x, value]);
      });
      return { ...signal, points };
    });
  }, [series, sourceTime, sourceGapBefore]);

  const chart1Series = useMemo(() => plotted.filter(s => s.chart_group === 'chart1_sat'), [plotted]);
  const chart2Series = useMemo(() => plotted.filter(s => s.chart_group === 'chart2_cmd'), [plotted]);
  const chart3Series = useMemo(() => plotted.filter(s => s.chart_group === 'chart3_thermal'), [plotted]);

  const sourceAxis = useMemo(() => sourceTime ? {
    type: 'value',
    min: 0,
    max: Math.max(1, sourceTime.offsets[sourceTime.offsets.length - 1]),
    splitLine: { lineStyle: { color: '#1e293b' } },
    axisLabel: { color: '#94a3b8', fontSize: 10, formatter: elapsedLabel }
  } : {
    type: 'time',
    axisLine: { lineStyle: { color: '#475569' } },
    axisLabel: { color: '#94a3b8', fontSize: 10 }
  }, [sourceTime]);
  const symbolSize = sourceTimestamps && sourceTimestamps.length > 60 ? 2 : 4;
  const cursor = sourceTime ? sourceSeconds(currentTimestamp) - sourceTime.origin : currentTimestamp;

  const handleChartClick = (params: { name?: string; value?: [number, number | null] }) => {
    const timestamp = sourceTime && params.value ? sourceTime.labels.get(params.value[0]) : params.name;
    if (timestamp) onSeekTimestamp?.(timestamp);
  };

  // Base chart theme options
  const baseChartConfig = useMemo(() => ({
    backgroundColor: 'transparent',
    animation: !sourceClock,
    grid: {
      left: '4%',
      right: '4%',
      top: '25%',
      bottom: '15%',
      containLabel: true
    },
    tooltip: {
      trigger: 'axis',
      ...(sourceTime ? {
        renderMode: 'richText',
        formatter: (items: Array<{ value: [number, number | null]; seriesName: string }>) => {
          const stamp = sourceTime.labels.get(items[0]?.value?.[0]);
          if (!stamp) return '';
          return [stamp, ...items.map(item => `${item.seriesName} · ${item.value[1] ?? 'нет данных'}`)].join('\n');
        }
      } : {}),
      axisPointer: {
        type: 'cross',
        lineStyle: {
          color: '#fbbf24',
          width: 1.5,
          type: 'dashed'
        }
      },
      backgroundColor: '#0f172a',
      borderColor: '#334155',
      textStyle: { color: '#f8fafc', fontSize: 11 },
      padding: [8, 12]
    },
    dataZoom: [
      {
        type: 'inside',
        xAxisIndex: [0],
        filterMode: sourceClock ? 'none' : 'filter'
      }
    ]
  }), [sourceTime, sourceClock]);

  // 1. Chart 1 Option: SAT, Setpoint, Virtual SAT + Residual
  const optionChart1 = useMemo(() => {
    const satPoint = chart1Series.find(s => s.channel === 'SA_TEMP');
    const sptPoint = chart1Series.find(s => s.channel === 'SA_TEMPSPT');
    const virtPoint = chart1Series.find(s => s.channel === 'SA_TEMP_VIRTUAL');
    const resPoint = chart1Series.find(s => s.channel === 'RESIDUAL');

    const echartsSeries: any[] = [];

    if (satPoint) {
      echartsSeries.push({
        name: 'SAT (Факт)',
        type: 'line',
        data: satPoint.points,
        showSymbol: sourceClock,
        symbolSize,
        smooth: false, // strictly no artificial smoothing
        connectNulls: false,
        lineStyle: { color: '#38bdf8', width: 2.5 },
        itemStyle: { color: '#38bdf8' }
      });
    }

    if (sptPoint) {
      echartsSeries.push({
        name: 'Уставка SAT',
        type: 'line',
        data: sptPoint.points,
        showSymbol: sourceClock,
        symbolSize,
        smooth: false,
        connectNulls: false,
        lineStyle: { color: '#94a3b8', width: 1.5, type: 'dashed' },
        itemStyle: { color: '#94a3b8' }
      });
    }

    if (isModelAvailable && virtPoint) {
      echartsSeries.push({
        name: 'Виртуальный SAT (Модель)',
        type: 'line',
        data: virtPoint.points,
        showSymbol: sourceClock,
        symbolSize,
        smooth: false,
        connectNulls: false,
        lineStyle: { color: '#a855f7', width: 2, type: 'dotted' },
        itemStyle: { color: '#a855f7' }
      });
    }

    if (isModelAvailable && resPoint) {
      echartsSeries.push({
        name: 'Невязка (SAT - Модель)',
        type: 'bar',
        yAxisIndex: 1,
        data: resPoint.points,
        itemStyle: {
          color: (params: any) => (params.value && params.value[1] > 2.0 ? '#ef4444' : '#6366f1')
        }
      });
    }

    // Add markLine for current replay cursor
    if (echartsSeries.length > 0 && currentTimestamp) {
      echartsSeries[0].markLine = {
        symbol: ['none', 'none'],
        silent: true,
        label: { show: true, formatter: 'Курсор', color: '#fbbf24', fontSize: 10 },
        lineStyle: { color: '#fbbf24', type: 'solid', width: 2 },
        data: [{ xAxis: cursor }]
      };
    }

    return {
      ...baseChartConfig,
      legend: {
        top: 0,
        textStyle: { color: '#cbd5e1', fontSize: 11 },
        itemWidth: 14,
        itemHeight: 8
      },
      xAxis: sourceAxis,
      yAxis: [
        {
          type: 'value',
          name: '°C',
          axisLine: { lineStyle: { color: '#475569' } },
          splitLine: { lineStyle: { color: '#1e293b' } },
          axisLabel: { color: '#94a3b8', fontSize: 10 }
        },
        {
          type: 'value',
          name: 'Невязка °C',
          axisLine: { lineStyle: { color: '#475569' } },
          splitLine: { show: false },
          axisLabel: { color: '#94a3b8', fontSize: 10 }
        }
      ],
      series: echartsSeries
    };
  }, [chart1Series, currentTimestamp, cursor, isModelAvailable, baseChartConfig, sourceAxis, sourceClock, symbolSize]);

  // 2. Chart 2 Option: Actuator Commands & Expected Corridor
  const optionChart2 = useMemo(() => {
    const chwcCmd = chart2Series.find(s => s.channel === 'CHWC_VLV_DM');
    const corridorUp = chart2Series.find(s => s.channel === 'CHWC_CORRIDOR_UPPER');
    const corridorLo = chart2Series.find(s => s.channel === 'CHWC_CORRIDOR_LOWER');
    const oaDmpr = chart2Series.find(s => s.channel === 'OA_DMPR_DM');

    const echartsSeries: any[] = [];

    // Lower corridor band
    if (corridorLo) {
      echartsSeries.push({
        name: 'Коридор (Нижняя граница)',
        type: 'line',
        data: corridorLo.points,
        showSymbol: sourceClock,
        symbolSize,
        lineStyle: { opacity: 0 },
        stack: 'corridor'
      });
    }

    // Upper corridor band (shaded area)
    if (corridorUp && corridorLo) {
      // Calculate delta for stacked area
      const deltaPoints = corridorUp.points.map((pt, idx) => {
        const loVal = corridorLo.points[idx] ? corridorLo.points[idx][1] : 0;
        const upVal = pt[1];
        const diff = (upVal !== null && loVal !== null) ? Math.max(0, upVal - loVal) : null;
        return [pt[0], diff];
      });

      echartsSeries.push({
        name: 'Ожидаемый коридор команды',
        type: 'line',
        data: deltaPoints,
        showSymbol: sourceClock,
        symbolSize,
        stack: 'corridor',
        areaStyle: { color: 'rgba(56, 189, 248, 0.15)' },
        lineStyle: { opacity: 0 }
      });
    }

    if (chwcCmd) {
      echartsSeries.push({
        name: 'Команда клапана CHWC_VLV_DM',
        type: 'line',
        data: chwcCmd.points,
        showSymbol: sourceClock,
        symbolSize,
        smooth: false,
        connectNulls: false,
        lineStyle: { color: '#ec4899', width: 2.2 },
        itemStyle: { color: '#ec4899' }
      });
    }

    if (oaDmpr) {
      echartsSeries.push({
        name: 'Заслонка OA_DMPR_DM',
        type: 'line',
        data: oaDmpr.points,
        showSymbol: sourceClock,
        symbolSize,
        smooth: false,
        connectNulls: false,
        lineStyle: { color: '#10b981', width: 1.8 },
        itemStyle: { color: '#10b981' }
      });
    }

    for (const [id, label, color] of [
      ['SF_CS', 'Команда вентилятора SF_CS', '#a78bfa'],
      ['SF_SPD_DM', 'Статус вентилятора SF_SPD_DM (0/100)', '#fbbf24'],
    ]) {
      const fan = chart2Series.find(series => series.channel === id);
      if (fan) echartsSeries.push({
        name: label, type: 'line', data: fan.points, showSymbol: sourceClock, symbolSize,
        smooth: false, connectNulls: false, lineStyle: { color, width: 1.8 }, itemStyle: { color },
      });
    }

    if (echartsSeries.length > 0 && currentTimestamp) {
      echartsSeries[echartsSeries.length - 1].markLine = {
        symbol: ['none', 'none'],
        silent: true,
        label: { show: false },
        lineStyle: { color: '#fbbf24', type: 'solid', width: 2 },
        data: [{ xAxis: cursor }]
      };
    }

    return {
      ...baseChartConfig,
      legend: {
        top: 0,
        textStyle: { color: '#cbd5e1', fontSize: 11 },
        itemWidth: 14,
        itemHeight: 8
      },
      xAxis: sourceAxis,
      yAxis: {
        type: 'value',
        name: '%',
        min: sourceClock ? undefined : 0,
        max: sourceClock ? undefined : 100,
        axisLine: { lineStyle: { color: '#475569' } },
        splitLine: { lineStyle: { color: '#1e293b' } },
        axisLabel: { color: '#94a3b8', fontSize: 10 }
      },
      series: echartsSeries
    };
  }, [chart2Series, currentTimestamp, cursor, baseChartConfig, sourceAxis, sourceClock, symbolSize]);

  // 3. Chart 3 Option: Thermal Context (OA, RA, MA)
  const optionChart3 = useMemo(() => {
    const oaPoint = chart3Series.find(s => s.channel === 'OA_TEMP');
    const raPoint = chart3Series.find(s => s.channel === 'RA_TEMP');
    const maPoint = chart3Series.find(s => s.channel === 'MA_TEMP');

    const echartsSeries: any[] = [];

    if (oaPoint) {
      echartsSeries.push({
        name: 'Наружный воздух (OA_TEMP)',
        type: 'line',
        data: oaPoint.points,
        showSymbol: sourceClock,
        symbolSize,
        smooth: false,
        connectNulls: false, // break night gaps
        lineStyle: { color: '#f59e0b', width: 2 },
        itemStyle: { color: '#f59e0b' }
      });
    }

    if (raPoint) {
      echartsSeries.push({
        name: 'Возвратный воздух (RA_TEMP)',
        type: 'line',
        data: raPoint.points,
        showSymbol: sourceClock,
        symbolSize,
        smooth: false,
        connectNulls: false,
        lineStyle: { color: '#a855f7', width: 2 },
        itemStyle: { color: '#a855f7' }
      });
    }

    if (maPoint) {
      echartsSeries.push({
        name: 'Смешанный воздух (MA_TEMP)',
        type: 'line',
        data: maPoint.points,
        showSymbol: sourceClock,
        symbolSize,
        smooth: false,
        connectNulls: false,
        lineStyle: { color: '#14b8a6', width: 2 },
        itemStyle: { color: '#14b8a6' }
      });
    }

    if (echartsSeries.length > 0 && currentTimestamp) {
      echartsSeries[0].markLine = {
        symbol: ['none', 'none'],
        silent: true,
        label: { show: false },
        lineStyle: { color: '#fbbf24', type: 'solid', width: 2 },
        data: [{ xAxis: cursor }]
      };
    }

    return {
      ...baseChartConfig,
      legend: {
        top: 0,
        textStyle: { color: '#cbd5e1', fontSize: 11 },
        itemWidth: 14,
        itemHeight: 8
      },
      xAxis: sourceAxis,
      yAxis: {
        type: 'value',
        name: '°C',
        axisLine: { lineStyle: { color: '#475569' } },
        splitLine: { lineStyle: { color: '#1e293b' } },
        axisLabel: { color: '#94a3b8', fontSize: 10 }
      },
      series: echartsSeries
    };
  }, [chart3Series, currentTimestamp, cursor, baseChartConfig, sourceAxis, sourceClock, symbolSize]);

  return (
    <div className="space-y-4">
      {/* 3 Synchronous Charts Stack */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
        {/* Chart 1: SAT / Setpoint / Virtual */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-3 shadow-md">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-bold text-slate-300 flex items-center space-x-1.5">
              <Thermometer className="w-3.5 h-3.5 text-sky-400" />
              <span>1. Контур притока SAT & Уставка</span>
            </span>
            {!isModelAvailable && (
              <span className="text-[10px] text-amber-400 font-mono px-1.5 py-0.5 rounded bg-amber-950/60 border border-amber-800">
                Модель недоступна
              </span>
            )}
          </div>
          <ReactECharts
            ref={chart1Ref}
            option={optionChart1}
            style={{ height: '220px', width: '100%' }}
            onEvents={{ click: handleChartClick }}
          />
        </div>

        {/* Chart 2: Actuator Commands & Expected Corridor */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-3 shadow-md">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-bold text-slate-300 flex items-center space-x-1.5">
              <Sliders className="w-3.5 h-3.5 text-pink-400" />
              <span>2. {sourceClock ? 'Команды приводов' : 'Команды приводов & Ожидаемый коридор'}</span>
            </span>
            <span className="text-[10px] text-slate-400 font-mono">{sourceClock ? "%" : "0 – 100%"}</span>
          </div>
          <ReactECharts
            ref={chart2Ref}
            option={optionChart2}
            style={{ height: '220px', width: '100%' }}
            onEvents={{ click: handleChartClick }}
          />
        </div>

        {/* Chart 3: Thermal Context */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-3 shadow-md">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-bold text-slate-300 flex items-center space-x-1.5">
              <Activity className="w-3.5 h-3.5 text-amber-400" />
              <span>3. Температуры смешения (OA / RA / MA)</span>
            </span>
            <span className="text-[10px] text-slate-400 font-mono">{sourceClock ? "Время от начала окна · разрывы по шагу источника" : "Разрыв ночных пауз"}</span>
          </div>
          <ReactECharts
            ref={chart3Ref}
            option={optionChart3}
            style={{ height: '220px', width: '100%' }}
            onEvents={{ click: handleChartClick }}
          />
        </div>
      </div>
    </div>
  );
};
