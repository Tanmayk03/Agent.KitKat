import React, { useState, useEffect, useCallback } from 'react';
import { Calendar, Save, RefreshCw, AlertTriangle, Bell, Star } from 'lucide-react';
import { api } from '../services/api';

// Every number here comes from /api/reports/daily (computed live from the
// database for the chosen day in your timezone) or a saved snapshot.

const ACTIVITY_ROWS = [
  ['discovery_runs', 'Discovery runs'],
  ['scheduled_runs', '…of which scheduled'],
  ['discovery_runs_failed', 'Runs that failed'],
  ['listings_fetched', 'Listings fetched from sources'],
  ['new_jobs', 'New jobs stored'],
  ['expired_found', 'Listings marked expired'],
  ['evaluated', 'Jobs evaluated'],
  ['eligible', 'Eligible (PASS)'],
  ['ineligible', 'Not eligible (FAIL)'],
  ['unknown', 'Needs your check (UNKNOWN)'],
  ['eligible_above_threshold', 'Eligible and above your match threshold'],
  ['shortlisted_by_you', 'Shortlisted by you'],
  ['drafts_prepared', 'Drafts prepared'],
  ['approvals_decided', 'Approvals you decided'],
  ['submitted', 'Applications submitted'],
  ['source_failures', 'Source errors'],
];

function Stat({ label, value, tone = 'text-zinc-100' }) {
  return (
    <div className="p-3 rounded-lg bg-zinc-900 border border-zinc-800">
      <span className="text-zinc-400 block mb-1 text-xs">{label}</span>
      <span className={`text-lg sm:text-xl font-semibold font-mono ${tone}`}>{value ?? 0}</span>
    </div>
  );
}

const todayStr = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
};

export default function DailyReportsPage({ onNavigateTab = () => {} }) {
  const [day, setDay] = useState(todayStr());
  const [report, setReport] = useState(null);
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const loadHistory = useCallback(async () => {
    try { setHistory(await api.getReportHistory()); } catch { /* history is optional */ }
  }, []);

  const loadDay = useCallback(async (d) => {
    setLoading(true); setError(''); setNotice('');
    try { setReport(await api.getDailyReport(d)); }
    catch (e) { setError(e.message || 'Could not load the report.'); setReport(null); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { loadHistory(); }, [loadHistory]);
  useEffect(() => { loadDay(day); }, [day, loadDay]);

  const save = async () => {
    setSaving(true); setError('');
    try {
      setReport(await api.generateDailyReport(day));
      await loadHistory();
      setNotice(`Saved a snapshot for ${day}.`);
    } catch (e) { setError(e.message || 'Could not save the report.'); }
    finally { setSaving(false); }
  };

  const d = report?.details_json || {};
  const a = d.activity || {};
  const s = d.snapshot || {};
  const resp = a.responses && typeof a.responses === 'object' ? a.responses : {};
  const respTotal = Object.values(resp).reduce((x, y) => x + (Number(y) || 0), 0);
  const isLive = report && String(report.id).startsWith('live-');

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-3">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-zinc-100 tracking-tight">Daily reports</h1>
          <p className="text-xs sm:text-sm text-zinc-400 mt-1 max-w-2xl">
            What happened on a given day{d.timezone ? ` (${d.timezone})` : ''}, counted from database records.
            Nothing here is estimated.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <label className="flex items-center gap-1.5 text-xs text-zinc-400">
            <Calendar className="w-3.5 h-3.5" />
            <input
              type="date"
              value={day}
              max={todayStr()}
              onChange={(e) => e.target.value && setDay(e.target.value)}
              className="bg-zinc-900 border border-zinc-700 rounded px-2 py-1.5 text-zinc-100 text-xs"
              aria-label="Report day"
            />
          </label>
          <button onClick={() => loadDay(day)} className="p-2 rounded border border-zinc-700 text-zinc-300 hover:bg-zinc-800" title="Refresh" aria-label="Refresh">
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
          <button onClick={save} disabled={saving || loading}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-zinc-100 text-zinc-900 text-xs font-medium disabled:opacity-50">
            <Save className="w-3.5 h-3.5" />{saving ? 'Saving…' : 'Save snapshot'}
          </button>
        </div>
      </div>

      {error && <div className="p-3 rounded border border-red-900 bg-red-950/40 text-red-300 text-xs">{error}</div>}
      {notice && <div className="p-3 rounded border border-emerald-900 bg-emerald-950/30 text-emerald-300 text-xs">{notice}</div>}

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
        <div className="lg:col-span-8 space-y-5">
          {loading ? (
            <div className="py-16 text-center text-zinc-500 text-sm">Loading…</div>
          ) : report && (
            <>
              <div className="text-xs text-zinc-500">
                {isLive ? 'Live view (not saved).' : `Saved snapshot from ${new Date(report.created_at).toLocaleString()}.`}
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
                <Stat label="New jobs stored" value={a.new_jobs} />
                <Stat label="Eligible (PASS)" value={a.eligible} tone="text-emerald-400" />
                <Stat label="Drafts prepared" value={a.drafts_prepared} />
                <Stat label="Submitted" value={a.submitted} />
                <Stat label="Pending your approval" value={s.pending_approvals} tone="text-amber-300" />
                <Stat label="Follow-ups due" value={s.follow_ups_due} tone="text-amber-300" />
                <Stat label="Responses" value={respTotal} />
                <Stat label="Source errors" value={a.source_failures} tone={a.source_failures ? 'text-red-400' : 'text-zinc-100'} />
              </div>

              <section className="rounded-xl bg-zinc-900/40 border border-zinc-800 p-4">
                <h2 className="text-sm font-semibold text-zinc-100 mb-3">Activity on {d.day}</h2>
                <dl className="divide-y divide-zinc-800/70 text-xs">
                  {ACTIVITY_ROWS.map(([k, label]) => (
                    <div key={k} className="flex justify-between py-1.5">
                      <dt className="text-zinc-400">{label}</dt>
                      <dd className="font-mono text-zinc-100">{a[k] ?? 0}</dd>
                    </div>
                  ))}
                  <div className="flex justify-between py-1.5">
                    <dt className="text-zinc-400">Responses recorded</dt>
                    <dd className="font-mono text-zinc-100 text-right">
                      {respTotal}
                      {respTotal > 0 && (
                        <span className="block text-[10px] text-zinc-500">
                          {Object.entries(resp).filter(([, v]) => v).map(([k, v]) => `${k.replace(/_/g, ' ')}: ${v}`).join(' · ')}
                        </span>
                      )}
                    </dd>
                  </div>
                </dl>
                {d.min_match_score != null && (
                  <p className="text-[11px] text-zinc-500 mt-2">Match threshold: {d.min_match_score}</p>
                )}
              </section>

              {(d.top_new || []).length > 0 && (
                <section className="rounded-xl bg-zinc-900/40 border border-zinc-800 p-4">
                  <h2 className="text-sm font-semibold text-zinc-100 mb-3 flex items-center gap-1.5"><Star className="w-4 h-4 text-amber-300" />Best new eligible jobs</h2>
                  <ul className="space-y-2 text-xs">
                    {d.top_new.map((j) => (
                      <li key={j.job_id} className="flex justify-between gap-3">
                        <span className="text-zinc-200">{j.title} <span className="text-zinc-500">· {j.company}{j.location ? ` · ${j.location}` : ''}</span></span>
                        <span className="font-mono text-zinc-300">{j.score != null ? Math.round(j.score) : '—'}</span>
                      </li>
                    ))}
                  </ul>
                  <button onClick={() => onNavigateTab('opportunities')} className="text-[11px] text-zinc-400 underline mt-2">Open opportunities</button>
                </section>
              )}

              {(d.follow_ups || []).length > 0 && (
                <section className="rounded-xl bg-zinc-900/40 border border-zinc-800 p-4">
                  <h2 className="text-sm font-semibold text-zinc-100 mb-3 flex items-center gap-1.5"><Bell className="w-4 h-4 text-amber-300" />Follow-ups due</h2>
                  <ul className="space-y-1.5 text-xs">
                    {d.follow_ups.map((f) => (
                      <li key={f.application_id} className="flex justify-between gap-3">
                        <span className="text-zinc-200">{f.title} <span className="text-zinc-500">· {f.company} · {f.stage}</span></span>
                        <span className="font-mono text-amber-300">{f.date}</span>
                      </li>
                    ))}
                  </ul>
                  <button onClick={() => onNavigateTab('tracker')} className="text-[11px] text-zinc-400 underline mt-2">Open tracker</button>
                </section>
              )}

              {(d.source_failures || []).length > 0 && (
                <section className="rounded-xl bg-red-950/20 border border-red-900/60 p-4">
                  <h2 className="text-sm font-semibold text-red-300 mb-3 flex items-center gap-1.5"><AlertTriangle className="w-4 h-4" />Source errors</h2>
                  <ul className="space-y-1.5 text-xs">
                    {d.source_failures.map((f, i) => (
                      <li key={i} className="text-zinc-300"><span className="font-medium">{f.source}</span>: <span className="text-zinc-400">{f.error || 'unknown error'}</span></li>
                    ))}
                  </ul>
                </section>
              )}

              {Object.keys(s.applications_by_stage || {}).length > 0 && (
                <section className="rounded-xl bg-zinc-900/40 border border-zinc-800 p-4">
                  <h2 className="text-sm font-semibold text-zinc-100 mb-3">Applications by stage (now)</h2>
                  <div className="flex flex-wrap gap-2 text-xs">
                    {Object.entries(s.applications_by_stage).map(([k, v]) => (
                      <span key={k} className="px-2 py-1 rounded bg-zinc-900 border border-zinc-800 text-zinc-300">{k}: <span className="font-mono">{v}</span></span>
                    ))}
                  </div>
                </section>
              )}
            </>
          )}
        </div>

        <aside className="lg:col-span-4 space-y-2">
          <span className="text-xs font-medium text-zinc-400 uppercase tracking-wider block px-1">Saved snapshots</span>
          {history.length === 0 && <p className="text-xs text-zinc-500 px-1">None yet. The scheduler saves one after each run, or use “Save snapshot”.</p>}
          {history.map((r) => (
            <button key={r.id} onClick={() => setDay(r.report_date)}
              className={`w-full text-left p-3 rounded-lg border transition-colors ${r.report_date === day ? 'bg-zinc-800/90 border-zinc-600' : 'bg-zinc-900/40 border-zinc-800 hover:border-zinc-700'}`}>
              <div className="flex justify-between text-xs">
                <span className="font-mono text-zinc-100">{r.report_date}</span>
                <span className="font-mono text-zinc-400">{r.new_found} new</span>
              </div>
              <div className="text-[10px] text-zinc-500 mt-1 font-mono">
                {r.eligible_count} eligible · {r.prepared_count} prepared · {r.submitted_count} submitted
              </div>
            </button>
          ))}
        </aside>
      </div>
    </div>
  );
}
