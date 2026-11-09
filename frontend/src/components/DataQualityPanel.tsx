import React, { useState } from 'react';
import { ShieldCheck, AlertTriangle, Play, ChevronDown, ChevronUp, Database } from 'lucide-react';
import { DataQualityReport, DiagnosticEventItem } from '../types/api';

interface DataQualityPanelProps {
  qualityReport: DataQualityReport | null;
  events: DiagnosticEventItem[];
  onRunRules: () => void;
  isRunningRules: boolean;
  sourceFaultLabel?: string;
  sourceFaultLabelType?: string;
}

export const DataQualityPanel: React.FC<DataQualityPanelProps> = ({
  qualityReport,
  events,
  onRunRules,
  isRunningRules,
  sourceFaultLabel,
  sourceFaultLabelType
}) => {
  const [expandedEventId, setExpandedEventId] = useState<string | null>(null);

  return (
    <div className="bg-slate-800/80 border border-slate-700/80 rounded-xl p-4 shadow-xl backdrop-blur-sm">
      <div className="flex items-center justify-between mb-3 border-b border-slate-700/60 pb-2">
        <div className="flex items-center space-x-2">
          <ShieldCheck className="w-5 h-5 text-emerald-400" />
          <h2 className="text-sm font-bold tracking-wide uppercase text-slate-200">
            Качество данных и диагностический Baseline
          </h2>
        </div>

        <button
          onClick={onRunRules}
          disabled={isRunningRules}
          className="flex items-center space-x-1 px-3 py-1 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-slate-950 font-semibold text-xs rounded-lg transition-colors shadow-sm"
        >
          {isRunningRules ? (
            <>
              <span className="w-3.5 h-3.5 border-2 border-slate-950 border-t-transparent rounded-full animate-spin" />
              <span>Расчёт...</span>
            </>
          ) : (
            <>
              <Play className="w-3.5 h-3.5 fill-current" />
              <span>Запуск правил</span>
            </>
          )}
        </button>
      </div>

      {/* Ground Truth Banner (Strictly separated from system detections!) */}
      <div className="mb-4 p-2.5 rounded-lg bg-slate-900/90 border border-slate-700/80 flex items-center justify-between text-xs">
        <div className="flex items-center space-x-2">
          <Database className="w-4 h-4 text-sky-400 shrink-0" />
          <div>
            <span className="text-slate-400">Метка источника датасета (Ground Truth): </span>
            <span className="font-mono font-semibold text-sky-300">
              {sourceFaultLabel || 'Истинная метка отсутствует'}
            </span>
            {sourceFaultLabelType && (
              <span className="ml-2 px-1.5 py-0.5 rounded bg-sky-950 border border-sky-800 text-[10px] text-sky-300">
                {sourceFaultLabelType}
              </span>
            )}
          </div>
        </div>
        <span className="text-[10px] text-slate-400 italic">
          *Не используется алгоритмами детекции
        </span>
      </div>

      {/* Data Quality Metrics Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mb-4">
        {qualityReport?.metrics.map((m, idx) => {
          const isOk = m.status === 'OK';
          const isWarning = m.status === 'WARNING';
          return (
            <div
              key={idx}
              className={`p-2.5 rounded-lg border text-xs ${
                isOk
                  ? 'bg-emerald-950/20 border-emerald-500/30 text-slate-300'
                  : isWarning
                  ? 'bg-amber-950/30 border-amber-500/40 text-slate-200'
                  : 'bg-rose-950/30 border-rose-500/40 text-slate-200'
              }`}
            >
              <div className="flex items-center justify-between mb-1">
                <span className="font-semibold text-slate-200">{m.name}</span>
                <span
                  className={`text-[10px] font-bold px-1.5 py-0.2 rounded ${
                    isOk
                      ? 'bg-emerald-500/20 text-emerald-300'
                      : isWarning
                      ? 'bg-amber-500/20 text-amber-300'
                      : 'bg-rose-500/20 text-rose-300'
                  }`}
                >
                  {m.status}
                </span>
              </div>
              <div className="text-[11px] text-slate-400 truncate">{m.description}</div>
              <div className="mt-1 font-mono font-medium text-emerald-300">{m.value}</div>
            </div>
          );
        })}
      </div>

      {/* Detected Events List */}
      <div>
        <div className="flex items-center justify-between text-xs text-slate-400 mb-2">
          <span>События диагностики и аномалий ({events.length}):</span>
          <span className="text-[11px] text-slate-400">
            Правила: {events.filter(e => e.conclusion_type !== 'VIRTUAL_SENSOR_RESIDUAL').length} | ML: {events.filter(e => e.conclusion_type === 'VIRTUAL_SENSOR_RESIDUAL').length}
          </span>
        </div>

        {events.length === 0 ? (
          <div className="p-3 bg-slate-900/50 rounded-lg text-center text-xs text-slate-400">
            События не зафиксированы или алгоритмы ещё не запускались. Нажмите «Запуск правил» или «Запуск ML-детекции».
          </div>
        ) : (
          <div className="space-y-2 max-h-[220px] overflow-y-auto pr-1">
            {events.map((ev, idx) => {
              const isCrit = ev.severity === 'CRITICAL';
              const isML = ev.conclusion_type === 'VIRTUAL_SENSOR_RESIDUAL';
              const isExpanded = expandedEventId === ev.id;
              return (
                <div
                  key={`${ev.id}-${idx}`}
                  className={`p-2.5 rounded-lg border text-xs transition-colors ${
                    isML
                      ? 'bg-rose-950/25 border-rose-500/40 text-rose-200'
                      : isCrit
                      ? 'bg-amber-950/25 border-amber-500/40 text-amber-200'
                      : 'bg-slate-900/40 border-slate-700/60 text-slate-200'
                  }`}
                >
                  <div
                    className="flex items-center justify-between cursor-pointer"
                    onClick={() => setExpandedEventId(isExpanded ? null : ev.id)}
                  >
                    <div className="flex items-center space-x-2">
                      <AlertTriangle className={`w-4 h-4 shrink-0 ${isML ? 'text-rose-400' : 'text-amber-400'}`} />
                      <span className="font-bold">{ev.rule_id}</span>
                      <span className={`text-[10px] px-1.5 py-0.2 rounded font-mono font-semibold ${
                        isML
                          ? 'bg-rose-900/60 text-rose-300 border border-rose-700'
                          : 'bg-slate-800 text-slate-300 border border-slate-700'
                      }`}>
                        {isML ? 'ML: VIRTUAL_SENSOR' : ev.conclusion_type}
                      </span>
                    </div>

                    <div className="flex items-center space-x-2">
                      <span className="font-mono text-[11px] text-slate-300">
                        {ev.started_at} → {ev.ended_at}
                      </span>
                      {isExpanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                    </div>
                  </div>

                  {isExpanded && ev.evidence_json && (
                    <div className="mt-2 pt-2 border-t border-slate-700/60 font-mono text-[11px] bg-slate-950/80 p-2.5 rounded text-slate-300 space-y-1">
                      {ev.evidence_json.scientific_disclaimer && (
                        <div className="mb-2 p-2 rounded bg-rose-950/40 border border-rose-800/40 text-rose-300 font-sans text-[11px]">
                          <strong>Диагностическое ограничение:</strong> {ev.evidence_json.scientific_disclaimer}
                        </div>
                      )}
                      <pre className="whitespace-pre-wrap">
                        {JSON.stringify(ev.evidence_json, null, 2)}
                      </pre>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};
