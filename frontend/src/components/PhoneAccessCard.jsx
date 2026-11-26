import React, { useCallback, useEffect, useState } from 'react';
import QRCode from 'qrcode';
import { Smartphone, ExternalLink, RefreshCw, Eye, EyeOff } from 'lucide-react';
import { api } from '../services/api';
import { useToast, useConfirm } from './Feedback';

/*
 * Settings → Phone access.
 * On this computer: the phone address, a QR code that pairs the phone in one scan,
 * the access code, on/off, and "new code". On a paired phone: just "unpair this device".
 * The QR code is generated locally (no external service sees the token).
 */
export default function PhoneAccessCard() {
  const toast = useToast();
  const confirm = useConfirm();
  const [who, setWho] = useState(null);
  const [net, setNet] = useState(null);
  const [access, setAccess] = useState(null);
  const [qr, setQr] = useState('');
  const [showCode, setShowCode] = useState(false);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setError('');
    try {
      const w = await api.whoami();
      setWho(w);
      const n = await api.getNetworkInfo();
      setNet(n);
      if (w.local) {
        const a = await api.getLanAccess(n.mobile_access_url);
        setAccess(a);
        setQr(a.pair_url ? await QRCode.toDataURL(a.pair_url, { margin: 1, width: 220, errorCorrectionLevel: 'M' }) : '');
      }
    } catch (e) {
      setError(e.message || 'Could not load phone access settings.');
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const copy = async (text, what) => {
    try {
      await navigator.clipboard.writeText(text);
      toast.success(`${what} copied.`);
    } catch {
      toast.info(`Copy it manually: ${text}`);
    }
  };

  const rotate = async () => {
    const ok = await confirm({
      title: 'Make a new access code?',
      body: 'Phones paired with the current code will be asked to pair again.',
      confirmLabel: 'New code',
    });
    if (!ok) return;
    try {
      await api.rotateLanToken();
      await load();
      toast.success('New access code created. Scan the new QR code on your phone.');
    } catch (e) {
      toast.error(`Could not create a new code: ${e.message}`);
    }
  };

  const toggleMode = async () => {
    const next = access?.mode === 'off' ? 'token' : 'off';
    try {
      await api.setLanMode(next);
      await load();
      toast.success(next === 'off' ? 'Phone access turned off.' : 'Phone access turned on.');
    } catch (e) {
      toast.error(`Could not change phone access: ${e.message}`);
    }
  };

  const unpair = async () => {
    const ok = await confirm({ title: 'Unpair this device?', body: 'You will need the QR code from your computer to use it here again.', confirmLabel: 'Unpair', danger: true });
    if (!ok) return;
    try {
      await api.unpair();
      window.dispatchEvent(new CustomEvent('kitkat:unpaired'));
    } catch (e) {
      toast.error(e.message);
    }
  };

  return (
    <div className="rounded-xl bg-zinc-900/40 border border-zinc-800 p-4 sm:p-6 space-y-4">
      <h2 className="text-sm font-semibold text-zinc-100 flex items-center gap-2">
        <Smartphone className="w-4 h-4 text-zinc-400" /> Phone access
      </h2>
      <p className="text-xs text-zinc-400 leading-relaxed">
        Your phone connects to this computer over your Wi-Fi; nothing goes through the internet. Other devices on the Wi-Fi need
        the access code, so they can't open your profile, resumes or applications. Setup details: docs/IPHONE.md.
      </p>

      {error && <p className="text-xs text-red-400" role="alert">{error}</p>}
      {!who && !error && <p className="text-xs text-zinc-500">Loading…</p>}

      {who && !who.local && (
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-3.5 rounded-lg bg-zinc-950 border border-zinc-800">
          <span className="text-xs text-zinc-300">This device is paired with your computer.</span>
          <button onClick={unpair} className="px-3 py-2 rounded-md text-xs font-medium border border-zinc-700 text-zinc-200 hover:bg-zinc-800">
            Unpair this device
          </button>
        </div>
      )}

      {who?.local && access && net && (
        <div className="space-y-4">
          <div className="flex items-center justify-between gap-3 p-3.5 rounded-lg bg-zinc-950 border border-zinc-800">
            <div className="text-xs">
              <span className="text-zinc-500 block">Phone access</span>
              <span className={`font-medium ${access.mode === 'off' ? 'text-zinc-400' : 'text-emerald-400'}`}>
                {access.mode === 'off' ? 'Off: other devices are refused' : 'On: other devices need the access code'}
              </span>
            </div>
            <button onClick={toggleMode} className="px-3 py-2 rounded-md text-xs font-medium border border-zinc-700 text-zinc-200 hover:bg-zinc-800">
              {access.mode === 'off' ? 'Turn on' : 'Turn off'}
            </button>
          </div>

          {access.mode !== 'off' && (
            <div className="grid grid-cols-1 sm:grid-cols-[auto_1fr] gap-4 items-start">
              {qr ? (
                <img src={qr} alt="QR code that opens Agent KitKat on your phone and pairs it" className="w-44 h-44 rounded-lg bg-white p-1.5 mx-auto sm:mx-0" />
              ) : (
                <div className="w-44 h-44 rounded-lg border border-dashed border-zinc-700 flex items-center justify-center text-[11px] text-zinc-500 text-center p-3">
                  No Wi-Fi address found
                </div>
              )}
              <div className="space-y-3 text-xs">
                <ol className="space-y-1 text-zinc-400 list-decimal list-inside">
                  <li>Start Agent KitKat with start.bat and keep both windows open.</li>
                  <li>Put your iPhone on the same Wi-Fi as this computer.</li>
                  <li>Scan the QR code with the iPhone camera and open the link in Safari.</li>
                  <li>Tap Share → Add to Home Screen.</li>
                </ol>
                <div className="p-3 rounded-lg bg-zinc-950 border border-zinc-800 space-y-1">
                  <span className="text-[10px] text-zinc-500 uppercase font-mono block">Phone address</span>
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-mono text-zinc-200 break-all">{net.mobile_access_url}</span>
                    <div className="flex gap-1.5 shrink-0">
                      <button onClick={() => copy(net.mobile_access_url, 'Address')} className="px-2.5 py-1.5 rounded-md bg-zinc-800 text-zinc-200 border border-zinc-700/60">Copy</button>
                      <a href={net.mobile_access_url} target="_blank" rel="noopener noreferrer" className="px-2.5 py-1.5 rounded-md bg-zinc-800 text-zinc-200 border border-zinc-700/60 flex items-center gap-1">
                        Open <ExternalLink className="w-3 h-3" />
                      </a>
                    </div>
                  </div>
                  {!net.https && (
                    <p className="text-[11px] text-zinc-500 pt-1">Plain http: works, but iOS won't keep an offline copy. HTTPS setup is in docs/IPHONE.md.</p>
                  )}
                </div>
                <div className="p-3 rounded-lg bg-zinc-950 border border-zinc-800 space-y-1">
                  <span className="text-[10px] text-zinc-500 uppercase font-mono block">Access code (if you can't scan)</span>
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-mono text-zinc-200 break-all">{showCode ? access.token : '•'.repeat(16)}</span>
                    <div className="flex gap-1.5 shrink-0">
                      <button onClick={() => setShowCode((v) => !v)} aria-label={showCode ? 'Hide code' : 'Show code'}
                        className="px-2.5 py-1.5 rounded-md bg-zinc-800 text-zinc-200 border border-zinc-700/60">
                        {showCode ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                      </button>
                      <button onClick={() => copy(access.token, 'Access code')} className="px-2.5 py-1.5 rounded-md bg-zinc-800 text-zinc-200 border border-zinc-700/60">Copy</button>
                    </div>
                  </div>
                </div>
                <button onClick={rotate} className="flex items-center gap-1.5 px-3 py-2 rounded-md text-xs font-medium border border-zinc-700 text-zinc-300 hover:bg-zinc-800">
                  <RefreshCw className="w-3.5 h-3.5" /> New access code (unpairs every phone)
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
