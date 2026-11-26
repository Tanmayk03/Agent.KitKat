import React, { useState } from 'react';
import {
  Clock,
  Layers,
  ShieldAlert,
  Play,
  Pause,
  Save,
  Check,
} from 'lucide-react';
import { api } from '../services/api';
import { useToast } from '../components/Feedback';
import CareerBoardsCard from '../components/CareerBoardsCard';
import PhoneAccessCard from '../components/PhoneAccessCard';
import BackupsCard from '../components/BackupsCard';

export default function SettingsPage({
  profile,
  schedulerStatus,
  onProfileUpdated,
  onSchedulerToggled,
  onEmergencyStop,
}) {
  const toast = useToast();

  const [prefs, setPrefs] = useState(
    profile?.application_preferences || {
      daily_search_time: '09:00',
      max_applications_per_day: 5,
      min_match_score: 75,
      submission_policy: 'prepare_only',
    }
  );

  const [saving, setSaving] = useState(false);
  const [success, setSuccess] = useState(false);

  const handleSavePrefs = async () => {
    try {
      setSaving(true);
      const updated = await api.updateProfile({
        ...profile,
        application_preferences: prefs,
      });
      onProfileUpdated(updated);
      setSuccess(true);
      toast.success('Settings saved.');
      setTimeout(() => setSuccess(false), 2500);
    } catch (err) {
      toast.error(`Could not save settings: ${err.message}`);
    } finally {
      setSaving(false);
    }
  };

  const startWithPrefs = async () => {
    const [h, m] = (prefs.daily_search_time || '09:00').split(':').map((v) => parseInt(v, 10));
    await api.startScheduler(
      Number.isFinite(h) ? h : 9,
      Number.isFinite(m) ? m : 0,
      prefs.schedule_mode || 'daily',
      prefs.interval_hours || 6,
    );
  };

  const toggleScheduler = async () => {
    try {
      if (schedulerStatus?.is_running) {
        await api.stopScheduler();
      } else {
        await startWithPrefs();
      }
      onSchedulerToggled();
    } catch (err) {
      toast.error(`Schedule change failed: ${err.message}`);
    }
  };

  const applySchedule = async () => {
    try {
      await startWithPrefs();
      onSchedulerToggled();
      toast.success('Schedule updated.');
    } catch (err) {
      toast.error(`Could not apply schedule: ${err.message}`);
    }
  };

  return (
    <div className="space-y-6 max-w-4xl">
      {/* Header */}
      <div>
        <div className="inline-flex items-center space-x-1.5 px-2.5 py-0.5 rounded-md text-xs font-mono bg-zinc-900 border border-zinc-800 text-zinc-400 mb-2">
          <span>System Governance</span>
        </div>
        <h1 className="text-xl sm:text-2xl font-bold text-zinc-100 tracking-tight">
          Settings & Automation Rules
        </h1>
        <p className="text-xs sm:text-sm text-zinc-400 mt-1">
          Configure daily autonomous discovery parameters, submission authorization policies, and local AI runtime.
        </p>
      </div>

      {/* Global Emergency Stop Card */}
      <div className="rounded-xl bg-red-950/20 border border-red-900/40 p-4 sm:p-5 space-y-3">
        <div className="flex items-center space-x-3">
          <div className="p-2 rounded-lg bg-red-900/30 text-red-400">
            <ShieldAlert className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-sm font-semibold text-zinc-100">Emergency Stop</h2>
            <p className="text-xs text-zinc-400">
              Closes any automation browser, stops discovery and pauses the schedule. Everything stays stopped, even after a restart, until you press Resume.
            </p>
          </div>
        </div>

        <div className="pt-1">
          <button
            onClick={onEmergencyStop}
            className="flex items-center space-x-1.5 px-3.5 py-2 rounded-lg text-xs font-medium bg-red-900/60 hover:bg-red-800/70 text-red-200 border border-red-700/50 transition-colors"
          >
            <ShieldAlert className="w-3.5 h-3.5" />
            <span>Trigger Emergency Stop Now</span>
          </button>
        </div>
      </div>

      {/* Submission Policies Selector */}
      <div className="rounded-xl bg-zinc-900/40 border border-zinc-800 p-4 sm:p-6 space-y-3.5">
        <h2 className="text-sm font-semibold text-zinc-100 flex items-center space-x-2">
          <Layers className="w-4 h-4 text-zinc-400" />
          <span>Application Submission Policy</span>
        </h2>
        <p className="text-xs text-zinc-400">
          Controls how prepared applications are queued. Nothing is ever submitted without your explicit approval and a final confirmation for that specific application.
        </p>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
          {[
            {
              id: 'prepare_only',
              title: 'A. Prepare only',
              desc: 'Drafts the cover letter and answers, and can fill the form for you to check. Never clicks a submit button: you send the application yourself.',
              badge: 'Default',
            },
            {
              id: 'manual_approval',
              title: 'B. Approve, then confirm',
              desc: 'Drafts wait in Approvals. After you approve one, Agent KitKat fills the form; it submits only when you press Submit and confirm that one application.',
              badge: 'Two checks',
            },
          ].map((policy) => {
            const isSelected = prefs.submission_policy === policy.id;
            return (
              <div
                key={policy.id}
                onClick={() => setPrefs({ ...prefs, submission_policy: policy.id })}
                className={`p-3.5 rounded-lg border cursor-pointer transition-colors flex flex-col justify-between space-y-3 ${
                  isSelected
                    ? 'bg-zinc-800/90 border-zinc-500 text-zinc-100'
                    : 'bg-zinc-900/40 border-zinc-800 hover:border-zinc-700 text-zinc-400'
                }`}
              >
                <div>
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-xs sm:text-sm text-zinc-100">{policy.title}</span>
                    <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-zinc-800 text-zinc-300 border border-zinc-700/50">
                      {policy.badge}
                    </span>
                  </div>
                  <p className="text-xs text-zinc-400 mt-1.5 leading-relaxed">{policy.desc}</p>
                </div>

                <div className="flex items-center space-x-1.5 text-xs font-medium">
                  <div
                    className={`w-3 h-3 rounded-full border flex items-center justify-center ${
                      isSelected ? 'border-zinc-200 bg-zinc-200' : 'border-zinc-600'
                    }`}
                  >
                    {isSelected && <div className="w-1.5 h-1.5 rounded-full bg-zinc-950" />}
                  </div>
                  <span className={isSelected ? 'text-zinc-200' : 'text-zinc-500'}>
                    {isSelected ? 'Active Policy' : 'Select'}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Autonomous Scheduler Controls */}
      <div className="rounded-xl bg-zinc-900/40 border border-zinc-800 p-4 sm:p-6 space-y-4">
        <h2 className="text-sm font-semibold text-zinc-100 flex items-center space-x-2">
          <Clock className="w-4 h-4 text-zinc-400" />
          <span>Discovery schedule</span>
        </h2>
        <p className="text-xs text-zinc-400">
          Each run searches your sources, evaluates new jobs and saves that day's report. It never submits anything.
          {schedulerStatus?.timezone ? ` Times are in ${schedulerStatus.timezone}.` : ''}
        </p>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 sm:gap-4">
          <div>
            <label className="block text-xs font-medium text-zinc-300 mb-1.5">Run</label>
            <select
              value={prefs.schedule_mode || 'daily'}
              onChange={(e) => setPrefs({ ...prefs, schedule_mode: e.target.value })}
              className="w-full px-3 py-2 rounded-lg bg-zinc-900 border border-zinc-800 text-xs sm:text-sm text-zinc-100"
            >
              <option value="daily">Once a day</option>
              <option value="interval">Every few hours</option>
            </select>
          </div>

          {(prefs.schedule_mode || 'daily') === 'daily' ? (
            <div>
              <label className="block text-xs font-medium text-zinc-300 mb-1.5">Time of day (24h)</label>
              <input
                type="time"
                value={prefs.daily_search_time || '09:00'}
                onChange={(e) => setPrefs({ ...prefs, daily_search_time: e.target.value })}
                className="w-full px-3 py-2 rounded-lg bg-zinc-900 border border-zinc-800 text-xs sm:text-sm text-zinc-100 focus:outline-none focus:border-zinc-600 font-mono"
              />
            </div>
          ) : (
            <div>
              <label className="block text-xs font-medium text-zinc-300 mb-1.5">Every</label>
              <select
                value={prefs.interval_hours || 6}
                onChange={(e) => setPrefs({ ...prefs, interval_hours: parseInt(e.target.value, 10) })}
                className="w-full px-3 py-2 rounded-lg bg-zinc-900 border border-zinc-800 text-xs sm:text-sm text-zinc-100"
              >
                {[3, 4, 6, 8, 12, 24].map((h) => <option key={h} value={h}>{h} hours</option>)}
              </select>
            </div>
          )}

          <div>
            <label className="block text-xs font-medium text-zinc-300 mb-1.5">
              Max Daily Applications Cap
            </label>
            <input
              type="number"
              min={1}
              max={25}
              value={prefs.max_applications_per_day || 5}
              onChange={(e) =>
                setPrefs({ ...prefs, max_applications_per_day: parseInt(e.target.value) || 5 })
              }
              className="w-full px-3 py-2 rounded-lg bg-zinc-900 border border-zinc-800 text-xs sm:text-sm text-zinc-100 focus:outline-none focus:border-zinc-600 font-mono"
            />
          </div>

          <div className="sm:col-span-2">
            <div className="flex justify-between items-center mb-1.5">
              <label className="text-xs font-medium text-zinc-300">
                Match score to highlight in reports: {prefs.min_match_score || 75}%
              </label>
            </div>
            <input
              type="range"
              min={50}
              max={95}
              step={5}
              value={prefs.min_match_score || 75}
              onChange={(e) => setPrefs({ ...prefs, min_match_score: parseInt(e.target.value) || 75 })}
              className="w-full accent-zinc-200 bg-zinc-800 h-1.5 rounded-lg cursor-pointer"
            />
          </div>
        </div>

        {/* Scheduler Toggle Bar */}
        <div className="pt-3 border-t border-zinc-800 flex items-center justify-between">
          <div className="text-xs">
            <span className="text-zinc-500 block">Schedule</span>
            <span
              className={`font-mono font-medium ${
                schedulerStatus?.is_running ? 'text-emerald-400' : 'text-zinc-500'
              }`}
            >
              {schedulerStatus?.is_running ? schedulerStatus.description || 'On' : 'Paused'}
            </span>
            {schedulerStatus?.is_running && schedulerStatus?.next_run_time && (
              <span className="text-zinc-500 block mt-0.5">Next run: <span className="font-mono text-zinc-300">{schedulerStatus.next_run_time}</span></span>
            )}
          </div>

          {schedulerStatus?.is_running && (
            <button
              onClick={applySchedule}
              className="ml-auto mr-2 px-3 py-1.5 rounded-lg text-xs font-medium border border-zinc-700 text-zinc-200 hover:bg-zinc-800"
              title="Re-apply the mode/time above to the running schedule"
            >
              Apply changes
            </button>
          )}

          <button
            onClick={toggleScheduler}
            className={`flex items-center space-x-1.5 px-3.5 py-1.5 rounded-lg text-xs font-medium transition-colors ${
              schedulerStatus?.is_running
                ? 'bg-zinc-800 text-red-300 hover:bg-zinc-700 border border-zinc-700/60'
                : 'bg-zinc-100 hover:bg-zinc-200 text-zinc-950'
            }`}
          >
            {schedulerStatus?.is_running ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
            <span>{schedulerStatus?.is_running ? 'Pause schedule' : 'Turn on schedule'}</span>
          </button>
        </div>

        {schedulerStatus?.last_run_status && (
          <p className={`text-xs ${schedulerStatus.last_run_status === 'failed' ? 'text-red-400' : 'text-zinc-400'}`}>
            Last scheduled run: {schedulerStatus.last_run_status}
            {schedulerStatus.last_run_finished_at ? ` at ${schedulerStatus.last_run_finished_at} UTC` : ''}
            {schedulerStatus.last_run_error ? ` — ${schedulerStatus.last_run_error}` : ''}
          </p>
        )}

        {(schedulerStatus?.recent_runs || []).length > 0 && (
          <div className="pt-2">
            <div className="flex justify-between text-xs mb-1.5">
              <span className="text-zinc-300 font-medium">Recent discovery runs</span>
              {schedulerStatus.failed_runs_7d > 0 && (
                <span className="text-red-400">{schedulerStatus.failed_runs_7d} failed in the last 7 days</span>
              )}
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-[11px] font-mono">
                <thead className="text-zinc-500 text-left">
                  <tr><th className="py-1 pr-3 font-normal">Started (UTC)</th><th className="pr-3 font-normal">Trigger</th><th className="pr-3 font-normal">Status</th><th className="pr-3 font-normal">Fetched</th><th className="pr-3 font-normal">New</th><th className="font-normal">Source errors</th></tr>
                </thead>
                <tbody className="text-zinc-300">
                  {schedulerStatus.recent_runs.map((r) => (
                    <tr key={r.id} className="border-t border-zinc-800/70" title={r.error || ''}>
                      <td className="py-1 pr-3">{r.started_at}</td>
                      <td className="pr-3">{r.trigger}</td>
                      <td className={`pr-3 ${r.status === 'failed' || r.status === 'interrupted' ? 'text-red-400' : r.status === 'partial' ? 'text-amber-300' : 'text-emerald-400'}`}>{r.status}</td>
                      <td className="pr-3">{r.fetched ?? 0}</td>
                      <td className="pr-3">{r.new_jobs ?? 0}</td>
                      <td>{r.failed_sources ?? 0}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>

      {/* Company career boards you follow (Greenhouse / Lever / Ashby public APIs) */}
      <CareerBoardsCard />

      <PhoneAccessCard />

      <BackupsCard />

      {/* Save Settings Bar */}
      <div className="flex items-center space-x-3 pt-1">
        <button
          onClick={handleSavePrefs}
          disabled={saving}
          className="flex items-center space-x-2 px-5 py-2 rounded-lg text-xs sm:text-sm font-medium bg-zinc-100 hover:bg-zinc-200 text-zinc-950 transition-colors disabled:opacity-50"
        >
          <Save className="w-3.5 h-3.5" />
          <span>{saving ? 'Saving...' : 'Save All Preferences'}</span>
        </button>

        {success && (
          <span className="text-xs font-medium text-emerald-400 flex items-center space-x-1">
            <Check className="w-3.5 h-3.5" />
            <span>Preferences saved successfully!</span>
          </span>
        )}
      </div>
    </div>
  );
}
