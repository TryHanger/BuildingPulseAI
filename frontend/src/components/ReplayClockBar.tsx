import React from 'react';
import {
  Play,
  Pause,
  RotateCcw,
  FastForward,
  Clock,
  AlertCircle,
  CheckCircle,
  HelpCircle,
  Gauge
} from 'lucide-react';

export type AHUOperatingMode = 'OFF' | 'COOLING' | 'ECONOMIZER' | 'TRANSITION' | 'TRANSITION_HOLD' | 'RUNNING' | 'UNKNOWN';

interface ReplayClockBarProps {
  isPlaying: boolean;
  onTogglePlay: () => void;
  onReset: () => void;
  currentIndex: number;
  totalPoints: number;
  onSeekIndex: (index: number) => void;
  currentTimestamp: string;
  playbackSpeed: number;
  onChangeSpeed: (speed: number) => void;
  currentMode: AHUOperatingMode;
  fanOn: boolean | null;
  clockKind?: "SOURCE_SIMULATION_TIME";
  hasDataGap?: boolean;
}

export const ReplayClockBar: React.FC<ReplayClockBarProps> = ({
  isPlaying,
  onTogglePlay,
  onReset,
  currentIndex,
  totalPoints,
  onSeekIndex,
  currentTimestamp,
  playbackSpeed,
  onChangeSpeed,
  currentMode,
  fanOn,
  clockKind,
  hasDataGap = false
}) => {
  // Format timestamps in UTC and Local
  const formatUtcAndLocal = (isoString: string) => {
    if (!isoString) return { utc: '—', local: '—' };
    try {
      const d = new Date(isoString);
      if (isNaN(d.getTime())) return { utc: isoString, local: isoString };
      const utcStr = d.toISOString().replace('T', ' ').substring(0, 19) + ' UTC';
      const localStr = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
      return { utc: utcStr, local: localStr };
    } catch {
      return { utc: isoString, local: isoString };
    }
  };

  const { utc, local } = clockKind ? { utc: currentTimestamp, local: "" } : formatUtcAndLocal(currentTimestamp);

  const getModeBadge = (mode: AHUOperatingMode) => {
    switch (mode) {
      case 'COOLING':
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-blue-900/60 text-blue-300 border border-blue-700">
            <span className="w-1.5 h-1.5 rounded-full bg-blue-400 mr-1.5"></span>
            Механическое охлаждение
          </span>
        );
      case 'ECONOMIZER':
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-emerald-900/60 text-emerald-300 border border-emerald-700">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 mr-1.5"></span>
            Свободное охлаждение (Экономайзер)
          </span>
        );
      case 'RUNNING':
        return <span className="rounded-lg bg-emerald-950 px-2 py-1 text-xs text-emerald-300">Устойчивый статус ON</span>;
      case 'TRANSITION_HOLD':
        return <span className="rounded-lg bg-amber-950 px-2 py-1 text-xs text-amber-300">Удержание после пуска</span>;
      case 'TRANSITION':
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-amber-900/60 text-amber-300 border border-amber-700">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-400 mr-1.5"></span>
            Переходный режим / Пуск
          </span>
        );
      case 'OFF':
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-slate-800 text-slate-400 border border-slate-700">
            <span className="w-1.5 h-1.5 rounded-full bg-slate-500 mr-1.5"></span>
            Остановлена (Fan OFF)
          </span>
        );
      case 'UNKNOWN':
      default:
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-purple-900/60 text-purple-300 border border-purple-700">
            <HelpCircle className="w-3 h-3 mr-1" />
            Режим не определен
          </span>
        );
    }
  };

  return (
    <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-3 shadow-lg select-none backdrop-blur-sm">
      <div className="flex flex-wrap items-center justify-between gap-3">
        {/* Playback Controls & Speed */}
        <div className="flex items-center space-x-2">
          <button
            onClick={onTogglePlay}
            className={`p-2 rounded-lg font-medium text-xs flex items-center space-x-1.5 transition-all shadow-sm ${
              isPlaying
                ? 'bg-amber-600/30 text-amber-300 border border-amber-500 hover:bg-amber-600/40'
                : 'bg-emerald-600/30 text-emerald-300 border border-emerald-500 hover:bg-emerald-600/40'
            }`}
            title={isPlaying ? 'Приостановить воспроизведение' : 'Запустить воспроизведение телеметрии'}
          >
            {isPlaying ? <Pause className="w-4 h-4 fill-current" /> : <Play className="w-4 h-4 fill-current" />}
            <span>{isPlaying ? 'Пауза' : 'Воспроизведение'}</span>
          </button>

          <button
            onClick={onReset}
            className="p-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition-colors"
            title="Сбросить на начало"
          >
            <RotateCcw className="w-4 h-4" />
          </button>

          {/* Speed Selector */}
          <div className="flex items-center bg-slate-800/80 rounded-lg p-0.5 border border-slate-700 text-xs">
            {[1, 5, 20].map((s) => (
              <button
                key={s}
                onClick={() => onChangeSpeed(s)}
                className={`px-2 py-1 rounded font-mono font-medium transition-colors ${
                  playbackSpeed === s
                    ? 'bg-emerald-500 text-slate-950 font-bold shadow-sm'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                x{s}
              </button>
            ))}
          </div>
        </div>

        {/* Timestamps (UTC & Local) */}
        <div className="flex items-center space-x-3 text-xs">
          <div className="flex items-center space-x-1.5 bg-slate-950/70 px-2.5 py-1.5 rounded-lg border border-slate-800">
            <Clock className="w-3.5 h-3.5 text-amber-400" />
            <span className="text-slate-400 font-mono">{clockKind ? "Время симуляции" : "UTC"}</span>
            <span className="font-mono text-amber-300 font-semibold">{utc}</span>
          </div>

          {!clockKind && <div className="hidden sm:flex items-center space-x-1 bg-slate-950/70 px-2.5 py-1.5 rounded-lg border border-slate-800">
            <span className="text-slate-400 text-[11px]">Местное:</span>
            <span className="font-mono text-slate-200 text-xs">{local}</span>
          </div>}
        </div>

        {/* Operational Status Badges */}
        <div className="flex items-center space-x-2">
          {getModeBadge(currentMode)}

          {/* Fan Confirmation Status */}
          <span
            className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold border ${
              fanOn
                ? 'bg-emerald-950 text-emerald-300 border-emerald-700'
                : 'bg-slate-800 text-slate-400 border-slate-700'
            }`}
          >
            <span
              className={`w-1.5 h-1.5 rounded-full mr-1.5 ${
                fanOn ? 'bg-emerald-400 animate-pulse' : 'bg-slate-500'
              }`}
            ></span>
            {fanOn === null ? 'Статус вентилятора неизвестен' : fanOn ? 'Вентилятор: ВКЛ' : 'Вентилятор: ВЫКЛ'}
          </span>

          {hasDataGap && (
            <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-rose-950/80 text-rose-300 border border-rose-700">
              <AlertCircle className="w-3 h-3 mr-1 text-rose-400" />
              Пропуск данных
            </span>
          )}
        </div>
      </div>

      {/* Scrubber Timeline Slider */}
      <div className="mt-2.5 pt-2 border-t border-slate-800/80 flex items-center space-x-3">
        <span className="text-[11px] font-mono text-slate-500 w-8 text-right">0%</span>
        <input
          type="range"
          min={0}
          max={Math.max(0, totalPoints - 1)}
          value={currentIndex}
          onChange={(e) => onSeekIndex(parseInt(e.target.value, 10))}
          className="flex-1 h-1.5 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-emerald-400 hover:accent-emerald-300 transition-all"
        />
        <span className="text-[11px] font-mono text-slate-400 w-16">
          {totalPoints > 0 ? `${Math.round(((currentIndex + 1) / totalPoints) * 100)}%` : '0%'}
        </span>
      </div>
    </div>
  );
};
