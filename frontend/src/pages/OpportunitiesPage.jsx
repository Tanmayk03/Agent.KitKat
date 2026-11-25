import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  Search, ExternalLink, ChevronLeft, ChevronRight, ChevronDown, ChevronUp, ListChecks, Sparkles, Bookmark,
} from 'lucide-react';
import { api } from '../services/api';
import { useToast, useConfirm, Loading, EmptyState, ErrorState } from '../components/Feedback';
import EvaluationView from '../components/EvaluationView';

// Every value shown comes from /api/jobs/opportunities: the stored job, its latest
// eligibility and match result, and its tracker entry. Nothing is computed here.

const ELIGIBILITY_CHIPS = [
  ['all', 'All'],
  ['PASS', 'Eligible'],
  ['UNKNOWN', 'Needs checking'],
  ['unevaluated', 'Not evaluated'],
  ['FAIL', 'Not eligible'],
];

const BADGE = {
  PASS: ['Eligible', 'bg-emerald-950/40 text-emerald-400 border-emerald-800/40'],
  UNKNOWN: ['Needs checking', 'bg-amber-950/30 text-amber-300 border-amber-800/40'],
  FAIL: ['Not eligible', 'bg-red-950/40 text-red-400 border-red-800/40'],
};

function EligibilityBadge({ status }) {
  const [label, cls] = BADGE[status] || ['Not evaluated', 'bg-zinc-800 text-zinc-400 border-zinc-700/60'];
  return <span className={`px-2 py-0.5 rounded text-[10px] sm:text-[11px] font-medium border whitespace-nowrap ${cls}`}>{label}</span>;
}

function Score({ value, above }) {
  if (value == null) return <span className="text-[11px] text-zinc-500">No score yet</span>;
  const pct = Math.max(0, Math.min(100, value));
  return (
    <div className="flex items-center gap-2 min-w-[120px]" title="Match score out of 100">
      <div className="flex-1 h-1.5 rounded bg-zinc-800 overflow-hidden">
        <div className={`h-full ${above ? 'bg-emerald-400' : 'bg-zinc-400'}`} style={{ width: `${pct}%` }} />
      </div>
      <span className={`font-mono text-xs font-semibold ${above ? 'text-emerald-300' : 'text-zinc-300'}`}>{Math.round(value)}</span>
    </div>
  );
}

function useDebounced(value, ms = 300) {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return v;
}

const PAGE_SIZE = 20;

export default function OpportunitiesPage({ onNavigateTab, refreshKey = 0 }) {
  const toast = useToast();
  const confirm = useConfirm();

  const [query, setQuery] = useState('');
  const q = useDebounced(query);
  const [eligibility, setEligibility] = useState('all');
  const [sort, setSort] = useState('best');
  const [remoteOnly, setRemoteOnly] = useState(false);
  const [includeExpired, setIncludeExpired] = useState(false);
  const [tracked, setTracked] = useState('all');
  const [page, setPage] = useState(1);

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState({});          // jobId -> 'shortlist' | 'prepare' | 'evaluate'
  const [expanded, setExpanded] = useState(null);  // jobId
  const [evaluation, setEvaluation] = useState({}); // jobId -> MatchResponse
  const topRef = useRef(null);
  const reqId = useRef(0);

  const load = useCallback(async () => {
    const id = ++reqId.current;
    setLoading(true);
    setError('');
    try {
      const d = await api.getOpportunities({
        q, eligibility, sort, page, page_size: PAGE_SIZE,
        remote_only: remoteOnly || undefined, include_expired: includeExpired || undefined,
        tracked: tracked === 'all' ? undefined : tracked,
      });
      if (id === reqId.current) setData(d);
    } catch (e) {
      if (id === reqId.current) setError(e.message || 'Could not load opportunities.');
    } finally {
      if (id === reqId.current) setLoading(false);
    }
  }, [q, eligibility, sort, page, remoteOnly, includeExpired, tracked]);

  useEffect(() => { load(); }, [load, refreshKey]);
  // Any filter change goes back to page 1.
  useEffect(() => { setPage(1); }, [q, eligibility, sort, remoteOnly, includeExpired, tracked]);

  const goPage = (p) => {
    setPage(p);
    topRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  const patchItem = (jobId, patch) =>
    setData((d) => d && { ...d, items: d.items.map((i) => (i.id === jobId ? { ...i, ...patch } : i)) });

  const run = async (jobId, kind, fn) => {
    setBusy((b) => ({ ...b, [jobId]: kind }));
    try { await fn(); } finally { setBusy((b) => { const n = { ...b }; delete n[jobId]; return n; }); }
  };

  const shortlist = (job) => run(job.id, 'shortlist', async () => {
    try {
      const app = await api.shortlistJob(job.id);
      patchItem(job.id, { application_id: app.id, application_stage: app.stage, application_stage_label: app.stage_label });
      toast.success(`${job.title} at ${job.company} added to your tracker.`);
    } catch (e) {
      if (String(e.message).startsWith('Already tracked')) {
        toast.info('This job is already in your tracker.');
        load();
      } else {
        toast.error(`Could not shortlist: ${e.message}`);
      }
    }
  });

  const evaluate = (job) => run(job.id, 'evaluate', async () => {
    try {
      const r = await api.evaluateJob(job.id);
      setEvaluation((m) => ({ ...m, [job.id]: r }));
      toast.success(`Evaluated: ${r.eligibility?.overall_status || 'done'}, score ${Math.round(r.overall_score ?? 0)}.`);
      load();
    } catch (e) {
      toast.error(`Could not evaluate: ${e.message}`);
    }
  });

  const prepare = async (job) => {
    if (job.eligibility_status === 'FAIL') {
      const ok = await confirm({
        title: 'Prepare anyway?',
        body: `This job failed a hard requirement:\n• ${(job.eligibility_reasons || []).join('\n• ') || 'see details'}\n\nA draft is only prepared; nothing is sent.`,
        confirmLabel: 'Prepare draft',
      });
      if (!ok) return;
    }
    run(job.id, 'prepare', async () => {
      try {
        await api.prepareApplication(job.id);
        toast.success('Draft prepared. Review it in Approvals.');
        onNavigateTab?.('approvals');
      } catch (e) {
        toast.error(`Could not prepare application: ${e.message}`);
      }
    });
  };

  const toggleDetails = async (job) => {
    if (expanded === job.id) { setExpanded(null); return; }
    setExpanded(job.id);
    if (!evaluation[job.id] && job.eligibility_status) {
      try {
        const r = await api.getEvaluation(job.id);
        setEvaluation((m) => ({ ...m, [job.id]: r }));
      } catch (e) {
        toast.error(`Could not load the evaluation: ${e.message}`);
      }
    }
  };

  const facets = data?.facets || {};
  const items = data?.items || [];
  const filtersActive = q || eligibility !== 'all' || remoteOnly || includeExpired || tracked !== 'all';

  return (
    <div className="space-y-5" ref={topRef}>
      <div>
        <h1 className="text-xl sm:text-2xl font-bold text-zinc-100 tracking-tight">
          Opportunities {data ? <span className="text-zinc-500 font-normal">({data.total})</span> : null}
        </h1>
        <p className="text-xs sm:text-sm text-zinc-400 mt-1">
          Eligible jobs first, then ones that need checking, then unevaluated, then ineligible. Within each group, best match first.
          {data ? ` Highlighted scores are at or above your ${data.min_match_score}% threshold.` : ''}
        </p>
      </div>

      {/* Controls */}
      <div className="space-y-3">
        <div className="flex flex-col sm:flex-row gap-2.5">
          <div className="relative flex-1 sm:max-w-sm">
            <Search className="w-4 h-4 text-zinc-500 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="search"
              placeholder="Search role, company or city"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              aria-label="Search opportunities"
              className="w-full pl-9 pr-3 py-2.5 sm:py-2 rounded-lg bg-zinc-900 border border-zinc-800 text-sm text-zinc-100 placeholder-zinc-500 focus:outline-none focus:border-zinc-600"
            />
          </div>
          <div className="flex gap-2">
            <select value={sort} onChange={(e) => setSort(e.target.value)} aria-label="Sort"
              className="flex-1 sm:flex-none px-3 py-2.5 sm:py-2 rounded-lg bg-zinc-900 border border-zinc-800 text-sm text-zinc-100">
              <option value="best">Best first</option>
              <option value="score">Highest score</option>
              <option value="newest">Newest found</option>
              <option value="posted">Recently posted</option>
            </select>
            <select value={tracked} onChange={(e) => setTracked(e.target.value)} aria-label="Tracking"
              className="flex-1 sm:flex-none px-3 py-2.5 sm:py-2 rounded-lg bg-zinc-900 border border-zinc-800 text-sm text-zinc-100">
              <option value="all">Tracked or not</option>
              <option value="no">Not tracked</option>
              <option value="yes">In tracker</option>
            </select>
          </div>
        </div>

        <div className="flex gap-1.5 overflow-x-auto pb-1 -mx-1 px-1" role="tablist" aria-label="Eligibility">
          {ELIGIBILITY_CHIPS.map(([id, label]) => (
            <button
              key={id}
              role="tab"
              aria-selected={eligibility === id}
              aria-label={facets[id] != null ? `${label} (${facets[id]})` : label}
              onClick={() => setEligibility(id)}
              className={`px-3 py-1.5 rounded-full text-xs font-medium whitespace-nowrap border transition-colors ${
                eligibility === id ? 'bg-zinc-100 text-zinc-950 border-zinc-100' : 'bg-zinc-900 text-zinc-400 border-zinc-800 hover:text-zinc-200'
              }`}
            >
              {label}{facets[id] != null ? <span className="ml-1 opacity-70 font-mono">{facets[id]}</span> : null}
            </button>
          ))}
        </div>

        <div className="flex flex-wrap gap-x-4 gap-y-2 text-xs text-zinc-400">
          <label className="flex items-center gap-1.5 cursor-pointer">
            <input type="checkbox" checked={remoteOnly} onChange={(e) => setRemoteOnly(e.target.checked)} className="accent-zinc-200 w-4 h-4" />
            Remote only
          </label>
          <label className="flex items-center gap-1.5 cursor-pointer">
            <input type="checkbox" checked={includeExpired} onChange={(e) => setIncludeExpired(e.target.checked)} className="accent-zinc-200 w-4 h-4" />
            Include listings no longer posted
          </label>
        </div>
      </div>

      {error && <ErrorState message={error} onRetry={load} />}

      {loading && !data ? (
        <Loading label="Loading opportunities…" />
      ) : items.length === 0 && !error ? (
        filtersActive ? (
          <EmptyState title="No jobs match these filters.">Clear the search or pick another eligibility group.</EmptyState>
        ) : (
          <EmptyState
            title="No jobs yet."
            action={
              <button onClick={() => onNavigateTab?.('dashboard')} className="px-3.5 py-2 rounded-lg text-xs font-medium bg-zinc-100 text-zinc-950">
                Run discovery from the Dashboard
              </button>
            }
          >
            Run discovery, follow company career boards in Settings, or paste a posting in Analyze Job.
          </EmptyState>
        )
      ) : (
        <div className={`grid grid-cols-1 xl:grid-cols-2 gap-3 sm:gap-4 transition-opacity ${loading ? 'opacity-60' : ''}`} aria-busy={loading}>
          {items.map((job) => {
            const b = busy[job.id];
            const expired = job.status === 'expired';
            const isOpen = expanded === job.id;
            return (
              <article key={job.id} className={`rounded-xl border p-4 sm:p-5 flex flex-col gap-3 ${
                job.above_threshold ? 'border-emerald-900/60 bg-emerald-950/5' : 'border-zinc-800 bg-zinc-900/40'
              }`}>
                <header className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <h3 className="text-sm sm:text-base font-semibold text-zinc-100 leading-snug">{job.title}</h3>
                    <p className="text-xs text-zinc-300 mt-0.5">{job.company}</p>
                  </div>
                  <EligibilityBadge status={job.eligibility_status} />
                </header>

                <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px] sm:text-xs text-zinc-400">
                  <span>{job.location}</span>
                  <span aria-hidden>·</span><span>{job.work_mode}</span>
                  {job.salary_stipend && (<><span aria-hidden>·</span><span className="font-mono text-zinc-300">{job.salary_stipend}</span></>)}
                  {job.posted_at && (<><span aria-hidden>·</span><span>Posted {job.posted_at.slice(0, 10)}</span></>)}
                  {expired && (<><span aria-hidden>·</span><span className="text-amber-300">No longer listed</span></>)}
                  <span aria-hidden>·</span><span className="uppercase font-mono text-[10px] text-zinc-500">{job.source}</span>
                </div>

                <Score value={job.match_score} above={job.above_threshold} />

                {job.eligibility_reasons?.length > 0 && (
                  <ul className={`text-[11px] sm:text-xs space-y-0.5 ${job.eligibility_status === 'FAIL' ? 'text-red-300/90' : 'text-amber-200/90'}`}>
                    {job.eligibility_reasons.map((r, i) => <li key={i}>• {r}</li>)}
                  </ul>
                )}

                {(job.matching_skills?.length > 0 || job.missing_skills?.length > 0) && (
                  <div className="flex flex-wrap gap-1">
                    {job.matching_skills.map((s) => (
                      <span key={`m-${s}`} className="px-1.5 py-0.5 rounded text-[10px] bg-emerald-950/30 text-emerald-300 border border-emerald-900/50">{s}</span>
                    ))}
                    {job.missing_skills.map((s) => (
                      <span key={`x-${s}`} className="px-1.5 py-0.5 rounded text-[10px] bg-zinc-900 text-zinc-500 border border-zinc-800 line-through decoration-zinc-600" title="Asked for, not in your profile">{s}</span>
                    ))}
                  </div>
                )}

                {job.next_action && (
                  <p className="text-xs text-zinc-300 flex gap-1.5"><Sparkles className="w-3.5 h-3.5 mt-0.5 text-zinc-500 shrink-0" /><span>{job.next_action}</span></p>
                )}

                {isOpen && (
                  <div className="pt-2 border-t border-zinc-800/80">
                    {job.description && <p className="text-xs text-zinc-400 leading-relaxed mb-3">{job.description}{job.description.length >= 400 ? '…' : ''}</p>}
                    {evaluation[job.id] ? <EvaluationView evaluation={evaluation[job.id]} />
                      : job.eligibility_status ? <Loading label="Loading evaluation…" className="py-6" />
                      : <p className="text-xs text-zinc-500">Not evaluated yet.</p>}
                  </div>
                )}

                <footer className="pt-3 mt-auto border-t border-zinc-800/80 flex flex-wrap items-center gap-2">
                  {job.url && (
                    <a href={job.url} target="_blank" rel="noopener noreferrer"
                      className="flex items-center gap-1 text-xs font-medium text-zinc-400 hover:text-zinc-200 py-2 pr-1">
                      Posting <ExternalLink className="w-3.5 h-3.5" />
                    </a>
                  )}
                  <button onClick={() => toggleDetails(job)} aria-expanded={isOpen}
                    className="flex items-center gap-1 text-xs font-medium text-zinc-400 hover:text-zinc-200 py-2 px-1">
                    Details {isOpen ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                  </button>

                  <div className="flex gap-2 ml-auto">
                    {!job.eligibility_status && (
                      <button onClick={() => evaluate(job)} disabled={!!b}
                        className="px-3 py-2 rounded-lg text-xs font-medium bg-zinc-800 hover:bg-zinc-700 text-zinc-200 border border-zinc-700/60 disabled:opacity-50">
                        {b === 'evaluate' ? 'Evaluating…' : 'Evaluate'}
                      </button>
                    )}
                    {job.application_id ? (
                      <button onClick={() => onNavigateTab?.('tracker')}
                        className="flex items-center gap-1 px-3 py-2 rounded-lg text-xs font-medium border border-zinc-700 text-zinc-300 hover:bg-zinc-800"
                        title={`In your tracker, stage: ${job.application_stage_label}. Open the tracker.`}>
                        <ListChecks className="w-3.5 h-3.5" /> In tracker
                      </button>
                    ) : (
                      <button onClick={() => shortlist(job)} disabled={!!b || expired}
                        className="flex items-center gap-1 px-3 py-2 rounded-lg text-xs font-medium bg-zinc-800 hover:bg-zinc-700 text-zinc-200 border border-zinc-700/60 disabled:opacity-50">
                        <Bookmark className="w-3.5 h-3.5" /> {b === 'shortlist' ? 'Adding…' : 'Shortlist'}
                      </button>
                    )}
                    <button onClick={() => prepare(job)} disabled={!!b || expired}
                      className="px-3 py-2 rounded-lg text-xs font-medium bg-zinc-100 hover:bg-zinc-200 text-zinc-950 disabled:opacity-50">
                      {b === 'prepare' ? 'Drafting…' : 'Prepare'}
                    </button>
                  </div>
                </footer>
              </article>
            );
          })}
        </div>
      )}

      {data && data.pages > 1 && (
        <nav className="flex items-center justify-between gap-3 pt-2" aria-label="Pages">
          <button onClick={() => goPage(page - 1)} disabled={page <= 1 || loading}
            className="flex items-center gap-1 px-3 py-2 rounded-lg text-xs border border-zinc-800 text-zinc-300 disabled:opacity-40">
            <ChevronLeft className="w-4 h-4" /> Previous
          </button>
          <span className="text-xs text-zinc-400">
            Page <span className="font-mono text-zinc-200">{data.page}</span> of <span className="font-mono">{data.pages}</span>
            <span className="hidden sm:inline"> · {(data.page - 1) * data.page_size + 1}–{Math.min(data.page * data.page_size, data.total)} of {data.total}</span>
          </span>
          <button onClick={() => goPage(page + 1)} disabled={page >= data.pages || loading}
            className="flex items-center gap-1 px-3 py-2 rounded-lg text-xs border border-zinc-800 text-zinc-300 disabled:opacity-40">
            Next <ChevronRight className="w-4 h-4" />
          </button>
        </nav>
      )}
    </div>
  );
}
