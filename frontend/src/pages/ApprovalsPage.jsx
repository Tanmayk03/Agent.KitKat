import React, { useState, useEffect } from 'react';
import {
  CheckSquare,
  CheckCircle2,
  XCircle,
  Sparkles,
  ExternalLink,
  Edit3,
  Save,
  Send,
  Shield,
  Layers,
} from 'lucide-react';
import { api } from '../services/api';

export default function ApprovalsPage({ onNavigateTab }) {
  const [approvals, setApprovals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedApproval, setSelectedApproval] = useState(null);
  const [editingCoverLetter, setEditingCoverLetter] = useState(false);
  const [coverLetterText, setCoverLetterText] = useState('');
  const [decisionNotes, setDecisionNotes] = useState('');
  const [submittingDecision, setSubmittingDecision] = useState(false);

  const fetchApprovals = async () => {
    try {
      setLoading(true);
      const data = await api.getApprovals();
      setApprovals(data);
      if (data.length > 0 && !selectedApproval) {
        setSelectedApproval(data[0]);
        setCoverLetterText(data[0].draft?.cover_letter || '');
      }
    } catch (err) {
      console.error('Failed to load approvals:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchApprovals();
  }, []);

  const handleSelect = (appr) => {
    setSelectedApproval(appr);
    setCoverLetterText(appr.draft?.cover_letter || '');
    setEditingCoverLetter(false);
    setDecisionNotes('');
  };

  const handleSaveCoverLetter = async () => {
    if (!selectedApproval?.draft_id) return;
    try {
      await api.updateDraft(selectedApproval.draft_id, {
        cover_letter: coverLetterText,
      });
      setEditingCoverLetter(false);
      await fetchApprovals();
    } catch (err) {
      alert(`Could not save draft updates: ${err.message}`);
    }
  };

  const handleDecision = async (decision) => {
    if (!selectedApproval) return;
    try {
      setSubmittingDecision(true);
      await api.decideApproval(selectedApproval.id, decision, decisionNotes);

      // If approved, trigger browser automation submission
      if (decision === 'approved') {
        try {
          await api.runBrowserAutomation(selectedApproval.draft_id, true);
        } catch (bErr) {
          console.warn('Browser automation background trigger note:', bErr);
        }
      }

      await fetchApprovals();
      setSelectedApproval(null);
      if (decision === 'approved') {
        onNavigateTab('tracker');
      }
    } catch (err) {
      alert(`Decision error: ${err.message}`);
    } finally {
      setSubmittingDecision(false);
    }
  };

  return (
    <div className="space-y-6 pb-16">
      {/* Header */}
      <div>
        <div className="inline-flex items-center space-x-2 px-3 py-1 rounded-full text-xs font-mono bg-amber-500/10 border border-amber-500/20 text-amber-300 mb-2">
          <span>Human-in-the-Loop Quality Assurance</span>
        </div>
        <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
          Pending Approvals Queue ({approvals.length})
        </h1>
        <p className="text-sm text-slate-400">
          Under Policy A (Manual Approval), Agent KitKat prepares full applications, form fields, and tailored cover letters,
          but waits for your final confirmation before submitting.
        </p>
      </div>

      {loading ? (
        <div className="py-16 text-center text-slate-400 text-sm">Loading pending approval queue...</div>
      ) : approvals.length === 0 ? (
        <div className="rounded-2xl bg-slate-900 border border-slate-800 p-12 text-center space-y-3">
          <CheckCircle2 className="w-12 h-12 text-emerald-400 mx-auto" />
          <h2 className="text-lg font-bold text-white">All Caught Up!</h2>
          <p className="text-xs text-slate-400 max-w-md mx-auto">
            Zero pending applications requiring your review. Discover new opportunities on the Dashboard or analyze a specific URL in Mode B.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          {/* Left Column: Approvals List */}
          <div className="lg:col-span-4 space-y-2">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider block px-1">
              Applications Awaiting Decision
            </span>
            <div className="space-y-2">
              {approvals.map((appr) => {
                const isSelected = selectedApproval?.id === appr.id;
                return (
                  <div
                    key={appr.id}
                    onClick={() => handleSelect(appr)}
                    className={`p-4 rounded-xl border cursor-pointer transition-all ${
                      isSelected
                        ? 'bg-amber-500/10 border-amber-500/50 shadow-md shadow-amber-500/5'
                        : 'bg-slate-900 border-slate-800 hover:border-slate-700'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <h3 className="text-sm font-bold text-white truncate">{appr.job_title}</h3>
                      <span className="text-xs font-mono font-bold text-amber-400">
                        {appr.match_score ? `${appr.match_score}%` : 'Eligible'}
                      </span>
                    </div>
                    <p className="text-xs text-slate-400 font-medium truncate mt-0.5">{appr.company_name}</p>
                    <div className="flex items-center space-x-2 mt-2 pt-2 border-t border-slate-800/80 text-[10px] text-slate-400">
                      <span className="uppercase font-mono px-1.5 py-0.2 bg-slate-800 rounded">
                        {appr.policy_applied || 'manual_approval'}
                      </span>
                      <span>•</span>
                      <span>Prepared {new Date(appr.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Right Column: Detailed Review & Decision Pane */}
          {selectedApproval && (
            <div className="lg:col-span-8 rounded-2xl bg-slate-900/90 border border-slate-800 p-6 space-y-6 shadow-xl">
              {/* Job Header */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-slate-800">
                <div>
                  <h2 className="text-lg font-bold text-white">{selectedApproval.job_title}</h2>
                  <p className="text-xs text-slate-300 font-medium">{selectedApproval.company_name}</p>
                </div>
                <div className="flex items-center space-x-2">
                  <span className="px-3 py-1 rounded-full text-xs font-mono font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30">
                    Match: {selectedApproval.match_score || 90}%
                  </span>
                  <span className="px-3 py-1 rounded-full text-xs font-mono font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                    PASS
                  </span>
                </div>
              </div>

              {/* Tailored Cover Letter Review & Edit */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-semibold text-slate-300 flex items-center space-x-1.5">
                    <Sparkles className="w-4 h-4 text-amber-400" />
                    <span>Tailored Cover Letter</span>
                  </label>
                  {!editingCoverLetter ? (
                    <button
                      onClick={() => setEditingCoverLetter(true)}
                      className="flex items-center space-x-1 text-xs text-amber-400 hover:text-amber-300 transition-colors"
                    >
                      <Edit3 className="w-3.5 h-3.5" />
                      <span>Edit Letter</span>
                    </button>
                  ) : (
                    <button
                      onClick={handleSaveCoverLetter}
                      className="flex items-center space-x-1 text-xs text-emerald-400 hover:text-emerald-300 font-semibold transition-colors"
                    >
                      <Save className="w-3.5 h-3.5" />
                      <span>Save Changes</span>
                    </button>
                  )}
                </div>

                {editingCoverLetter ? (
                  <textarea
                    rows={8}
                    value={coverLetterText}
                    onChange={(e) => setCoverLetterText(e.target.value)}
                    className="w-full p-4 rounded-xl bg-slate-950 border border-amber-500/50 text-xs font-mono text-slate-200 focus:outline-none leading-relaxed"
                  />
                ) : (
                  <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 text-xs font-mono text-slate-300 whitespace-pre-wrap leading-relaxed max-h-72 overflow-y-auto">
                    {coverLetterText || selectedApproval.draft?.cover_letter}
                  </div>
                )}
              </div>

              {/* Form Field Values Preview */}
              <div className="space-y-2">
                <label className="text-xs font-semibold text-slate-300">ATS Form Fields to be Filled</label>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 text-xs">
                  {Object.entries(selectedApproval.draft?.form_field_values || {}).map(([k, v]) => (
                    <div key={k} className="p-2.5 rounded-lg bg-slate-800/60 border border-slate-800">
                      <span className="text-[10px] text-slate-400 block uppercase font-mono">{k}</span>
                      <span className="text-slate-200 font-medium truncate block">{String(v)}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Decision Notes */}
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-slate-300">Approval / Rejection Notes (Optional)</label>
                <input
                  type="text"
                  placeholder="e.g. Approved with updated experience highlights..."
                  value={decisionNotes}
                  onChange={(e) => setDecisionNotes(e.target.value)}
                  className="w-full px-3.5 py-2 rounded-xl bg-slate-800/80 border border-slate-700 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-amber-500"
                />
              </div>

              {/* Action Buttons */}
              <div className="pt-4 border-t border-slate-800 flex flex-wrap items-center justify-between gap-3">
                <button
                  onClick={() => handleDecision('rejected')}
                  disabled={submittingDecision}
                  className="flex items-center space-x-1.5 px-4 py-2 rounded-xl text-xs font-semibold bg-slate-800 hover:bg-rose-950/60 text-slate-300 hover:text-rose-300 border border-slate-700 hover:border-rose-500/40 transition-all disabled:opacity-50"
                >
                  <XCircle className="w-4 h-4 text-rose-400" />
                  <span>Reject Opportunity</span>
                </button>

                <button
                  onClick={() => handleDecision('approved')}
                  disabled={submittingDecision}
                  className="flex items-center space-x-2 px-6 py-2.5 rounded-xl text-sm font-semibold bg-emerald-500 hover:bg-emerald-400 text-slate-950 shadow-lg shadow-emerald-500/20 active:scale-95 transition-all disabled:opacity-50"
                >
                  <CheckCircle2 className="w-4 h-4" />
                  <span>{submittingDecision ? 'Submitting Application...' : 'Approve & Submit Application'}</span>
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
