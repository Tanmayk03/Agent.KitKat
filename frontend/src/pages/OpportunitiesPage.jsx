import React, { useState } from 'react';
import {
  Search,
  Filter,
  ExternalLink,
  Sparkles,
  Shield,
  CheckCircle2,
  XCircle,
  HelpCircle,
  Briefcase,
  Layers,
} from 'lucide-react';
import { api } from '../services/api';

export default function OpportunitiesPage({ jobs = [], onPrepareApplication, onNavigateTab }) {
  const [filter, setFilter] = useState('all'); // 'all', 'eligible', 'high_match', 'remote'
  const [searchQuery, setSearchQuery] = useState('');
  const [preparingId, setPreparingId] = useState(null);

  const filteredJobs = jobs.filter((job) => {
    // Text search
    const q = searchQuery.toLowerCase();
    const textMatch =
      !q ||
      job.title?.toLowerCase().includes(q) ||
      job.company?.toLowerCase().includes(q) ||
      job.location?.toLowerCase().includes(q);

    if (!textMatch) return false;

    // Filter pills
    if (filter === 'remote') {
      return (
        job.work_mode?.toLowerCase() === 'remote' ||
        job.location?.toLowerCase().includes('remote')
      );
    }
    // Note: If eligibility/match is loaded on job
    return true;
  });

  const handlePrepare = async (jobId) => {
    try {
      setPreparingId(jobId);
      await api.prepareApplication(jobId);
      onNavigateTab('approvals');
    } catch (err) {
      alert(`Could not prepare application: ${err.message}`);
    } finally {
      setPreparingId(null);
    }
  };

  return (
    <div className="space-y-6 pb-16">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
            Discovered Opportunities ({jobs.length})
          </h1>
          <p className="text-sm text-slate-400">
            Real opportunities discovered across permitted public feeds, Remotive, and curated tech startups.
          </p>
        </div>
      </div>

      {/* Filter & Search Bar */}
      <div className="flex flex-col sm:flex-row gap-3 items-center justify-between">
        {/* Search Input */}
        <div className="relative w-full sm:w-80">
          <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-3" />
          <input
            type="text"
            placeholder="Search by role, company, or city..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-2 rounded-xl bg-slate-900 border border-slate-800 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-amber-500"
          />
        </div>

        {/* Filter Pills */}
        <div className="flex items-center space-x-1.5 self-start sm:self-auto overflow-x-auto w-full sm:w-auto pb-1 sm:pb-0">
          {[
            { id: 'all', label: 'All Jobs' },
            { id: 'remote', label: 'Remote Only' },
          ].map((pill) => (
            <button
              key={pill.id}
              onClick={() => setFilter(pill.id)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all whitespace-nowrap ${
                filter === pill.id
                  ? 'bg-amber-500 text-slate-950 font-bold shadow-sm'
                  : 'bg-slate-900 text-slate-400 hover:text-white border border-slate-800'
              }`}
            >
              {pill.label}
            </button>
          ))}
        </div>
      </div>

      {/* Jobs Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {filteredJobs.map((job) => (
          <div
            key={job.id}
            className="rounded-2xl bg-slate-900/90 border border-slate-800 p-5 hover:border-slate-700 transition-all flex flex-col justify-between space-y-4 shadow-lg"
          >
            <div className="space-y-2">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h3 className="text-base font-bold text-white hover:text-amber-400 transition-colors">
                    {job.title}
                  </h3>
                  <p className="text-xs font-medium text-slate-300">{job.company}</p>
                </div>
                <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-slate-800 text-amber-300 border border-slate-700 whitespace-nowrap">
                  {job.work_mode || 'Remote'}
                </span>
              </div>

              <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-slate-400">
                <span>{job.location || 'India'}</span>
                <span>•</span>
                <span className="font-mono text-slate-300">{job.salary_stipend || 'Competitive'}</span>
                <span>•</span>
                <span className="text-[10px] text-slate-500 uppercase font-mono">
                  {job.source || 'public'}
                </span>
              </div>

              {job.description && (
                <p className="text-xs text-slate-400 line-clamp-3 leading-relaxed pt-1">
                  {job.description}
                </p>
              )}
            </div>

            {/* Bottom Actions */}
            <div className="pt-3 border-t border-slate-800/80 flex items-center justify-between gap-2">
              {job.url ? (
                <a
                  href={job.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center space-x-1 text-xs font-medium text-slate-400 hover:text-slate-200 transition-colors"
                >
                  <span>View Posting</span>
                  <ExternalLink className="w-3.5 h-3.5" />
                </a>
              ) : (
                <span className="text-xs text-slate-500">Internal listing</span>
              )}

              <button
                onClick={() => handlePrepare(job.id)}
                disabled={preparingId === job.id}
                className="flex items-center space-x-1.5 px-3.5 py-1.5 rounded-lg text-xs font-semibold bg-amber-500 hover:bg-amber-400 text-slate-950 shadow-md shadow-amber-500/20 active:scale-95 transition-all disabled:opacity-50"
              >
                <Sparkles className="w-3.5 h-3.5" />
                <span>{preparingId === job.id ? 'Drafting...' : 'Prepare Application'}</span>
              </button>
            </div>
          </div>
        ))}

        {filteredJobs.length === 0 && (
          <div className="col-span-full py-16 text-center text-slate-500 text-sm">
            No opportunities match your current filter. Try resetting search or triggering a discovery sweep on the Dashboard.
          </div>
        )}
      </div>
    </div>
  );
}
