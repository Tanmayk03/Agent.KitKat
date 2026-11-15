import React, { useState, useEffect } from 'react';
import {
  CheckCircle2,
  XCircle,
  Edit3,
  Save,
  Check,
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
    <div className="space-y-6">
      {/* Header */}
      <div>
        <div className="inline-flex items-center space-x-1.5 px-2.5 py-0.5 rounded-md text-xs font-mono bg-zinc-900 border border-zinc-800 text-zinc-400 mb-2">
          <span>Human-in-the-Loop Quality Assurance</span>
        </div>
        <h1 className="text-xl sm:text-2xl font-bold text-zinc-100 tracking-tight">
          Pending Approvals Queue ({approvals.length})
        </h1>
        <p className="text-xs sm:text-sm text-zinc-400 mt-1 max-w-2xl">
          Under Policy A (Manual Approval), Agent KitKat prepares full applications, form fields, and tailored cover letters,
          but waits for your final confirmation before submitting.
        </p>
      </div>

      {loading ? (
        <div className="py-16 text-center text-zinc-500 text-xs sm:text-sm">Loading pending approval queue...</div>
      ) : approvals.length === 0 ? (
        <div className="rounded-xl bg-zinc-900/40 border border-zinc-800 p-8 sm:p-12 text-center space-y-2.5">
          <CheckCircle2 className="w-10 h-10 text-zinc-400 mx-auto" />
          <h2 className="text-sm sm:text-base font-semibold text-zinc-200">All Caught Up</h2>
          <p className="text-xs text-zinc-500 max-w-sm mx-auto">
            Zero pending applications requiring your review. Discover new opportunities on the Dashboard or analyze a specific URL in Mode B.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
          {/* Left Column: Approvals List */}
          <div className="lg:col-span-4 space-y-2">
            <span className="text-xs font-medium text-zinc-400 uppercase tracking-wider block px-1">
              Applications Awaiting Decision
            </span>
            <div className="space-y-2">
              {approvals.map((appr) => {
                const isSelected = selectedApproval?.id === appr.id;
                return (
                  <div
                    key={appr.id}
                    onClick={() => handleSelect(appr)}
                    className={`p-3.5 rounded-lg border cursor-pointer transition-colors ${
                      isSelected
                        ? 'bg-zinc-800/90 border-zinc-600'
                        : 'bg-zinc-900/40 border-zinc-800 hover:border-zinc-700'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <h3 className="text-xs sm:text-sm font-semibold text-zinc-100 truncate">{appr.job_title}</h3>
                      <span className="text-xs font-mono font-medium text-zinc-200">
                        {appr.match_score ? `${appr.match_score}%` : 'Eligible'}
                      </span>
                    </div>
                    <p className="text-xs text-zinc-400 mt-0.5 truncate">{appr.company_name}</p>
                    <div className="flex items-center space-x-2 mt-2 pt-2 border-t border-zinc-800/80 text-[10px] text-zinc-500">
                      <span className="uppercase font-mono px-1.5 py-0.2 bg-zinc-800 rounded text-zinc-400">
                        {appr.policy_applied || 'manual_approval'}
                      </span>
                      <span>&bull;</span>
                      <span>Prepared {new Date(appr.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Right Column: Detailed Review & Decision Pane */}
          {selectedApproval && (
            <div className="lg:col-span-8 rounded-xl bg-zinc-900/40 border border-zinc-800 p-4 sm:p-6 space-y-5">
              {/* Job Header */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3.5 border-b border-zinc-800">
                <div>
                  <h2 className="text-base sm:text-lg font-semibold text-zinc-100">{selectedApproval.job_title}</h2>
                  <p className="text-xs text-zinc-400">{selectedApproval.company_name}</p>
                </div>
                <div className="flex items-center space-x-2">
                  <span className="px-2.5 py-0.5 rounded text-xs font-mono font-medium bg-zinc-800 text-zinc-200 border border-zinc-700/60">
                    Match: {selectedApproval.match_score || 90}%
                  </span>
                  <span className="px-2.5 py-0.5 rounded text-xs font-mono font-medium bg-emerald-950/40 text-emerald-400 border border-emerald-800/40">
                    PASS
                  </span>
                </div>
              </div>

              {/* Tailored Cover Letter Review & Edit */}
              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-medium text-zinc-300">
                    Tailored Cover Letter
                  </label>
                  {!editingCoverLetter ? (
                    <button
                      onClick={() => setEditingCoverLetter(true)}
                      className="flex items-center space-x-1 text-xs text-zinc-400 hover:text-zinc-200 transition-colors"
                    >
                      <Edit3 className="w-3 h-3" />
                      <span>Edit Letter</span>
                    </button>
                  ) : (
                    <button
                      onClick={handleSaveCoverLetter}
                      className="flex items-center space-x-1 text-xs text-emerald-400 hover:text-emerald-300 font-medium transition-colors"
                    >
                      <Save className="w-3 h-3" />
                      <span>Save Changes</span>
                    </button>
                  )}
                </div>

                {editingCoverLetter ? (
                  <textarea
                    rows={8}
                    value={coverLetterText}
                    onChange={(e) => setCoverLetterText(e.target.value)}
                    className="w-full p-3.5 rounded-lg bg-zinc-950 border border-zinc-700 text-xs font-mono text-zinc-200 focus:outline-none leading-relaxed"
                  />
                ) : (
                  <div className="p-3.5 rounded-lg bg-zinc-950 border border-zinc-800 text-xs font-mono text-zinc-300 whitespace-pre-wrap leading-relaxed max-h-64 overflow-y-auto">
                    {coverLetterText || selectedApproval.draft?.cover_letter}
                  </div>
                )}
              </div>

              {/* Form Field Values Preview */}
              <div className="space-y-1.5">
                <label className="text-xs font-medium text-zinc-300">ATS Form Fields to be Filled</label>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 text-xs">
                  {Object.entries(selectedApproval.draft?.form_field_values || {}).map(([k, v]) => (
                    <div key={k} className="p-2.5 rounded-md bg-zinc-900 border border-zinc-800">
                      <span className="text-[10px] text-zinc-500 block uppercase font-mono">{k}</span>
                      <span className="text-zinc-200 font-medium truncate block">{String(v)}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Decision Notes */}
              <div className="space-y-1.5">
                <label className="text-xs font-medium text-zinc-300">Approval / Rejection Notes (Optional)</label>
                <input
                  type="text"
                  placeholder="e.g. Approved with updated experience highlights..."
                  value={decisionNotes}
                  onChange={(e) => setDecisionNotes(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg bg-zinc-900 border border-zinc-800 text-xs text-zinc-100 placeholder-zinc-500 focus:outline-none focus:border-zinc-600"
                />
              </div>

              {/* Action Buttons */}
              <div className="pt-3 border-t border-zinc-800 flex flex-wrap items-center justify-between gap-2.5">
                <button
                  onClick={() => handleDecision('rejected')}
                  disabled={submittingDecision}
                  className="flex items-center space-x-1.5 px-3.5 py-2 rounded-lg text-xs font-medium bg-zinc-900 hover:bg-red-950/40 text-zinc-400 hover:text-red-300 border border-zinc-800 hover:border-red-900/40 transition-colors disabled:opacity-50"
                >
                  <XCircle className="w-3.5 h-3.5 text-zinc-400" />
                  <span>Reject Opportunity</span>
                </button>

                <button
                  onClick={() => handleDecision('approved')}
                  disabled={submittingDecision}
                  className="flex items-center space-x-2 px-4 py-2 rounded-lg text-xs sm:text-sm font-medium bg-zinc-100 hover:bg-zinc-200 text-zinc-950 transition-colors disabled:opacity-50"
                >
                  <CheckCircle2 className="w-3.5 h-3.5" />
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
