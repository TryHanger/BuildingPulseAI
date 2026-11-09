import React, { useState } from 'react';
import {
  Sliders,
  CheckCircle2,
  AlertCircle,
  HelpCircle,
  RefreshCw,
  Info,
  ShieldCheck,
  Check,
  X
} from 'lucide-react';

export interface SensorLabChannel {
  canonical_id: string;
  name_ru: string;
  unit: string;
  tier: 'BASIC' | 'EXTRA';
  recorded_in_source: boolean;
  verified_semantics: boolean;
  status: string;
}

export interface SensorLabProfile {
  id: string;
  name: string;
  description: string;
  channels: string[];
  cost_estimate: string;
  isolation_capability: string;
}

interface SensorLabPanelProps {
  profiles: SensorLabProfile[];
  channelMatrix: SensorLabChannel[];
  activeProfileId: string;
  onSelectProfile: (profileId: string) => void;
  onRequestRecomputation?: () => void;
  isRecomputing?: boolean;
}

export const SensorLabPanel: React.FC<SensorLabPanelProps> = ({
  profiles,
  channelMatrix,
  activeProfileId,
  onSelectProfile,
  onRequestRecomputation,
  isRecomputing = false
}) => {
  const activeProfile = profiles.find(p => p.id === activeProfileId) || profiles[0];

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 shadow-xl select-none space-y-4">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between pb-3 border-b border-slate-800 gap-2">
        <div>
          <div className="flex items-center space-x-2">
            <Sliders className="w-4 h-4 text-emerald-400" />
            <h3 className="text-xs font-bold tracking-wider uppercase text-slate-200">
              Sensor Lab (Лаборатория панели наблюдаемости)
            </h3>
          </div>
          <div className="text-[11px] text-slate-400 mt-0.5">
            Переключение между профилями каналов. Фронтенд не выполняет вычислений — расчеты только через backend.
          </div>
        </div>

        {onRequestRecomputation && (
          <button
            onClick={onRequestRecomputation}
            disabled={isRecomputing}
            className="px-3 py-1.5 rounded-lg text-xs font-medium flex items-center space-x-1.5 bg-emerald-600/30 text-emerald-300 border border-emerald-500 hover:bg-emerald-600/40 transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isRecomputing ? 'animate-spin' : ''}`} />
            <span>{isRecomputing ? 'Пересчет...' : 'Запросить пересчет на сервере'}</span>
          </button>
        )}
      </div>

      {/* Profile Selector Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
        {profiles.map(prof => {
          const isSelected = prof.id === activeProfileId;
          return (
            <div
              key={prof.id}
              onClick={() => onSelectProfile(prof.id)}
              className={`p-3 rounded-lg border cursor-pointer transition-all ${
                isSelected
                  ? 'bg-emerald-950/60 border-emerald-500 shadow-md ring-1 ring-emerald-500/50'
                  : 'bg-slate-950/60 border-slate-800 hover:border-slate-700'
              }`}
            >
              <div className="flex items-center justify-between mb-1.5">
                <span className={`text-xs font-bold ${isSelected ? 'text-emerald-300' : 'text-slate-200'}`}>
                  {prof.name}
                </span>
                {isSelected && <Check className="w-4 h-4 text-emerald-400" />}
              </div>
              <p className="text-[11px] text-slate-400 line-clamp-2 mb-2">{prof.description}</p>
              <div className="text-[10px] space-y-0.5 pt-1.5 border-t border-slate-800">
                <div className="text-slate-500">
                  Оценка затрат: <span className="text-slate-300">{prof.cost_estimate}</span>
                </div>
                <div className="text-slate-500">
                  Разрешимость: <span className="text-amber-300">{prof.isolation_capability}</span>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Channel Availability Matrix */}
      <div className="bg-slate-950/70 rounded-lg border border-slate-800 overflow-hidden">
        <div className="px-3 py-2 bg-slate-950 border-b border-slate-800 flex items-center justify-between text-xs font-semibold text-slate-300">
          <span>Матрица доступности и семантической валидности каналов</span>
          <span className="text-[11px] font-mono text-slate-400">
            Включено в текущий профиль: {activeProfile?.channels.length || 0}
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-900/80 text-slate-400 font-mono text-[11px] border-b border-slate-800">
              <tr>
                <th className="py-2 px-3">Канонический ID</th>
                <th className="py-2 px-3">Наименование</th>
                <th className="py-2 px-3">Категория</th>
                <th className="py-2 px-3">Записан в источнике</th>
                <th className="py-2 px-3">Семантика верифицирована</th>
                <th className="py-2 px-3">Статус в профиле</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 font-mono text-slate-300">
              {channelMatrix.map(ch => {
                const isIncludedInProfile = activeProfile?.channels.includes(ch.canonical_id);
                return (
                  <tr key={ch.canonical_id} className={isIncludedInProfile ? 'bg-emerald-950/20' : 'opacity-70'}>
                    <td className="py-2 px-3 font-bold text-slate-200">{ch.canonical_id}</td>
                    <td className="py-2 px-3 font-sans text-slate-300">{ch.name_ru}</td>
                    <td className="py-2 px-3">
                      <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                        ch.tier === 'BASIC'
                          ? 'bg-blue-950 text-blue-300 border border-blue-800'
                          : 'bg-purple-950 text-purple-300 border border-purple-800'
                      }`}>
                        {ch.tier}
                      </span>
                    </td>
                    <td className="py-2 px-3">
                      {ch.recorded_in_source ? (
                        <span className="text-emerald-400 flex items-center space-x-1">
                          <Check className="w-3.5 h-3.5" />
                          <span>ДА</span>
                        </span>
                      ) : (
                        <span className="text-rose-400 flex items-center space-x-1">
                          <X className="w-3.5 h-3.5" />
                          <span>НЕТ</span>
                        </span>
                      )}
                    </td>
                    <td className="py-2 px-3">
                      {ch.verified_semantics ? (
                        <span className="text-emerald-400 flex items-center space-x-1">
                          <Check className="w-3.5 h-3.5" />
                          <span>ПОДТВЕРЖДЕНА</span>
                        </span>
                      ) : (
                        <span className="text-amber-400 flex items-center space-x-1">
                          <AlertCircle className="w-3.5 h-3.5" />
                          <span>НЕ ПОДТВЕРЖДЕНА</span>
                        </span>
                      )}
                    </td>
                    <td className="py-2 px-3">
                      {isIncludedInProfile ? (
                        <span className="text-emerald-400 font-bold">АКТИВЕН В ПРОФИЛЕ</span>
                      ) : (
                        <span className="text-slate-500 italic">Исключен</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
