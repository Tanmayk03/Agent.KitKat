import React, { useState } from 'react';
import {
  Search,
  CheckCircle2,
  Clock,
  Send,
  ArrowRight,
  TrendingUp,
  Briefcase,
  Play,
  Layers,
  Cpu,
} from 'lucide-react';
import SourceHealthPanel from '../components/SourceHealthPanel';

export default function DashboardPage({
  profile,
  report,
  jobs = [],
  schedulerStatus,
  onTriggerDiscovery,
  onNavigateTab,
  discoveryRun = null,
  healthRefreshKey = 0,
}) {
  const [triggering, setTriggering] = useState(false);

  const handleTrigger = async () => {
    try {
      setTriggering(true);
      await onTriggerDiscovery();
    } finally {
      setTriggering(false);
    }
  };

  const candidateName = profile?.full_name ? `, ${profile.full_name}` : '';
  const running = triggering || discoveryRun?.status === 'running';
  const education = profile?.education || {};
  const prefs = profile?.application_preferences || {};
  const details = report?.details_json || {};
  const today = details.activity || {};
  const snap = details.snapshot || {};
  const followUps = details.follow_ups || [];

  return (
    <div className="space-y-6">
      {/* Hero Welcome Banner */}
      <div className="rounded-xl bg-zinc-900/60 border border-zinc-800 p-5 sm:p-7 shadow-sm">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-5">
          <div className="space-y-1.5">
            <div className="inline-flex items-center space-x-1.5 px-2.5 py-0.5 rounded-md text-xs font-mono bg-zinc-800/80 border border-zinc-700/60 text-zinc-300">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
              <span>Career Engine Ready</span>
            </div>
            <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-zinc-100">
              Welcome back{candidateName}
            </h1>
            <p className="text-xs sm:text-sm text-zinc-400 max-w-2xl leading-relaxed">
              {education.degree ? (
                <>
                  Targeting <span className="text-zinc-200 font-medium">{education.degree}</span>
                  {education.specialization ? ` (${education.specialization})` : ''}
                  {education.college ? `, ${education.college}` : ''}
                  {education.graduation_year ? ` · Batch ${education.graduation_year}` : ''} opportunities across India & Remote.
                </>
              ) : (
                <>Your education details are missing: fill in your Profile so eligibility checks can work.</>
              )}
            </p>
            {discoveryRun && (
              <p className="text-xs text-zinc-400" role="status">
                Discovery: <span className="text-zinc-200">{discoveryRun.status}</span>
                {discoveryRun.status === 'running'
                  ? ` · ${discoveryRun.progress}`
                  : ` · ${discoveryRun.new_saved ?? 0} new, ${discoveryRun.duplicates ?? 0} duplicates, ${discoveryRun.failed_sources ?? 0} failed sources`}
              </p>
            )}
          </div>

          {/* Quick Actions */}
          <div className="flex flex-wrap items-center gap-2.5">
            <button
              onClick={handleTrigger}
              disabled={running}
              className="flex items-center space-x-2 px-3.5 py-2 rounded-lg text-xs sm:text-sm font-medium bg-zinc-100 hover:bg-zinc-200 text-zinc-950 transition-colors disabled:opacity-50"
            >
              <Play className={`w-3.5 h-3.5 ${running ? 'animate-spin' : ''}`} />
              <span>{running ? 'Discovering…' : 'Run Discovery Now'}</span>
            </button>
            <button
              onClick={() => onNavigateTab('analyze')}
              className="flex items-center space-x-2 px-3.5 py-2 rounded-lg text-xs sm:text-sm font-medium bg-zinc-900 hover:bg-zinc-800 text-zinc-200 border border-zinc-800 transition-colors"
            >
              <Search className="w-3.5 h-3.5 text-zinc-400" />
              <span>Analyze Job URL (Mode B)</span>
            </button>
          </div>
        </div>
      </div>

      {/* Metrics Grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
        {[
          {
            label: 'New jobs today',
            val: today.new_jobs ?? 0,
            icon: Briefcase,
            sub: `${today.listings_fetched ?? 0} listings fetched · ${jobs.length} stored in total`,
          },
          {
            label: 'Eligible today (PASS)',
            val: today.eligible ?? 0,
            icon: CheckCircle2,
            sub: `${today.unknown ?? 0} need your check · ${today.ineligible ?? 0} not eligible`,
          },
          {
            label: `Eligible today, ≥${details.min_match_score ?? prefs.min_match_score ?? 75}% match`,
            val: today.eligible_above_threshold ?? 0,
            icon: TrendingUp,
            sub: `${today.drafts_prepared ?? 0} drafts prepared today`,
          },
          {
            label: 'Submitted today',
            val: today.submitted ?? 0,
            icon: Send,
            sub: `${snap.pending_approvals ?? 0} waiting for your approval`,
          },
        ].map((card, i) => {
          const Icon = card.icon;
          return (
            <div
              key={i}
              className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-4 sm:p-5 flex flex-col justify-between hover:border-zinc-700/70 transition-colors"
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium text-zinc-400">{card.label}</span>
                <Icon className="w-4 h-4 text-zinc-500" />
              </div>
              <div className="mt-3">
                <span className="text-2xl sm:text-3xl font-semibold tracking-tight text-zinc-100 font-mono">
                  {card.val}
                </span>
                <p className="text-[11px] text-zinc-400 mt-1 truncate">{card.sub}</p>
              </div>
            </div>
          );
        })}
      </div>

      {followUps.length > 0 && (
        <div className="rounded-xl border border-amber-900/50 bg-amber-950/10 p-4 sm:p-5">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-medium text-amber-200 flex items-center gap-1.5"><Clock className="w-3.5 h-3.5" />Follow-ups due ({followUps.length})</span>
            <button onClick={() => onNavigateTab('tracker')} className="text-[11px] text-zinc-300 underline">Open tracker</button>
          </div>
          <ul className="space-y-1 text-xs">
            {followUps.slice(0, 5).map((f) => (
              <li key={f.application_id} className="flex justify-between gap-3">
                <span className="text-zinc-200 truncate">{f.title} <span className="text-zinc-500">· {f.company} · {f.stage}</span></span>
                <span className="font-mono text-amber-300 shrink-0">{f.date}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Autonomous System Status & Mode Details */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3 sm:gap-4">
        {/* Scheduler Card */}
        <div className="rounded-xl bg-zinc-900/40 border border-zinc-800 p-4 sm:p-5 space-y-3">
          <div className="flex items-center space-x-2 text-xs font-medium text-zinc-200">
            <Clock className="w-3.5 h-3.5 text-zinc-400" />
            <span>Discovery schedule</span>
          </div>
          <div className="flex items-center justify-between pt-1">
            <span className="text-xs text-zinc-400">Status</span>
            <span
              className={`px-2 py-0.5 rounded text-[11px] font-mono font-medium ${
                schedulerStatus?.is_running
                  ? 'bg-emerald-950/40 text-emerald-400 border border-emerald-800/40'
                  : 'bg-zinc-800 text-zinc-400 border border-zinc-700/50'
              }`}
            >
              {schedulerStatus?.is_running ? 'Active (Scheduled)' : 'Standby'}
            </span>
          </div>
          <div className="flex items-center justify-between text-xs text-zinc-400">
            <span>Runs</span>
            <span className="font-mono text-zinc-200">{schedulerStatus?.is_running ? schedulerStatus.description : 'Paused'}</span>
          </div>
          <div className="flex items-center justify-between text-xs text-zinc-400">
            <span>Next Run</span>
            <span className="font-mono text-zinc-300 truncate max-w-[150px]">
              {schedulerStatus?.is_running ? schedulerStatus?.next_run_time || '—' : 'Manual only'}
            </span>
          </div>
          {schedulerStatus?.failed_runs_7d > 0 && (
            <p className="text-[11px] text-red-400">{schedulerStatus.failed_runs_7d} discovery run(s) failed in the last 7 days. See Settings.</p>
          )}
        </div>

        {/* Submission Policy Card */}
        <div className="rounded-xl bg-zinc-900/40 border border-zinc-800 p-4 sm:p-5 space-y-3">
          <div className="flex items-center space-x-2 text-xs font-medium text-zinc-200">
            <Layers className="w-3.5 h-3.5 text-zinc-400" />
            <span>Submission Policy</span>
          </div>
          <div className="flex items-center justify-between pt-1">
            <span className="text-xs text-zinc-400">Active Policy</span>
            <span className="px-2 py-0.5 rounded text-[11px] font-medium bg-zinc-800 text-zinc-200 border border-zinc-700/50">
              {(prefs.submission_policy || 'prepare_only') === 'manual_approval' ? 'Approve, then confirm' : 'Prepare only'}
            </span>
          </div>
          <div className="flex items-center justify-between text-xs text-zinc-400">
            <span>Daily Application Limit</span>
            <span className="font-mono text-zinc-200">{prefs.max_applications_per_day || 5} per day</span>
          </div>
          <div className="flex items-center justify-between text-xs text-zinc-400">
            <span>Min Match Threshold</span>
            <span className="font-mono text-zinc-200">{prefs.min_match_score || 75}%</span>
          </div>
        </div>

        {/* Local AI Runtime Card */}
        <div className="rounded-xl bg-zinc-900/40 border border-zinc-800 p-4 sm:p-5 space-y-3">
          <div className="flex items-center space-x-2 text-xs font-medium text-zinc-200">
            <Cpu className="w-3.5 h-3.5 text-zinc-400" />
            <span>AI Architecture</span>
          </div>
          <div className="flex items-center justify-between pt-1">
            <span className="text-xs text-zinc-400">Local Runtime</span>
            <span className="text-xs font-mono text-zinc-200">Ollama (127.0.0.1:11434)</span>
          </div>
          <div className="flex items-center justify-between text-xs text-zinc-400">
            <span>Model</span>
            <span className="font-mono text-zinc-200">qwen2.5:1.5b</span>
          </div>
          <div className="flex items-center justify-between text-xs text-zinc-400">
            <span>Monthly Cost</span>
            <span className="font-mono text-emerald-400 font-medium">₹0.00 (Local Hardware)</span>
          </div>
        </div>
      </div>

      {/* Source Health (stored discovery history) */}
      <SourceHealthPanel refreshKey={healthRefreshKey} />

      {/* Discovered Opportunities Feed */}
      <div className="rounded-xl bg-zinc-900/40 border border-zinc-800 overflow-hidden shadow-sm">
        <div className="px-4 sm:px-6 py-3.5 border-b border-zinc-800/80 flex items-center justify-between">
          <div>
            <h2 className="text-sm font-semibold text-zinc-100">Recent Opportunities Pipeline</h2>
            <p className="text-xs text-zinc-400">Most recently stored listings from all sources</p>
          </div>
          <button
            onClick={() => onNavigateTab('opportunities')}
            className="flex items-center space-x-1 text-xs font-medium text-zinc-300 hover:text-white transition-colors"
          >
            <span>View All</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>

        <div className="divide-y divide-zinc-800/60">
          {jobs.slice(0, 5).map((job) => (
            <div
              key={job.id}
              className="p-4 sm:px-6 hover:bg-zinc-850/40 transition-colors flex flex-col sm:flex-row sm:items-center justify-between gap-3"
            >
              <div className="space-y-1">
                <div className="flex items-center space-x-2">
                  <h3 className="text-sm font-medium text-zinc-100">{job.title}</h3>
                  <span className="text-[10px] px-2 py-0.5 rounded font-mono bg-zinc-800 text-zinc-300 border border-zinc-700/50">
                    {job.work_mode || 'Unknown'}
                  </span>
                </div>
                <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1 text-xs text-zinc-400">
                  <span className="text-zinc-300">{job.company}</span>
                  <span>&bull;</span>
                  <span>{job.location || 'Location not stated'}</span>
                  {job.salary_stipend && (
                    <>
                      <span>&bull;</span>
                      <span className="font-mono text-zinc-300">{job.salary_stipend}</span>
                    </>
                  )}
                  {job.posted_at && (
                    <>
                      <span>&bull;</span>
                      <span>Posted {job.posted_at.slice(0, 10)}</span>
                    </>
                  )}
                  <span>&bull;</span>
                  <span className="text-[10px] uppercase font-mono px-1.5 py-0.2 bg-zinc-800/80 rounded text-zinc-400">
                    Source: {job.source || 'unknown'}
                  </span>
                </div>
              </div>

              <div className="flex items-center space-x-2 self-end sm:self-center">
                <button
                  onClick={() => onNavigateTab('opportunities')}
                  className="px-3 py-1.5 rounded-md text-xs font-medium bg-zinc-800 hover:bg-zinc-700 text-zinc-200 border border-zinc-700/60 transition-colors"
                >
                  View Details
                </button>
              </div>
            </div>
          ))}

          {jobs.length === 0 && (
            <div className="py-10 text-center text-zinc-500 text-xs">
              No opportunities discovered yet. Click <span className="text-zinc-200 font-medium">"Run Discovery Now"</span> above to search.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
