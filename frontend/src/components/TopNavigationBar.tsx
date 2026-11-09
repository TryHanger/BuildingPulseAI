import React from 'react';
import {
  Activity,
  AlertTriangle,
  Flame,
  LayoutDashboard,
  Cpu,
  Layers,
  FlaskConical,
  ExternalLink,
  ShieldCheck,
  Building
} from 'lucide-react';

export type AppViewRoute =
  | 'investigator'
  | 'incidents'
  | 'incident-detail'
  | 'research'
  | 'virtual-sensor-research'
  | 'field-evidence'
  | 'monitoring'
  | 'diagnostics';

export type ProvenanceKind = 'SIMULATED_BENCHMARK' | 'LEGACY_ANALYSIS' | 'DEMO_FIXTURE' | 'REAL_BMS_REPORTED' | 'RESEARCH_EVIDENCE';

interface TopNavigationBarProps {
  currentRoute: AppViewRoute;
  onNavigate: (route: AppViewRoute, param?: string) => void;
  activeAssetId?: string;
  provenanceKind: ProvenanceKind;
  runtimeDemo?: boolean;
  g36Benchmark?: boolean;
  onSelectProvenance?: (kind: ProvenanceKind) => void;
  unresolvedIncidentsCount?: number;
}

export const TopNavigationBar: React.FC<TopNavigationBarProps> = ({
  currentRoute,
  onNavigate,
  activeAssetId = 'ahu-sd',
  provenanceKind,
  runtimeDemo,
  g36Benchmark,
  onSelectProvenance,
  unresolvedIncidentsCount = 3
}) => {
  const getProvenanceBadge = () => {
    switch (provenanceKind) {
      case 'SIMULATED_BENCHMARK':
        return (
          <span className="inline-flex items-center px-2.5 py-1 rounded-md text-xs font-semibold bg-blue-950/80 text-blue-300 border border-blue-700/80 shadow-sm">
            <span className="w-1.5 h-1.5 rounded-full bg-blue-400 mr-1.5 animate-pulse"></span>
            {g36Benchmark ? 'G36 · Simulation' : 'LBNL SD-AHU · Simulation'}
          </span>
        );
      case 'REAL_BMS_REPORTED':
        return <span className="text-xs text-sky-200">REAL_BMS_REPORTED · Stage09</span>;
      case 'RESEARCH_EVIDENCE':
        return <span className="text-xs text-sky-200">BP-15 · RESEARCH_ONLY</span>;
      case 'LEGACY_ANALYSIS':
        return <span className="text-xs text-slate-300">LEGACY_ANALYSIS</span>;
      case 'DEMO_FIXTURE':
      default:
        return (
          <span className="inline-flex items-center px-2.5 py-1 rounded-md text-xs font-semibold bg-amber-950/80 text-amber-300 border border-amber-700/80 shadow-sm">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-400 mr-1.5"></span>
            {runtimeDemo ? 'Синтетический источник G4' : 'Demo Fixture (UI_MOCK_V0)'}
          </span>
        );
    }
  };

  return (
    <header className="bg-slate-900 border-b border-slate-800 text-slate-100 sticky top-0 z-50 select-none shadow-md">
      <div className="max-w-[1920px] mx-auto px-4 py-2.5 flex flex-wrap items-center justify-between gap-3">
        {/* Brand & Project Identity */}
        <div className="flex items-center space-x-3">
          <div className="w-9 h-9 rounded-lg bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400 shadow-inner">
            <Activity className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <span className="font-bold text-base tracking-tight text-white">
                BuildingPulse <span className="text-emerald-400">AI</span>
              </span>
              <span className="px-2 py-0.5 rounded text-[11px] font-mono bg-slate-800 text-slate-300 border border-slate-700">
                v0.7.1-stage7.1
              </span>
            </div>
            <div className="text-[11px] text-slate-400 hidden sm:block">
              Интеллектуальная диагностика инженерных систем AHU
            </div>
          </div>
        </div>

        {/* Provenance Badge & Environment Switcher */}
        <div className="flex items-center space-x-2">
          {getProvenanceBadge()}
          {onSelectProvenance && (
            <select
              aria-label="Источник данных"
              value={provenanceKind}
              onChange={(e) => onSelectProvenance(e.target.value as ProvenanceKind)}
              className="bg-slate-800 text-slate-200 text-xs rounded border border-slate-700 px-2 py-1 outline-none focus:border-emerald-500 cursor-pointer"
            >
              <option value="SIMULATED_BENCHMARK">LBNL Simulation</option>
              <option value="DEMO_FIXTURE">Demo Fixture</option>
            </select>
          )}
        </div>

        {/* Primary Unified Navigation */}
        <nav className="flex max-w-full flex-wrap items-center gap-1 py-1">
          <button
            onClick={() => onNavigate('investigator', activeAssetId)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium flex items-center space-x-1.5 transition-colors ${
              currentRoute === 'investigator'
                ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 shadow-sm'
                : 'text-slate-300 hover:text-white hover:bg-slate-800 border border-transparent'
            }`}
          >
            <Layers className="w-4 h-4 text-emerald-400" />
            <span>AHU Investigator</span>
          </button>

          <button
            onClick={() => onNavigate('incidents')}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium flex items-center space-x-1.5 transition-colors relative ${
              currentRoute === 'incidents' || currentRoute === 'incident-detail'
                ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 shadow-sm'
                : 'text-slate-300 hover:text-white hover:bg-slate-800 border border-transparent'
            }`}
          >
            <AlertTriangle className="w-4 h-4 text-amber-400" />
            <span>{provenanceKind === 'DEMO_FIXTURE' ? 'Инциденты · DEMO' : 'Инциденты · LBNL'}</span>
            {unresolvedIncidentsCount > 0 && (
              <span className="ml-1 px-1.5 py-0.2 rounded-full text-[10px] font-mono font-bold bg-amber-500/20 text-amber-300 border border-amber-500/40">
                {unresolvedIncidentsCount}
              </span>
            )}
          </button>

          <button
            onClick={() => onNavigate('diagnostics')}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium flex items-center space-x-1.5 transition-colors ${
              currentRoute === 'diagnostics'
                ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 shadow-sm'
                : 'text-slate-300 hover:text-white hover:bg-slate-800 border border-transparent'
            }`}
          >
            <Cpu className="w-4 h-4 text-cyan-400" />
            <span>Диагностика (Stage 4)</span>
          </button>

          <button
            onClick={() => onNavigate('research')}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium flex items-center space-x-1.5 transition-colors ${
              (currentRoute === 'research' || currentRoute === 'virtual-sensor-research' || currentRoute === 'field-evidence')
                ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 shadow-sm'
                : 'text-slate-300 hover:text-white hover:bg-slate-800 border border-transparent'
            }`}
          >
            <FlaskConical className="w-4 h-4 text-purple-400" />
            <span>Научный Хаб</span>
          </button>

          <button
            onClick={() => onNavigate('monitoring')}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium flex items-center space-x-1.5 transition-colors ${
              currentRoute === 'monitoring'
                ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 shadow-sm'
                : 'text-slate-300 hover:text-white hover:bg-slate-800 border border-transparent'
            }`}
          >
            <LayoutDashboard className="w-4 h-4 text-slate-400" />
            <span>Мониторинг (Stage 1)</span>
          </button>
        </nav>
      </div>
    </header>
  );
};
