import React, { useState } from 'react';
import {
  Search,
  ExternalLink,
} from 'lucide-react';
import { api } from '../services/api';

export default function OpportunitiesPage({ jobs = [], onPrepareApplication, onNavigateTab }) {
  const [filter, setFilter] = useState('all'); // 'all', 'remote'
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
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-xl sm:text-2xl font-bold text-zinc-100 tracking-tight">
          Discovered Opportunities ({jobs.length})
        </h1>
        <p className="text-xs sm:text-sm text-zinc-400 mt-1">
          Opportunities discovered across verified public feeds, Remotive, and curated tech startups.
        </p>
      </div>

      {/* Filter & Search Bar */}
      <div className="flex flex-col sm:flex-row gap-3 items-stretch sm:items-center justify-between">
        {/* Search Input */}
        <div className="relative w-full sm:w-80">
          <Search className="w-3.5 h-3.5 text-zinc-500 absolute left-3 top-3" />
          <input
            type="text"
            placeholder="Search by role, company, or city..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-3.5 py-2 rounded-lg bg-zinc-900 border border-zinc-800 text-xs sm:text-sm text-zinc-100 placeholder-zinc-500 focus:outline-none focus:border-zinc-600"
          />
        </div>

        {/* Filter Pills */}
        <div className="flex items-center space-x-1.5 overflow-x-auto pb-1 sm:pb-0">
          {[
            { id: 'all', label: 'All Jobs' },
            { id: 'remote', label: 'Remote Only' },
          ].map((pill) => (
            <button
              key={pill.id}
              onClick={() => setFilter(pill.id)}
              className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors whitespace-nowrap ${
                filter === pill.id
                  ? 'bg-zinc-100 text-zinc-950 font-medium'
                  : 'bg-zinc-900 text-zinc-400 hover:text-zinc-200 border border-zinc-800'
              }`}
            >
              {pill.label}
            </button>
          ))}
        </div>
      </div>

      {/* Jobs Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 sm:gap-4">
        {filteredJobs.map((job) => (
          <div
            key={job.id}
            className="rounded-xl bg-zinc-900/40 border border-zinc-800 p-4 sm:p-5 hover:border-zinc-700/70 transition-colors flex flex-col justify-between space-y-4"
          >
            <div className="space-y-2">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h3 className="text-sm sm:text-base font-semibold text-zinc-100">
                    {job.title}
                  </h3>
                  <p className="text-xs text-zinc-300 mt-0.5">{job.company}</p>
                </div>
                <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-zinc-800 text-zinc-300 border border-zinc-700/50 whitespace-nowrap">
                  {job.work_mode || 'Unknown'}
                </span>
              </div>

              <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1 text-xs text-zinc-400">
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
                {job.status === 'expired' && (
                  <>
                    <span>&bull;</span>
                    <span className="text-amber-300">No longer listed</span>
                  </>
                )}
                <span>&bull;</span>
                <span className="text-[10px] text-zinc-500 uppercase font-mono">
                  {job.source || 'unknown'}
                </span>
              </div>

              {job.description && (
                <p className="text-xs text-zinc-400 line-clamp-3 leading-relaxed pt-1">
                  {job.description}
                </p>
              )}
            </div>

            {/* Bottom Actions */}
            <div className="pt-3 border-t border-zinc-800/80 flex items-center justify-between gap-2">
              {job.url ? (
                <a
                  href={job.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center space-x-1 text-xs font-medium text-zinc-400 hover:text-zinc-200 transition-colors"
                >
                  <span>View Posting</span>
                  <ExternalLink className="w-3.5 h-3.5" />
                </a>
              ) : (
                <span className="text-xs text-zinc-500">Internal listing</span>
              )}

              <button
                onClick={() => handlePrepare(job.id)}
                disabled={preparingId === job.id}
                className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-zinc-100 hover:bg-zinc-200 text-zinc-950 transition-colors disabled:opacity-50"
              >
                <span>{preparingId === job.id ? 'Drafting...' : 'Prepare Application'}</span>
              </button>
            </div>
          </div>
        ))}

        {filteredJobs.length === 0 && (
          <div className="col-span-full py-16 text-center text-zinc-500 text-xs sm:text-sm">
            No opportunities match your current filter. Try resetting search or triggering a discovery sweep on the Dashboard.
          </div>
        )}
      </div>
    </div>
  );
}
