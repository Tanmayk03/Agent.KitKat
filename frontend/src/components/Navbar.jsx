import React, { useState } from 'react';
import {
  LayoutDashboard,
  Search,
  CheckSquare,
  FileText,
  User,
  Settings,
  ShieldAlert,
  BarChart3,
  ListOrdered,
  Menu,
  X,
  Zap,
} from 'lucide-react';

export default function Navbar({
  activeTab,
  setActiveTab,
  health,
  onEmergencyStop,
  pendingApprovalsCount = 0,
}) {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const navItems = [
    { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { id: 'analyze', label: 'Analyze Job', icon: Search },
    { id: 'opportunities', label: 'Opportunities', icon: ListOrdered },
    {
      id: 'approvals',
      label: 'Approvals',
      icon: CheckSquare,
      badge: pendingApprovalsCount > 0 ? pendingApprovalsCount : null,
    },
    { id: 'tracker', label: 'Tracker', icon: FileText },
    { id: 'profile', label: 'Profile', icon: User },
    { id: 'resumes', label: 'Resumes', icon: FileText },
    { id: 'reports', label: 'Daily Reports', icon: BarChart3 },
    { id: 'settings', label: 'Settings', icon: Settings },
  ];

  const handleTabClick = (id) => {
    setActiveTab(id);
    setMobileMenuOpen(false);
  };

  const isOllamaOnline = health && health.status === 'connected';

  return (
    <header className="sticky top-0 z-50 bg-slate-900/90 backdrop-blur-md border-b border-slate-800">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Brand */}
          <div className="flex items-center space-x-3 cursor-pointer" onClick={() => handleTabClick('dashboard')}>
            <span className="text-3xl filter drop-shadow">🍫</span>
            <div>
              <div className="flex items-center space-x-2">
                <span className="text-xl font-bold bg-gradient-to-r from-amber-400 via-amber-200 to-amber-500 bg-clip-text text-transparent tracking-tight">
                  Agent KitKat
                </span>
                <span className="text-[10px] px-2 py-0.5 rounded-full font-mono bg-amber-500/10 text-amber-300 border border-amber-500/20">
                  v0.1.0
                </span>
              </div>
              <p className="text-[11px] text-slate-400 hidden sm:block">Autonomous AI Career Assistant</p>
            </div>
          </div>

          {/* Desktop Navigation */}
          <nav className="hidden lg:flex items-center space-x-1">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = activeTab === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => handleTabClick(item.id)}
                  className={`relative flex items-center space-x-1.5 px-3 py-2 rounded-lg text-xs font-medium transition-all ${
                    isActive
                      ? 'bg-amber-500/15 text-amber-300 border border-amber-500/30 shadow-sm shadow-amber-500/10'
                      : 'text-slate-300 hover:text-white hover:bg-slate-800/60'
                  }`}
                >
                  <Icon className="w-4 h-4" />
                  <span>{item.label}</span>
                  {item.badge && (
                    <span className="ml-1 px-1.5 py-0.2 text-[10px] font-bold rounded-full bg-amber-500 text-slate-950 animate-pulse">
                      {item.badge}
                    </span>
                  )}
                </button>
              );
            })}
          </nav>

          {/* Right Action Tools */}
          <div className="flex items-center space-x-2 sm:space-x-3">
            {/* Local AI status badge */}
            <div
              className={`hidden md:flex items-center space-x-1.5 px-2.5 py-1 rounded-full text-xs font-mono border ${
                isOllamaOnline
                  ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'
                  : 'bg-rose-500/10 border-rose-500/30 text-rose-400'
              }`}
            >
              <div
                className={`w-2 h-2 rounded-full ${
                  isOllamaOnline ? 'bg-emerald-400 animate-pulse' : 'bg-rose-400'
                }`}
              />
              <span>{isOllamaOnline ? 'Qwen2.5 1.5B (₹0/mo)' : 'Ollama Offline'}</span>
            </div>

            {/* Emergency Stop Button */}
            <button
              onClick={onEmergencyStop}
              className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-rose-600 hover:bg-rose-500 text-white shadow-md shadow-rose-900/30 active:scale-95 transition-all border border-rose-400/30"
              title="Immediately halts all active Playwright browser sessions"
            >
              <ShieldAlert className="w-4 h-4" />
              <span className="hidden sm:inline">Emergency Stop</span>
            </button>

            {/* Mobile Menu Hamburger */}
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="lg:hidden p-2 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800"
            >
              {mobileMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
            </button>
          </div>
        </div>
      </div>

      {/* Mobile Drawer */}
      {mobileMenuOpen && (
        <div className="lg:hidden border-t border-slate-800 bg-slate-900/95 px-4 pt-3 pb-6 space-y-1 shadow-2xl">
          <div className="flex items-center justify-between pb-3 mb-2 border-b border-slate-800 text-xs text-slate-400">
            <span>AI Runtime: {isOllamaOnline ? 'Online' : 'Offline'}</span>
            <span className="font-mono text-amber-400">Strictly ₹0 Budget</span>
          </div>
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => handleTabClick(item.id)}
                className={`w-full flex items-center justify-between px-4 py-2.5 rounded-lg text-sm font-medium transition-all ${
                  isActive
                    ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                    : 'text-slate-300 hover:bg-slate-800 hover:text-white'
                }`}
              >
                <div className="flex items-center space-x-3">
                  <Icon className="w-5 h-5 text-amber-400" />
                  <span>{item.label}</span>
                </div>
                {item.badge && (
                  <span className="px-2 py-0.5 text-xs font-bold rounded-full bg-amber-500 text-slate-950">
                    {item.badge}
                  </span>
                )}
              </button>
            );
          })}
        </div>
      )}

      {/* Mobile Bottom Navigation Bar (iPhone Friendly) */}
      <div className="lg:hidden fixed bottom-0 left-0 right-0 z-50 bg-slate-950/95 backdrop-blur-md border-t border-slate-800 px-2 py-1.5 flex justify-around items-center">
        {[
          { id: 'dashboard', label: 'Home', icon: LayoutDashboard },
          { id: 'analyze', label: 'Analyze', icon: Search },
          { id: 'opportunities', label: 'Jobs', icon: ListOrdered },
          { id: 'approvals', label: 'Approvals', icon: CheckSquare, badge: pendingApprovalsCount },
          { id: 'tracker', label: 'Tracker', icon: FileText },
        ].map((item) => {
          const Icon = item.icon;
          const isActive = activeTab === item.id;
          return (
            <button
              key={item.id}
              onClick={() => handleTabClick(item.id)}
              className={`flex flex-col items-center justify-center py-1 px-2 relative transition-all ${
                isActive ? 'text-amber-400' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Icon className="w-5 h-5" />
              <span className="text-[10px] mt-0.5 font-medium">{item.label}</span>
              {item.badge > 0 && (
                <span className="absolute top-0 right-1 w-2 h-2 rounded-full bg-amber-500" />
              )}
            </button>
          );
        })}
      </div>
    </header>
  );
}
