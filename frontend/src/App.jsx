import React, { useState, useEffect, useCallback } from 'react';
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
import { useToast } from './components/Feedback';

// Tabs live in the URL hash (#/tracker) so reload, bookmarks and the phone's back button work.
const TABS = ['dashboard', 'analyze', 'opportunities', 'approvals', 'tracker', 'profile', 'resumes', 'reports', 'settings'];
const tabFromHash = () => {
  const t = window.location.hash.replace(/^#\/?/, '');
  return TABS.includes(t) ? t : 'dashboard';
};

export default function App() {
  const toast = useToast();
  const [activeTab, setActiveTabState] = useState(tabFromHash);
  const setActiveTab = useCallback((tab) => {
    if (!TABS.includes(tab)) return;
    if (tabFromHash() !== tab) window.location.hash = `/${tab}`;
    setActiveTabState(tab);
    window.scrollTo({ top: 0 });
  }, []);
  useEffect(() => {
    const onHash = () => setActiveTabState(tabFromHash());
    window.addEventListener('hashchange', onHash);
    return () => window.removeEventListener('hashchange', onHash);
  }, []);
  const [health, setHealth] = useState(null);
  const [profile, setProfile] = useState(null);
  const [jobs, setJobs] = useState([]);
  const [report, setReport] = useState(null);
  const [schedulerStatus, setSchedulerStatus] = useState(null);
  const [pendingApprovalsCount, setPendingApprovalsCount] = useState(0);
  const [halted, setHalted] = useState(false);
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
    api.getBrowserStatus().then((st) => setHalted(!!st.halted)).catch(() => {});

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
      setHalted(true);
      toast.error(res.message || 'All automation halted.', { title: 'Emergency Stop' });
    } catch (err) {
      toast.error(`Emergency stop failed: ${err.message}. Close any automation browser windows yourself.`);
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
      toast.error(`Could not start discovery: ${err.message}`);
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

  // Show the outcome of a discovery run once it finishes.
  useEffect(() => {
    if (!discoveryRun || discoveryRun.status === 'running') return;
    const r = discoveryRun;
    const msg = `${r.new_saved ?? 0} new, ${r.duplicates ?? 0} duplicates, ${r.failed_sources ?? 0} failed sources.`;
    if (r.status === 'success') toast.success(msg, { title: 'Discovery finished' });
    else if (r.status === 'partial') toast.info(msg, { title: 'Discovery finished with source errors' });
    else toast.error(r.error || r.progress || 'Discovery failed.', { title: 'Discovery failed' });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [discoveryRun?.status]);

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

      {/* Persistent halt banner: automation stays stopped until you resume */}
      {halted && (
        <div className="bg-red-950/60 border-b border-red-800/50 text-red-100 text-xs sm:text-sm py-2.5 px-4 flex flex-wrap items-center justify-center gap-3" role="alert">
          <span>Automation is halted by Emergency Stop: no browser runs, no discovery, schedule paused.</span>
          <button
            onClick={async () => {
              try {
                const st = await api.resumeAutomation();
                setHalted(!!st.halted);
                if (!st.halted) toast.success('Automation resumed. The schedule is back on if it was enabled.');
              } catch (err) {
                toast.error(`Could not resume: ${err.message}`);
              }
            }}
            className="px-2.5 py-1 rounded-md bg-red-100 text-red-950 font-medium"
          >
            Resume automation
          </button>
        </div>
      )}

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-3.5 sm:px-6 lg:px-8 py-5 sm:py-8 pb-mobile-nav lg:pb-12">
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
          <OpportunitiesPage onNavigateTab={setActiveTab} refreshKey={healthRefreshKey} />
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
              try {
                setProfile(await api.getProfile());
              } catch (err) {
                toast.error(`Could not reload your profile: ${err.message}`);
              }
            }}
            onProfileUpdated={setProfile}
          />
        )}

        {activeTab === 'reports' && <DailyReportsPage onNavigateTab={setActiveTab} />}

        {activeTab === 'settings' && (
          <SettingsPage
            profile={profile}
            schedulerStatus={schedulerStatus}
            onProfileUpdated={(up) => setProfile(up)}
            onSchedulerToggled={async () => {
              try {
                setSchedulerStatus(await api.getSchedulerStatus());
              } catch (err) {
                toast.error(`Could not refresh the schedule status: ${err.message}`);
              }
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
