import React, { useState, useEffect } from 'react';
import {
  Settings,
  Sparkles,
  Clock,
  Layers,
  ShieldAlert,
  CheckCircle2,
  AlertTriangle,
  Play,
  Pause,
  Save,
  Check,
  Smartphone,
  Wifi,
  ExternalLink,
} from 'lucide-react';
import { api } from '../services/api';

export default function SettingsPage({
  profile,
  schedulerStatus,
  onProfileUpdated,
  onSchedulerToggled,
  onEmergencyStop,
}) {
  const [networkInfo, setNetworkInfo] = useState(null);

  useEffect(() => {
    api.getNetworkInfo().then(setNetworkInfo).catch(console.warn);
  }, []);
  const [prefs, setPrefs] = useState(
    profile?.application_preferences || {
      daily_search_time: '09:00',
      max_applications_per_day: 5,
      min_match_score: 75,
      submission_policy: 'manual_approval',
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
      setTimeout(() => setSuccess(false), 2500);
    } catch (err) {
      alert(`Failed to save settings: ${err.message}`);
    } finally {
      setSaving(false);
    }
  };

  const toggleScheduler = async () => {
    try {
      if (schedulerStatus?.is_running) {
        await api.stopScheduler();
      } else {
        const [h, m] = (prefs.daily_search_time || '09:00').split(':').map((v) => parseInt(v, 10));
        await api.startScheduler(h || 9, m || 0);
      }
      onSchedulerToggled();
    } catch (err) {
      alert(`Scheduler action failed: ${err.message}`);
    }
  };

  return (
    <div className="space-y-6 pb-16 max-w-4xl">
      {/* Header */}
      <div>
        <div className="inline-flex items-center space-x-2 px-3 py-1 rounded-full text-xs font-mono bg-amber-500/10 border border-amber-500/20 text-amber-300 mb-2">
          <span>System Architecture & Governance</span>
        </div>
        <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
          Settings & Automation Rules
        </h1>
        <p className="text-sm text-slate-400">
          Configure daily autonomous discovery parameters, submission authorization policies, and local AI runtime.
        </p>
      </div>

      {/* Global Emergency Stop Card */}
      <div className="rounded-2xl bg-rose-950/20 border border-rose-500/40 p-6 space-y-3 shadow-lg">
        <div className="flex items-center space-x-3">
          <div className="p-2 rounded-xl bg-rose-500/20 text-rose-400">
            <ShieldAlert className="w-6 h-6" />
          </div>
          <div>
            <h2 className="text-base font-bold text-white">Global Emergency Stop Kill-Switch</h2>
            <p className="text-xs text-rose-300/80">
              Immediately aborts and closes any in-progress Playwright browser automation sessions.
            </p>
          </div>
        </div>

        <div className="pt-2">
          <button
            onClick={onEmergencyStop}
            className="flex items-center space-x-2 px-5 py-2.5 rounded-xl text-xs sm:text-sm font-bold bg-rose-600 hover:bg-rose-500 text-white shadow-lg shadow-rose-950/50 active:scale-95 transition-all"
          >
            <ShieldAlert className="w-4 h-4" />
            <span>TRIGGER EMERGENCY STOP NOW</span>
          </button>
        </div>
      </div>

      {/* Submission Policies Selector */}
      <div className="rounded-2xl bg-slate-900/90 border border-slate-800 p-6 space-y-4 shadow-xl">
        <h2 className="text-base font-bold text-white flex items-center space-x-2">
          <Layers className="w-4 h-4 text-amber-400" />
          <span>Application Submission Policy</span>
        </h2>
        <p className="text-xs text-slate-400">
          Controls whether Agent KitKat submits job applications autonomously or holds them for review.
        </p>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-2">
          {[
            {
              id: 'manual_approval',
              title: 'A. Manual Approval',
              desc: 'Prepares draft & maps fields. Holds application in queue until you explicitly click approve.',
              badge: 'Recommended',
            },
            {
              id: 'pre_authorized',
              title: 'B. Pre-Authorized',
              desc: 'Submits automatically ONLY when eligibility is 100% PASS and match score ≥ threshold.',
              badge: 'Autonomous',
            },
            {
              id: 'prepare_only',
              title: 'C. Prepare Only',
              desc: 'Generates tailored cover letters and mapped answers. Never touches website submit buttons.',
              badge: 'Safe Mode',
            },
          ].map((policy) => {
            const isSelected = prefs.submission_policy === policy.id;
            return (
              <div
                key={policy.id}
                onClick={() => setPrefs({ ...prefs, submission_policy: policy.id })}
                className={`p-4 rounded-xl border cursor-pointer transition-all flex flex-col justify-between space-y-3 ${
                  isSelected
                    ? 'bg-amber-500/10 border-amber-500 text-amber-300 shadow-md shadow-amber-500/5'
                    : 'bg-slate-800/40 border-slate-800 hover:border-slate-700 text-slate-400'
                }`}
              >
                <div>
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-sm text-slate-100">{policy.title}</span>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-800 text-amber-400 border border-slate-700">
                      {policy.badge}
                    </span>
                  </div>
                  <p className="text-xs text-slate-400 mt-2 leading-relaxed">{policy.desc}</p>
                </div>

                <div className="flex items-center space-x-1.5 text-xs font-semibold">
                  <div
                    className={`w-3.5 h-3.5 rounded-full border flex items-center justify-center ${
                      isSelected ? 'border-amber-400 bg-amber-400' : 'border-slate-600'
                    }`}
                  >
                    {isSelected && <div className="w-1.5 h-1.5 rounded-full bg-slate-950" />}
                  </div>
                  <span className={isSelected ? 'text-amber-300' : 'text-slate-500'}>
                    {isSelected ? 'Active Policy' : 'Select'}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Autonomous Scheduler Controls */}
      <div className="rounded-2xl bg-slate-900/90 border border-slate-800 p-6 space-y-4 shadow-xl">
        <h2 className="text-base font-bold text-white flex items-center space-x-2">
          <Clock className="w-4 h-4 text-amber-400" />
          <span>Daily Autonomous Scheduler (Mode A)</span>
        </h2>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1.5">
              Daily Search Time (24h format)
            </label>
            <input
              type="time"
              value={prefs.daily_search_time || '09:00'}
              onChange={(e) => setPrefs({ ...prefs, daily_search_time: e.target.value })}
              className="w-full px-3.5 py-2 rounded-xl bg-slate-800/80 border border-slate-700 text-sm text-white focus:outline-none focus:border-amber-500 font-mono"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1.5">
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
              className="w-full px-3.5 py-2 rounded-xl bg-slate-800/80 border border-slate-700 text-sm text-white focus:outline-none focus:border-amber-500 font-mono"
            />
          </div>

          <div className="sm:col-span-2">
            <div className="flex justify-between items-center mb-1.5">
              <label className="text-xs font-semibold text-slate-300">
                Minimum Match Score for Auto-Shortlist: {prefs.min_match_score || 75}%
              </label>
            </div>
            <input
              type="range"
              min={50}
              max={95}
              step={5}
              value={prefs.min_match_score || 75}
              onChange={(e) => setPrefs({ ...prefs, min_match_score: parseInt(e.target.value) || 75 })}
              className="w-full accent-amber-500 bg-slate-800 h-2 rounded-lg cursor-pointer"
            />
          </div>
        </div>

        {/* Scheduler Toggle Bar */}
        <div className="pt-3 border-t border-slate-800 flex items-center justify-between">
          <div className="text-xs">
            <span className="text-slate-400 block">Scheduler Runner State</span>
            <span
              className={`font-mono font-bold ${
                schedulerStatus?.is_running ? 'text-emerald-400' : 'text-slate-500'
              }`}
            >
              {schedulerStatus?.is_running ? 'Running (Active)' : 'Stopped (Standby)'}
            </span>
          </div>

          <button
            onClick={toggleScheduler}
            className={`flex items-center space-x-1.5 px-4 py-2 rounded-xl text-xs font-semibold transition-all ${
              schedulerStatus?.is_running
                ? 'bg-slate-800 text-rose-300 hover:bg-rose-950/60 border border-slate-700'
                : 'bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold shadow-md shadow-emerald-500/20'
            }`}
          >
            {schedulerStatus?.is_running ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
            <span>{schedulerStatus?.is_running ? 'Pause Scheduler' : 'Activate Scheduler'}</span>
          </button>
        </div>
      </div>

      {/* iPhone PWA & Remote Network Access Card */}
      <div className="rounded-2xl bg-slate-900/90 border border-slate-800 p-6 space-y-4 shadow-xl">
        <h2 className="text-base font-bold text-white flex items-center space-x-2">
          <Smartphone className="w-4 h-4 text-amber-400" />
          <span>iPhone PWA & Local Network Remote Access</span>
        </h2>
        <p className="text-xs text-slate-400">
          Control Agent KitKat directly from your iPhone without installing third-party apps from the App Store.
        </p>

        {networkInfo ? (
          <div className="space-y-4 pt-1">
            <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div>
                <span className="text-[10px] text-slate-500 uppercase font-mono block">Your iPhone Safari Access URL</span>
                <span className="font-mono text-sm font-bold text-amber-400">{networkInfo.mobile_access_url}</span>
              </div>
              <a
                href={networkInfo.mobile_access_url}
                target="_blank"
                rel="noopener noreferrer"
                className="px-3.5 py-1.5 rounded-lg text-xs font-semibold bg-amber-500/10 hover:bg-amber-500/20 text-amber-300 border border-amber-500/30 flex items-center space-x-1.5 self-start sm:self-auto"
              >
                <span>Open URL</span>
                <ExternalLink className="w-3.5 h-3.5" />
              </a>
            </div>

            <div className="space-y-2 text-xs text-slate-300">
              <span className="font-semibold text-slate-200 block">How to Install on iPhone:</span>
              <ul className="space-y-1.5 list-disc list-inside text-slate-400">
                {networkInfo.setup_instructions?.map((inst, i) => (
                  <li key={i}>{inst}</li>
                ))}
              </ul>
            </div>
          </div>
        ) : (
          <div className="text-xs text-slate-500">Detecting local network IP...</div>
        )}
      </div>

      {/* Save Settings Bar */}
      <div className="flex items-center space-x-4 pt-2">
        <button
          onClick={handleSavePrefs}
          disabled={saving}
          className="flex items-center space-x-2 px-6 py-2.5 rounded-xl text-sm font-semibold bg-amber-500 hover:bg-amber-400 text-slate-950 shadow-md shadow-amber-500/20 active:scale-95 transition-all disabled:opacity-50"
        >
          <Save className="w-4 h-4" />
          <span>{saving ? 'Saving...' : 'Save All Preferences'}</span>
        </button>

        {success && (
          <span className="text-xs font-semibold text-emerald-400 flex items-center space-x-1">
            <Check className="w-4 h-4" />
            <span>Preferences saved successfully!</span>
          </span>
        )}
      </div>
    </div>
  );
}
