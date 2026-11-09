import React, { useState, useMemo } from 'react';
import {
  AlertTriangle,
  Search,
  Filter,
  Clock,
  ArrowRight,
  ExternalLink,
  ShieldAlert,
  Info,
  HelpCircle,
  Calendar,
  Layers
} from 'lucide-react';
import incidentsFixtureData from '../fixtures/incidents_fixture.json';

export interface IncidentFeedItem {
  id: string;
  equipment_id: string;
  equipment_name: string;
  timestamp_start: string;
  timestamp_end: string;
  seek_timestamp: string;
  detection_state: 'DETECTED' | 'NOT_EVALUABLE' | 'AMBIGUOUS' | 'CONFLICTED';
  cause_state: string;
  data_state: string;
  model_state: string;
  rule_id: string;
  rule_name: string;
  severity_category: string;
  symptom_description: string;
  prerequisites_met: string[];
  missing_observability: string[];
  candidate_causes: Array<{ cause_id: string; name: string; status: string }>;
  recommended_action: string;
}

interface IncidentFeedPageProps {
  onNavigateToInvestigator: (assetId: string, timestamp: string) => void;
  onNavigateToIncidentDetail: (incidentId: string) => void;
}

export const IncidentFeedPage: React.FC<IncidentFeedPageProps> = ({
  onNavigateToInvestigator,
  onNavigateToIncidentDetail
}) => {
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [stateFilter, setStateFilter] = useState<string>('ALL');
  const [equipmentFilter, setEquipmentFilter] = useState<string>('ALL');

  const incidents: IncidentFeedItem[] = (incidentsFixtureData.items as IncidentFeedItem[]) || [];

  const filteredIncidents = useMemo(() => {
    return incidents.filter(inc => {
      if (stateFilter !== 'ALL' && inc.detection_state !== stateFilter) return false;
      if (equipmentFilter !== 'ALL' && inc.equipment_id !== equipmentFilter) return false;
      if (searchQuery.trim() !== '') {
        const q = searchQuery.toLowerCase();
        const matchesText =
          inc.rule_name.toLowerCase().includes(q) ||
          inc.symptom_description.toLowerCase().includes(q) ||
          inc.equipment_name.toLowerCase().includes(q) ||
          inc.id.toLowerCase().includes(q);
        if (!matchesText) return false;
      }
      return true;
    });
  }, [incidents, stateFilter, equipmentFilter, searchQuery]);

  const getStateBadge = (state: string) => {
    switch (state) {
      case 'DETECTED':
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-bold bg-rose-950/90 text-rose-300 border border-rose-700">
            <AlertTriangle className="w-3.5 h-3.5 mr-1 text-rose-400" />
            DETECTED (ОТКЛОНЕНИЕ)
          </span>
        );
      case 'CONFLICTED':
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-bold bg-amber-950/90 text-amber-300 border border-amber-700">
            <AlertTriangle className="w-3.5 h-3.5 mr-1 text-amber-400" />
            CONFLICTED (ПРОТИВОРЕЧИЕ)
          </span>
        );
      case 'AMBIGUOUS':
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-bold bg-purple-950/90 text-purple-300 border border-purple-700">
            <HelpCircle className="w-3.5 h-3.5 mr-1 text-purple-400" />
            AMBIGUOUS (НЕОДНОЗНАЧНО)
          </span>
        );
      case 'NOT_EVALUABLE':
      default:
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-bold bg-slate-800 text-slate-400 border border-slate-700">
            <Info className="w-3.5 h-3.5 mr-1" />
            NOT_EVALUABLE
          </span>
        );
    }
  };

  return (
    <div className="max-w-[1920px] mx-auto p-4 space-y-4 select-none">
      {/* Page Title & Context Header */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 shadow-md flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="flex items-center space-x-2">
            <ShieldAlert className="w-5 h-5 text-emerald-400" />
            <h1 className="text-base font-bold uppercase tracking-wider text-slate-100">
              Лента зарегистрированных инцидентов AHU
            </h1>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            События классифицированы по инженерным правилам без надуманных процентов вероятности неисправностей.
          </p>
        </div>

        <div className="flex items-center space-x-2 font-mono text-xs">
          <span className="px-2.5 py-1 rounded-md bg-slate-950 border border-slate-800 text-slate-300">
            Всего: <strong className="text-white">{incidents.length}</strong>
          </span>
          <span className="px-2.5 py-1 rounded-md bg-rose-950/60 border border-rose-800 text-rose-300">
            Активных: <strong>{incidents.filter(i => i.detection_state === 'DETECTED').length}</strong>
          </span>
        </div>
      </div>

      {/* Filters and Search Bar */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-3 shadow-md flex flex-wrap items-center justify-between gap-3">
        {/* Search */}
        <div className="flex items-center bg-slate-950 px-3 py-1.5 rounded-lg border border-slate-800 w-full sm:w-80">
          <Search className="w-4 h-4 text-slate-500 mr-2" />
          <input
            type="text"
            placeholder="Поиск по описанию или правилу..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="bg-transparent border-none text-xs text-slate-200 outline-none w-full placeholder:text-slate-500"
          />
        </div>

        {/* Status Filters */}
        <div className="flex flex-wrap items-center gap-1.5 text-xs">
          <span className="text-slate-500 text-[11px] font-mono mr-1">Статус:</span>
          {['ALL', 'DETECTED', 'AMBIGUOUS', 'CONFLICTED', 'NOT_EVALUABLE'].map(st => (
            <button
              key={st}
              onClick={() => setStateFilter(st)}
              className={`px-2.5 py-1 rounded font-mono transition-colors ${
                stateFilter === st
                  ? 'bg-emerald-500 text-slate-950 font-bold shadow-sm'
                  : 'bg-slate-800 text-slate-400 hover:text-white'
              }`}
            >
              {st === 'ALL' ? 'ВСЕ' : st}
            </button>
          ))}
        </div>

        {/* Equipment Filters */}
        <div className="flex items-center space-x-2 text-xs">
          <span className="text-slate-500 text-[11px] font-mono">Установка:</span>
          <select
            value={equipmentFilter}
            onChange={(e) => setEquipmentFilter(e.target.value)}
            className="bg-slate-950 text-slate-300 text-xs rounded border border-slate-800 px-2 py-1 outline-none"
          >
            <option value="ALL">Все установки</option>
            <option value="ahu-sd">LBNL SD-AHU 01</option>
            <option value="ahu-10">CSIRO AHU-10</option>
            <option value="ahu-09">CSIRO AHU-09</option>
          </select>
        </div>
      </div>

      {/* Incidents Cards List */}
      <div className="space-y-3">
        {filteredIncidents.length === 0 ? (
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-8 text-center text-slate-400 text-xs">
            Инцидентов с выбранными фильтрами не найдено.
          </div>
        ) : (
          filteredIncidents.map(inc => (
            <div
              key={inc.id}
              className="bg-slate-900 border border-slate-800 rounded-xl p-4 shadow-md hover:border-slate-700 transition-all space-y-3"
            >
              <div className="flex flex-wrap items-center justify-between gap-2 pb-2 border-b border-slate-800">
                <div className="flex items-center space-x-3">
                  <span className="font-mono font-bold text-xs text-emerald-400">{inc.id}</span>
                  <span className="text-xs font-semibold text-slate-200">{inc.equipment_name}</span>
                  <span className="text-[11px] font-mono text-slate-400 bg-slate-950 px-2 py-0.5 rounded border border-slate-800">
                    Категория: {inc.severity_category}
                  </span>
                </div>
                {getStateBadge(inc.detection_state)}
              </div>

              {/* Rule Name & Symptom */}
              <div>
                <div className="text-xs font-bold text-slate-100 flex items-center space-x-2">
                  <span className="text-amber-400 font-mono text-[11px]">{inc.rule_id}</span>
                  <span>—</span>
                  <span>{inc.rule_name}</span>
                </div>
                <p className="text-xs text-slate-300 mt-1 leading-relaxed">
                  {inc.symptom_description}
                </p>
              </div>

              {/* 4 Status Axes Badges */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-[11px] font-mono bg-slate-950/70 p-2 rounded-lg border border-slate-800">
                <div>
                  <span className="text-slate-500 block text-[9px] uppercase">Data State</span>
                  <span className="text-emerald-400 font-semibold">{inc.data_state}</span>
                </div>
                <div>
                  <span className="text-slate-500 block text-[9px] uppercase">Cause State</span>
                  <span className="text-amber-300 font-semibold">{inc.cause_state}</span>
                </div>
                <div>
                  <span className="text-slate-500 block text-[9px] uppercase">Model Scope</span>
                  <span className="text-cyan-300 font-semibold">{inc.model_state}</span>
                </div>
                <div>
                  <span className="text-slate-500 block text-[9px] uppercase">Интервал</span>
                  <span className="text-slate-300">{inc.timestamp_start.substring(11, 16)} – {inc.timestamp_end.substring(11, 16)}</span>
                </div>
              </div>

              {/* Missing Observability Note */}
              {inc.missing_observability.length > 0 && (
                <div className="text-[11px] text-amber-300/90 bg-amber-950/30 p-2 rounded border border-amber-900/50">
                  <span className="font-semibold text-amber-400">Ограничение наблюдаемости:</span> {inc.missing_observability.join(', ')}
                </div>
              )}

              {/* Recommended Action & Timeline Seek Button */}
              <div className="flex flex-wrap items-center justify-between gap-3 pt-2 border-t border-slate-800 text-xs">
                <div className="text-slate-400 max-w-2xl text-[11px]">
                  <strong className="text-slate-300">Рекомендованное действие:</strong> {inc.recommended_action}
                </div>

                <div className="flex items-center space-x-2">
                  <button
                    onClick={() => onNavigateToIncidentDetail(inc.id)}
                    className="px-3 py-1.5 rounded-lg text-xs font-medium bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition-colors flex items-center space-x-1"
                  >
                    <ExternalLink className="w-3.5 h-3.5 text-cyan-400" />
                    <span>Свидетельства</span>
                  </button>

                  <button
                    onClick={() => onNavigateToInvestigator(inc.equipment_id, inc.seek_timestamp)}
                    className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-emerald-600/30 text-emerald-300 border border-emerald-500 hover:bg-emerald-600/40 transition-colors flex items-center space-x-1.5 shadow-sm"
                  >
                    <span>Перейти на таймлайн</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};
