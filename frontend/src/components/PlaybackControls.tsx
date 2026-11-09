import React from 'react';
import { Play, Pause, RotateCcw, ChevronLeft, ChevronRight, FastForward } from 'lucide-react';

interface PlaybackControlsProps {
  isPlaying: boolean;
  onTogglePlay: () => void;
  onRewind: () => void;
  onStep: (delta: number) => void;
  currentIndex: number;
  totalPoints: number;
  currentTimestamp?: string;
  speed: number;
  onSetSpeed: (speed: number) => void;
  onSeekIndex: (index: number) => void;
}

export const PlaybackControls: React.FC<PlaybackControlsProps> = ({
  isPlaying,
  onTogglePlay,
  onRewind,
  onStep,
  currentIndex,
  totalPoints,
  currentTimestamp,
  speed,
  onSetSpeed,
  onSeekIndex
}) => {
  const isEnd = totalPoints > 0 && currentIndex >= totalPoints - 1;
  const progressPercent = totalPoints > 1 ? ((currentIndex / (totalPoints - 1)) * 100).toFixed(1) : '0';

  return (
    <div className="bg-slate-800/80 border border-slate-700/80 rounded-xl p-3 shadow-xl backdrop-blur-sm">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
        {/* Buttons: Play, Pause, Rewind, Step */}
        <div className="flex items-center space-x-2">
          <button
            onClick={onRewind}
            title="В начало сценария"
            className="p-2 rounded-lg bg-slate-700 hover:bg-slate-600 text-slate-200 transition-colors"
          >
            <RotateCcw className="w-4 h-4" />
          </button>

          <button
            onClick={() => onStep(-1)}
            disabled={currentIndex <= 0}
            title="-1 минута"
            className="p-2 rounded-lg bg-slate-700 hover:bg-slate-600 disabled:opacity-40 disabled:cursor-not-allowed text-slate-200 transition-colors"
          >
            <ChevronLeft className="w-4 h-4" />
          </button>

          <button
            onClick={onTogglePlay}
            title={isPlaying ? 'Пауза' : 'Воспроизведение истории'}
            className={`flex items-center space-x-1 px-4 py-2 rounded-lg font-semibold text-sm transition-all shadow-md ${
              isPlaying
                ? 'bg-amber-500 hover:bg-amber-600 text-slate-950'
                : 'bg-emerald-500 hover:bg-emerald-600 text-slate-950'
            }`}
          >
            {isPlaying ? (
              <>
                <Pause className="w-4 h-4 fill-current" />
                <span>Пауза</span>
              </>
            ) : (
              <>
                <Play className="w-4 h-4 fill-current" />
                <span>{isEnd ? 'Повтор' : 'Старт'}</span>
              </>
            )}
          </button>

          <button
            onClick={() => onStep(1)}
            disabled={isEnd}
            title="+1 минута"
            className="p-2 rounded-lg bg-slate-700 hover:bg-slate-600 disabled:opacity-40 disabled:cursor-not-allowed text-slate-200 transition-colors"
          >
            <ChevronRight className="w-4 h-4" />
          </button>

          {/* Speed Presets */}
          <div className="flex items-center space-x-1 pl-2 border-l border-slate-700">
            <span className="text-xs text-slate-400 mr-1">Скорость:</span>
            {[1, 5, 20].map(s => (
              <button
                key={s}
                onClick={() => onSetSpeed(s)}
                className={`px-2 py-1 text-xs rounded font-mono font-medium transition-colors ${
                  speed === s
                    ? 'bg-emerald-600 text-white'
                    : 'bg-slate-700 hover:bg-slate-600 text-slate-300'
                }`}
              >
                x{s}
              </button>
            ))}
          </div>
        </div>

        {/* Current Time and Progress Bar */}
        <div className="flex-1 flex flex-col md:flex-row md:items-center space-y-1 md:space-y-0 md:space-x-4">
          <input
            type="range"
            min={0}
            max={Math.max(0, totalPoints - 1)}
            value={currentIndex}
            onChange={e => onSeekIndex(parseInt(e.target.value, 10))}
            className="w-full h-2 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-emerald-500"
          />

          <div className="flex items-center justify-between md:justify-end space-x-3 text-xs whitespace-nowrap min-w-[200px]">
            <span className="font-mono text-emerald-300 font-medium">
              {currentTimestamp || '—'}
            </span>
            <span className="text-slate-400 font-mono">
              {progressPercent}%
            </span>
            {isEnd && (
              <span className="px-1.5 py-0.5 rounded text-[10px] bg-amber-500/20 text-amber-300 border border-amber-500/40">
                Конец данных
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
