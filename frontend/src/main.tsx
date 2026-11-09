/// <reference types="vite/client" />

import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './index.css';

const PilotPage = import.meta.env.VITE_BP16_PILOT === '1'
  ? React.lazy(() => import('./pilot/PilotPage'))
  : undefined;
const pilotRoute = window.location.pathname === '/research/engineer-decision-pilot';
const loopback = ['localhost', '127.0.0.1', '[::1]'].includes(window.location.hostname);

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    {pilotRoute
      ? PilotPage && loopback
        ? <React.Suspense fallback={<p role="status">Открывается исследовательский сеанс…</p>}><PilotPage /></React.Suspense>
        : <p role="alert">Исследовательский сеанс недоступен.</p>
      : <App />}
  </React.StrictMode>
);
