import React from 'react';
import {
  ArrowLeft,
  ShieldAlert,
  ArrowRight,
  Clock,
  Wrench,
  CheckCircle2,
  XCircle,
  HelpCircle,
  AlertTriangle,
  Network
} from 'lucide-react';
import { EvidenceInspectorCard } from '../components/EvidenceInspectorCard';
import incidentsFixtureData from '../fixtures/incidents_fixture.json';
import evidenceFixtureData from '../fixtures/evidence_fixture.json';

interface IncidentDetailPageProps {
  incidentId: string;
  onBack: () => void;
  onNavigateToInvestigator: (assetId: string, timestamp: string) => void;
}

export const IncidentDetailPage: React.FC<IncidentDetailPageProps> = ({
  incidentId,
  onBack,
  onNavigateToInvestigator
}) => {
  const incidents = incidentsFixtureData.items;
  const currentIncident = incidents.find(i => i.id === incidentId) || incidents[0];

  return (
    <div className="max-w-[1920px] mx-auto p-4 space-y-4 select-none">
      {/* Top Action Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 bg-slate-900 border border-slate-800 rounded-xl p-3 shadow-md">
        <button
          onClick={onBack}
          className="px-3 py-1.5 rounded-lg text-xs font-medium bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition-colors flex items-center space-x-1.5"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Назад к списку инцидентов</span>
        </button>

        <div className="flex items-center space-x-2">
          <span className="font-mono text-xs text-slate-400">Инцидент:</span>
          <span className="font-mono font-bold text-xs text-emerald-400">{currentIncident.id}</span>
        </div>

        <button
          onClick={() => onNavigateToInvestigator(currentIncident.equipment_id, currentIncident.seek_timestamp)}
          className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-emerald-600/30 text-emerald-300 border border-emerald-500 hover:bg-emerald-600/40 transition-colors flex items-center space-x-1.5 shadow-sm"
        >
          <span>Перейти к AHU мнемосхеме и таймлайну</span>
          <ArrowRight className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* Main Evidence Inspector Card */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Left Column: Summary of Incident */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 shadow-xl space-y-4">
          <div>
            <div className="text-xs font-mono text-amber-400">{currentIncident.rule_id}</div>
            <h2 className="text-sm font-bold text-slate-100 mt-1">{currentIncident.rule_name}</h2>
            <p className="text-xs text-slate-300 mt-2 leading-relaxed">
              {currentIncident.symptom_description}
            </p>
          </div>

          <div className="p-3 bg-slate-950/80 rounded-lg border border-slate-800 space-y-2 text-xs">
            <div className="text-slate-400 font-semibold text-[11px] uppercase tracking-wider">
              Временной интервал инцидента
            </div>
            <div className="flex justify-between text-slate-300 font-mono text-[11px]">
              <span>Начало:</span> <span>{currentIncident.timestamp_start}</span>
            </div>
            <div className="flex justify-between text-slate-300 font-mono text-[11px]">
              <span>Окончание:</span> <span>{currentIncident.timestamp_end}</span>
            </div>
            <div className="flex justify-between text-amber-300 font-mono text-[11px]">
              <span>Момент отсчета:</span> <span>{currentIncident.seek_timestamp}</span>
            </div>
          </div>

          <div className="p-3 bg-slate-950/80 rounded-lg border border-slate-800 space-y-2 text-xs">
            <div className="text-slate-400 font-semibold text-[11px] uppercase tracking-wider">
              Выполненные предварительные условия
            </div>
            <ul className="text-xs text-slate-300 space-y-1 list-disc list-inside">
              {currentIncident.prerequisites_met.map((prereq, idx) => (
                <li key={idx} className="font-mono text-[11px]">{prereq}</li>
              ))}
            </ul>
          </div>
        </div>

        {/* Right 2 Columns: Full Evidence Inspector Component */}
        <div className="lg:col-span-2">
          <EvidenceInspectorCard
            detectionState={currentIncident.detection_state as 'DETECTED' | 'NOT_EVALUABLE' | 'AMBIGUOUS' | 'CONFLICTED'}
            causeState={currentIncident.cause_state}
            dataState={currentIncident.data_state}
            modelScope={currentIncident.model_state}
            ruleEvaluation={evidenceFixtureData.rule_evaluation}
            hypotheses={evidenceFixtureData.hypotheses}
            unexecutableChecks={evidenceFixtureData.unexecutable_checks}
            recommendedActions={evidenceFixtureData.recommended_actions_whitelist as any}
            causalityGraph={evidenceFixtureData.causality_graph}
          />
        </div>
      </div>
    </div>
  );
};
