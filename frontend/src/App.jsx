import React, { useState, useEffect } from 'react';
import Navbar from './components/Navbar';
import DashboardPage from './pages/DashboardPage';
import AnalyzeJobPage from './pages/AnalyzeJobPage';
import OpportunitiesPage from './pages/OpportunitiesPage';
import ApprovalsPage from './pages/ApprovalsPage';
import TrackerPage from './pages/TrackerPage';
import ProfilePage from './pages/ProfilePage';
import ResumesPage from './pages/ResumesPage';
import DailyReportsPage from './pages/DailyReportsPage';
import SettingsPage from './pages/SettingsPage';
import { api } from './services/api';

export default function App() {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [health, setHealth] = useState(null);
  const [profile, setProfile] = useState(null);
  const [jobs, setJobs] = useState([]);
  const [report, setReport] = useState(null);
  const [schedulerStatus, setSchedulerStatus] = useState(null);
  const [pendingApprovalsCount, setPendingApprovalsCount] = useState(0);
  const [emergencyAlert, setEmergencyAlert] = useState(null);
  const [discoveryRun, setDiscoveryRun] = useState(null); // live background run (progress)
  const [healthRefreshKey, setHealthRefreshKey] = useState(0);

  // Initial load
  const loadInitialData = async () => {
    try {
      const [h, p, j, r, s, appr] = await Promise.allSettled([
        api.getHealth(),
        api.getProfile(),
        api.getJobs(),
        api.getDailyReport(),
        api.getSchedulerStatus(),
        api.getApprovals(),
      ]);

      if (h.status === 'fulfilled') setHealth(h.value);
      if (p.status === 'fulfilled') setProfile(p.value);
      if (j.status === 'fulfilled') setJobs(j.value);
      if (r.status === 'fulfilled') setReport(r.value);
      if (s.status === 'fulfilled') setSchedulerStatus(s.value);
      if (appr.status === 'fulfilled') setPendingApprovalsCount(appr.value?.length || 0);
    } catch (err) {
      console.warn('Initial data load note:', err);
    }
  };

  useEffect(() => {
    loadInitialData();

    // Periodic lightweight refresh for pending approvals count every 20 seconds
    const interval = setInterval(async () => {
      try {
        const appr = await api.getApprovals();
        setPendingApprovalsCount(appr?.length || 0);
      } catch {
        // silence poll error
      }
    }, 20000);

    return () => clearInterval(interval);
  }, []);

  const handleEmergencyStop = async () => {
    try {
      const res = await api.emergencyStop();
      setEmergencyAlert(res.message || 'Emergency Stop Activated: All active browser sessions terminated.');
      setTimeout(() => setEmergencyAlert(null), 5000);
    } catch (err) {
      alert(`Emergency stop failed: ${err.message}`);
    }
  };

  const refreshAfterDiscovery = async () => {
    const [j, r, appr] = await Promise.allSettled([api.getJobs(), api.getDailyReport(), api.getApprovals()]);
    if (j.status === 'fulfilled') setJobs(j.value);
    if (r.status === 'fulfilled') setReport(r.value);
    if (appr.status === 'fulfilled') setPendingApprovalsCount(appr.value?.length || 0);
    setHealthRefreshKey((k) => k + 1);
  };

  // Starts a background discovery run and polls its progress until it finishes.
  const handleTriggerDiscovery = async () => {
    let runId;
    try {
      const started = await api.startDiscoveryRun({});
      runId = started.run_id;
      setDiscoveryRun({ run_id: runId, status: 'running', progress: 'Starting...' });
    } catch (err) {
      alert(`Could not start discovery: ${err.message}`);
      return;
    }
    for (;;) {
      await new Promise((r) => setTimeout(r, 2000));
      try {
        const run = await api.getDiscoveryRun(runId);
        setDiscoveryRun(run);
        if (run.status !== 'running') break;
      } catch (err) {
        setDiscoveryRun({ run_id: runId, status: 'unknown', progress: `Lost track of run: ${err.message}` });
        break;
      }
    }
    await refreshAfterDiscovery();
  };

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 flex flex-col font-sans">
      {/* Top Navbar */}
      <Navbar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        health={health}
        onEmergencyStop={handleEmergencyStop}
        pendingApprovalsCount={pendingApprovalsCount}
      />

      {/* Emergency Alert Toast Banner */}
      {emergencyAlert && (
        <div className="bg-red-500/15 border-b border-red-500/30 text-red-200 text-xs sm:text-sm font-medium py-2.5 px-4 text-center backdrop-blur-md">
          {emergencyAlert}
        </div>
      )}

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-3.5 sm:px-6 lg:px-8 py-5 sm:py-8 pb-24 lg:pb-12">
        {activeTab === 'dashboard' && (
          <DashboardPage
            profile={profile}
            report={report}
            jobs={jobs}
            schedulerStatus={schedulerStatus}
            onTriggerDiscovery={handleTriggerDiscovery}
            discoveryRun={discoveryRun}
            healthRefreshKey={healthRefreshKey}
            onNavigateTab={setActiveTab}
            onEmergencyStop={handleEmergencyStop}
          />
        )}

        {activeTab === 'analyze' && <AnalyzeJobPage onNavigateTab={setActiveTab} />}

        {activeTab === 'opportunities' && (
          <OpportunitiesPage
            jobs={jobs}
            onNavigateTab={setActiveTab}
            onPrepareApplication={() => setActiveTab('approvals')}
          />
        )}

        {activeTab === 'approvals' && <ApprovalsPage onNavigateTab={setActiveTab} />}

        {activeTab === 'tracker' && <TrackerPage />}

        {activeTab === 'profile' && (
          <ProfilePage
            profile={profile}
            onProfileUpdated={(up) => setProfile(up)}
          />
        )}

        {activeTab === 'resumes' && (
          <ResumesPage
            onResumeChanged={async () => {
              const p = await api.getProfile();
              setProfile(p);
            }}
          />
        )}

        {activeTab === 'reports' && <DailyReportsPage />}

        {activeTab === 'settings' && (
          <SettingsPage
            profile={profile}
            schedulerStatus={schedulerStatus}
            onProfileUpdated={(up) => setProfile(up)}
            onSchedulerToggled={async () => {
              const s = await api.getSchedulerStatus();
              setSchedulerStatus(s);
            }}
            onEmergencyStop={handleEmergencyStop}
          />
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-zinc-850/80 bg-zinc-950 py-5 text-center text-xs text-zinc-500 hidden sm:block">
        <p>
          <span className="text-zinc-200 font-medium">Agent KitKat</span> &mdash; Autonomous Career Assistant &bull; Local Ollama{' '}
          <span className="font-mono text-zinc-400 text-[11px]">(qwen2.5:1.5b)</span> &bull; 100% Free
        </p>
      </footer>
    </div>
  );
}
