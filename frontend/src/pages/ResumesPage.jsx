import React, { useState, useEffect } from 'react';
import {
  Upload,
  CheckCircle2,
  Trash2,
  FileCheck,
} from 'lucide-react';
import { api } from '../services/api';
import ResumeImportModal from '../components/ResumeImportModal';

export default function ResumesPage({ onResumeChanged, onProfileUpdated }) {
  const [importing, setImporting] = useState(null);
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
    <div className="space-y-6">
      {/* Header */}
      <div>
        <div className="inline-flex items-center space-x-1.5 px-2.5 py-0.5 rounded-md text-xs font-mono bg-zinc-900 border border-zinc-800 text-zinc-400 mb-2">
          <span>Candidate Resume Repository</span>
        </div>
        <h1 className="text-xl sm:text-2xl font-bold text-zinc-100 tracking-tight">
          Manage Resumes & Verification
        </h1>
        <p className="text-xs sm:text-sm text-zinc-400 mt-1 max-w-2xl">
          Upload your latest PDF or DOCX resume. Agent KitKat parses qualifications and uses it as the source of truth for skill verification and tailoring.
        </p>
      </div>

      {/* Upload Box */}
      <div className="rounded-xl bg-zinc-900/40 border border-zinc-800 p-4 sm:p-6 space-y-3">
        <h2 className="text-sm font-semibold text-zinc-100 flex items-center space-x-2">
          <Upload className="w-4 h-4 text-zinc-400" />
          <span>Upload New Resume</span>
        </h2>

        <div className="border border-dashed border-zinc-700 hover:border-zinc-500 rounded-xl p-6 text-center transition-colors">
          <input
            type="file"
            accept=".pdf,.docx"
            onChange={handleFileUpload}
            disabled={uploading}
            className="hidden"
            id="resume-file-input"
          />
          <label htmlFor="resume-file-input" className="cursor-pointer space-y-2 flex flex-col items-center">
            <Upload className={`w-6 h-6 text-zinc-400 ${uploading ? 'animate-bounce' : ''}`} />
            <span className="text-xs sm:text-sm font-medium text-zinc-200">
              {uploading ? 'Parsing and Verifying Skills...' : 'Click to browse or drop your PDF / DOCX resume'}
            </span>
            <span className="text-[11px] text-zinc-500">Supports standard ATS PDF and Word documents up to 15MB</span>
          </label>
        </div>
      </div>

      {/* Resumes List & Preview */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
        {/* Left Column: List */}
        <div className="lg:col-span-5 space-y-2">
          <span className="text-xs font-medium text-zinc-400 uppercase tracking-wider block px-1">
            Uploaded Resumes ({resumes.length})
          </span>

          {loading ? (
            <div className="py-8 text-center text-zinc-500 text-xs">Loading resumes...</div>
          ) : resumes.length === 0 ? (
            <div className="p-8 rounded-xl bg-zinc-900/40 border border-zinc-800 text-center text-xs text-zinc-500">
              No resumes uploaded yet. Upload your B.Tech resume above.
            </div>
          ) : (
            resumes.map((r) => {
              const isSelected = selectedResume?.id === r.id;
              return (
                <div
                  key={r.id}
                  onClick={() => setSelectedResume(r)}
                  className={`p-3.5 rounded-lg border cursor-pointer transition-colors ${
                    isSelected
                      ? 'bg-zinc-800/90 border-zinc-600'
                      : 'bg-zinc-900/40 border-zinc-800 hover:border-zinc-700'
                  }`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex items-center space-x-2.5">
                      <FileCheck className="w-4 h-4 text-zinc-400 flex-shrink-0" />
                      <div>
                        <h3 className="text-xs sm:text-sm font-semibold text-zinc-100 truncate max-w-[180px] sm:max-w-[220px]">
                          {r.file_name}
                        </h3>
                        <div className="text-[11px] text-zinc-500 font-mono">
                          {(r.file_size_bytes / 1024).toFixed(1)} KB &bull; {r.file_type.toUpperCase()}
                        </div>
                      </div>
                    </div>

                    {r.is_active && (
                      <span className="px-2 py-0.5 rounded text-[10px] font-mono font-medium bg-emerald-950/40 text-emerald-400 border border-emerald-800/40">
                        ACTIVE
                      </span>
                    )}
                  </div>

                  <div className="flex items-center justify-between mt-2.5 pt-2 border-t border-zinc-800/80 text-xs">
                    <span className="text-zinc-400 font-mono text-[11px]">
                      {r.extracted_skills_count} skills extracted
                    </span>

                    <div className="flex items-center space-x-2">
                      {!r.is_active && (
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleActivate(r.id);
                          }}
                          className="px-2 py-0.5 rounded text-[11px] font-medium bg-zinc-800 hover:bg-zinc-700 text-zinc-300 border border-zinc-700/60 transition-colors"
                        >
                          Make Active
                        </button>
                      )}
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setImporting(r);
                        }}
                        className="px-2 py-0.5 rounded text-[11px] font-medium bg-zinc-800 hover:bg-zinc-700 text-zinc-300 border border-zinc-700/60 transition-colors"
                        title="Copy details from this resume into your profile (you review each field)"
                      >
                        Import to profile
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDelete(r.id);
                        }}
                        className="p-1 text-zinc-500 hover:text-red-400 transition-colors"
                        title="Delete resume"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
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
          <div className="lg:col-span-7 rounded-xl bg-zinc-900/40 border border-zinc-800 p-4 sm:p-6 space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-zinc-800">
              <div>
                <h3 className="text-sm sm:text-base font-semibold text-zinc-100">{selectedResume.file_name}</h3>
                <p className="text-xs text-zinc-400">
                  Uploaded {new Date(selectedResume.uploaded_at).toLocaleDateString()}
                </p>
              </div>
              {selectedResume.is_active && (
                <span className="flex items-center space-x-1.5 px-2.5 py-0.5 rounded text-xs font-mono font-medium bg-emerald-950/40 text-emerald-400 border border-emerald-800/40">
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  <span>Primary Ground Truth</span>
                </span>
              )}
            </div>

            {/* Extracted Skills */}
            <div className="space-y-1.5">
              <span className="text-xs font-medium text-zinc-300 block">
                Extracted Skills ({selectedResume.structured_data?.extracted_skills?.length || 0})
              </span>
              <div className="flex flex-wrap gap-1.5">
                {selectedResume.structured_data?.extracted_skills?.map((s, idx) => (
                  <span
                    key={idx}
                    className="px-2 py-0.5 rounded text-xs font-mono bg-zinc-800 text-zinc-200 border border-zinc-700/50"
                  >
                    {s}
                  </span>
                ))}
              </div>
            </div>

            {/* Structured Sections Preview */}
            <div className="space-y-1.5 pt-1">
              <span className="text-xs font-medium text-zinc-300 block">Structured Resume Text</span>
              <div className="p-3.5 rounded-lg bg-zinc-950 border border-zinc-800 font-mono text-xs text-zinc-300 whitespace-pre-wrap leading-relaxed max-h-72 overflow-y-auto">
                {selectedResume.raw_text || 'No text extracted.'}
              </div>
            </div>
          </div>
        )}
      </div>
      {importing && (
        <ResumeImportModal
          resume={importing}
          onClose={() => setImporting(null)}
          onApplied={(profile) => onProfileUpdated?.(profile)}
        />
      )}
    </div>
  );
}
