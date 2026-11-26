import React, { useCallback, useEffect, useState } from 'react';
import { ShieldCheck, Smartphone, Loader2 } from 'lucide-react';
import { api } from '../services/api';

/*
 * Wraps the app. On this computer it renders the app straight away. On another device
 * (your iPhone) it asks for the phone access token first, which normally arrives by
 * scanning the QR code in Settings: that opens  <address>/#pair=<token>.
 * The token is exchanged for an HttpOnly cookie and removed from the address bar.
 */

const readPairToken = () => {
  const m = window.location.hash.match(/(?:^#|[&#])pair=([A-Za-z0-9_-]{20,})/);
  return m ? m[1] : null;
};

export default function AccessGate({ children }) {
  const [state, setState] = useState({ status: 'checking' }); // checking | ok | needs-pair | off | error
  const [code, setCode] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const check = useCallback(async () => {
    try {
      const w = await api.whoami();
      if (w.authorized) setState({ status: 'ok', local: w.local });
      else setState({ status: w.mode === 'off' ? 'off' : 'needs-pair' });
    } catch (e) {
      setState({ status: 'error', message: e.message });
    }
  }, []);

  const pairWith = useCallback(async (token) => {
    setBusy(true);
    setError('');
    try {
      await api.pair(token);
      await check();
    } catch (e) {
      setError(e.message || 'Pairing failed.');
      setState((s) => (s.status === 'checking' ? { status: 'needs-pair' } : s));
    } finally {
      setBusy(false);
    }
  }, [check]);

  useEffect(() => {
    const token = readPairToken();
    if (token) {
      // Remove the token from the address bar and history before doing anything else.
      window.history.replaceState(null, '', `${window.location.pathname}${window.location.search}#/dashboard`);
      pairWith(token);
    } else {
      check();
    }
    // A pairing link opened in a tab that is already showing the app only changes the hash.
    const onHash = () => {
      const t = readPairToken();
      if (t) {
        window.history.replaceState(null, '', `${window.location.pathname}${window.location.search}#/dashboard`);
        pairWith(t);
      }
    };
    window.addEventListener('hashchange', onHash);
    const onUnpaired = () => setState({ status: 'needs-pair' });
    const onOff = () => setState({ status: 'off' });
    window.addEventListener('kitkat:unpaired', onUnpaired);
    window.addEventListener('kitkat:lan-off', onOff);
    return () => {
      window.removeEventListener('hashchange', onHash);
      window.removeEventListener('kitkat:unpaired', onUnpaired);
      window.removeEventListener('kitkat:lan-off', onOff);
    };
  }, [check, pairWith]);

  if (state.status === 'ok') return children;

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 flex items-center justify-center p-5 safe-top safe-bottom">
      <div className="w-full max-w-sm space-y-5">
        <div className="flex items-center gap-2.5">
          <div className="w-9 h-9 rounded-lg bg-zinc-100 text-zinc-950 flex items-center justify-center font-bold">K</div>
          <span className="text-base font-semibold">Agent KitKat</span>
        </div>

        {state.status === 'checking' && (
          <p className="flex items-center gap-2 text-sm text-zinc-400"><Loader2 className="w-4 h-4 animate-spin" /> Connecting…</p>
        )}

        {state.status === 'error' && (
          <div className="space-y-3">
            <h1 className="text-lg font-semibold">Can't reach your computer</h1>
            <p className="text-sm text-zinc-400">
              Make sure Agent KitKat is running (start.bat) and this device is on the same Wi-Fi. ({state.message})
            </p>
            <button onClick={check} className="w-full py-3 rounded-lg bg-zinc-100 text-zinc-950 text-sm font-medium">Try again</button>
          </div>
        )}

        {state.status === 'off' && (
          <div className="space-y-3">
            <h1 className="text-lg font-semibold">Phone access is off</h1>
            <p className="text-sm text-zinc-400">
              On your computer, open Settings → Phone access and turn it on, then try again.
            </p>
            <button onClick={check} className="w-full py-3 rounded-lg bg-zinc-100 text-zinc-950 text-sm font-medium">Try again</button>
          </div>
        )}

        {state.status === 'needs-pair' && (
          <div className="space-y-4">
            <div className="space-y-1.5">
              <h1 className="text-lg font-semibold flex items-center gap-2"><Smartphone className="w-5 h-5 text-zinc-400" /> Pair this device</h1>
              <p className="text-sm text-zinc-400 leading-relaxed">
                On your computer, open <span className="text-zinc-200">Settings → Phone access</span> and scan the QR code with this
                phone's camera. Or copy the access code from there and paste it here.
              </p>
            </div>
            <form
              onSubmit={(e) => { e.preventDefault(); if (code.trim()) pairWith(code.trim()); }}
              className="space-y-2.5"
            >
              <label className="block text-xs text-zinc-400" htmlFor="pair-code">Access code</label>
              <input
                id="pair-code"
                value={code}
                onChange={(e) => setCode(e.target.value)}
                autoComplete="off"
                autoCapitalize="none"
                spellCheck={false}
                className="w-full px-3 py-3 rounded-lg bg-zinc-900 border border-zinc-700 font-mono text-sm"
                placeholder="Paste the code"
              />
              {error && <p className="text-xs text-red-400" role="alert">{error}</p>}
              <button type="submit" disabled={busy || !code.trim()}
                className="w-full py-3 rounded-lg bg-zinc-100 text-zinc-950 text-sm font-medium disabled:opacity-50 flex items-center justify-center gap-2">
                {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <ShieldCheck className="w-4 h-4" />} Pair
              </button>
            </form>
            <p className="text-[11px] text-zinc-500 leading-relaxed">
              The code keeps other people on your Wi-Fi out of your profile, resumes and applications. It's kept on this device
              in a cookie that web pages' scripts can't read.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
