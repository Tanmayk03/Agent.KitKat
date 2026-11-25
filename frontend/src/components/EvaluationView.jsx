import React from 'react';
import { Shield, CheckCircle2 } from 'lucide-react';

const STATUS_STYLE = {
  PASS: 'bg-emerald-950/40 text-emerald-400 border-emerald-800/40',
  FAIL: 'bg-red-950/40 text-red-400 border-red-800/40',
  UNKNOWN: 'bg-amber-950/30 text-amber-300 border-amber-800/40',
};
const PROVENANCE = {
  explicit: 'stated in posting',
  inferred: 'from listing / title',
  missing: 'not stated',
};
const FACTORS = [
  ['technical_skills', 'Skills', 35],
  ['education_and_graduation', 'Education & graduation', 20],
  ['projects_and_experience', 'Projects & experience', 20],
  ['role_relevance', 'Role relevance', 15],
  ['location', 'Location', 10],
];

function Badge({ status }) {
  return (
    <span className={`px-2 py-0.5 rounded text-[11px] font-mono font-semibold uppercase border ${STATUS_STYLE[status] || STATUS_STYLE.UNKNOWN}`}>
      {status}
    </span>
  );
}

/** Eligibility (all checks with evidence) + explainable match score for one job. */
export default function EvaluationView({ evaluation }) {
  if (!evaluation) return null;
  const el = evaluation.eligibility || {};
  const checks = el.checks && Object.keys(el.checks).length
    ? Object.entries(el.checks)
    : ['degree', 'graduation', 'cgpa', 'location', 'work_mode', 'experience_level']
        .filter((k) => el[k])
        .map((k) => [k, el[k]]);
  const na = new Set(evaluation.na_factors || []);

  return (
    <div className="space-y-3">
      {evaluation.next_action && (
        <div className="rounded-lg border border-zinc-700/60 bg-zinc-900/70 px-4 py-2.5 text-xs text-zinc-200">
          <span className="text-zinc-400">Next step: </span>
          {evaluation.next_action}
        </div>
      )}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3 sm:gap-4">
        {/* Eligibility */}
        <div className="rounded-xl bg-zinc-900/60 border border-zinc-800 p-4 sm:p-5">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <Shield className="w-4 h-4 text-zinc-400" />
              <span className="font-semibold text-xs sm:text-sm text-zinc-200">Eligibility</span>
            </div>
            <Badge status={el.overall_status} />
          </div>
          <ul className="mt-3 divide-y divide-zinc-800/60">
            {checks.map(([key, c]) => (
              <li key={key} className="py-2 text-xs">
                <div className="flex items-start justify-between gap-3">
                  <span className="text-zinc-300">
                    {c.label || key}
                    {c.hard === false && <span className="text-zinc-500"> (advisory)</span>}
                  </span>
                  <Badge status={c.status} />
                </div>
                <p className="text-zinc-400 mt-0.5">{c.details}</p>
                {(c.evidence || c.provenance) && (
                  <p className="text-[10px] text-zinc-500 mt-0.5">
                    {c.provenance && <span className="uppercase tracking-wide">{PROVENANCE[c.provenance] || c.provenance}</span>}
                    {c.evidence && <span className="italic"> · “{c.evidence}”</span>}
                  </p>
                )}
              </li>
            ))}
          </ul>
        </div>

        {/* Match score */}
        <div className="rounded-xl bg-zinc-900/60 border border-zinc-800 p-4 sm:p-5 space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2 text-zinc-200 text-xs sm:text-sm font-semibold">
              <CheckCircle2 className="w-4 h-4 text-zinc-400" />
              <span>Match score</span>
            </div>
            <span className="text-2xl font-bold text-zinc-100 font-mono">{evaluation.overall_score}%</span>
          </div>
          {FACTORS.map(([key, label, weight]) => {
            const val = evaluation.category_scores?.[key] ?? 0;
            const isNa = na.has(key);
            return (
              <div key={key} className="space-y-1 text-xs">
                <div className="flex justify-between text-zinc-400">
                  <span>{label} ({weight}%)</span>
                  <span className="font-mono text-zinc-200">{isNa ? 'N/A' : `${val} / ${weight}`}</span>
                </div>
                <div className="w-full bg-zinc-800 rounded-full h-1.5 overflow-hidden">
                  <div className="bg-zinc-200 h-full rounded-full" style={{ width: isNa ? '0%' : `${(val / weight) * 100}%` }} />
                </div>
                {evaluation.factor_explanations?.[key] && (
                  <p className="text-[10px] text-zinc-500">{evaluation.factor_explanations[key]}</p>
                )}
              </div>
            );
          })}
          {na.size > 0 && <p className="text-[10px] text-zinc-500">N/A factors are excluded and the rest rescaled to 100.</p>}
          <div className="grid grid-cols-2 gap-2 pt-1 text-[11px]">
            <div>
              <span className="text-zinc-500 block">Matching skills</span>
              <span className="text-emerald-300">{(evaluation.matching_skills || []).join(', ') || '—'}</span>
            </div>
            <div>
              <span className="text-zinc-500 block">Missing skills</span>
              <span className="text-amber-300">{(evaluation.missing_skills || []).join(', ') || '—'}</span>
            </div>
          </div>
          {evaluation.relevant_projects?.length > 0 && (
            <div className="text-[11px]">
              <span className="text-zinc-500 block">Relevant projects / experience</span>
              <span className="text-zinc-300">{evaluation.relevant_projects.join(' · ')}</span>
            </div>
          )}
          <div className="pt-1 flex items-center justify-between text-xs border-t border-zinc-800">
            <span className="text-zinc-400 pt-2">Recommendation</span>
            <span className="font-mono font-medium text-zinc-200 pt-2">{evaluation.recommendation}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
