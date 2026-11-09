import React, { useState, useEffect } from 'react';
import { TopNavigationBar, AppViewRoute, ProvenanceKind } from './components/TopNavigationBar';
import { G36BenchmarkPage } from './pages/G36BenchmarkPage';
import { RuntimeInvestigatorPage } from './pages/RuntimeInvestigatorPage';
import { AHUInvestigatorPage } from './pages/AHUInvestigatorPage';
import { demoDatasetId } from './components/InvestigationEvidence';
import { RuntimeIncidentPage } from './pages/RuntimeIncidentPage';
import { IncidentFeedPage } from './pages/IncidentFeedPage';
import { IncidentDetailPage } from './pages/IncidentDetailPage';
import { MonitoringPage } from './pages/MonitoringPage';
import { DiagnosticsPage } from './pages/DiagnosticsPage';
import { ResearchPage } from './pages/ResearchPage';
import { VirtualSensorResearchPage } from './pages/VirtualSensorResearchPage';

import { FieldEvidencePage } from './pages/FieldEvidencePage';

export function App() {
  // Parse initial route from window.location.pathname
  const parseCurrentPath = (): { route: AppViewRoute; id?: string; timestamp?: string; datasetId?: string } => {
    if (typeof window === 'undefined') return { route: 'investigator', id: 'ahu-sd' };
    const path = window.location.pathname;
    const searchParams = new URLSearchParams(window.location.search);
    const tsParam = searchParams.get('timestamp') || undefined;

    if (path.startsWith('/incidents/')) {
      const incId = path.replace('/incidents/', '').trim();
      return { route: 'incident-detail', id: incId, timestamp: tsParam };
    }
    if (path === '/incidents') {
      return { route: 'incidents', timestamp: tsParam };
    }
    if (path.startsWith('/assets/')) {
      const aId = path.replace('/assets/', '').trim();
      return { route: 'investigator', id: aId || 'ahu-sd', timestamp: tsParam, datasetId: searchParams.get('dataset_id') || undefined };
    }
    if (path === '/assets') {
      return { route: 'investigator', id: 'ahu-sd', timestamp: tsParam };
    }
    if (path === '/diagnostics') {
      return { route: 'diagnostics' };
    }
    if (path === '/research/virtual-sensors') {
      return { route: 'virtual-sensor-research' };
    }
    if (path === '/research/field-evidence') {
      return { route: 'field-evidence' };
    }
    if (path === '/research') {
      return { route: 'research' };
    }
    if (path === '/monitoring') {
      return { route: 'monitoring' };
    }

    // Default for root '/'
    return { route: 'investigator', id: 'ahu-sd', timestamp: tsParam };
  };

  const initial = parseCurrentPath();
  const [currentRoute, setCurrentRoute] = useState<AppViewRoute>(initial.route);
  const [activeAssetId, setActiveAssetId] = useState<string>(initial.id || 'ahu-sd');
  const [activeIncidentId, setActiveIncidentId] = useState<string>(initial.id || 'inc-2026-001');
  const [seekTimestamp, setSeekTimestamp] = useState<string | undefined>(initial.timestamp);
  const [seekDatasetId, setSeekDatasetId] = useState(initial.datasetId);
  const [g4DemoFeed, setG4DemoFeed] = useState(() => new URLSearchParams(window.location.search).get('mode') === 'g4-demo');
  const [incidentsDemo, setIncidentsDemo] = useState(() => new URLSearchParams(window.location.search).get('mode') === 'demo');
  const [provenanceKind, setProvenanceKind] = useState<ProvenanceKind>(() => new URLSearchParams(window.location.search).get('mode') === 'demo'
    ? 'DEMO_FIXTURE' : 'SIMULATED_BENCHMARK');
  const [selectedScenarioId, setSelectedScenarioId] = useState<string>('');

  // Handle browser back/forward buttons
  useEffect(() => {
    const handlePopState = () => {
      const parsed = parseCurrentPath();
      setCurrentRoute(parsed.route);
      setProvenanceKind(new URLSearchParams(window.location.search).get('mode') === 'demo'
        ? 'DEMO_FIXTURE' : 'SIMULATED_BENCHMARK');
      if (parsed.id) {
        if (parsed.route === 'investigator') setActiveAssetId(parsed.id);
        if (parsed.route === 'incident-detail') setActiveIncidentId(parsed.id);
      }
      setSeekTimestamp(parsed.timestamp);
      setSeekDatasetId(parsed.datasetId);
      const mode = new URLSearchParams(window.location.search).get('mode');
      setIncidentsDemo(mode === 'demo');
      setG4DemoFeed(mode === 'g4-demo');
    };

    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  // Navigation dispatcher with pushState
  const navigate = (route: AppViewRoute, param?: string, timestamp?: string) => {
    setCurrentRoute(route);
    let targetPath = '/';

    if (route === 'investigator') {
      const asset = param || activeAssetId || 'ahu-sd';
      setActiveAssetId(asset);
      targetPath = `/assets/${asset}`;
      setSeekTimestamp(timestamp);
      const g4 = currentRoute === 'incidents' ? g4DemoFeed
        : currentRoute === 'investigator' && seekDatasetId === demoDatasetId && provenanceKind !== 'DEMO_FIXTURE';
      setSeekDatasetId(g4 ? demoDatasetId : undefined);
      const demo = currentRoute === 'incidents' ? incidentsDemo
        : currentRoute === 'incident-detail' || provenanceKind === 'DEMO_FIXTURE';
      setProvenanceKind(demo ? 'DEMO_FIXTURE' : 'SIMULATED_BENCHMARK');
      const query = new URLSearchParams();
      if (g4) query.set('dataset_id', demoDatasetId);
      else if (demo) query.set('mode', 'demo');
      if (timestamp) query.set('timestamp', timestamp);
      if (query.size) targetPath += `?${query}`;
    } else if (route === 'incidents') {
      const demo = currentRoute === 'incident-detail' || (currentRoute === 'incidents' && incidentsDemo)
        || (currentRoute === 'investigator' && provenanceKind === 'DEMO_FIXTURE');
      const g4 = currentRoute === 'incidents' ? g4DemoFeed
        : currentRoute === 'investigator' && seekDatasetId === demoDatasetId && provenanceKind !== 'DEMO_FIXTURE';
      setG4DemoFeed(g4);
      setIncidentsDemo(demo);
      targetPath = g4 ? '/incidents?mode=g4-demo' : demo ? '/incidents?mode=demo' : '/incidents';
    } else if (route === 'incident-detail') {
      const incId = param || activeIncidentId || 'inc-2026-001';
      setActiveIncidentId(incId);
      targetPath = `/incidents/${incId}`;
    } else if (route === 'diagnostics') {
      targetPath = '/diagnostics';
    } else if (route === 'virtual-sensor-research') {
      targetPath = '/research/virtual-sensors';
    } else if (route === 'field-evidence') {
      targetPath = '/research/field-evidence';
    } else if (route === 'research') {
      targetPath = '/research';
    } else if (route === 'monitoring') {
      targetPath = '/monitoring';
    }

    try {
      window.history.pushState({}, '', targetPath);
    } catch {
      // In sandboxed or file:// environments
    }
  };

  const isInvestigator = currentRoute === 'investigator';
  const g36Benchmark = isInvestigator && activeAssetId === 'ahu-g36';
  const g4Demo = (currentRoute === 'incidents' && g4DemoFeed) || (isInvestigator && provenanceKind !== 'DEMO_FIXTURE' && seekDatasetId === demoDatasetId);
  const displayedProvenance = currentRoute === 'field-evidence' ? 'REAL_BMS_REPORTED' : g36Benchmark ? 'SIMULATED_BENCHMARK' : g4Demo ? 'DEMO_FIXTURE' : isInvestigator ? provenanceKind
    : currentRoute === 'incident-detail' || (currentRoute === 'incidents' && incidentsDemo) ? 'DEMO_FIXTURE'
    : currentRoute === 'incidents' || currentRoute === 'virtual-sensor-research' ? 'SIMULATED_BENCHMARK' : 'LEGACY_ANALYSIS';

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
      {/* Universal Top Navigation Bar */}
      <TopNavigationBar
        currentRoute={currentRoute}
        onNavigate={navigate}
        activeAssetId={activeAssetId}
        provenanceKind={displayedProvenance}
        runtimeDemo={g4Demo && !g36Benchmark}
        g36Benchmark={g36Benchmark}
        onSelectProvenance={isInvestigator && !g36Benchmark ? kind => {
          if (g4Demo && kind === 'DEMO_FIXTURE') return;
          setProvenanceKind(kind);
          const url = new URL(window.location.href);
          if (g4Demo) {
            setSeekDatasetId(undefined);
            setSeekTimestamp(undefined);
            for (const field of ['dataset_id', 'timestamp', 'incident_id', 'window_start', 'confirmed_at']) {
              url.searchParams.delete(field);
            }
          }
          if (kind === 'DEMO_FIXTURE') url.searchParams.set('mode', 'demo');
          else url.searchParams.delete('mode');
          window.history.replaceState({}, '', url);
        } : undefined}
        unresolvedIncidentsCount={displayedProvenance === 'DEMO_FIXTURE' && !g4Demo ? 3 : 0}
      />

      {/* Main View Router */}
      <div className="flex-1">
        {displayedProvenance === 'DEMO_FIXTURE' && <div className="border-b border-amber-700 bg-amber-950 px-4 py-2 text-sm text-amber-200">
          DEMO_FIXTURE · {g4Demo ? 'G4 · синтетический источник и серверное правило' : 'UI_MOCK_V0 · синтетические данные и результаты'}
        </div>}
        {displayedProvenance === 'LEGACY_ANALYSIS' && <div className="border-b border-slate-700 px-4 py-2 text-sm text-slate-300">
          LEGACY_ANALYSIS · прежний API
        </div>}
        {g36Benchmark && <G36BenchmarkPage />}
        {isInvestigator && !g36Benchmark && provenanceKind !== 'DEMO_FIXTURE' && <RuntimeInvestigatorPage
          key={`${seekDatasetId ?? ''}:${seekTimestamp ?? ''}`} initialDatasetId={seekDatasetId} initialTimestamp={seekTimestamp} />}
        {isInvestigator && !g36Benchmark && provenanceKind === 'DEMO_FIXTURE' && (
          <AHUInvestigatorPage
            assetId={activeAssetId}
            initialTimestamp={seekTimestamp}
            onSelectAsset={(id) => navigate('investigator', id)}
            onNavigateToIncidents={() => navigate('incidents')}
          />
        )}

        {currentRoute === 'incidents' && (incidentsDemo ? <>
          <a className="inline-block px-4 pt-3 text-sm text-sky-300 underline" href="/incidents">Открыть ленту LBNL</a>
          <IncidentFeedPage
            onNavigateToInvestigator={(asset, ts) => navigate('investigator', asset, ts)}
            onNavigateToIncidentDetail={(incId) => navigate('incident-detail', incId)}
          />
        </> : <RuntimeIncidentPage key={String(g4DemoFeed)} demo={g4DemoFeed} />)}

        {currentRoute === 'incident-detail' && (
          <IncidentDetailPage
            incidentId={activeIncidentId}
            onBack={() => navigate('incidents')}
            onNavigateToInvestigator={(asset, ts) => navigate('investigator', asset, ts)}
          />
        )}

        {currentRoute === 'monitoring' && (
          <MonitoringPage
            activeTab="monitoring"
            onTabChange={(tab) => navigate(tab as AppViewRoute)}
            selectedScenarioId={selectedScenarioId}
            onSelectScenarioId={setSelectedScenarioId}
          />
        )}

        {currentRoute === 'diagnostics' && (
          <DiagnosticsPage
            activeTab="diagnostics"
            onTabChange={(tab) => navigate(tab as AppViewRoute)}
            selectedScenarioId={selectedScenarioId}
            onSelectScenarioId={setSelectedScenarioId}
          />
        )}

        {currentRoute === 'field-evidence' && <FieldEvidencePage />}
        {currentRoute === 'virtual-sensor-research' && <VirtualSensorResearchPage />}
        {currentRoute === 'research' && (
          <>
            <div className="mx-auto max-w-7xl px-4 pt-4 flex flex-wrap gap-x-6 gap-y-2">
              <a href="/research/field-evidence" className="text-sky-300 underline">Полевые свидетельства · BAS</a>
              <a href="/research/virtual-sensors" className="text-sky-300 underline">Виртуальный датчик SAT · исследование LBNL</a>
            </div>
            <ResearchPage
              activeTab="research"
              onTabChange={(tab) => navigate(tab as AppViewRoute)}
              selectedScenarioId={selectedScenarioId}
              onSelectScenarioId={setSelectedScenarioId}
            />
          </>
        )}
      </div>
    </div>
  );
}

export default App;
