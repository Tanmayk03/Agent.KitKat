import React, { useState, useEffect } from 'react';
import {
  FileText,
  Upload,
  CheckCircle2,
  Trash2,
  Sparkles,
  ShieldCheck,
  Check,
  AlertCircle,
  FileCheck,
} from 'lucide-react';
import { api } from '../services/api';

export default function ResumesPage({ onResumeChanged }) {
  const [resumes, setResumes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [selectedResume, setSelectedResume] = useState(null);

  const fetchResumes = async () => {
    try {
      setLoading(true);
      const data = await api.getResumes();
      setResumes(data);
      const active = data.find((r) => r.is_active);
      if (active) setSelectedResume(active);
      else if (data.length > 0) setSelectedResume(data[0]);
    } catch (err) {
      console.error('Failed to load resumes:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchResumes();
  }, []);

  const handleFileUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    try {
      setUploading(true);
      const result = await api.uploadResume(file);
      await fetchResumes();
      if (onResumeChanged) onResumeChanged();
      alert(`Resume uploaded successfully! Verified ${result.verified_skills_count} skills.`);
    } catch (err) {
      alert(`Upload failed: ${err.message}`);
    } finally {
      setUploading(false);
    }
  };

  const handleActivate = async (id) => {
    try {
      await api.activateResume(id);
      await fetchResumes();
      if (onResumeChanged) onResumeChanged();
    } catch (err) {
      alert(`Could not activate resume: ${err.message}`);
    }
  };

  const handleDelete = async (id) => {
    if (!confirm('Are you sure you want to delete this resume?')) return;
    try {
      await api.deleteResume(id);
      await fetchResumes();
      if (onResumeChanged) onResumeChanged();
    } catch (err) {
      alert(`Could not delete resume: ${err.message}`);
    }
  };

  return (
    <div className="space-y-6 pb-16">
      {/* Header */}
      <div>
        <div className="inline-flex items-center space-x-2 px-3 py-1 rounded-full text-xs font-mono bg-amber-500/10 border border-amber-500/20 text-amber-300 mb-2">
          <span>Candidate Resume Repository</span>
        </div>
        <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
          Manage Resumes & Verification
        </h1>
        <p className="text-sm text-slate-400">
          Upload your latest PDF or DOCX resume. Agent KitKat parses qualifications and uses it as the source of truth for skill verification and tailoring.
        </p>
      </div>

      {/* Upload Box */}
      <div className="rounded-2xl bg-slate-900/90 border border-slate-800 p-6 shadow-xl space-y-4">
        <h2 className="text-base font-bold text-white flex items-center space-x-2">
          <Upload className="w-4 h-4 text-amber-400" />
          <span>Upload New Resume</span>
        </h2>

        <div className="border-2 border-dashed border-slate-700 hover:border-amber-500/50 rounded-2xl p-6 text-center transition-colors">
          <input
            type="file"
            accept=".pdf,.docx"
            onChange={handleFileUpload}
            disabled={uploading}
            className="hidden"
            id="resume-file-input"
          />
          <label htmlFor="resume-file-input" className="cursor-pointer space-y-2 flex flex-col items-center">
            <Upload className={`w-8 h-8 text-amber-400 ${uploading ? 'animate-bounce' : ''}`} />
            <span className="text-sm font-medium text-slate-200">
              {uploading ? 'Parsing and Verifying Skills...' : 'Click to browse or drop your PDF / DOCX resume'}
            </span>
            <span className="text-xs text-slate-500">Supports standard ATS PDF and Word documents up to 15MB</span>
          </label>
        </div>
      </div>

      {/* Resumes List & Preview */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left Column: List */}
        <div className="lg:col-span-5 space-y-3">
          <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider block px-1">
            Uploaded Resumes ({resumes.length})
          </span>

          {loading ? (
            <div className="py-8 text-center text-slate-500 text-xs">Loading resumes...</div>
          ) : resumes.length === 0 ? (
            <div className="p-8 rounded-xl bg-slate-900 border border-slate-800 text-center text-xs text-slate-500">
              No resumes uploaded yet. Upload your B.Tech resume above.
            </div>
          ) : (
            resumes.map((r) => {
              const isSelected = selectedResume?.id === r.id;
              return (
                <div
                  key={r.id}
                  onClick={() => setSelectedResume(r)}
                  className={`p-4 rounded-xl border cursor-pointer transition-all ${
                    isSelected
                      ? 'bg-amber-500/10 border-amber-500/50 shadow-md shadow-amber-500/5'
                      : 'bg-slate-900 border-slate-800 hover:border-slate-700'
                  }`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex items-center space-x-2">
                      <FileCheck className="w-5 h-5 text-amber-400 flex-shrink-0" />
                      <div>
                        <h3 className="text-sm font-bold text-white truncate max-w-[200px]">
                          {r.file_name}
                        </h3>
                        <div className="text-[11px] text-slate-400 font-mono">
                          {(r.file_size_bytes / 1024).toFixed(1)} KB • {r.file_type.toUpperCase()}
                        </div>
                      </div>
                    </div>

                    {r.is_active && (
                      <span className="px-2 py-0.5 rounded-full text-[10px] font-mono font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                        ACTIVE
                      </span>
                    )}
                  </div>

                  <div className="flex items-center justify-between mt-3 pt-2.5 border-t border-slate-800/80 text-xs">
                    <span className="text-slate-400 font-mono text-[11px]">
                      {r.extracted_skills_count} skills extracted
                    </span>

                    <div className="flex items-center space-x-2">
                      {!r.is_active && (
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleActivate(r.id);
                          }}
                          className="px-2.5 py-1 rounded-md text-[11px] font-semibold bg-amber-500/15 hover:bg-amber-500/25 text-amber-300 border border-amber-500/30 transition-all"
                        >
                          Make Active
                        </button>
                      )}
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDelete(r.id);
                        }}
                        className="p-1 text-slate-500 hover:text-rose-400 transition-colors"
                        title="Delete resume"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Right Column: Structured Data Inspector */}
        {selectedResume && (
          <div className="lg:col-span-7 rounded-2xl bg-slate-900/90 border border-slate-800 p-6 space-y-5 shadow-xl">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <div>
                <h3 className="text-base font-bold text-white">{selectedResume.file_name}</h3>
                <p className="text-xs text-slate-400">
                  Uploaded {new Date(selectedResume.uploaded_at).toLocaleDateString()}
                </p>
              </div>
              {selectedResume.is_active && (
                <span className="flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-mono font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  <span>Primary Ground Truth</span>
                </span>
              )}
            </div>

            {/* Extracted Skills */}
            <div className="space-y-2">
              <span className="text-xs font-semibold text-slate-300 block">
                Extracted Skills ({selectedResume.structured_data?.extracted_skills?.length || 0})
              </span>
              <div className="flex flex-wrap gap-1.5">
                {selectedResume.structured_data?.extracted_skills?.map((s, idx) => (
                  <span
                    key={idx}
                    className="px-2.5 py-1 rounded-md text-xs font-mono bg-slate-800 text-slate-200 border border-slate-700"
                  >
                    {s}
                  </span>
                ))}
              </div>
            </div>

            {/* Structured Sections Preview */}
            <div className="space-y-3 pt-2">
              <span className="text-xs font-semibold text-slate-300 block">Structured Resume Text Preview</span>
              <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 font-mono text-xs text-slate-300 whitespace-pre-wrap leading-relaxed max-h-80 overflow-y-auto">
                {selectedResume.raw_text || 'No text extracted.'}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
