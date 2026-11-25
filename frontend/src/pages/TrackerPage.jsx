import React, { useCallback, useEffect, useState } from 'react';
import { Search, X, Eye, ExternalLink, Clock } from 'lucide-react';
import { api } from '../services/api';
import { useToast, useConfirm } from '../components/Feedback';

const STAGE_STYLE = {
  discovered: 'text-zinc-400 border-zinc-700',
  shortlisted: 'text-zinc-200 border-zinc-600',
  eligible: 'text-emerald-300 border-emerald-800/50',
  not_eligible: 'text-red-300 border-red-900/50',
  draft_ready: 'text-sky-300 border-sky-900/50',
  awaiting_approval: 'text-amber-300 border-amber-800/50',
  submitted: 'text-emerald-300 border-emerald-800/50',
  submission_unverified: 'text-amber-300 border-amber-800/50',
  application_confirmed: 'text-emerald-300 border-emerald-700',
  assessment_received: 'text-violet-300 border-violet-900/50',
  interview: 'text-violet-200 border-violet-700',
  rejected: 'text-red-300 border-red-900/50',
  withdrawn: 'text-zinc-500 border-zinc-800',
  offer_received: 'text-emerald-200 border-emerald-600',
};
const AUTOMATION_NOTE = {
  filling: 'Filling form…',
  filled_ready_for_review: 'Form filled: review the screenshot',
  paused_captcha: 'Paused: CAPTCHA (finish manually)',
  paused_login: 'Paused: login required',
  paused_unknown_field: 'Paused: questions need your answer',
  halted_emergency: 'Stopped by emergency stop',
  failed: 'Automation failed',
  unsupported_site: 'Site not supported: apply manually (copy prepared application)',
  previewed: 'Form previewed',
};
const ACTION_STYLE = {
  fill: 'text-emerald-300', select: 'text-emerald-300', upload: 'text-emerald-300', keep: 'text-zinc-400',
  needs_input: 'text-amber-300', sensitive: 'text-red-300', manual: 'text-zinc-400',
};
const ACTION_LABEL = {
  fill: 'Will fill', select: 'Will select', upload: 'Will upload resume', keep: 'Already filled',
  needs_input: 'Needs your input', sensitive: 'Sensitive: you answer', manual: 'You answer',
};
const SORTS = [
  ['updated', 'Recently updated'],
  ['applied', 'Application date'],
  ['follow_up', 'Follow-up date'],
  ['score', 'Match score'],
  ['company', 'Company'],
];
const PAGE_SIZE = 20;

function StageBadge({ stage, label }) {
  return (
    <span className={`inline-block px-2 py-0.5 rounded text-[11px] font-medium border bg-zinc-900 ${STAGE_STYLE[stage] || STAGE_STYLE.discovered}`}>
      {label}
    </span>
  );
}

function fmtDate(v) {
  if (!v) return '—';
  const d = new Date(v.endsWith?.('Z') || v.includes?.('+') ? v : `${v}Z`);
  return isNaN(d) ? v : d.toLocaleDateString();
}

export default function TrackerPage() {
  const toast = useToast();
  const confirm = useConfirm();
  const [stages, setStages] = useState({});
  const [data, setData] = useState({ items: [], total: 0, stage_counts: {} });
  const [stageFilter, setStageFilter] = useState('');
  const [q, setQ] = useState('');
  const [sort, setSort] = useState('updated');
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selected, setSelected] = useState(null);
  const [events, setEvents] = useState([]);
  const [form, setForm] = useState({});
  const [runningDraftId, setRunningDraftId] = useState(null);
  const [screenshot, setScreenshot] = useState(null);
  const [preview, setPreview] = useState(null);
  const [previewing, setPreviewing] = useState(false);
  const [exportText, setExportText] = useState(null);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      setData(await api.getApplications({ stage: stageFilter, q, sort, page, page_size: PAGE_SIZE }));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [stageFilter, q, sort, page]);

  useEffect(() => {
    api.getStages().then((s) => setStages(s.stages)).catch(() => {});
  }, []);

  useEffect(() => {
    const t = setTimeout(load, q ? 300 : 0); // debounce search typing
    return () => clearTimeout(t);
  }, [load, q]);

  const open = async (app) => {
    setSelected(app);
    setPreview(app.form_state ? { form_plan: app.form_state.fields || [], adapter: app.form_state.adapter, status: app.form_state.status, mode: app.form_state.mode } : null);
    setExportText(null);
    setForm({ stage: '', note: '', notes: app.notes || '', confirmation_id: app.confirmation_id || '', follow_up_date: app.follow_up_date || '' });
    try {
      setEvents(await api.getApplicationEvents(app.id));
    } catch {
      setEvents([]);
    }
  };

  const runPreview = async () => {
    try {
      setPreviewing(true);
      setError(null);
      const r = await api.previewApplicationForm(selected.draft_id);
      setPreview({ ...r, mode: 'preview' });
      if (r.status === 'unsupported_site' || r.intervention_reason) setError(r.intervention_reason);
    } catch (err) {
      setError(err.message);
    } finally {
      setPreviewing(false);
    }
  };

  const copyExport = async () => {
    try {
      const text = await api.getDraftExport(selected.draft_id);
      setExportText(text);
      try {
        await navigator.clipboard.writeText(text);
      } catch {
        /* clipboard unavailable (http on a LAN IP): the text is shown for manual copy */
      }
    } catch (err) {
      setError(err.message);
    }
  };

  const saveDetails = async () => {
    try {
      setError(null);
      const patch = {
        notes: form.notes,
        confirmation_id: form.confirmation_id,
        follow_up_date: form.follow_up_date,
      };
      if (form.stage) patch.stage = form.stage;
      if (form.note) patch.note = form.note;
      const updated = await api.updateApplication(selected.id, patch);
      await load();
      await open(updated);
    } catch (err) {
      setError(err.message);
    }
  };

  const runBrowser = async (app, submit) => {
    if (submit) {
      const ok = await confirm({
        title: `Submit the application to ${app.company} now?`,
        body: 'Agent KitKat will fill the form again and click Submit. Only continue if you reviewed the pre-submit screenshot and every answer is correct.',
        confirmLabel: 'Submit application',
        danger: true,
      });
      if (!ok) return;
    }
    try {
      setRunningDraftId(app.draft_id);
      const result = await api.runBrowserAutomation(app.draft_id, submit, submit);
      if (result?.intervention_reason) toast.info(result.intervention_reason, { title: `Paused: ${result.status}`, duration: 12000 });
      else if (result?.status) toast.success(`Browser run finished: ${result.status}.`);
      await load();
    } catch (err) {
      toast.error(`Browser automation: ${err.message}`);
    } finally {
      setRunningDraftId(null);
    }
  };

  const sent = (app) => ['submitted', 'submission_unverified', 'application_confirmed', 'assessment_received', 'interview', 'rejected', 'offer_received'].includes(app.stage);
  const totalPages = Math.max(1, Math.ceil(data.total / PAGE_SIZE));
  const allCount = Object.values(data.stage_counts || {}).reduce((a, b) => a + b, 0);

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl sm:text-2xl font-bold text-zinc-100 tracking-tight">Application Tracker</h1>
        <p className="text-xs sm:text-sm text-zinc-400 mt-1">
          Every job you shortlisted or prepared, from shortlist to offer. Changing a stage is recorded in its history.
        </p>
      </div>

      {/* Stage filter chips */}
      <div className="flex flex-wrap gap-1.5">
        <button
          onClick={() => { setStageFilter(''); setPage(1); }}
          className={`px-2.5 py-1 rounded-md text-xs border ${!stageFilter ? 'bg-zinc-100 text-zinc-950 border-zinc-100' : 'text-zinc-300 border-zinc-800 hover:bg-zinc-900'}`}
        >
          All ({allCount})
        </button>
        {Object.entries(stages).map(([key, label]) =>
          data.stage_counts?.[key] ? (
            <button
              key={key}
              onClick={() => { setStageFilter(key); setPage(1); }}
              className={`px-2.5 py-1 rounded-md text-xs border ${stageFilter === key ? 'bg-zinc-100 text-zinc-950 border-zinc-100' : 'text-zinc-300 border-zinc-800 hover:bg-zinc-900'}`}
            >
              {label} ({data.stage_counts[key]})
            </button>
          ) : null
        )}
      </div>

      {/* Search + sort */}
      <div className="flex flex-col sm:flex-row gap-2">
        <div className="relative flex-1">
          <Search className="w-3.5 h-3.5 text-zinc-500 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            value={q}
            onChange={(e) => { setQ(e.target.value); setPage(1); }}
            placeholder="Search company, role, notes, confirmation ID"
            aria-label="Search applications"
            className="w-full pl-8 pr-3 py-2 rounded-lg bg-zinc-900 border border-zinc-800 text-xs text-zinc-100 placeholder-zinc-500"
          />
        </div>
        <select
          value={sort}
          onChange={(e) => setSort(e.target.value)}
          aria-label="Sort"
          className="px-3 py-2 rounded-lg bg-zinc-900 border border-zinc-800 text-xs text-zinc-100"
        >
          {SORTS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select>
      </div>

      {error && <p className="text-xs text-red-300" role="alert">{error}</p>}

      {loading && data.items.length === 0 ? (
        <div className="py-16 text-center text-zinc-500 text-xs">Loading applications…</div>
      ) : data.items.length === 0 ? (
        <div className="rounded-xl bg-zinc-900/40 border border-zinc-800 p-10 text-center text-zinc-500 text-xs">
          {q || stageFilter ? 'No applications match these filters.' : 'Nothing tracked yet. Shortlist or prepare a job from Opportunities.'}
        </div>
      ) : (
        <div className="rounded-xl bg-zinc-900/40 border border-zinc-800 overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-left text-zinc-500 border-b border-zinc-800">
                <th className="py-2.5 px-4 font-medium">Opportunity</th>
                <th className="py-2.5 px-3 font-medium">Stage</th>
                <th className="py-2.5 px-3 font-medium text-right">Match</th>
                <th className="py-2.5 px-3 font-medium">Applied</th>
                <th className="py-2.5 px-3 font-medium">Follow-up</th>
                <th className="py-2.5 px-4 font-medium text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800/60">
              {data.items.map((app) => (
                <tr key={app.id} className="align-top hover:bg-zinc-900/60">
                  <td className="py-2.5 px-4">
                    <button onClick={() => open(app)} className="text-left">
                      <span className="text-zinc-100 font-medium hover:underline">{app.job_title}</span>
                      <span className="block text-zinc-400">{app.company_name} · {app.location || 'location not stated'}</span>
                    </button>
                    {AUTOMATION_NOTE[app.status] && <span className="block text-[10px] text-amber-300/80 mt-0.5">{AUTOMATION_NOTE[app.status]}</span>}
                  </td>
                  <td className="py-2.5 px-3">
                    <StageBadge stage={app.stage} label={app.stage_label} />
                    {app.approval_status === 'approved' && !sent(app) && <span className="block text-[10px] text-emerald-300/80 mt-0.5">Approved · not sent</span>}
                  </td>
                  <td className="py-2.5 px-3 text-right text-zinc-300 font-mono">{app.match_score != null ? `${app.match_score}%` : '—'}</td>
                  <td className="py-2.5 px-3 text-zinc-400 whitespace-nowrap">{fmtDate(app.applied_at)}</td>
                  <td className="py-2.5 px-3 text-zinc-400 whitespace-nowrap">{app.follow_up_date || '—'}</td>
                  <td className="py-2.5 px-4 text-right">
                    <div className="flex justify-end gap-1.5 flex-wrap">
                      {app.draft_id && !sent(app) && app.stage !== 'withdrawn' && (
                        <button
                          onClick={() => runBrowser(app, false)}
                          disabled={runningDraftId === app.draft_id}
                          title="Fill the form and save a screenshot. Never clicks Submit."
                          className="px-2 py-1 rounded-md bg-zinc-800 hover:bg-zinc-700 text-zinc-200 border border-zinc-700/60 disabled:opacity-50"
                        >
                          {runningDraftId === app.draft_id ? 'Running…' : 'Fill (no submit)'}
                        </button>
                      )}
                      {app.draft_id && app.approval_status === 'approved' && !sent(app) && (
                        <button
                          onClick={() => runBrowser(app, true)}
                          disabled={runningDraftId === app.draft_id}
                          className="px-2 py-1 rounded-md bg-amber-700 hover:bg-amber-600 text-white border border-amber-600 disabled:opacity-50"
                        >
                          Submit…
                        </button>
                      )}
                      <button onClick={() => open(app)} className="px-2 py-1 rounded-md text-zinc-300 hover:bg-zinc-800">Details</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="flex items-center justify-between px-4 py-2.5 border-t border-zinc-800 text-xs text-zinc-400">
            <span>{data.total} application(s)</span>
            <div className="flex items-center gap-2">
              <button disabled={page <= 1} onClick={() => setPage(page - 1)} className="px-2 py-1 rounded hover:bg-zinc-800 disabled:opacity-40">Prev</button>
              <span>Page {page} / {totalPages}</span>
              <button disabled={page >= totalPages} onClick={() => setPage(page + 1)} className="px-2 py-1 rounded hover:bg-zinc-800 disabled:opacity-40">Next</button>
            </div>
          </div>
        </div>
      )}

      {/* Detail drawer */}
      {selected && (
        <div className="fixed inset-0 z-[60] flex justify-end bg-zinc-950/70" role="dialog" aria-modal="true" onClick={() => setSelected(null)}>
          <div className="w-full max-w-lg h-full overflow-y-auto bg-zinc-900 border-l border-zinc-800 p-5 space-y-4" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-start justify-between gap-3">
              <div>
                <h2 className="text-sm font-semibold text-zinc-100">{selected.job_title}</h2>
                <p className="text-xs text-zinc-400">{selected.company_name} · {selected.source}</p>
                {selected.job_url && (
                  <a href={selected.job_url} target="_blank" rel="noreferrer" className="text-[11px] text-zinc-400 hover:text-zinc-100 inline-flex items-center gap-1 mt-1">
                    Open posting <ExternalLink className="w-3 h-3" />
                  </a>
                )}
              </div>
              <button onClick={() => setSelected(null)} className="p-1 text-zinc-400 hover:text-zinc-100" aria-label="Close"><X className="w-4 h-4" /></button>
            </div>

            <div className="grid grid-cols-2 gap-2 text-[11px]">
              <div><span className="text-zinc-500 block">Stage</span><StageBadge stage={selected.stage} label={selected.stage_label} /></div>
              <div><span className="text-zinc-500 block">Eligibility</span><span className="text-zinc-200">{selected.eligibility_status || '—'}</span></div>
              <div><span className="text-zinc-500 block">Resume used</span><span className="text-zinc-200">{selected.resume_file_name || '—'}</span></div>
              <div><span className="text-zinc-500 block">Applied</span><span className="text-zinc-200">{fmtDate(selected.applied_at)}</span></div>
              {selected.submission_result && (
                <div className="col-span-2"><span className="text-zinc-500 block">Submission evidence</span><span className="text-zinc-300">{selected.submission_result}</span></div>
              )}
            </div>

            {(selected.pre_submit_screenshot || selected.post_submit_screenshot) && (
              <div className="flex gap-2">
                {selected.pre_submit_screenshot && (
                  <button onClick={() => setScreenshot(`/api/browser/screenshots/${selected.draft_id}/pre_submit.png`)} className="px-2 py-1 rounded bg-zinc-800 text-zinc-300 text-[11px] flex items-center gap-1">
                    <Eye className="w-3 h-3" /> Pre-submit
                  </button>
                )}
                {selected.post_submit_screenshot && (
                  <button onClick={() => setScreenshot(`/api/browser/screenshots/${selected.draft_id}/post_submit.png`)} className="px-2 py-1 rounded bg-zinc-800 text-zinc-300 text-[11px] flex items-center gap-1">
                    <Eye className="w-3 h-3" /> After submit
                  </button>
                )}
              </div>
            )}

            {selected.draft_id && (
              <div className="space-y-2">
                <div className="flex flex-wrap gap-2">
                  {!sent(selected) && (
                    <button onClick={runPreview} disabled={previewing} className="px-2.5 py-1 rounded-md bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-[11px] border border-zinc-700 disabled:opacity-50">
                      {previewing ? 'Reading form…' : 'Preview form (types nothing)'}
                    </button>
                  )}
                  <button onClick={copyExport} className="px-2.5 py-1 rounded-md bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-[11px] border border-zinc-700">
                    Copy prepared application
                  </button>
                </div>
                {exportText && (
                  <textarea readOnly rows={8} value={exportText} aria-label="Prepared application" className="w-full p-2 rounded-md bg-zinc-950 border border-zinc-800 text-[11px] font-mono text-zinc-300" />
                )}
                {preview?.form_plan?.length > 0 && (
                  <div className="rounded-lg border border-zinc-800">
                    <p className="px-2.5 py-1.5 text-[11px] text-zinc-400 border-b border-zinc-800">
                      {preview.mode === 'preview' ? 'Form preview' : 'Last fill'} · {preview.adapter || 'site'} · {preview.form_plan.length} field(s)
                    </p>
                    <table className="w-full text-[11px]">
                      <tbody className="divide-y divide-zinc-800/60">
                        {preview.form_plan.map((f) => (
                          <tr key={f.kk} className="align-top">
                            <td className="px-2.5 py-1 text-zinc-300">
                              {f.label}{f.option ? ` · ${f.option}` : ''}{f.required && <span className="text-red-300"> *</span>}
                            </td>
                            <td className={`px-2.5 py-1 whitespace-nowrap ${ACTION_STYLE[f.action] || 'text-zinc-400'}`}>
                              {f.result && f.result !== 'left for you' ? f.result : ACTION_LABEL[f.action] || f.action}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}

            <div className="space-y-2 text-xs">
              <label className="block">
                <span className="text-zinc-400">Move to stage</span>
                <select
                  value={form.stage}
                  onChange={(e) => setForm({ ...form, stage: e.target.value })}
                  className="mt-1 w-full px-2.5 py-1.5 rounded-md bg-zinc-950 border border-zinc-800 text-zinc-100"
                >
                  <option value="">Keep “{selected.stage_label}”</option>
                  {selected.allowed_next_stages.filter((s) => s !== selected.stage).map((s) => (
                    <option key={s} value={s}>{stages[s] || s}</option>
                  ))}
                </select>
              </label>
              <label className="block">
                <span className="text-zinc-400">Note for the history (optional)</span>
                <input value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} placeholder="e.g. Applied manually on Naukri" className="mt-1 w-full px-2.5 py-1.5 rounded-md bg-zinc-950 border border-zinc-800 text-zinc-100" />
              </label>
              <div className="grid grid-cols-2 gap-2">
                <label className="block">
                  <span className="text-zinc-400">Confirmation ID</span>
                  <input value={form.confirmation_id} onChange={(e) => setForm({ ...form, confirmation_id: e.target.value })} className="mt-1 w-full px-2.5 py-1.5 rounded-md bg-zinc-950 border border-zinc-800 text-zinc-100" />
                </label>
                <label className="block">
                  <span className="text-zinc-400">Follow-up date</span>
                  <input type="date" value={form.follow_up_date} onChange={(e) => setForm({ ...form, follow_up_date: e.target.value })} className="mt-1 w-full px-2.5 py-1.5 rounded-md bg-zinc-950 border border-zinc-800 text-zinc-100" />
                </label>
              </div>
              <label className="block">
                <span className="text-zinc-400">Notes</span>
                <textarea rows={3} value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} className="mt-1 w-full px-2.5 py-1.5 rounded-md bg-zinc-950 border border-zinc-800 text-zinc-100" />
              </label>
              <button onClick={saveDetails} className="px-3 py-1.5 rounded-md bg-zinc-100 text-zinc-950 font-medium">Save</button>
            </div>

            <div>
              <h3 className="text-xs font-semibold text-zinc-200 mb-2 flex items-center gap-1.5"><Clock className="w-3.5 h-3.5" /> History</h3>
              <ol className="space-y-2 border-l border-zinc-800 pl-3">
                {events.map((e) => (
                  <li key={e.id} className="text-[11px]">
                    <span className="text-zinc-500">{new Date(e.created_at.endsWith('Z') ? e.created_at : `${e.created_at}Z`).toLocaleString()} · {e.actor}</span>
                    <span className="block text-zinc-200">
                      {e.from_stage !== e.to_stage ? `${stages[e.from_stage] || e.from_stage} → ${stages[e.to_stage] || e.to_stage}` : 'Note'}
                    </span>
                    {e.note && <span className="block text-zinc-400">{e.note}</span>}
                  </li>
                ))}
                {events.length === 0 && <li className="text-[11px] text-zinc-500">No history yet.</li>}
              </ol>
            </div>
          </div>
        </div>
      )}

      {screenshot && (
        <div className="fixed inset-0 z-[70] flex items-center justify-center bg-zinc-950/85 p-4" onClick={() => setScreenshot(null)}>
          <img src={screenshot} alt="Application form screenshot" className="max-h-[90vh] max-w-full rounded-lg border border-zinc-800" />
        </div>
      )}
    </div>
  );
}
