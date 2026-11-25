import React, { useEffect, useState, useCallback } from 'react';
import { Activity, RefreshCw, CheckCircle2, XCircle, MinusCircle, Clock } from 'lucide-react';
import { api } from '../services/api';

function timeAgo(iso) {
  if (!iso) return 'never';
  // Backend stores naive UTC timestamps
  const then = new Date(iso.endsWith('Z') || iso.includes('+') ? iso : `${iso}Z`);
  const mins = Math.round((Date.now() - then.getTime()) / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins} min ago`;
  const hrs = Math.round(mins / 60);
  if (hrs < 48) return `${hrs} h ago`;
  return `${Math.round(hrs / 24)} d ago`;
}

function StatusIcon({ status }) {
  if (status === 'ok') return <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" aria-label="OK" />;
  if (status === 'failed') return <XCircle className="w-3.5 h-3.5 text-red-400" aria-label="Failed" />;
  if (status === 'skipped') return <MinusCircle className="w-3.5 h-3.5 text-zinc-500" aria-label="Skipped" />;
  return <Clock className="w-3.5 h-3.5 text-zinc-500" aria-label="Never run" />;
}

/**
 * Source Health: built only from stored discovery history (SourceRun rows) and stored jobs.
 */
export default function SourceHealthPanel({ refreshKey = 0 }) {
  const [rows, setRows] = useState([]);
  const [lastRun, setLastRun] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const [health, runs] = await Promise.all([api.getSourceHealth(), api.getDiscoveryRuns(1)]);
      setRows(health);
      setLastRun(runs[0] || null);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load, refreshKey]);

  const ok = rows.filter((r) => r.last_status === 'ok').length;
  const failed = rows.filter((r) => r.last_status === 'failed').length;

  return (
    <div className="rounded-xl bg-zinc-900/40 border border-zinc-800 overflow-hidden shadow-sm">
      <div className="px-4 sm:px-6 py-3.5 border-b border-zinc-800/80 flex items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-zinc-100 flex items-center gap-2">
            <Activity className="w-4 h-4 text-zinc-400" /> Source Health
          </h2>
          <p className="text-xs text-zinc-400">
            {rows.length ? `${ok} working · ${failed} failing · ${rows.length - ok - failed} not run / skipped` : 'Job sources and their last results'}
            {lastRun && (
              <> · last run {timeAgo(lastRun.started_at)} ({lastRun.status}{lastRun.status === 'running' ? `: ${lastRun.progress}` : ''})</>
            )}
          </p>
        </div>
        <button
          onClick={load}
          disabled={loading}
          className="p-1.5 rounded-md text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800 disabled:opacity-50"
          title="Refresh"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {error && <div className="px-4 sm:px-6 py-3 text-xs text-red-300">Could not load source health: {error}</div>}

      {lastRun && lastRun.status !== 'running' && (
        <div className="px-4 sm:px-6 py-2.5 border-b border-zinc-800/60 text-[11px] text-zinc-400 flex flex-wrap gap-x-4 gap-y-1">
          <span>Fetched <b className="text-zinc-200">{lastRun.total_fetched}</b></span>
          <span>New <b className="text-zinc-200">{lastRun.new_saved}</b></span>
          <span>Duplicates removed <b className="text-zinc-200">{lastRun.duplicates}</b></span>
          <span>Expired found <b className="text-zinc-200">{lastRun.expired_marked}</b></span>
          <span>Failed sources <b className={lastRun.failed_sources ? 'text-red-300' : 'text-zinc-200'}>{lastRun.failed_sources}</b></span>
        </div>
      )}

      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-left text-zinc-500 border-b border-zinc-800/60">
              <th className="py-2 px-4 font-medium">Source</th>
              <th className="py-2 px-3 font-medium">Last run</th>
              <th className="py-2 px-3 font-medium text-right">Fetched</th>
              <th className="py-2 px-3 font-medium text-right">New</th>
              <th className="py-2 px-3 font-medium text-right">Dupes</th>
              <th className="py-2 px-3 font-medium text-right">Expired</th>
              <th className="py-2 px-3 font-medium">Last success</th>
              <th className="py-2 px-4 font-medium text-right">Stored</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-800/50">
            {rows.map((r) => (
              <tr key={r.source_name} className="align-top">
                <td className="py-2 px-4">
                  <div className="flex items-center gap-1.5 text-zinc-200 font-mono">
                    <StatusIcon status={r.last_status} />
                    {r.source_name}
                  </div>
                  {r.last_error && <div className="text-[10px] text-red-300/90 mt-0.5 max-w-xs break-words">{r.last_error}</div>}
                  {r.last_status === 'skipped' && <div className="text-[10px] text-zinc-500 mt-0.5">Not configured</div>}
                </td>
                <td className="py-2 px-3 text-zinc-400 whitespace-nowrap">{timeAgo(r.last_run_at)}</td>
                <td className="py-2 px-3 text-right text-zinc-300">{r.last_fetched}</td>
                <td className="py-2 px-3 text-right text-zinc-300">{r.last_new}</td>
                <td className="py-2 px-3 text-right text-zinc-300">{r.last_duplicates}</td>
                <td className="py-2 px-3 text-right text-zinc-300">{r.last_expired}</td>
                <td className="py-2 px-3 text-zinc-400 whitespace-nowrap">
                  {timeAgo(r.last_success_at)}
                  {r.success_rate !== null && (
                    <span className="text-zinc-500"> · {Math.round(r.success_rate * 100)}% of last {r.runs_considered}</span>
                  )}
                </td>
                <td className="py-2 px-4 text-right text-zinc-300">
                  {r.jobs_total}
                  {r.jobs_expired > 0 && <span className="text-zinc-500"> ({r.jobs_expired} expired)</span>}
                </td>
              </tr>
            ))}
            {!loading && rows.length === 0 && !error && (
              <tr>
                <td colSpan={8} className="py-6 text-center text-zinc-500">No sources configured.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
