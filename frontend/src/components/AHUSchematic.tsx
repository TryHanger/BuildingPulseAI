import React from 'react';
import { Wind, Snowflake, Activity, AlertCircle } from 'lucide-react';

interface AHUSchematicProps {
  currentValues: Record<string, number | null>;
  currentTimestamp?: string;
  hasFreezeAlert?: boolean;
  hasCoolingAlert?: boolean;
}

export const AHUSchematic: React.FC<AHUSchematicProps> = ({
  currentValues,
  currentTimestamp,
  hasFreezeAlert,
  hasCoolingAlert
}) => {
  const formatVal = (key: string, unit: string = '') => {
    const val = currentValues[key];
    if (val === undefined || val === null || isNaN(val)) {
      return <span className="text-slate-500 font-mono text-xs">N/A</span>;
    }
    return (
      <span className="font-mono font-semibold text-emerald-400 text-xs">
        {val.toFixed(1)} {unit}
      </span>
    );
  };

  const formatFraction = (key: string) => {
    const val = currentValues[key];
    if (val === undefined || val === null || isNaN(val)) {
      return <span className="text-slate-500 font-mono text-xs">N/A</span>;
    }
    return (
      <span className="font-mono font-semibold text-cyan-400 text-xs">
        {(val * 100).toFixed(0)}%
      </span>
    );
  };

  const isFanRunning = (currentValues['SF_SPD_DM'] ?? 0) > 0.5 || (currentValues['SF_SPD'] ?? 0) > 0.1;

  return (
    <div className="bg-slate-800/80 border border-slate-700/80 rounded-xl p-4 shadow-xl backdrop-blur-sm">
      <div className="flex items-center justify-between mb-3 border-b border-slate-700/60 pb-2">
        <div className="flex items-center space-x-2">
          <Activity className="w-5 h-5 text-emerald-400" />
          <h2 className="text-sm font-bold tracking-wide uppercase text-slate-200">
            Мнемосхема установки AHU
          </h2>
        </div>
        <div className="text-xs text-slate-400">
          Курсор:{' '}
          <span className="font-mono text-amber-300 font-medium">
            {currentTimestamp || 'Нет данных'}
          </span>
        </div>
      </div>

      {/* SVG Schematic */}
      <div className="relative w-full overflow-x-auto">
        <svg viewBox="0 0 920 340" className="w-full h-auto min-w-[760px] select-none">
          <defs>
            <linearGradient id="ductGrad" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#1e293b" />
              <stop offset="50%" stopColor="#334155" />
              <stop offset="100%" stopColor="#1e293b" />
            </linearGradient>
            <linearGradient id="coolingGrad" x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stopColor="#0284c7" />
              <stop offset="100%" stopColor="#0369a1" />
            </linearGradient>
            <filter id="glowAlert" x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="3" result="blur" />
              <feComposite in="SourceGraphic" in2="blur" operator="over" />
            </filter>
          </defs>

          {/* Main AHU Casing */}
          <rect
            x="180"
            y="90"
            width="560"
            height="160"
            rx="12"
            fill="url(#ductGrad)"
            stroke="#475569"
            strokeWidth="3"
          />

          {/* Outdoor Air (OA) Duct on the left */}
          <path
            d="M 60 170 L 180 170"
            stroke="#38bdf8"
            strokeWidth="36"
            strokeLinecap="round"
            opacity="0.25"
          />
          <path
            d="M 60 170 L 180 170"
            stroke="#38bdf8"
            strokeWidth="4"
            strokeDasharray="8 6"
          />
          <text x="70" y="140" fill="#94a3b8" fontSize="12" fontWeight="bold">
            Наружный воздух (OA)
          </text>

          {/* Return Air (RA) Duct from top */}
          <path
            d="M 270 20 L 270 90"
            stroke="#f59e0b"
            strokeWidth="32"
            strokeLinecap="round"
            opacity="0.2"
          />
          <path
            d="M 270 20 L 270 90"
            stroke="#f59e0b"
            strokeWidth="4"
            strokeDasharray="8 6"
          />
          <text x="210" y="24" fill="#f59e0b" fontSize="12" fontWeight="bold">
            Возвратный воздух (RA)
          </text>

          {/* Supply Air (SA) Duct on the right */}
          <path
            d="M 740 170 L 860 170"
            stroke="#10b981"
            strokeWidth="36"
            strokeLinecap="round"
            opacity="0.25"
          />
          <path
            d="M 740 170 L 860 170"
            stroke="#10b981"
            strokeWidth="4"
            strokeDasharray="8 6"
          />
          <text x="760" y="140" fill="#34d399" fontSize="12" fontWeight="bold">
            Приток в зоны (SA)
          </text>

          {/* OA Damper */}
          <g transform="translate(195, 140)">
            <rect x="0" y="0" width="16" height="60" fill="#334155" stroke="#64748b" strokeWidth="2" rx="2" />
            <line x1="8" y1="10" x2="8" y2="50" stroke="#38bdf8" strokeWidth="3" />
            <text x="-15" y="75" fill="#cbd5e1" fontSize="10">Заслонка OA</text>
          </g>

          {/* RA Damper */}
          <g transform="translate(255, 95)">
            <rect x="0" y="0" width="30" height="14" fill="#334155" stroke="#64748b" strokeWidth="2" rx="2" />
            <text x="-5" y="-6" fill="#cbd5e1" fontSize="10">Заслонка RA</text>
          </g>

          {/* Mixing Box (MA) */}
          <rect
            x="240"
            y="120"
            width="80"
            height="100"
            fill="#0f172a"
            stroke={hasFreezeAlert ? '#ef4444' : '#64748b'}
            strokeWidth={hasFreezeAlert ? '3' : '1.5'}
            filter={hasFreezeAlert ? 'url(#glowAlert)' : undefined}
            rx="6"
          />
          <text x="250" y="140" fill="#cbd5e1" fontSize="11" fontWeight="bold">
            Смешение
          </text>

          {/* Filter Section */}
          <g transform="translate(350, 115)">
            <rect x="0" y="0" width="22" height="110" fill="#1e293b" stroke="#64748b" strokeWidth="1.5" rx="2" />
            <path d="M 4 10 L 18 25 M 4 35 L 18 50 M 4 60 L 18 75 M 4 85 L 18 100" stroke="#94a3b8" strokeWidth="2" />
            <text x="-4" y="125" fill="#94a3b8" fontSize="10">Фильтр</text>
          </g>

          {/* Cooling Coil */}
          <g transform="translate(420, 110)">
            <rect
              x="0"
              y="0"
              width="65"
              height="120"
              fill="url(#coolingGrad)"
              stroke={hasCoolingAlert ? '#f59e0b' : '#38bdf8'}
              strokeWidth={hasCoolingAlert ? '3' : '2'}
              filter={hasCoolingAlert ? 'url(#glowAlert)' : undefined}
              rx="6"
            />
            {/* Coil pipes representation */}
            <path
              d="M 12 15 Q 50 15 50 35 T 12 55 T 50 75 T 12 95 T 50 110"
              fill="none"
              stroke="#e0f2fe"
              strokeWidth="3"
            />
            <Snowflake className="w-4 h-4 text-white" x="24" y="5" />
            <text x="6" y="135" fill="#7dd3fc" fontSize="10" fontWeight="bold">
              Охладитель
            </text>
          </g>

          {/* Chilled Water Valve on top of Cooling Coil */}
          <g transform="translate(435, 50)">
            <path d="M 0 0 L 35 25 L 35 0 L 0 25 Z" fill="#0284c7" stroke="#38bdf8" strokeWidth="2" />
            <circle cx="17.5" cy="12.5" r="5" fill="#f8fafc" />
            <text x="-12" y="-6" fill="#38bdf8" fontSize="10">Клапан CHWC</text>
          </g>

          {/* Supply Fan (SF) */}
          <g transform="translate(560, 125)">
            <circle
              cx="45"
              cy="45"
              r="40"
              fill="#0f172a"
              stroke={isFanRunning ? '#10b981' : '#64748b'}
              strokeWidth="3"
            />
            <Wind
              className={`w-10 h-10 ${isFanRunning ? 'text-emerald-400' : 'text-slate-600'}`}
              x="25"
              y="25"
            />
            <text x="12" y="105" fill="#cbd5e1" fontSize="10" fontWeight="bold">
              Вентилятор SF
            </text>
          </g>
        </svg>

        {/* Live Channel Overlays with absolute / grid layout */}
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mt-4 pt-3 border-t border-slate-700/60 text-xs">
          {/* Outdoor Section */}
          <div className="bg-slate-900/80 p-2.5 rounded-lg border border-slate-700">
            <div className="text-slate-400 font-medium mb-1">Наружный воздух (OA)</div>
            <div className="flex justify-between">
              <span className="text-slate-400">OA_TEMP:</span>
              {formatVal('OA_TEMP', '°F')}
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Заслонка (cmd):</span>
              {formatFraction('OA_DMPR_DM')}
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Заслонка (факт):</span>
              {formatFraction('OA_DMPR')}
            </div>
          </div>

          {/* Return Section */}
          <div className="bg-slate-900/80 p-2.5 rounded-lg border border-slate-700">
            <div className="text-slate-400 font-medium mb-1">Возвратный воздух (RA)</div>
            <div className="flex justify-between">
              <span className="text-slate-400">RA_TEMP:</span>
              {formatVal('RA_TEMP', '°F')}
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Заслонка (cmd):</span>
              {formatFraction('RA_DMPR_DM')}
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Заслонка (факт):</span>
              {formatFraction('RA_DMPR')}
            </div>
          </div>

          {/* Mixed Air Section */}
          <div className="bg-slate-900/80 p-2.5 rounded-lg border border-slate-700">
            <div className="text-slate-400 font-medium mb-1">Камера смешения (MA)</div>
            <div className="flex justify-between">
              <span className="text-slate-400">MA_TEMP:</span>
              {formatVal('MA_TEMP', '°F')}
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">SYS_CTL:</span>
              <span className="font-mono text-emerald-400">
                {(currentValues['SYS_CTL'] ?? 0) > 0.5 ? 'Осн (Раб)' : 'Дежурный'}
              </span>
            </div>
          </div>

          {/* Cooling Coil Section */}
          <div className="bg-slate-900/80 p-2.5 rounded-lg border border-slate-700">
            <div className="text-slate-400 font-medium mb-1">Охлаждение (CHWC)</div>
            <div className="flex justify-between">
              <span className="text-slate-400">Клапан (cmd):</span>
              {formatFraction('CHWC_VLV_DM')}
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Клапан (факт):</span>
              {formatFraction('CHWC_VLV')}
            </div>
            {currentValues['CHWC_VLV'] === undefined && (
              <div className="text-[10px] text-amber-400/80 mt-1 italic">
                *Обратная связь не предусмотрена проектом
              </div>
            )}
          </div>

          {/* Supply Fan Section */}
          <div className="bg-slate-900/80 p-2.5 rounded-lg border border-slate-700">
            <div className="text-slate-400 font-medium mb-1">Приток воздуха (SA)</div>
            <div className="flex justify-between">
              <span className="text-slate-400">SA_TEMP:</span>
              {formatVal('SA_TEMP', '°F')}
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Уставка:</span>
              {formatVal('SA_TEMPSPT', '°F')}
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Давление SA_SP:</span>
              {formatVal('SA_SP', 'in')}
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Вентилятор:</span>
              <span className={`font-semibold ${isFanRunning ? 'text-emerald-400' : 'text-slate-500'}`}>
                {isFanRunning ? 'ВКЛ' : 'ВЫКЛ'}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
