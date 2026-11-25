import React, { useEffect, useState } from 'react';
import { Building2, Plus, Trash2 } from 'lucide-react';
import { api } from '../services/api';

/**
 * Follow companies' public career boards. Paste the careers URL, e.g.
 *   https://boards.greenhouse.io/<company>, https://jobs.lever.co/<company>, https://jobs.ashbyhq.com/<company>
 * Each followed board becomes its own discovery source (with its own health row).
 */
export default function CareerBoardsCard() {
  const [boards, setBoards] = useState([]);
  const [url, setUrl] = useState('');
  const [company, setCompany] = useState('');
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.getCareerBoards().then(setBoards).catch((e) => setError(e.message));
  }, []);

  const add = async (e) => {
    e.preventDefault();
    if (!url.trim()) return;
    try {
      setBusy(true);
      setError(null);
      setBoards(await api.addCareerBoard(url.trim(), company.trim()));
      setUrl('');
      setCompany('');
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const remove = async (b) => {
    if (!window.confirm(`Stop following ${b.company}? Jobs already stored are kept.`)) return;
    try {
      setBoards(await api.removeCareerBoard(b.ats, b.token));
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <div className="rounded-xl bg-zinc-900/40 border border-zinc-800 p-4 sm:p-6 space-y-3.5">
      <h2 className="text-sm font-semibold text-zinc-100 flex items-center space-x-2">
        <Building2 className="w-4 h-4 text-zinc-400" />
        <span>Company Career Boards</span>
      </h2>
      <p className="text-xs text-zinc-400">
        Follow companies that post on Greenhouse, Lever or Ashby. Agent KitKat reads their official public job-board
        APIs, keeps intern / fresher tech roles in India or open-remote, and notices when a job is taken down.
      </p>

      <form onSubmit={add} className="flex flex-col sm:flex-row gap-2">
        <input
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://jobs.lever.co/company"
          aria-label="Careers page URL"
          className="flex-1 px-3 py-2 rounded-md bg-zinc-950 border border-zinc-800 text-xs text-zinc-100 placeholder-zinc-600"
        />
        <input
          value={company}
          onChange={(e) => setCompany(e.target.value)}
          placeholder="Company name (optional)"
          aria-label="Company name"
          className="sm:w-48 px-3 py-2 rounded-md bg-zinc-950 border border-zinc-800 text-xs text-zinc-100 placeholder-zinc-600"
        />
        <button
          type="submit"
          disabled={busy || !url.trim()}
          className="px-3 py-2 rounded-md text-xs font-medium bg-zinc-100 hover:bg-zinc-200 text-zinc-950 disabled:opacity-50 flex items-center justify-center gap-1.5"
        >
          <Plus className="w-3.5 h-3.5" /> Follow
        </button>
      </form>
      {error && <p className="text-xs text-red-300">{error}</p>}

      {boards.length === 0 ? (
        <p className="text-xs text-zinc-500">Not following any company boards yet.</p>
      ) : (
        <ul className="divide-y divide-zinc-800/60">
          {boards.map((b) => (
            <li key={`${b.ats}:${b.token}`} className="py-2 flex items-center justify-between text-xs">
              <span className="text-zinc-200">
                {b.company} <span className="font-mono text-zinc-500">({b.ats}:{b.token})</span>
              </span>
              <button onClick={() => remove(b)} className="p-1 rounded text-zinc-500 hover:text-red-300 hover:bg-zinc-800" title="Stop following">
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
