import React, { useState, useEffect, useCallback } from 'react';
import { CheckCircle2, XCircle, Save, AlertTriangle, History, RotateCcw } from 'lucide-react';
import { api } from '../services/api';
import { useToast, useConfirm } from '../components/Feedback';

const STATUS_STYLE = {
  PASS: 'bg-emerald-950/40 text-emerald-400 border-emerald-800/40',
  FAIL: 'bg-red-950/40 text-red-400 border-red-800/40',
  UNKNOWN: 'bg-amber-950/30 text-amber-300 border-amber-800/40',
};
const ANSWER_LABELS = {
  why_join: 'Why do you want to join?',
  relevant_project: 'Most relevant project',
  availability: 'Availability',
  salary_expectation: 'Stipend / salary expectation',
};

/**
 * Review queue. Approving never submits: it fills the form (no submit click) and the final
 * submission is a separate confirmed action in the Tracker. Approval is refused while the
 * grounding check flags claims, unless you tick that you checked them yourself.
 */
export default function ApprovalsPage({ onNavigateTab }) {
  const toast = useToast();
  const confirm = useConfirm();
  const [approvals, setApprovals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState(null);
  const [letter, setLetter] = useState('');
  const [answers, setAnswers] = useState({});
  const [dirty, setDirty] = useState(false);
  const [notes, setNotes] = useState('');
  const [ack, setAck] = useState(false);
  const [versions, setVersions] = useState([]);
  const [showVersions, setShowVersions] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const select = useCallback((appr) => {
    setSelected(appr);
    setLetter(appr?.draft?.cover_letter || '');
    setAnswers({ ...(appr?.draft?.custom_answers || {}) });
    setDirty(false);
    setNotes('');
    setAck(false);
    setShowVersions(false);
    setError(null);
  }, []);

  const load = useCallback(async (keepId) => {
    try {
      setLoading(true);
      const data = await api.getApprovals();
      setApprovals(data);
      const next = data.find((a) => a.id === keepId) || data[0] || null;
      select(next);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [select]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (selected?.draft_id && showVersions) {
      api.getDraftVersions(selected.draft_id).then(setVersions).catch((e) => setError(e.message));
    }
  }, [selected?.draft_id, showVersions]);

  const save = async () => {
    try {
      setBusy(true);
      setError(null);
      await api.updateDraft(selected.draft_id, { cover_letter: letter, custom_answers: answers });
      await load(selected.id);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const restore = async (version) => {
    if (!(await confirm({ title: `Restore version ${version}?`, body: 'Your current text is kept as an earlier version.', confirmLabel: 'Restore' }))) return;
    try {
      await api.restoreDraftVersion(selected.draft_id, version);
      await load(selected.id);
    } catch (err) {
      setError(err.message);
    }
  };

  const decide = async (decision) => {
    if (dirty) {
      setError('Save your edits first.');
      return;
    }
    try {
      setBusy(true);
      setError(null);
      await api.decideApproval(selected.id, decision, notes, ack);
      if (decision === 'approved') {
        // Approval never submits. Fill the form and take a screenshot for your final review.
        try {
          await api.runBrowserAutomation(selected.draft_id, false);
        } catch (bErr) {
          toast.info(`Could not pre-fill the form automatically: ${bErr.message}. Retry from the Tracker or apply manually.`, { title: 'Approved', duration: 10000 });
        }
        onNavigateTab?.('tracker');
      }
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const issues = selected?.draft?.grounding_report || [];
  const unanswered = selected?.draft?.unanswered_questions || [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl sm:text-2xl font-bold text-zinc-100 tracking-tight">Approvals ({approvals.length})</h1>
        <p className="text-xs sm:text-sm text-zinc-400 mt-1">
          Review every word before anything is sent. Approving fills the application form without submitting it.
        </p>
      </div>

      {loading && approvals.length === 0 ? (
        <div className="py-16 text-center text-zinc-500 text-xs sm:text-sm">Loading approval queue...</div>
      ) : approvals.length === 0 ? (
        <div className="rounded-xl bg-zinc-900/40 border border-zinc-800 p-10 text-center space-y-2">
          <CheckCircle2 className="w-10 h-10 text-zinc-400 mx-auto" />
          <p className="text-sm text-zinc-300">Nothing waiting for approval.</p>
          <p className="text-xs text-zinc-500">Prepare an application from Opportunities or Analyse Job.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 sm:gap-6">
          <div className="lg:col-span-4 space-y-2">
            {approvals.map((a) => (
              <button
                key={a.id}
                onClick={() => select(a)}
                className={`w-full text-left p-3.5 rounded-xl border transition-colors ${
                  selected?.id === a.id ? 'bg-zinc-800/80 border-zinc-600' : 'bg-zinc-900/40 border-zinc-800 hover:bg-zinc-900'
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <h3 className="text-xs sm:text-sm font-semibold text-zinc-100 truncate">{a.job_title}</h3>
                  <span className={`px-1.5 py-0.5 rounded text-[10px] font-mono border ${STATUS_STYLE[a.eligibility_status] || STATUS_STYLE.UNKNOWN}`}>
                    {a.eligibility_status}
                  </span>
                </div>
                <p className="text-xs text-zinc-400 mt-0.5 truncate">{a.company_name}</p>
                <p className="text-[10px] text-zinc-500 mt-1">
                  Match {a.match_score}% · {(a.draft?.grounding_report || []).length} flagged claim(s)
                </p>
              </button>
            ))}
          </div>

          {selected && (
            <div className="lg:col-span-8 rounded-xl bg-zinc-900/40 border border-zinc-800 p-4 sm:p-6 space-y-5">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3.5 border-b border-zinc-800">
                <div>
                  <h2 className="text-base sm:text-lg font-semibold text-zinc-100">{selected.job_title}</h2>
                  <p className="text-xs text-zinc-400">
                    {selected.company_name}
                    {selected.job_url && (
                      <>
                        {' · '}
                        <a href={selected.job_url} target="_blank" rel="noreferrer" className="underline hover:text-zinc-200">posting</a>
                      </>
                    )}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <span className="px-2.5 py-0.5 rounded text-xs font-mono bg-zinc-800 text-zinc-200 border border-zinc-700/60">
                    Match {selected.match_score}%
                  </span>
                  <span className={`px-2.5 py-0.5 rounded text-xs font-mono border ${STATUS_STYLE[selected.eligibility_status] || STATUS_STYLE.UNKNOWN}`}>
                    {selected.eligibility_status}
                  </span>
                </div>
              </div>

              {issues.length > 0 && (
                <div className="rounded-lg border border-amber-800/40 bg-amber-950/20 p-3 space-y-1.5" role="alert">
                  <p className="text-xs font-semibold text-amber-200 flex items-center gap-1.5">
                    <AlertTriangle className="w-3.5 h-3.5" /> {issues.length} claim(s) not found in your profile or resume
                  </p>
                  <ul className="space-y-1">
                    {issues.map((i, n) => (
                      <li key={n} className="text-[11px] text-amber-100/90">
                        <span className="font-mono text-amber-300/80">{i.where}</span>: {i.issue}
                        <span className="block text-amber-100/50 italic">“{i.sentence}”</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              <div className="space-y-1.5">
                <label htmlFor="cover" className="text-xs font-medium text-zinc-300">Cover letter</label>
                <textarea
                  id="cover"
                  rows={9}
                  value={letter}
                  onChange={(e) => {
                    setLetter(e.target.value);
                    setDirty(true);
                  }}
                  className="w-full p-3 rounded-lg bg-zinc-950 border border-zinc-800 text-xs font-mono text-zinc-200 leading-relaxed focus:outline-none focus:border-zinc-600"
                />
              </div>

              <div className="space-y-2">
                <p className="text-xs font-medium text-zinc-300">Screening answers</p>
                {Object.entries(answers).map(([key, val]) => (
                  <div key={key}>
                    <label htmlFor={`ans-${key}`} className="text-[11px] text-zinc-400">{ANSWER_LABELS[key] || key}</label>
                    <textarea
                      id={`ans-${key}`}
                      rows={2}
                      value={val === 'NEEDS_YOUR_INPUT' ? '' : val}
                      placeholder={val === 'NEEDS_YOUR_INPUT' ? 'Needs your input: write your own answer' : ''}
                      onChange={(e) => {
                        setAnswers({ ...answers, [key]: e.target.value || 'NEEDS_YOUR_INPUT' });
                        setDirty(true);
                      }}
                      className={`w-full p-2 rounded-lg bg-zinc-950 border text-xs text-zinc-200 focus:outline-none ${
                        val === 'NEEDS_YOUR_INPUT' ? 'border-amber-800/60' : 'border-zinc-800'
                      }`}
                    />
                  </div>
                ))}
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <button
                  onClick={save}
                  disabled={!dirty || busy}
                  className="px-3 py-1.5 rounded-md text-xs font-medium bg-zinc-800 hover:bg-zinc-700 text-zinc-100 border border-zinc-700 disabled:opacity-40 flex items-center gap-1.5"
                >
                  <Save className="w-3.5 h-3.5" /> Save (new version, re-checks claims)
                </button>
                <button
                  onClick={() => setShowVersions((v) => !v)}
                  className="px-3 py-1.5 rounded-md text-xs text-zinc-300 hover:bg-zinc-800 flex items-center gap-1.5"
                >
                  <History className="w-3.5 h-3.5" /> Version {selected.draft?.current_version || 1} · history
                </button>
              </div>

              {showVersions && (
                <ul className="rounded-lg border border-zinc-800 divide-y divide-zinc-800/60 text-xs">
                  {versions.map((v) => (
                    <li key={v.id} className="p-2.5 flex items-center justify-between gap-2">
                      <span className="text-zinc-300">
                        v{v.version} · {v.source} · {new Date(v.created_at).toLocaleString()} · {v.grounding_report.length} flag(s)
                      </span>
                      {v.version !== selected.draft?.current_version && (
                        <button onClick={() => restore(v.version)} className="text-zinc-400 hover:text-zinc-100 flex items-center gap-1">
                          <RotateCcw className="w-3 h-3" /> Restore
                        </button>
                      )}
                    </li>
                  ))}
                </ul>
              )}

              <div className="space-y-1.5">
                <p className="text-xs font-medium text-zinc-300">Form fields that will be filled</p>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 text-xs">
                  {Object.entries(selected.draft?.form_field_values || {}).map(([k, v]) => (
                    <div key={k} className="p-2 rounded-md bg-zinc-900 border border-zinc-800">
                      <span className="text-[10px] text-zinc-500 block uppercase font-mono">{k}</span>
                      <span className={`font-medium truncate block ${v ? 'text-zinc-200' : 'text-amber-300/80'}`}>{v ? String(v) : 'missing'}</span>
                    </div>
                  ))}
                </div>
                {unanswered.length > 0 && (
                  <ul className="text-[11px] text-zinc-400 list-disc pl-4">
                    {unanswered.map((u, i) => <li key={i}>{u}</li>)}
                  </ul>
                )}
              </div>

              <div className="space-y-1.5">
                <label htmlFor="notes" className="text-xs font-medium text-zinc-300">Decision notes (optional)</label>
                <input
                  id="notes"
                  type="text"
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg bg-zinc-900 border border-zinc-800 text-xs text-zinc-100 focus:outline-none focus:border-zinc-600"
                />
              </div>

              {issues.length > 0 && (
                <label className="flex items-start gap-2 text-xs text-amber-200">
                  <input type="checkbox" checked={ack} onChange={(e) => setAck(e.target.checked)} className="mt-0.5" />
                  I checked every flagged claim above and it is true.
                </label>
              )}

              {error && <p className="text-xs text-red-300" role="alert">{error}</p>}

              <div className="pt-3 border-t border-zinc-800 flex flex-wrap items-center justify-between gap-2.5">
                <button
                  onClick={() => decide('rejected')}
                  disabled={busy}
                  className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-xs font-medium bg-zinc-900 hover:bg-red-950/40 text-zinc-400 hover:text-red-300 border border-zinc-800 disabled:opacity-50"
                >
                  <XCircle className="w-3.5 h-3.5" /> Reject
                </button>
                <button
                  onClick={() => decide('approved')}
                  disabled={busy || dirty || (issues.length > 0 && !ack)}
                  title={issues.length > 0 && !ack ? 'Fix or confirm the flagged claims first' : ''}
                  className="flex items-center gap-2 px-4 py-2 rounded-lg text-xs sm:text-sm font-medium bg-zinc-100 hover:bg-zinc-200 text-zinc-950 disabled:opacity-40"
                >
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  {busy ? 'Working…' : 'Approve & fill form (does not submit)'}
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
