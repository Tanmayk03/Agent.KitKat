import React, { useEffect, useState } from 'react';
import { AlertTriangle, CheckCircle2, Info, XCircle } from 'lucide-react';
import { api } from '../services/api';

const ICONS = {
  error: <XCircle className="w-3.5 h-3.5 text-red-400 shrink-0 mt-0.5" />,
  warning: <AlertTriangle className="w-3.5 h-3.5 text-amber-400 shrink-0 mt-0.5" />,
  info: <Info className="w-3.5 h-3.5 text-zinc-400 shrink-0 mt-0.5" />,
};

/** Missing / inconsistent profile facts (incl. CGPA vs active resume). Re-checks when refreshKey changes. */
export default function ProfileHealthCard({ refreshKey = 0 }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    api.getProfileCompleteness().then(setData).catch((e) => setError(e.message));
  }, [refreshKey]);

  if (error) return <div className="text-xs text-red-300">Could not check profile: {error}</div>;
  if (!data) return null;
  if (data.warnings.length === 0) {
    return (
      <div className="rounded-xl bg-emerald-950/20 border border-emerald-900/40 p-4 text-xs text-emerald-300 flex items-center gap-2">
        <CheckCircle2 className="w-4 h-4" /> Profile complete and consistent with your active resume.
      </div>
    );
  }
  return (
    <div className="rounded-xl bg-zinc-900/40 border border-zinc-800 p-4 sm:p-5 space-y-2.5">
      <h2 className="text-sm font-semibold text-zinc-100">
        Profile check: {data.error_count ? `${data.error_count} problem(s) to fix` : 'a few things to add'}
      </h2>
      <ul className="space-y-1.5">
        {data.warnings.map((w, i) => (
          <li key={i} className="flex items-start gap-2 text-xs text-zinc-300">
            {ICONS[w.severity] || ICONS.info}
            <span>{w.message}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
