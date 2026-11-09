import React, { useState } from 'react';
import {
  ShieldAlert,
  CheckCircle2,
  XCircle,
  HelpCircle,
  AlertTriangle,
  Info,
  Layers,
  Wrench,
  ArrowRight,
  GitCommit,
  Network
} from 'lucide-react';

export interface HypothesisItem {
  id: string;
  code: string;
  name: string;
  evidence_status: string;
  confidence_statement: string;
  supporting_evidence: string[];
  contradicting_evidence: string[];
  missing_evidence: string[];
}

export interface UnexecutableCheckItem {
  check_id: string;
  name: string;
  reason_code: string;
  reason_ru: string;
  resolution: string;
}

export interface RecommendedActionItem {
  action_id: string;
  priority: 'HIGH' | 'MEDIUM' | 'LOW';
  title: string;
  instruction: string;
  preconditions: string;
  safety_note: string;
}

interface EvidenceInspectorCardProps {
  detectionState: 'DETECTED' | 'NOT_EVALUABLE' | 'AMBIGUOUS' | 'CONFLICTED';
  causeState: string;
  dataState: string;
  modelScope: string;
  ruleEvaluation: {
    rule_id: string;
    name: string;
    execution_status: string;
    evaluation_mode: string;
    scope_validity: string;
    threshold: string;
    observed_value: string;
    quality_status: string;
  };
  hypotheses: HypothesisItem[];
  unexecutableChecks: UnexecutableCheckItem[];
  recommendedActions: RecommendedActionItem[];
  causalityGraph?: {
    nodes: Array<{ id: string; label: string; type: string; status: string }>;
    links: Array<{ source: string; target: string; relation: string }>;
  };
}

export const EvidenceInspectorCard: React.FC<EvidenceInspectorCardProps> = ({
  detectionState,
  causeState,
  dataState,
  modelScope,
  ruleEvaluation,
  hypotheses,
  unexecutableChecks,
  recommendedActions,
  causalityGraph
}) => {
  const [activeTab, setActiveTab] = useState<'hypotheses' | 'unexecutable' | 'actions' | 'graph'>('hypotheses');
  const [selectedHypothesisId, setSelectedHypothesisId] = useState<string>(hypotheses[0]?.id || '');

  const getDetectionBadge = (state: string) => {
    switch (state) {
      case 'DETECTED':
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-bold bg-rose-950/80 text-rose-300 border border-rose-700">
            <AlertTriangle className="w-3.5 h-3.5 mr-1 text-rose-400" />
            ОТКЛОНЕНИЕ ОБНАРУЖЕНО
          </span>
        );
      case 'CONFLICTED':
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-bold bg-amber-950/80 text-amber-300 border border-amber-700">
            <AlertTriangle className="w-3.5 h-3.5 mr-1 text-amber-400" />
            ПРОТИВОРЕЧИЕ ДЕТЕКТОРОВ
          </span>
        );
      case 'AMBIGUOUS':
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-bold bg-purple-950/80 text-purple-300 border border-purple-700">
            <HelpCircle className="w-3.5 h-3.5 mr-1 text-purple-400" />
            НЕОДНОЗНАЧНОСТЬ ПРИЧИНЫ
          </span>
        );
      case 'NOT_EVALUABLE':
      default:
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-bold bg-slate-800 text-slate-400 border border-slate-700">
            <Info className="w-3.5 h-3.5 mr-1" />
            НЕ ПОДЛЕЖИТ ОЦЕНКЕ
          </span>
        );
    }
  };

  const selectedHypothesis = hypotheses.find(h => h.id === selectedHypothesisId) || hypotheses[0];

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 shadow-xl select-none flex flex-col h-full">
      {/* Header and 4 Independent Status Axes */}
      <div className="pb-3 border-b border-slate-800">
        <div className="flex items-center justify-between gap-2 mb-2">
          <div className="flex items-center space-x-2">
            <ShieldAlert className="w-4 h-4 text-emerald-400" />
            <h3 className="text-xs font-bold tracking-wider uppercase text-slate-200">
              Evidence Inspector (Инспектор свидетельств)
            </h3>
          </div>
          {getDetectionBadge(detectionState)}
        </div>

        {/* 4 Status Axes Badges */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-1.5 text-[11px] font-mono mt-2">
          <div className="bg-slate-950/80 px-2 py-1 rounded border border-slate-800">
            <span className="text-slate-500 block text-[9px] uppercase">Data State</span>
            <span className="text-emerald-400 font-semibold">{dataState}</span>
          </div>
          <div className="bg-slate-950/80 px-2 py-1 rounded border border-slate-800">
            <span className="text-slate-500 block text-[9px] uppercase">Cause State</span>
            <span className="text-amber-300 font-semibold">{causeState}</span>
          </div>
          <div className="bg-slate-950/80 px-2 py-1 rounded border border-slate-800">
            <span className="text-slate-500 block text-[9px] uppercase">Model Scope</span>
            <span className="text-cyan-300 font-semibold">{modelScope}</span>
          </div>
          <div className="bg-slate-950/80 px-2 py-1 rounded border border-slate-800">
            <span className="text-slate-500 block text-[9px] uppercase">Ground Truth</span>
            <span className="text-slate-400 font-semibold">Изолирован</span>
          </div>
        </div>
      </div>

      {/* Evaluated Rule Context Strip */}
      <div className="mt-3 p-2.5 rounded-lg bg-slate-950/70 border border-slate-800 text-xs">
        <div className="flex items-center justify-between text-slate-400 font-semibold mb-1">
          <span className="text-amber-400 font-mono text-[11px]">{ruleEvaluation.rule_id}</span>
          <span className="px-1.5 py-0.2 rounded bg-rose-950/80 text-rose-300 font-mono text-[10px] border border-rose-800">
            {ruleEvaluation.execution_status}
          </span>
        </div>
        <div className="text-slate-300 font-medium text-xs mb-1.5">{ruleEvaluation.name}</div>
        <div className="grid grid-cols-2 gap-2 text-[11px] text-slate-400 pt-1.5 border-t border-slate-800/80">
          <div>
            <span className="text-slate-500">Порог:</span> <span className="font-mono text-slate-300">{ruleEvaluation.threshold}</span>
          </div>
          <div>
            <span className="text-slate-500">Факт:</span> <span className="font-mono text-rose-400 font-semibold">{ruleEvaluation.observed_value}</span>
          </div>
        </div>
      </div>

      {/* Internal Tabs Navigation */}
      <div className="flex items-center space-x-1 mt-3 border-b border-slate-800 pb-2 text-xs">
        <button
          onClick={() => setActiveTab('hypotheses')}
          className={`px-2.5 py-1 rounded-md font-medium transition-colors ${
            activeTab === 'hypotheses'
              ? 'bg-slate-800 text-emerald-400 border border-slate-700 shadow-sm'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          Гипотезы причин ({hypotheses.length})
        </button>

        <button
          onClick={() => setActiveTab('unexecutable')}
          className={`px-2.5 py-1 rounded-md font-medium transition-colors ${
            activeTab === 'unexecutable'
              ? 'bg-slate-800 text-emerald-400 border border-slate-700 shadow-sm'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          Неисполняемые проверки ({unexecutableChecks.length})
        </button>

        <button
          onClick={() => setActiveTab('actions')}
          className={`px-2.5 py-1 rounded-md font-medium transition-colors ${
            activeTab === 'actions'
              ? 'bg-slate-800 text-emerald-400 border border-slate-700 shadow-sm'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          Действия инженера ({recommendedActions.length})
        </button>

        {causalityGraph && (
          <button
            onClick={() => setActiveTab('graph')}
            className={`px-2.5 py-1 rounded-md font-medium transition-colors flex items-center space-x-1 ${
              activeTab === 'graph'
                ? 'bg-slate-800 text-emerald-400 border border-slate-700 shadow-sm'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Network className="w-3.5 h-3.5" />
            <span>Граф связей</span>
          </button>
        )}
      </div>

      {/* Tab Content */}
      <div className="flex-1 overflow-y-auto mt-3 pr-1 space-y-3">
        {/* TAB 1: HYPOTHESES */}
        {activeTab === 'hypotheses' && (
          <div className="space-y-3">
            {/* Hypotheses Selector Chips */}
            <div className="flex flex-wrap gap-1.5">
              {hypotheses.map(hyp => (
                <button
                  key={hyp.id}
                  onClick={() => setSelectedHypothesisId(hyp.id)}
                  className={`px-2 py-1 rounded text-xs font-mono transition-colors text-left ${
                    selectedHypothesis?.id === hyp.id
                      ? 'bg-emerald-950/80 text-emerald-300 border border-emerald-700 font-semibold'
                      : 'bg-slate-950/60 text-slate-400 border border-slate-800 hover:text-slate-300'
                  }`}
                >
                  {hyp.code}
                </button>
              ))}
            </div>

            {selectedHypothesis && (
              <div className="p-3 bg-slate-950/80 rounded-lg border border-slate-800 space-y-2.5">
                <div>
                  <div className="text-xs font-bold text-slate-200">{selectedHypothesis.name}</div>
                  <div className="text-[11px] text-amber-300/90 italic mt-0.5">
                    {selectedHypothesis.confidence_statement}
                  </div>
                </div>

                {/* Supporting evidence */}
                {selectedHypothesis.supporting_evidence.length > 0 && (
                  <div>
                    <div className="text-[11px] font-semibold text-emerald-400 flex items-center space-x-1 mb-1">
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      <span>Подтверждающие наблюдения:</span>
                    </div>
                    <ul className="text-xs text-slate-300 space-y-1 list-disc list-inside">
                      {selectedHypothesis.supporting_evidence.map((item, idx) => (
                        <li key={idx} className="leading-snug">{item}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Contradicting evidence */}
                {selectedHypothesis.contradicting_evidence.length > 0 && (
                  <div>
                    <div className="text-[11px] font-semibold text-rose-400 flex items-center space-x-1 mb-1">
                      <XCircle className="w-3.5 h-3.5" />
                      <span>Опровергающие наблюдения:</span>
                    </div>
                    <ul className="text-xs text-slate-300 space-y-1 list-disc list-inside">
                      {selectedHypothesis.contradicting_evidence.map((item, idx) => (
                        <li key={idx} className="leading-snug">{item}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Missing evidence */}
                {selectedHypothesis.missing_evidence.length > 0 && (
                  <div>
                    <div className="text-[11px] font-semibold text-amber-400 flex items-center space-x-1 mb-1">
                      <HelpCircle className="w-3.5 h-3.5" />
                      <span>Отсутствующие свидетельства (не наблюдаемы):</span>
                    </div>
                    <ul className="text-xs text-slate-400 space-y-1 list-disc list-inside">
                      {selectedHypothesis.missing_evidence.map((item, idx) => (
                        <li key={idx} className="leading-snug">{item}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* TAB 2: UNEXECUTABLE CHECKS */}
        {activeTab === 'unexecutable' && (
          <div className="space-y-2">
            {unexecutableChecks.map(check => (
              <div key={check.check_id} className="p-2.5 rounded-lg bg-slate-950/80 border border-slate-800 text-xs">
                <div className="font-semibold text-slate-200">{check.name}</div>
                <div className="text-[11px] font-mono text-rose-400/90 mt-1">
                  Причина блокировки: {check.reason_code}
                </div>
                <div className="text-[11px] text-slate-400 mt-0.5">{check.reason_ru}</div>
                <div className="text-[11px] text-emerald-400 mt-1 pt-1 border-t border-slate-850">
                  <span className="font-semibold">Как устранить:</span> {check.resolution}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* TAB 3: RECOMMENDED ACTIONS */}
        {activeTab === 'actions' && (
          <div className="space-y-2.5">
            <div className="text-[11px] text-slate-400 italic">
              Рекомендации сформированы строго из разрешенного белого списка (whitelist) процедур инспекции:
            </div>
            {recommendedActions.map(act => (
              <div key={act.action_id} className="p-3 rounded-lg bg-slate-950/80 border border-slate-800 text-xs space-y-1.5">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-slate-200 flex items-center space-x-1.5">
                    <Wrench className="w-3.5 h-3.5 text-emerald-400" />
                    <span>{act.title}</span>
                  </span>
                  <span className="px-1.5 py-0.2 rounded font-mono text-[10px] font-semibold bg-emerald-950 text-emerald-300 border border-emerald-700">
                    Приоритет: {act.priority}
                  </span>
                </div>
                <div className="text-slate-300">{act.instruction}</div>
                <div className="text-[11px] text-slate-400">
                  <span className="text-slate-500 font-semibold">Условия проверки:</span> {act.preconditions}
                </div>
                <div className="text-[11px] text-amber-400/90">
                  <span className="font-semibold">Безопасность:</span> {act.safety_note}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* TAB 4: INTERACTIVE CAUSALITY GRAPH */}
        {activeTab === 'graph' && causalityGraph && (
          <div className="p-3 bg-slate-950/90 rounded-lg border border-slate-800 text-xs space-y-2">
            <div className="text-slate-400 text-[11px] font-semibold mb-2">
              Граф свидетельств и гипотез (EvidenceV1 Structure):
            </div>
            <div className="space-y-2">
              {causalityGraph.links.map((link, idx) => {
                const srcNode = causalityGraph.nodes.find(n => n.id === link.source);
                const tgtNode = causalityGraph.nodes.find(n => n.id === link.target);
                return (
                  <div key={idx} className="flex items-center justify-between bg-slate-900 p-2 rounded border border-slate-800 text-[11px]">
                    <span className="font-mono text-slate-300 truncate max-w-[40%]">
                      {srcNode?.label || link.source}
                    </span>
                    <span className={`px-1.5 py-0.5 rounded text-[10px] font-mono font-bold ${
                      link.relation === 'SUPPORTS'
                        ? 'bg-emerald-950 text-emerald-300 border border-emerald-800'
                        : 'bg-amber-950 text-amber-300 border border-amber-800'
                    }`}>
                      {link.relation}
                    </span>
                    <span className="font-mono text-slate-300 truncate max-w-[40%] text-right">
                      {tgtNode?.label || link.target}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
