import React, { useState } from 'react';
import {
  Sparkles,
  Search,
  CheckCircle2,
  AlertCircle,
  Clock,
  Send,
  ArrowRight,
  TrendingUp,
  Briefcase,
  Play,
  Layers,
  ShieldAlert,
} from 'lucide-react';

export default function DashboardPage({
  profile,
  report,
  jobs = [],
  schedulerStatus,
  onTriggerDiscovery,
  onNavigateTab,
  onEmergencyStop,
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

  const candidateName = profile?.full_name || 'Candidate';
  const education = profile?.education || {};
  const prefs = profile?.application_preferences || {};

  return (
    <div className="space-y-6 pb-16">
      {/* Hero Welcome Banner */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-slate-900 via-slate-850 to-slate-900 border border-slate-800 p-6 sm:p-8 shadow-xl">
        <div className="absolute top-0 right-0 -mr-16 -mt-16 w-64 h-64 bg-amber-500/10 rounded-full blur-3xl pointer-events-none" />
        <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="space-y-2">
            <div className="inline-flex items-center space-x-2 px-3 py-1 rounded-full text-xs font-mono bg-amber-500/10 border border-amber-500/20 text-amber-300">
              <Sparkles className="w-3.5 h-3.5 text-amber-400" />
              <span>Autonomous Career Engine Ready</span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-white">
              Welcome back, <span className="text-amber-400">{candidateName}</span>! 🍫
            </h1>
            <p className="text-sm text-slate-300 max-w-2xl leading-relaxed">
              Targeting <span className="text-amber-300 font-semibold">{education.degree || 'B.Tech'}</span> (
              {education.specialization || 'CS & Data Science'}, {education.college || 'SRM University'} • Batch{' '}
              {education.graduation_year || 2027}) opportunities across India & Remote.
            </p>
          </div>

          {/* Quick Actions */}
          <div className="flex flex-wrap items-center gap-3">
            <button
              onClick={handleTrigger}
              disabled={triggering}
              className="flex items-center space-x-2 px-4 py-2.5 rounded-xl text-xs sm:text-sm font-semibold bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-400 hover:to-amber-500 text-slate-950 shadow-lg shadow-amber-500/20 active:scale-95 transition-all disabled:opacity-50"
            >
              <Play className={`w-4 h-4 ${triggering ? 'animate-spin' : ''}`} />
              <span>{triggering ? 'Hunting Jobs...' : 'Run Daily Hunt (Mode A)'}</span>
            </button>
            <button
              onClick={() => onNavigateTab('analyze')}
              className="flex items-center space-x-2 px-4 py-2.5 rounded-xl text-xs sm:text-sm font-semibold bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 active:scale-95 transition-all"
            >
              <Search className="w-4 h-4 text-amber-400" />
              <span>Analyze Job URL (Mode B)</span>
            </button>
          </div>
        </div>
      </div>

      {/* Metrics Grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          {
            label: 'Total Discovered',
            val: report?.total_discovered || jobs.length || 0,
            icon: Briefcase,
            sub: `${report?.new_found || 0} found today`,
            color: 'text-sky-400',
            bg: 'bg-sky-500/10 border-sky-500/20',
          },
          {
            label: 'Eligible (PASS)',
            val: report?.eligible_count || 0,
            icon: CheckCircle2,
            sub: '100% Verified Profile Match',
            color: 'text-emerald-400',
            bg: 'bg-emerald-500/10 border-emerald-500/20',
          },
          {
            label: 'Shortlisted (≥75%)',
            val: report?.shortlisted_count || 0,
            icon: TrendingUp,
            sub: 'Strong Resume Compatibility',
            color: 'text-amber-400',
            bg: 'bg-amber-500/10 border-amber-500/20',
          },
          {
            label: 'Applications Submitted',
            val: report?.submitted_count || 0,
            icon: Send,
            sub: `${report?.pending_approvals_count || 0} pending review`,
            color: 'text-purple-400',
            bg: 'bg-purple-500/10 border-purple-500/20',
          },
        ].map((card, i) => {
          const Icon = card.icon;
          return (
            <div
              key={i}
              className={`rounded-2xl border p-4 sm:p-5 flex flex-col justify-between ${card.bg} backdrop-blur-sm shadow-md transition-all hover:translate-y-[-2px]`}
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium text-slate-400">{card.label}</span>
                <Icon className={`w-5 h-5 ${card.color}`} />
              </div>
              <div className="mt-3">
                <span className={`text-2xl sm:text-3xl font-extrabold tracking-tight ${card.color}`}>
                  {card.val}
                </span>
                <p className="text-[11px] text-slate-400 mt-1 truncate">{card.sub}</p>
              </div>
            </div>
          );
        })}
      </div>

      {/* Autonomous System Status & Mode Details */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Scheduler Card */}
        <div className="rounded-2xl bg-slate-900/80 border border-slate-800 p-5 space-y-3">
          <div className="flex items-center space-x-2 text-xs font-semibold text-slate-300">
            <Clock className="w-4 h-4 text-amber-400" />
            <span>Autonomous Daily Scheduler</span>
          </div>
          <div className="flex items-center justify-between pt-1">
            <span className="text-sm text-slate-400">Status</span>
            <span
              className={`px-2.5 py-0.5 rounded-full text-xs font-mono font-medium ${
                schedulerStatus?.is_running
                  ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                  : 'bg-slate-800 text-slate-400 border border-slate-700'
              }`}
            >
              {schedulerStatus?.is_running ? 'Active (Scheduled)' : 'Standby'}
            </span>
          </div>
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>Daily Schedule</span>
            <span className="font-mono text-slate-200">{prefs.daily_search_time || '09:00'} AM</span>
          </div>
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>Next Run</span>
            <span className="font-mono text-amber-400 truncate max-w-[160px]">
              {schedulerStatus?.next_run_time || 'On-demand'}
            </span>
          </div>
        </div>

        {/* Submission Policy Card */}
        <div className="rounded-2xl bg-slate-900/80 border border-slate-800 p-5 space-y-3">
          <div className="flex items-center space-x-2 text-xs font-semibold text-slate-300">
            <Layers className="w-4 h-4 text-amber-400" />
            <span>Submission Policy</span>
          </div>
          <div className="flex items-center justify-between pt-1">
            <span className="text-sm text-slate-400">Active Policy</span>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-mono font-medium bg-amber-500/20 text-amber-300 border border-amber-500/30 uppercase">
              {prefs.submission_policy || 'manual_approval'}
            </span>
          </div>
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>Daily Application Limit</span>
            <span className="font-mono text-slate-200">{prefs.max_applications_per_day || 5} per day</span>
          </div>
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>Min Match Threshold</span>
            <span className="font-mono text-emerald-400">{prefs.min_match_score || 75}%</span>
          </div>
        </div>

        {/* Local AI Runtime Card */}
        <div className="rounded-2xl bg-slate-900/80 border border-slate-800 p-5 space-y-3">
          <div className="flex items-center space-x-2 text-xs font-semibold text-slate-300">
            <Sparkles className="w-4 h-4 text-amber-400" />
            <span>Zero-Cost AI Architecture</span>
          </div>
          <div className="flex items-center justify-between pt-1">
            <span className="text-sm text-slate-400">Local Runtime</span>
            <span className="text-xs font-mono text-emerald-400 font-medium">Ollama (Local)</span>
          </div>
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>Model</span>
            <span className="font-mono text-slate-200">qwen2.5:1.5b</span>
          </div>
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>Monthly Cost</span>
            <span className="font-mono text-emerald-400 font-bold">₹0.00 / month</span>
          </div>
        </div>
      </div>

      {/* Discovered Opportunities Feed */}
      <div className="rounded-2xl bg-slate-900/90 border border-slate-800 overflow-hidden shadow-xl">
        <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between">
          <div>
            <h2 className="text-base font-bold text-white">Recent Opportunities Pipeline</h2>
            <p className="text-xs text-slate-400">Discovered across public feeds, Remotive, and curated tech startups</p>
          </div>
          <button
            onClick={() => onNavigateTab('opportunities')}
            className="flex items-center space-x-1 text-xs font-medium text-amber-400 hover:text-amber-300 transition-colors"
          >
            <span>View All</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>

        <div className="divide-y divide-slate-800/60">
          {jobs.slice(0, 5).map((job) => (
            <div
              key={job.id}
              className="p-4 sm:px-6 hover:bg-slate-800/40 transition-colors flex flex-col sm:flex-row sm:items-center justify-between gap-3"
            >
              <div className="space-y-1">
                <div className="flex items-center space-x-2">
                  <h3 className="text-sm font-semibold text-slate-100">{job.title}</h3>
                  <span className="text-[11px] px-2 py-0.5 rounded-md font-mono bg-slate-800 text-slate-300 border border-slate-700">
                    {job.work_mode || 'Remote'}
                  </span>
                </div>
                <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-slate-400">
                  <span className="font-medium text-slate-300">{job.company}</span>
                  <span>•</span>
                  <span>{job.location || 'India'}</span>
                  <span>•</span>
                  <span className="text-amber-400/90 font-mono">{job.salary_stipend || 'Competitive'}</span>
                  <span>•</span>
                  <span className="text-[10px] uppercase font-mono px-1.5 py-0.2 bg-slate-800/80 rounded text-slate-400">
                    Source: {job.source || 'public'}
                  </span>
                </div>
              </div>

              <div className="flex items-center space-x-2 self-end sm:self-center">
                <button
                  onClick={() => onNavigateTab('opportunities')}
                  className="px-3 py-1.5 rounded-lg text-xs font-medium bg-amber-500/10 hover:bg-amber-500/20 text-amber-300 border border-amber-500/30 transition-all"
                >
                  View Details
                </button>
              </div>
            </div>
          ))}

          {jobs.length === 0 && (
            <div className="py-12 text-center text-slate-500 text-sm">
              No opportunities discovered yet. Click <span className="text-amber-400 font-semibold">"Run Daily Hunt"</span> above to search!
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
