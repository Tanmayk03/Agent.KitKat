import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import { FeedbackProvider } from './components/Feedback';
import AccessGate from './components/AccessGate';
import './index.css';

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <FeedbackProvider>
      <AccessGate>
        <App />
      </AccessGate>
    </FeedbackProvider>
  </React.StrictMode>
);

// Service worker (offline shell). Registered relative to the page so it works at / and /ui/.
// Browsers only allow it on https:// or localhost; on http://<LAN-IP> this quietly does nothing.
if ('serviceWorker' in navigator && import.meta.env.PROD && window.isSecureContext) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('sw.js').catch((err) => {
      console.warn('Service worker not registered:', err);
    });
  });
}
