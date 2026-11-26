import React, { useCallback, useEffect, useState } from 'react';
import { Archive, Download, Loader2 } from 'lucide-react';
import { api } from '../services/api';
import { useToast } from './Feedback';

const mb = (n) => `${(n / 1e6).toFixed(n < 1e6 ? 2 : 1)} MB`;
const LABELS = { auto: 'Automatic', manual: 'Manual', 'pre-restore': 'Before a restore' };

/** Settings → Backups. Listing and "Back up now" work on this computer only; restore is restore.bat. */
export default function BackupsCard() {
  const toast = useToast();
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [local, setLocal] = useState(null);

  const load = useCallback(async () => {
    setError('');
    try {
      const w = await api.whoami();
      setLocal(w.local);
      if (w.local) setData(await api.listBackups());
    } catch (e) {
      setError(e.message || 'Could not list backups.');
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const backupNow = async () => {
    setBusy(true);
    try {
      const b = await api.createBackup();
      toast.success(`Backup saved (${mb(b.size)}, ${b.files} files).`);
      await load();
    } catch (e) {
      toast.error(`Backup failed: ${e.message}`);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="rounded-xl bg-zinc-900/40 border border-zinc-800 p-4 sm:p-6 space-y-3.5">
      <h2 className="text-sm font-semibold text-zinc-100 flex items-center gap-2">
        <Archive className="w-4 h-4 text-zinc-400" /> Backups
      </h2>
      <p className="text-xs text-zinc-400 leading-relaxed">
        A backup holds your database, resumes, prepared applications and screenshots. One is made automatically each day
        (the last 7 are kept). To restore, stop Agent KitKat with stop.bat and run restore.bat; your current data is backed
        up first.
      </p>

      {error && <p className="text-xs text-red-400" role="alert">{error}</p>}
      {local === false && <p className="text-xs text-zinc-500">Backups are managed on your computer.</p>}

      {local && data && (
        <>
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
            <span className="text-[11px] text-zinc-500 font-mono break-all">{data.folder}</span>
            <button onClick={backupNow} disabled={busy}
              className="flex items-center justify-center gap-1.5 px-3 py-2 rounded-md text-xs font-medium bg-zinc-100 text-zinc-950 disabled:opacity-50">
              {busy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Archive className="w-3.5 h-3.5" />} Back up now
            </button>
          </div>
          {data.items.length === 0 ? (
            <p className="text-xs text-zinc-500">No backups yet.</p>
          ) : (
            <ul className="divide-y divide-zinc-800/70 text-xs">
              {data.items.slice(0, 10).map((b) => (
                <li key={b.name} className="py-2 flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <div className="text-zinc-200">
                      {b.created_at ? new Date(b.created_at).toLocaleString() : b.name}
                      <span className="ml-2 text-zinc-500">{LABELS[b.label] || b.label}</span>
                    </div>
                    <div className="text-[11px] text-zinc-500">
                      {b.error ? <span className="text-red-400">{b.error}</span> : (
                        <>{mb(b.size)} · {b.counts?.jobs ?? '?'} jobs · {b.counts?.applications ?? '?'} applications · {b.files} files</>
                      )}
                    </div>
                  </div>
                  <a href={`/api/maintenance/backups/${encodeURIComponent(b.name)}`} download
                    className="shrink-0 p-2 rounded-md border border-zinc-700 text-zinc-300 hover:bg-zinc-800" aria-label={`Download ${b.name}`}>
                    <Download className="w-3.5 h-3.5" />
                  </a>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </div>
  );
}
