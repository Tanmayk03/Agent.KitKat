import React, { useState, useEffect } from 'react';
import {
  BarChart3,
  Calendar,
  FileText,
  CheckCircle2,
  AlertCircle,
  Briefcase,
  Send,
  Clock,
  TrendingUp,
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
    <div className="space-y-6 pb-16">
      {/* Header */}
      <div>
        <div className="inline-flex items-center space-x-2 px-3 py-1 rounded-full text-xs font-mono bg-amber-500/10 border border-amber-500/20 text-amber-300 mb-2">
          <span>Continuous Career Intelligence</span>
        </div>
        <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
          Daily Autonomous Hunting Reports
        </h1>
        <p className="text-sm text-slate-400">
          Audited summaries generated after each daily discovery cycle. Every single number is derived directly from live database tables.
        </p>
      </div>

      {loading ? (
        <div className="py-16 text-center text-slate-400 text-sm">Loading activity reports...</div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          {/* Left Column: Historical Reports List */}
          <div className="lg:col-span-4 space-y-3">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider block px-1">
              Historical Activity Reports
            </span>

            <div className="space-y-2">
              {reports.map((r) => {
                const isSelected = selectedReport?.id === r.id;
                return (
                  <div
                    key={r.id}
                    onClick={() => setSelectedReport(r)}
                    className={`p-4 rounded-xl border cursor-pointer transition-all ${
                      isSelected
                        ? 'bg-amber-500/10 border-amber-500/50 shadow-md shadow-amber-500/5'
                        : 'bg-slate-900 border-slate-800 hover:border-slate-700'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-2">
                        <Calendar className="w-4 h-4 text-amber-400" />
                        <span className="text-sm font-bold text-white font-mono">{r.report_date}</span>
                      </div>
                      <span className="text-xs font-mono font-semibold text-slate-400">
                        {r.new_found} found
                      </span>
                    </div>

                    <div className="grid grid-cols-3 gap-2 mt-3 pt-2.5 border-t border-slate-800/80 text-[10px] text-slate-400 font-mono text-center">
                      <div>
                        <span className="text-emerald-400 font-bold block">{r.eligible_count}</span>
                        <span>Eligible</span>
                      </div>
                      <div>
                        <span className="text-purple-400 font-bold block">{r.prepared_count}</span>
                        <span>Prepared</span>
                      </div>
                      <div>
                        <span className="text-sky-400 font-bold block">{r.submitted_count}</span>
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
            <div className="lg:col-span-8 rounded-2xl bg-slate-900/90 border border-slate-800 p-6 space-y-6 shadow-xl">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-slate-800">
                <div>
                  <h2 className="text-lg font-bold text-white">Daily Report: {selectedReport.report_date}</h2>
                  <p className="text-xs text-slate-400">
                    Generated {new Date(selectedReport.created_at).toLocaleString()}
                  </p>
                </div>
                <div className="inline-flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-mono bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  <span>Real Database Verified</span>
                </div>
              </div>

              {/* Metrics Grid */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
                <div className="p-3 rounded-xl bg-slate-800/50 border border-slate-800">
                  <span className="text-slate-400 block mb-1">New Today</span>
                  <span className="text-xl font-bold font-mono text-white">{selectedReport.new_found}</span>
                </div>
                <div className="p-3 rounded-xl bg-slate-800/50 border border-slate-800">
                  <span className="text-slate-400 block mb-1">Eligible (PASS)</span>
                  <span className="text-xl font-bold font-mono text-emerald-400">
                    {selectedReport.eligible_count}
                  </span>
                </div>
                <div className="p-3 rounded-xl bg-slate-800/50 border border-slate-800">
                  <span className="text-slate-400 block mb-1">Prepared</span>
                  <span className="text-xl font-bold font-mono text-amber-400">
                    {selectedReport.prepared_count}
                  </span>
                </div>
                <div className="p-3 rounded-xl bg-slate-800/50 border border-slate-800">
                  <span className="text-slate-400 block mb-1">Submitted</span>
                  <span className="text-xl font-bold font-mono text-purple-400">
                    {selectedReport.submitted_count}
                  </span>
                </div>
              </div>

              {/* Formatted Markdown Report View */}
              <div className="space-y-2">
                <span className="text-xs font-semibold text-slate-300 block">Executive Summary Document</span>
                <div className="p-5 rounded-xl bg-slate-950 border border-slate-800 font-mono text-xs text-slate-300 whitespace-pre-wrap leading-relaxed max-h-96 overflow-y-auto">
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
