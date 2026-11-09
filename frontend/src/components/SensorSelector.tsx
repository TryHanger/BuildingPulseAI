import React from 'react';
import { SlidersHorizontal, Check } from 'lucide-react';
import { SensorItem } from '../types/api';

interface SensorSelectorProps {
  sensors: SensorItem[];
  selectedChannels: string[];
  onToggleChannel: (channel: string) => void;
  onSelectPreset: (channels: string[]) => void;
  currentValues: Record<string, number | null>;
}

export const SensorSelector: React.FC<SensorSelectorProps> = ({
  sensors,
  selectedChannels,
  onToggleChannel,
  onSelectPreset,
  currentValues
}) => {
  const PRESETS = [
    {
      name: 'Тепловой баланс',
      channels: ['OA_TEMP', 'MA_TEMP', 'SA_TEMP', 'RA_TEMP']
    },
    {
      name: 'Контур охлаждения',
      channels: ['SA_TEMP', 'SA_TEMPSPT', 'CHWC_VLV_DM', 'CHWC_VLV']
    },
    {
      name: 'Экономайзер',
      channels: ['OA_TEMP', 'MA_TEMP', 'OA_DMPR_DM', 'OA_DMPR']
    }
  ];

  return (
    <div className="bg-slate-800/80 border border-slate-700/80 rounded-xl p-4 shadow-xl backdrop-blur-sm">
      <div className="flex items-center justify-between mb-3 border-b border-slate-700/60 pb-2">
        <div className="flex items-center space-x-2">
          <SlidersHorizontal className="w-5 h-5 text-emerald-400" />
          <h2 className="text-sm font-bold tracking-wide uppercase text-slate-200">
            Каналы телеметрии ({selectedChannels.length}/5)
          </h2>
        </div>

        {/* Quick Presets */}
        <div className="flex items-center space-x-1">
          <span className="text-xs text-slate-400 mr-1 hidden sm:inline">Пресеты:</span>
          {PRESETS.map(p => (
            <button
              key={p.name}
              onClick={() => onSelectPreset(p.channels)}
              className="px-2 py-0.5 text-[11px] bg-slate-700 hover:bg-slate-600 rounded text-slate-300 transition-colors"
            >
              {p.name}
            </button>
          ))}
        </div>
      </div>

      {/* Sensor List */}
      <div className="flex flex-wrap gap-2 max-h-[140px] overflow-y-auto pr-1">
        {sensors.map(s => {
          const isSelected = selectedChannels.includes(s.canonical_key);
          const val = currentValues[s.canonical_key];
          const valStr = val !== undefined && val !== null && !isNaN(val)
            ? (s.unit_raw === '0-1' ? `${(val * 100).toFixed(0)}%` : `${val.toFixed(1)} ${s.unit_raw || ''}`)
            : '—';

          return (
            <button
              key={s.canonical_key}
              onClick={() => onToggleChannel(s.canonical_key)}
              className={`flex items-center space-x-1.5 px-2.5 py-1.5 rounded-lg border text-xs transition-all ${
                isSelected
                  ? 'bg-emerald-950/70 border-emerald-500 text-emerald-200 shadow-sm'
                  : 'bg-slate-900/60 border-slate-700/80 text-slate-400 hover:border-slate-500 hover:text-slate-200'
              }`}
            >
              <div
                className={`w-3.5 h-3.5 rounded flex items-center justify-center border ${
                  isSelected ? 'bg-emerald-500 border-emerald-400 text-slate-950' : 'border-slate-600'
                }`}
              >
                {isSelected && <Check className="w-2.5 h-2.5 stroke-[3]" />}
              </div>

              <span className="font-medium">{s.canonical_key}</span>

              {s.is_basic ? (
                <span className="text-[9px] px-1 py-0.2 rounded bg-sky-900/60 text-sky-300 font-mono">
                  B
                </span>
              ) : (
                <span className="text-[9px] px-1 py-0.2 rounded bg-purple-900/60 text-purple-300 font-mono">
                  E
                </span>
              )}

              <span className="font-mono text-[11px] text-slate-300 ml-1">
                {valStr}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
};
