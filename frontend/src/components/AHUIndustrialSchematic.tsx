import React from 'react';
import { Wind, Snowflake, Activity, AlertCircle, HelpCircle, Check, X } from 'lucide-react';

interface AHUIndustrialSchematicProps {
  currentValues: Record<string, number | null>;
  currentTimestamp?: string;
  hasCoolingAlert?: boolean;
  hasFreezeAlert?: boolean;
  fanOn?: boolean;
  sourceSimulation?: boolean;
  unverifiedUnitSignals?: readonly string[];
  activeProfile?: 'BASIC' | 'BASIC_PLUS_VALVE' | 'BASIC_PLUS_DAMPER' | 'FULL';
}

export const AHUIndustrialSchematic: React.FC<AHUIndustrialSchematicProps> = ({
  currentValues,
  currentTimestamp,
  hasCoolingAlert = false,
  hasFreezeAlert = false,
  fanOn = false,
  sourceSimulation = false,
  unverifiedUnitSignals = [],
  activeProfile = 'BASIC'
}) => {
  const formatVal = (key: string, unit: string = '°C') => {
    const val = currentValues[key];
    if (val === undefined || val === null || isNaN(val)) {
      return <span className="text-slate-500 font-mono text-xs">нет данных</span>;
    }
    return (
      <span className="font-mono font-bold text-emerald-400 text-xs">
        {val.toFixed(1)} {unit}
      </span>
    );
  };

  const formatFraction = (key: string) => {
    const val = currentValues[key];
    if (val === undefined || val === null || isNaN(val)) {
      return <span className="text-slate-500 font-mono text-xs">нет данных</span>;
    }
    // If value is between 0 and 1, multiply by 100, else use as is
    const pct = sourceSimulation || val <= 1.0 ? val * 100 : val;
    return (
      <span className="font-mono font-bold text-cyan-400 text-xs">
        {pct.toFixed(0)}%
      </span>
    );
  };

  const hasValvePosition = activeProfile === 'BASIC_PLUS_VALVE' || activeProfile === 'FULL' || currentValues['CHWC_VLV'] !== undefined;
  const hasDamperPosition = activeProfile === 'BASIC_PLUS_DAMPER' || activeProfile === 'FULL' || currentValues['OA_DMPR'] !== undefined;

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 shadow-xl select-none">
      {/* Header bar */}
      <div className="flex flex-wrap items-center justify-between pb-3 mb-3 border-b border-slate-800 gap-2">
        <div className="flex items-center space-x-2">
          <Activity className="w-4 h-4 text-emerald-400" />
          <h3 className="text-xs font-bold tracking-wider uppercase text-slate-200">
            Мнемосхема установки AHU-SD (Канонические каналы)
          </h3>
          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700">
            Профиль: {sourceSimulation && activeProfile === "FULL" ? "EXTRA_SIMULATED" : activeProfile}
          </span>
        </div>
        <div className="text-xs text-slate-400">
          Курсор телеметрии:{' '}
          <span className="font-mono text-amber-300 font-medium">
            {currentTimestamp || 'Нет отсчета'}
          </span>
        </div>
      </div>

      {/* SVG Schematic Canvas */}
      <div className="relative w-full overflow-x-auto bg-slate-950/60 rounded-lg p-2 border border-slate-800/80">
        <svg viewBox="0 0 960 360" className="w-full h-auto min-w-[780px]">
          <defs>
            <linearGradient id="casingGrad" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#1e293b" />
              <stop offset="50%" stopColor="#293548" />
              <stop offset="100%" stopColor="#1e293b" />
            </linearGradient>
            <linearGradient id="coolingCoilGrad" x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stopColor="#0284c7" />
              <stop offset="100%" stopColor="#0369a1" />
            </linearGradient>
            <filter id="alertGlow" x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="4" result="blur" />
              <feComposite in="SourceGraphic" in2="blur" operator="over" />
            </filter>
          </defs>

          {/* Main AHU Duct Casing */}
          <rect
            x="190"
            y="100"
            width="580"
            height="160"
            rx="10"
            fill="url(#casingGrad)"
            stroke="#475569"
            strokeWidth="3"
          />

          {/* Duct Sections Dividers */}
          <line x1="330" y1="100" x2="330" y2="260" stroke="#334155" strokeWidth="2" strokeDasharray="4 4" />
          <line x1="410" y1="100" x2="410" y2="260" stroke="#334155" strokeWidth="2" strokeDasharray="4 4" />
          <line x1="560" y1="100" x2="560" y2="260" stroke="#334155" strokeWidth="2" strokeDasharray="4 4" />

          {/* Outdoor Air (OA) Duct on the Left */}
          <path
            d="M 50 180 L 190 180"
            stroke="#0284c7"
            strokeWidth="38"
            strokeLinecap="round"
            opacity="0.2"
          />
          <path
            d="M 50 180 L 190 180"
            stroke="#38bdf8"
            strokeWidth="3"
            strokeDasharray="6 4"
          />
          <text x="60" y="150" fill="#7dd3fc" fontSize="12" fontWeight="bold">
            Наружный воздух (OA)
          </text>

          {/* Return Air (RA) Duct from Top */}
          <path
            d="M 270 25 L 270 100"
            stroke="#f59e0b"
            strokeWidth="34"
            strokeLinecap="round"
            opacity="0.2"
          />
          <path
            d="M 270 25 L 270 100"
            stroke="#fbbf24"
            strokeWidth="3"
            strokeDasharray="6 4"
          />
          <text x="210" y="24" fill="#fbbf24" fontSize="12" fontWeight="bold">
            Возвратный воздух (RA)
          </text>

          {/* Supply Air (SA) Duct on the Right */}
          <path
            d="M 770 180 L 910 180"
            stroke="#10b981"
            strokeWidth="38"
            strokeLinecap="round"
            opacity="0.2"
          />
          <path
            d="M 770 180 L 910 180"
            stroke="#34d399"
            strokeWidth="3"
            strokeDasharray="6 4"
          />
          <text x="790" y="150" fill="#34d399" fontSize="12" fontWeight="bold">
            Приток в здание (SA)
          </text>

          {unverifiedUnitSignals.length > 0 && (
            <g fill="#fbbf24" fontSize="11" aria-label="Исходные значения давления">
              <text x="48" y="285">Давление · единицы не проверены</text>
              {unverifiedUnitSignals.map((key, index) => (
                <text key={key} x="48" y={304 + index * 16}>
                  {key} · raw {currentValues[key] ?? 'нет данных'}
                </text>
              ))}
            </g>
          )}

          {/* Air Flow Arrows - Only shown when Fan is ON */}
          {fanOn && (
            <g opacity="0.8">
              <path d="M 120 180 L 140 180" stroke="#38bdf8" strokeWidth="3" markerEnd="url(#arrow)" />
              <path d="M 360 180 L 380 180" stroke="#94a3b8" strokeWidth="3" />
              <path d="M 500 180 L 520 180" stroke="#38bdf8" strokeWidth="3" />
              <path d="M 720 180 L 740 180" stroke="#34d399" strokeWidth="3" />
            </g>
          )}

          {/* OA Damper */}
          <g transform="translate(200, 150)">
            <rect x="0" y="0" width="16" height="60" fill="#334155" stroke="#64748b" strokeWidth="2" rx="2" />
            <line x1="8" y1="8" x2="8" y2="52" stroke="#38bdf8" strokeWidth="3" />
            <text x="-12" y="75" fill="#94a3b8" fontSize="10">Заслонка OA</text>
          </g>

          {/* RA Damper */}
          <g transform="translate(255, 105)">
            <rect x="0" y="0" width="30" height="14" fill="#334155" stroke="#64748b" strokeWidth="2" rx="2" />
            <text x="-5" y="-6" fill="#94a3b8" fontSize="10">Заслонка RA</text>
          </g>

          {/* Mixing Chamber (MA) */}
          <rect
            x="240"
            y="130"
            width="80"
            height="100"
            fill="#0f172a"
            stroke={hasFreezeAlert ? '#ef4444' : '#64748b'}
            strokeWidth={hasFreezeAlert ? '3' : '1.5'}
            filter={hasFreezeAlert ? 'url(#alertGlow)' : undefined}
            rx="6"
          />
          <text x="252" y="150" fill="#cbd5e1" fontSize="11" fontWeight="bold">
            Смешение
          </text>

          {/* Air Filter */}
          <g transform="translate(345, 120)">
            <rect x="0" y="0" width="20" height="120" fill="#1e293b" stroke="#64748b" strokeWidth="1.5" rx="2" />
            <path d="M 3 15 L 17 30 M 3 45 L 17 60 M 3 75 L 17 90 M 3 105 L 17 120" stroke="#94a3b8" strokeWidth="2" />
            <text x="-2" y="136" fill="#94a3b8" fontSize="10">Фильтр</text>
          </g>

          {/* Cooling Coil & CHWC Valve */}
          <g transform="translate(435, 115)">
            <rect
              x="0"
              y="0"
              width="75"
              height="130"
              fill="url(#coolingCoilGrad)"
              stroke={hasCoolingAlert ? '#f59e0b' : '#38bdf8'}
              strokeWidth={hasCoolingAlert ? '3' : '2'}
              filter={hasCoolingAlert ? 'url(#alertGlow)' : undefined}
              rx="6"
            />
            {/* Winding tubes */}
            <path
              d="M 15 15 Q 60 15 60 40 T 15 65 T 60 90 T 15 115"
              fill="none"
              stroke="#e0f2fe"
              strokeWidth="3.5"
            />
            <Snowflake className="w-4 h-4 text-white" x="28" y="6" />
            <text x="8" y="145" fill="#7dd3fc" fontSize="10" fontWeight="bold">
              Охладитель
            </text>
          </g>

          {/* Chilled Water Valve on Top of Cooling Coil */}
          <g transform="translate(452, 45)">
            <path d="M 0 0 L 40 30 L 40 0 L 0 30 Z" fill="#0284c7" stroke="#38bdf8" strokeWidth="2" />
            <circle cx="20" cy="15" r="5" fill="#f8fafc" />
            <text x="-14" y="-6" fill="#38bdf8" fontSize="10" fontWeight="bold">
              Клапан CHWC
            </text>
          </g>

          {/* Supply Fan (SF) */}
          <g transform="translate(610, 130)">
            <circle
              cx="50"
              cy="50"
              r="45"
              fill="#0f172a"
              stroke={fanOn ? '#10b981' : '#64748b'}
              strokeWidth="3"
            />
            <g
              transform="translate(25, 25)"
              className={fanOn ? 'origin-center animate-spin' : ''}
              style={{ transformOrigin: '25px 25px', animationDuration: '2s' }}
            >
              <Wind className={`w-12 h-12 ${fanOn ? 'text-emerald-400' : 'text-slate-600'}`} />
            </g>
            <text x="12" y="115" fill="#cbd5e1" fontSize="10" fontWeight="bold">
              Вентилятор SF
            </text>
          </g>
        </svg>

        {/* Real Canonical Channels Status Strip */}
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mt-3 pt-3 border-t border-slate-800 text-xs">
          {/* Outdoor Air Section */}
          <div className="bg-slate-900/90 p-2.5 rounded-lg border border-slate-800">
            <div className="text-slate-400 font-semibold mb-1 text-[11px] uppercase tracking-wider">
              Наружный воздух (OA)
            </div>
            <div className="flex justify-between py-0.5">
              <span className="text-slate-400 font-mono">OA_TEMP:</span>
              {formatVal('OA_TEMP')}
            </div>
            <div className="flex justify-between py-0.5">
              <span className="text-slate-400 font-mono">OA_DMPR_DM (команда):</span>
              {formatFraction('OA_DMPR_DM')}
            </div>
            <div className="flex justify-between py-0.5">
              <span className="text-slate-400 font-mono">OA_DMPR ({sourceSimulation ? "положение модели" : "факт"}):</span>
              {hasDamperPosition ? (
                <>{formatFraction("OA_DMPR")}</>
              ) : (
                <span className="text-slate-500 font-mono text-[11px] italic">{sourceSimulation ? "Недоступен в панели" : "[Не установлен в BASIC]"}</span>
              )}
            </div>
          </div>

          {/* Return Air Section */}
          <div className="bg-slate-900/90 p-2.5 rounded-lg border border-slate-800">
            <div className="text-slate-400 font-semibold mb-1 text-[11px] uppercase tracking-wider">
              Возвратный воздух (RA)
            </div>
            <div className="flex justify-between py-0.5">
              <span className="text-slate-400 font-mono">RA_TEMP:</span>
              {formatVal('RA_TEMP')}
            </div>
            <div className="flex justify-between py-0.5">
              <span className="text-slate-400 font-mono">RA_DMPR_DM (команда):</span>
              {formatFraction('RA_DMPR_DM')}
            </div>
          </div>

          {/* Mixed Air Section */}
          <div className="bg-slate-900/90 p-2.5 rounded-lg border border-slate-800">
            <div className="text-slate-400 font-semibold mb-1 text-[11px] uppercase tracking-wider">
              Смешанный воздух (MA)
            </div>
            <div className="flex justify-between py-0.5">
              <span className="text-slate-400 font-mono">MA_TEMP:</span>
              {formatVal('MA_TEMP')}
            </div>
            <div className="text-[10px] text-slate-500 mt-1">
              *Без включения SYS_CTL в Basic семантику
            </div>
          </div>

          {/* Cooling Coil Section */}
          <div className="bg-slate-900/90 p-2.5 rounded-lg border border-slate-800">
            <div className="text-slate-400 font-semibold mb-1 text-[11px] uppercase tracking-wider">
              Охлаждение (CHWC)
            </div>
            <div className="flex justify-between py-0.5">
              <span className="text-slate-400 font-mono">CHWC_VLV_DM (команда):</span>
              {formatFraction('CHWC_VLV_DM')}
            </div>
            <div className="flex justify-between py-0.5">
              <span className="text-slate-400 font-mono">CHWC_VLV ({sourceSimulation ? "положение модели" : "факт"}):</span>
              {hasValvePosition ? (
                <>{formatFraction("CHWC_VLV")}</>
              ) : (
                <span className="text-amber-400/80 font-mono text-[10px] italic">{sourceSimulation ? "Недоступен в панели" : "[Не установлен в BASIC]"}</span>
              )}
            </div>
          </div>

          {/* Supply Air Section */}
          <div className="bg-slate-900/90 p-2.5 rounded-lg border border-slate-800">
            <div className="text-slate-400 font-semibold mb-1 text-[11px] uppercase tracking-wider">
              Приток (SA)
            </div>
            <div className="flex justify-between py-0.5">
              <span className="text-slate-400 font-mono">SA_TEMP:</span>
              {formatVal('SA_TEMP')}
            </div>
            <div className="flex justify-between py-0.5">
              <span className="text-slate-400 font-mono">SA_TEMPSPT:</span>
              {formatVal('SA_TEMPSPT')}
            </div>
            <div className="flex justify-between py-0.5">
              <span className="text-slate-400 font-mono">SA_CFM (расход):</span>
              <span className="text-slate-500 font-mono text-[11px] italic">[Нет расходомера]</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
