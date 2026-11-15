import React, { useState, useEffect } from 'react';
import {
  Calendar,
  CheckCircle2,
} from 'lucide-react';
import { api } from '../services/api';

export default function DailyReportsPage() {
  const [reports, setReports] = useState([]);
  const [selectedReport, setSelectedReport] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchReports = async () => {
    try {
      setLoading(true);
      const hist = await api.getReportHistory();
      setReports(hist);
      if (hist.length > 0) {
        setSelectedReport(hist[0]);
      } else {
        const todayRep = await api.getDailyReport();
        setSelectedReport(todayRep);
        setReports([todayRep]);
      }
    } catch (err) {
      console.error('Failed to load reports:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchReports();
  }, []);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <div className="inline-flex items-center space-x-1.5 px-2.5 py-0.5 rounded-md text-xs font-mono bg-zinc-900 border border-zinc-800 text-zinc-400 mb-2">
          <span>Career Intelligence</span>
        </div>
        <h1 className="text-xl sm:text-2xl font-bold text-zinc-100 tracking-tight">
          Daily Autonomous Hunting Reports
        </h1>
        <p className="text-xs sm:text-sm text-zinc-400 mt-1 max-w-2xl">
          Audited summaries generated after each daily discovery cycle. Every single number is derived directly from live database records.
        </p>
      </div>

      {loading ? (
        <div className="py-16 text-center text-zinc-500 text-xs sm:text-sm">Loading activity reports...</div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
          {/* Left Column: Historical Reports List */}
          <div className="lg:col-span-4 space-y-2">
            <span className="text-xs font-medium text-zinc-400 uppercase tracking-wider block px-1">
              Historical Activity Reports
            </span>

            <div className="space-y-2">
              {reports.map((r) => {
                const isSelected = selectedReport?.id === r.id;
                return (
                  <div
                    key={r.id}
                    onClick={() => setSelectedReport(r)}
                    className={`p-3.5 rounded-lg border cursor-pointer transition-colors ${
                      isSelected
                        ? 'bg-zinc-800/90 border-zinc-600'
                        : 'bg-zinc-900/40 border-zinc-800 hover:border-zinc-700'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-2">
                        <Calendar className="w-3.5 h-3.5 text-zinc-400" />
                        <span className="text-xs sm:text-sm font-semibold text-zinc-100 font-mono">{r.report_date}</span>
                      </div>
                      <span className="text-xs font-mono font-medium text-zinc-400">
                        {r.new_found} found
                      </span>
                    </div>

                    <div className="grid grid-cols-3 gap-2 mt-2.5 pt-2 border-t border-zinc-800/80 text-[10px] text-zinc-400 font-mono text-center">
                      <div>
                        <span className="text-emerald-400 font-medium block">{r.eligible_count}</span>
                        <span>Eligible</span>
                      </div>
                      <div>
                        <span className="text-zinc-200 font-medium block">{r.prepared_count}</span>
                        <span>Prepared</span>
                      </div>
                      <div>
                        <span className="text-zinc-300 font-medium block">{r.submitted_count}</span>
                        <span>Submitted</span>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Right Column: Active Report Viewer */}
          {selectedReport && (
            <div className="lg:col-span-8 rounded-xl bg-zinc-900/40 border border-zinc-800 p-4 sm:p-6 space-y-5">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3.5 border-b border-zinc-800">
                <div>
                  <h2 className="text-sm sm:text-base font-semibold text-zinc-100">Daily Report: {selectedReport.report_date}</h2>
                  <p className="text-xs text-zinc-400">
                    Generated {new Date(selectedReport.created_at).toLocaleString()}
                  </p>
                </div>
                <div className="inline-flex items-center space-x-1.5 px-2.5 py-0.5 rounded text-xs font-mono bg-zinc-800 text-zinc-300 border border-zinc-700/60">
                  <CheckCircle2 className="w-3 h-3 text-emerald-400" />
                  <span>Database Verified</span>
                </div>
              </div>

              {/* Metrics Grid */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 text-xs">
                <div className="p-3 rounded-lg bg-zinc-900 border border-zinc-800">
                  <span className="text-zinc-400 block mb-1">New Today</span>
                  <span className="text-lg sm:text-xl font-semibold font-mono text-zinc-100">{selectedReport.new_found}</span>
                </div>
                <div className="p-3 rounded-lg bg-zinc-900 border border-zinc-800">
                  <span className="text-zinc-400 block mb-1">Eligible (PASS)</span>
                  <span className="text-lg sm:text-xl font-semibold font-mono text-emerald-400">
                    {selectedReport.eligible_count}
                  </span>
                </div>
                <div className="p-3 rounded-lg bg-zinc-900 border border-zinc-800">
                  <span className="text-zinc-400 block mb-1">Prepared</span>
                  <span className="text-lg sm:text-xl font-semibold font-mono text-zinc-200">
                    {selectedReport.prepared_count}
                  </span>
                </div>
                <div className="p-3 rounded-lg bg-zinc-900 border border-zinc-800">
                  <span className="text-zinc-400 block mb-1">Submitted</span>
                  <span className="text-lg sm:text-xl font-semibold font-mono text-zinc-300">
                    {selectedReport.submitted_count}
                  </span>
                </div>
              </div>

              {/* Formatted Markdown Report View */}
              <div className="space-y-1.5">
                <span className="text-xs font-medium text-zinc-300 block">Executive Summary Document</span>
                <div className="p-4 rounded-lg bg-zinc-950 border border-zinc-800 font-mono text-xs text-zinc-300 whitespace-pre-wrap leading-relaxed max-h-80 overflow-y-auto">
                  {selectedReport.summary_markdown}
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
