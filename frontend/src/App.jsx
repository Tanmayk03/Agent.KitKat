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
      setEmergencyAlert(res.message || '🚨 All active browser sessions terminated immediately.');
      setTimeout(() => setEmergencyAlert(null), 5000);
    } catch (err) {
      alert(`Emergency stop failed: ${err.message}`);
    }
  };

  const handleTriggerDiscovery = async () => {
    try {
      await api.triggerDiscovery();
      const updatedJobs = await api.getJobs();
      setJobs(updatedJobs);
      const updatedReport = await api.getDailyReport();
      setReport(updatedReport);
      const appr = await api.getApprovals();
      setPendingApprovalsCount(appr?.length || 0);
      setActiveTab('opportunities');
    } catch (err) {
      alert(`Discovery cycle failed: ${err.message}`);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
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
        <div className="bg-rose-600 text-white text-xs sm:text-sm font-bold py-2.5 px-4 text-center shadow-lg animate-pulse">
          {emergencyAlert}
        </div>
      )}

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6 sm:py-8">
        {activeTab === 'dashboard' && (
          <DashboardPage
            profile={profile}
            report={report}
            jobs={jobs}
            schedulerStatus={schedulerStatus}
            onTriggerDiscovery={handleTriggerDiscovery}
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
      <footer className="border-t border-slate-900 bg-slate-950 py-6 text-center text-xs text-slate-500 hidden sm:block">
        <p>
          <span className="text-amber-400 font-bold">Agent KitKat</span> – Autonomous AI Career Assistant • Powered by Ollama{' '}
          <span className="font-mono text-slate-400">(qwen2.5:1.5b)</span> • ₹0 Operating Budget
        </p>
      </footer>
    </div>
  );
}
