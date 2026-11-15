import React, { useState, useEffect } from 'react';
import {
  FileText,
  ExternalLink,
  Play,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Lock,
  HelpCircle,
  Eye,
  X,
  ShieldAlert,
} from 'lucide-react';
import { api } from '../services/api';

export default function TrackerPage() {
  const [trackedApps, setTrackedApps] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeScreenshotModal, setActiveScreenshotModal] = useState(null);
  const [runningDraftId, setRunningDraftId] = useState(null);

  const fetchTracker = async () => {
    try {
      setLoading(true);
      const data = await api.getTracker();
      setTrackedApps(data);
    } catch (err) {
      console.error('Failed to load application tracker:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTracker();
  }, []);

  const handleRunBrowser = async (draftId, autoSubmit = false) => {
    try {
      setRunningDraftId(draftId);
      await api.runBrowserAutomation(draftId, autoSubmit);
      await fetchTracker();
    } catch (err) {
      alert(`Browser automation error: ${err.message}`);
    } finally {
      setRunningDraftId(null);
    }
  };

  const getStatusBadge = (status) => {
    switch (status) {
      case 'submitted':
        return (
          <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
            <CheckCircle2 className="w-3.5 h-3.5" />
            <span>Submitted</span>
          </span>
        );
      case 'paused_captcha':
        return (
          <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-rose-500/20 text-rose-400 border border-rose-500/30">
            <AlertTriangle className="w-3.5 h-3.5" />
            <span>Paused (CAPTCHA)</span>
          </span>
        );
      case 'paused_login':
        return (
          <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-500/20 text-amber-400 border border-amber-500/30">
            <Lock className="w-3.5 h-3.5" />
            <span>Paused (Login Wall)</span>
          </span>
        );
      case 'paused_unknown_field':
        return (
          <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-purple-500/20 text-purple-400 border border-purple-500/30">
            <HelpCircle className="w-3.5 h-3.5" />
            <span>Paused (Declaration Needed)</span>
          </span>
        );
      case 'halted_emergency':
        return (
          <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-rose-500/30 text-rose-300 border border-rose-500/50">
            <ShieldAlert className="w-3.5 h-3.5" />
            <span>Emergency Stopped</span>
          </span>
        );
      case 'filling':
        return (
          <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-sky-500/20 text-sky-400 border border-sky-500/30 animate-pulse">
            <Play className="w-3.5 h-3.5" />
            <span>Filling in Browser...</span>
          </span>
        );
      case 'approved_for_submission':
      case 'auto_approved':
        return (
          <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-300 border border-emerald-500/20">
            <span>Approved for Submit</span>
          </span>
        );
      case 'pending_approval':
        return (
          <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-500/10 text-amber-300 border border-amber-500/20">
            <span>Pending Review</span>
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-slate-800 text-slate-300 border border-slate-700">
            <span>{status || 'Draft'}</span>
          </span>
        );
    }
  };

  return (
    <div className="space-y-6 pb-16">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
            Application Tracker ({trackedApps.length})
          </h1>
          <p className="text-sm text-slate-400">
            Real-time status of every application prepared, filled, submitted, or paused by Agent KitKat.
          </p>
        </div>
      </div>

      {loading ? (
        <div className="py-16 text-center text-slate-400 text-sm">Loading applications...</div>
      ) : trackedApps.length === 0 ? (
        <div className="rounded-2xl bg-slate-900 border border-slate-800 p-12 text-center text-slate-400 text-sm">
          No applications tracked yet. Prepare an application from Discovered Opportunities or Analyze a Job URL.
        </div>
      ) : (
        <div className="rounded-2xl bg-slate-900/90 border border-slate-800 overflow-hidden shadow-xl">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-950/80 text-slate-400 uppercase font-mono text-[10px] tracking-wider border-b border-slate-800">
                <tr>
                  <th className="py-3.5 px-4 font-semibold">Opportunity</th>
                  <th className="py-3.5 px-4 font-semibold">Status</th>
                  <th className="py-3.5 px-4 font-semibold">Match Score</th>
                  <th className="py-3.5 px-4 font-semibold">Method / Result</th>
                  <th className="py-3.5 px-4 font-semibold">Screenshots</th>
                  <th className="py-3.5 px-4 font-semibold text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {trackedApps.map((app) => (
                  <tr key={app.application_id} className="hover:bg-slate-800/30 transition-colors">
                    <td className="py-3.5 px-4">
                      <div className="font-bold text-slate-100 text-sm">{app.job_title}</div>
                      <div className="text-slate-400 font-medium text-xs flex items-center space-x-2 mt-0.5">
                        <span>{app.company_name}</span>
                        {app.job_url && (
                          <a
                            href={app.job_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-amber-400 hover:text-amber-300"
                          >
                            <ExternalLink className="w-3 h-3 inline" />
                          </a>
                        )}
                      </div>
                    </td>

                    <td className="py-3.5 px-4">{getStatusBadge(app.status)}</td>

                    <td className="py-3.5 px-4">
                      {app.match_score ? (
                        <span className="font-mono font-bold text-amber-400 text-xs">
                          {app.match_score}%
                        </span>
                      ) : (
                        <span className="text-slate-500">—</span>
                      )}
                    </td>

                    <td className="py-3.5 px-4 max-w-xs">
                      <div className="text-slate-300 truncate font-mono text-[11px]">
                        {app.submission_result || app.failure_reason || app.submission_method}
                      </div>
                      <div className="text-[10px] text-slate-500">
                        {app.applied_at
                          ? `Applied ${new Date(app.applied_at).toLocaleDateString()}`
                          : `Updated ${new Date(app.updated_at).toLocaleTimeString()}`}
                      </div>
                    </td>

                    <td className="py-3.5 px-4">
                      <div className="flex items-center space-x-2">
                        {app.draft_id && (
                          <>
                            <button
                              onClick={() =>
                                setActiveScreenshotModal(`/api/browser/screenshots/${app.draft_id}/pre_submit.png`)
                              }
                              className="px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 text-[10px] flex items-center space-x-1"
                              title="Pre-submission screenshot"
                            >
                              <Eye className="w-3 h-3 text-amber-400" />
                              <span>Pre</span>
                            </button>

                            <button
                              onClick={() =>
                                setActiveScreenshotModal(`/api/browser/screenshots/${app.draft_id}/post_submit.png`)
                              }
                              className="px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 text-[10px] flex items-center space-x-1"
                              title="Post-submission confirmation screenshot"
                            >
                              <Eye className="w-3 h-3 text-emerald-400" />
                              <span>Post</span>
                            </button>
                          </>
                        )}
                      </div>
                    </td>

                    <td className="py-3.5 px-4 text-right">
                      {app.draft_id && app.status !== 'submitted' && (
                        <button
                          onClick={() => handleRunBrowser(app.draft_id, false)}
                          disabled={runningDraftId === app.draft_id}
                          className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-amber-500/10 hover:bg-amber-500/20 text-amber-300 border border-amber-500/30 transition-all disabled:opacity-50"
                        >
                          {runningDraftId === app.draft_id ? 'Running...' : 'Run in Browser'}
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Screenshot Modal Viewer */}
      {activeScreenshotModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 backdrop-blur-sm p-4">
          <div className="relative max-w-4xl w-full bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden shadow-2xl">
            <div className="p-4 border-b border-slate-800 flex items-center justify-between">
              <span className="text-xs font-mono text-slate-300 font-semibold">
                Form Verification Screenshot
              </span>
              <button
                onClick={() => setActiveScreenshotModal(null)}
                className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="p-4 max-h-[80vh] overflow-y-auto bg-slate-950 flex justify-center">
              <img
                src={activeScreenshotModal}
                alt="Verification Screenshot"
                className="rounded-lg shadow-lg border border-slate-800 max-w-full"
                onError={(e) => {
                  e.target.style.display = 'none';
                  e.target.parentNode.innerHTML +=
                    '<p class="text-xs text-slate-500 py-8">Screenshot not yet generated for this step.</p>';
                }}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
