import React, { useState, useEffect } from 'react';
import {
  ExternalLink,
  Play,
  CheckCircle2,
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
          <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded text-[11px] font-medium bg-emerald-950/40 text-emerald-400 border border-emerald-800/40">
            <CheckCircle2 className="w-3 h-3" />
            <span>Submitted</span>
          </span>
        );
      case 'paused_captcha':
        return (
          <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded text-[11px] font-medium bg-red-950/40 text-red-400 border border-red-800/40">
            <AlertTriangle className="w-3 h-3" />
            <span>Paused (CAPTCHA)</span>
          </span>
        );
      case 'paused_login':
        return (
          <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded text-[11px] font-medium bg-zinc-800 text-zinc-300 border border-zinc-700/60">
            <Lock className="w-3 h-3" />
            <span>Paused (Login Wall)</span>
          </span>
        );
      case 'paused_unknown_field':
        return (
          <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded text-[11px] font-medium bg-zinc-800 text-zinc-300 border border-zinc-700/60">
            <HelpCircle className="w-3 h-3" />
            <span>Paused (Declaration Needed)</span>
          </span>
        );
      case 'halted_emergency':
        return (
          <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded text-[11px] font-medium bg-red-950/40 text-red-300 border border-red-800/50">
            <ShieldAlert className="w-3 h-3" />
            <span>Emergency Stopped</span>
          </span>
        );
      case 'filling':
        return (
          <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded text-[11px] font-medium bg-zinc-800 text-zinc-200 border border-zinc-700/60">
            <Play className="w-3 h-3 animate-pulse" />
            <span>Filling in Browser...</span>
          </span>
        );
      case 'approved_for_submission':
      case 'auto_approved':
        return (
          <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded text-[11px] font-medium bg-zinc-800 text-zinc-200 border border-zinc-700/50">
            <span>Approved for Submit</span>
          </span>
        );
      case 'pending_approval':
        return (
          <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded text-[11px] font-medium bg-zinc-800 text-zinc-300 border border-zinc-700/50">
            <span>Pending Review</span>
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded text-[11px] font-medium bg-zinc-800 text-zinc-400 border border-zinc-700/50">
            <span>{status || 'Draft'}</span>
          </span>
        );
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-xl sm:text-2xl font-bold text-zinc-100 tracking-tight">
          Application Tracker ({trackedApps.length})
        </h1>
        <p className="text-xs sm:text-sm text-zinc-400 mt-1">
          Real-time status of every application prepared, filled, submitted, or paused by Agent KitKat.
        </p>
      </div>

      {loading ? (
        <div className="py-16 text-center text-zinc-500 text-xs sm:text-sm">Loading applications...</div>
      ) : trackedApps.length === 0 ? (
        <div className="rounded-xl bg-zinc-900/40 border border-zinc-800 p-8 sm:p-12 text-center text-zinc-500 text-xs sm:text-sm">
          No applications tracked yet. Prepare an application from Discovered Opportunities or Analyze a Job URL.
        </div>
      ) : (
        <div className="rounded-xl bg-zinc-900/40 border border-zinc-800 overflow-hidden shadow-sm">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs min-w-[640px]">
              <thead className="bg-zinc-950 text-zinc-500 uppercase font-mono text-[10px] tracking-wider border-b border-zinc-800">
                <tr>
                  <th className="py-3 px-4 font-medium">Opportunity</th>
                  <th className="py-3 px-4 font-medium">Status</th>
                  <th className="py-3 px-4 font-medium">Match Score</th>
                  <th className="py-3 px-4 font-medium">Method / Result</th>
                  <th className="py-3 px-4 font-medium">Screenshots</th>
                  <th className="py-3 px-4 font-medium text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800/60">
                {trackedApps.map((app) => (
                  <tr key={app.application_id} className="hover:bg-zinc-850/30 transition-colors">
                    <td className="py-3.5 px-4">
                      <div className="font-medium text-zinc-100 text-xs sm:text-sm">{app.job_title}</div>
                      <div className="text-zinc-400 text-xs flex items-center space-x-1.5 mt-0.5">
                        <span>{app.company_name}</span>
                        {app.job_url && (
                          <a
                            href={app.job_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-zinc-400 hover:text-zinc-200"
                          >
                            <ExternalLink className="w-3 h-3 inline" />
                          </a>
                        )}
                      </div>
                    </td>

                    <td className="py-3.5 px-4">{getStatusBadge(app.status)}</td>

                    <td className="py-3.5 px-4">
                      {app.match_score ? (
                        <span className="font-mono font-medium text-zinc-200 text-xs">
                          {app.match_score}%
                        </span>
                      ) : (
                        <span className="text-zinc-500">—</span>
                      )}
                    </td>

                    <td className="py-3.5 px-4 max-w-xs">
                      <div className="text-zinc-300 truncate font-mono text-[11px]">
                        {app.submission_result || app.failure_reason || app.submission_method}
                      </div>
                      <div className="text-[10px] text-zinc-500 mt-0.5">
                        {app.applied_at
                          ? `Applied ${new Date(app.applied_at).toLocaleDateString()}`
                          : `Updated ${new Date(app.updated_at).toLocaleTimeString()}`}
                      </div>
                    </td>

                    <td className="py-3.5 px-4">
                      <div className="flex items-center space-x-1.5">
                        {app.draft_id && (
                          <>
                            <button
                              onClick={() =>
                                setActiveScreenshotModal(`/api/browser/screenshots/${app.draft_id}/pre_submit.png`)
                              }
                              className="px-2 py-0.5 rounded bg-zinc-800 hover:bg-zinc-700 text-zinc-300 text-[10px] flex items-center space-x-1"
                              title="Pre-submission screenshot"
                            >
                              <Eye className="w-3 h-3 text-zinc-400" />
                              <span>Pre</span>
                            </button>

                            <button
                              onClick={() =>
                                setActiveScreenshotModal(`/api/browser/screenshots/${app.draft_id}/post_submit.png`)
                              }
                              className="px-2 py-0.5 rounded bg-zinc-800 hover:bg-zinc-700 text-zinc-300 text-[10px] flex items-center space-x-1"
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
                          className="px-2.5 py-1 rounded-md text-xs font-medium bg-zinc-800 hover:bg-zinc-700 text-zinc-200 border border-zinc-700/60 transition-colors disabled:opacity-50"
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
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-zinc-950/80 backdrop-blur-sm p-4">
          <div className="relative max-w-4xl w-full bg-zinc-900 border border-zinc-800 rounded-xl overflow-hidden shadow-2xl">
            <div className="p-3.5 border-b border-zinc-800 flex items-center justify-between">
              <span className="text-xs font-mono text-zinc-300 font-medium">
                Form Verification Screenshot
              </span>
              <button
                onClick={() => setActiveScreenshotModal(null)}
                className="p-1 rounded-md text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="p-4 max-h-[80vh] overflow-y-auto bg-zinc-950 flex justify-center">
              <img
                src={activeScreenshotModal}
                alt="Verification Screenshot"
                className="rounded-lg border border-zinc-800 max-w-full"
                onError={(e) => {
                  e.target.style.display = 'none';
                  e.target.parentNode.innerHTML +=
                    '<p class="text-xs text-zinc-500 py-8">Screenshot not yet generated for this step.</p>';
                }}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
