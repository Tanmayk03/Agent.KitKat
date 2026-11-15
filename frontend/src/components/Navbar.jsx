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
  FileCheck,
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
    { id: 'resumes', label: 'Resumes', icon: FileCheck },
    { id: 'reports', label: 'Daily Reports', icon: BarChart3 },
    { id: 'settings', label: 'Settings', icon: Settings },
  ];

  const handleTabClick = (id) => {
    setActiveTab(id);
    setMobileMenuOpen(false);
  };

  const isOllamaOnline = health && health.status === 'connected';

  return (
    <header className="sticky top-0 z-50 bg-zinc-950/85 backdrop-blur-md border-b border-zinc-800/80">
      <div className="max-w-7xl mx-auto px-3.5 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-14 sm:h-16">
          {/* Brand */}
          <div
            className="flex items-center space-x-2.5 cursor-pointer select-none"
            onClick={() => handleTabClick('dashboard')}
          >
            <div className="w-8 h-8 rounded-lg bg-zinc-100 text-zinc-950 flex items-center justify-center font-bold text-sm tracking-tight shadow-sm">
              K
            </div>
            <div>
              <div className="flex items-center space-x-1.5">
                <span className="text-sm sm:text-base font-semibold text-zinc-100 tracking-tight">
                  Agent KitKat
                </span>
                <span className="text-[10px] px-1.5 py-0.5 rounded font-mono bg-zinc-900 text-zinc-400 border border-zinc-800">
                  v0.1
                </span>
              </div>
              <p className="text-[11px] text-zinc-400 hidden md:block">Career Assistant</p>
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
                  className={`relative flex items-center space-x-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                    isActive
                      ? 'bg-zinc-800/90 text-zinc-100 border border-zinc-700/60'
                      : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900/60'
                  }`}
                >
                  <Icon className="w-3.5 h-3.5" />
                  <span>{item.label}</span>
                  {item.badge && (
                    <span className="ml-1 px-1.5 py-0.2 text-[10px] font-semibold rounded-full bg-zinc-100 text-zinc-950">
                      {item.badge}
                    </span>
                  )}
                </button>
              );
            })}
          </nav>

          {/* Right Action Tools */}
          <div className="flex items-center space-x-2">
            {/* Local AI status badge */}
            <div
              className={`hidden sm:flex items-center space-x-1.5 px-2.5 py-1 rounded-md text-xs font-mono border ${
                isOllamaOnline
                  ? 'bg-zinc-900 border-zinc-800 text-zinc-300'
                  : 'bg-red-950/20 border-red-900/30 text-red-400'
              }`}
            >
              <div
                className={`w-1.5 h-1.5 rounded-full ${
                  isOllamaOnline ? 'bg-emerald-400' : 'bg-red-400'
                }`}
              />
              <span className="text-[11px]">
                {isOllamaOnline ? 'qwen2.5:1.5b' : 'Ollama Offline'}
              </span>
            </div>

            {/* Emergency Stop Button */}
            <button
              onClick={onEmergencyStop}
              className="flex items-center space-x-1.5 px-2.5 sm:px-3 py-1.5 rounded-md text-xs font-medium bg-red-950/40 hover:bg-red-900/50 text-red-300 hover:text-red-200 border border-red-800/40 transition-colors"
              title="Immediately halts all active Playwright browser sessions"
            >
              <ShieldAlert className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">Emergency Stop</span>
            </button>

            {/* Mobile Menu Hamburger */}
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="lg:hidden p-1.5 rounded-md text-zinc-400 hover:text-zinc-100 hover:bg-zinc-900"
              aria-label="Toggle Navigation Menu"
            >
              {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
            </button>
          </div>
        </div>
      </div>

      {/* Mobile Drawer */}
      {mobileMenuOpen && (
        <div className="lg:hidden border-t border-zinc-800/80 bg-zinc-950 px-4 pt-3 pb-5 space-y-1 shadow-2xl">
          <div className="flex items-center justify-between pb-3 mb-2 border-b border-zinc-850 text-xs text-zinc-400">
            <span>Runtime: {isOllamaOnline ? 'Online (Local)' : 'Offline'}</span>
            <span className="font-mono text-zinc-400 text-[11px]">₹0 Cost</span>
          </div>
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => handleTabClick(item.id)}
                className={`w-full flex items-center justify-between px-3 py-2 rounded-md text-xs font-medium transition-colors ${
                  isActive
                    ? 'bg-zinc-800 text-zinc-100 border border-zinc-700/60'
                    : 'text-zinc-400 hover:bg-zinc-900 hover:text-zinc-200'
                }`}
              >
                <div className="flex items-center space-x-2.5">
                  <Icon className="w-4 h-4 text-zinc-400" />
                  <span>{item.label}</span>
                </div>
                {item.badge && (
                  <span className="px-1.5 py-0.5 text-[10px] font-semibold rounded-full bg-zinc-100 text-zinc-950">
                    {item.badge}
                  </span>
                )}
              </button>
            );
          })}
        </div>
      )}

      {/* Mobile Bottom Navigation Bar */}
      <div className="lg:hidden fixed bottom-0 left-0 right-0 z-50 bg-zinc-950/90 backdrop-blur-lg border-t border-zinc-800/80 px-2 py-1.5 flex justify-around items-center">
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
              className={`flex flex-col items-center justify-center py-1 px-3 relative transition-colors ${
                isActive ? 'text-zinc-100' : 'text-zinc-500 hover:text-zinc-300'
              }`}
            >
              <Icon className="w-4 h-4" />
              <span className="text-[10px] mt-1 font-medium">{item.label}</span>
              {item.badge > 0 && (
                <span className="absolute top-0 right-2 w-1.5 h-1.5 rounded-full bg-zinc-100" />
              )}
            </button>
          );
        })}
      </div>
    </header>
  );
}
