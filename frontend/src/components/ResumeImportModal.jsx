import React, { useEffect, useState } from 'react';
import { X } from 'lucide-react';
import { api } from '../services/api';

function show(value) {
  if (value === null || value === undefined || value === '') return <span className="text-zinc-600">empty</span>;
  if (Array.isArray(value)) {
    if (value.length && typeof value[0] === 'object') return value.map((p) => p.name).join(', ');
    return value.join(', ');
  }
  return String(value);
}

/**
 * Review what your resume says next to what your profile says, tick what to copy, apply.
 * Nothing is applied without your selection; values are recomputed server-side from the resume.
 */
export default function ResumeImportModal({ resume, onClose, onApplied }) {
  const [rows, setRows] = useState(null);
  const [selected, setSelected] = useState({});
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api
      .getResumeSuggestions(resume.id)
      .then((data) => {
        setRows(data);
        // pre-select only fields where the profile is empty and the resume has a value
        const pre = {};
        data.forEach((r) => {
          const empty = r.current === null || r.current === undefined || r.current === '' || (Array.isArray(r.current) && r.current.length === 0);
          pre[r.field] = r.differs && (empty || r.field === 'verified_skills');
        });
        setSelected(pre);
      })
      .catch((e) => setError(e.message));
  }, [resume.id]);

  const apply = async () => {
    const fields = Object.keys(selected).filter((k) => selected[k]);
    if (!fields.length) return onClose();
    try {
      setBusy(true);
      const profile = await api.applyResumeSuggestions(resume.id, fields);
      onApplied?.(profile);
      onClose();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-zinc-950/80 backdrop-blur-sm p-3" role="dialog" aria-modal="true">
      <div className="w-full max-w-4xl max-h-[90vh] overflow-y-auto bg-zinc-900 border border-zinc-800 rounded-xl">
        <div className="p-4 border-b border-zinc-800 flex items-center justify-between">
          <div>
            <h2 className="text-sm font-semibold text-zinc-100">Import from {resume.file_name}</h2>
            <p className="text-xs text-zinc-400">Each value is shown with the resume line it came from. Tick what should go into your profile.</p>
          </div>
          <button onClick={onClose} className="p-1 rounded text-zinc-400 hover:text-zinc-100" aria-label="Close">
            <X className="w-4 h-4" />
          </button>
        </div>
        {error && <p className="p-4 text-xs text-red-300">{error}</p>}
        {!rows && !error && <p className="p-4 text-xs text-zinc-500">Reading resume…</p>}
        {rows && rows.length === 0 && <p className="p-4 text-xs text-zinc-500">No recognisable profile details found in this resume.</p>}
        {rows && rows.length > 0 && (
          <table className="w-full text-xs">
            <thead>
              <tr className="text-left text-zinc-500 border-b border-zinc-800">
                <th className="p-2 w-8" />
                <th className="p-2">Field</th>
                <th className="p-2">Profile now</th>
                <th className="p-2">From resume</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800/60">
              {rows.map((r) => (
                <tr key={r.field} className="align-top">
                  <td className="p-2">
                    <input
                      type="checkbox"
                      aria-label={`Apply ${r.label}`}
                      checked={!!selected[r.field]}
                      disabled={!r.differs}
                      onChange={(e) => setSelected({ ...selected, [r.field]: e.target.checked })}
                    />
                  </td>
                  <td className="p-2 text-zinc-300 whitespace-nowrap">{r.label}</td>
                  <td className="p-2 text-zinc-400 max-w-[14rem] break-words">{show(r.current)}</td>
                  <td className="p-2">
                    <div className={r.differs ? 'text-zinc-100' : 'text-zinc-500'}>{show(r.suggested)}</div>
                    {r.note && <div className="text-[10px] text-amber-300/90 mt-0.5">{r.note}</div>}
                    {r.evidence && <div className="text-[10px] text-zinc-500 mt-0.5 italic">“{r.evidence}”</div>}
                    {!r.differs && <div className="text-[10px] text-zinc-600">Same as profile</div>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <div className="p-4 border-t border-zinc-800 flex justify-end gap-2">
          <button onClick={onClose} className="px-3 py-1.5 rounded-md text-xs bg-zinc-800 text-zinc-200">Cancel</button>
          <button
            onClick={apply}
            disabled={busy || !rows}
            className="px-3 py-1.5 rounded-md text-xs font-medium bg-zinc-100 text-zinc-950 disabled:opacity-50"
          >
            {busy ? 'Applying…' : 'Apply selected'}
          </button>
        </div>
      </div>
    </div>
  );
}
