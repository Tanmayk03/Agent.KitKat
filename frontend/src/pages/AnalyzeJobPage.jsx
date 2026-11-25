import React, { useState } from 'react';
import {
  Link,
  FileText,
  Upload,
  CheckCircle2,
  XCircle,
  Shield,
  Copy,
  Check,
  ArrowRight,
} from 'lucide-react';
import { api } from '../services/api';
import EvaluationView from '../components/EvaluationView';

export default function AnalyzeJobPage({ onNavigateTab }) {
  const [activeMode, setActiveMode] = useState('url'); // 'url', 'text', 'file'
  const [urlInput, setUrlInput] = useState('');
  const [textInput, setTextInput] = useState('');
  const [titleInput, setTitleInput] = useState('');
  const [companyInput, setCompanyInput] = useState('');
  const [selectedFile, setSelectedFile] = useState(null);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [analysisResult, setAnalysisResult] = useState(null);
  const [evalResult, setEvalResult] = useState(null);
  const [draftResult, setDraftResult] = useState(null);
  const [preparingDraft, setPreparingDraft] = useState(false);
  const [copied, setCopied] = useState(false);

  const handleAnalyze = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setAnalysisResult(null);
    setEvalResult(null);
    setDraftResult(null);

    try {
      let res;
      if (activeMode === 'url') {
        if (!urlInput.trim()) throw new Error('Please enter a valid job URL.');
        res = await api.analyzeJobUrl(urlInput.trim());
      } else if (activeMode === 'text') {
        if (!textInput.trim()) throw new Error('Please paste the job description text.');
        res = await api.analyzeJobText(textInput.trim(), titleInput.trim() || null, companyInput.trim() || null);
      } else if (activeMode === 'file') {
        if (!selectedFile) throw new Error('Please select a PDF or DOCX file to upload.');
        res = await api.analyzeJobFile(selectedFile);
      }

      setAnalysisResult(res);

      if (res && res.id && !res.requires_manual_paste) {
        const evalData = await api.evaluateJob(res.id);
        setEvalResult(evalData);
      }
    } catch (err) {
      setError(err.message || 'Failed to analyze job description.');
    } finally {
      setLoading(false);
    }
  };

  const handlePrepareDraft = async () => {
    if (!analysisResult?.id) return;
    try {
      setPreparingDraft(true);
      const draft = await api.prepareApplication(analysisResult.id);
      setDraftResult(draft);
    } catch (err) {
      setError(err.message || 'Failed to prepare application draft.');
    } finally {
      setPreparingDraft(false);
    }
  };

  const copyCoverLetter = () => {
    if (draftResult?.cover_letter) {
      navigator.clipboard.writeText(draftResult.cover_letter);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const extracted = analysisResult?.extracted;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <div className="inline-flex items-center space-x-1.5 px-2.5 py-0.5 rounded-md text-xs font-mono bg-zinc-900 border border-zinc-800 text-zinc-400 mb-2">
          <span>Mode B &bull; Targeted Opportunity Analysis</span>
        </div>
        <h1 className="text-xl sm:text-2xl font-bold text-zinc-100 tracking-tight">
          Analyze Any Job Opportunity
        </h1>
        <p className="text-xs sm:text-sm text-zinc-400 mt-1 max-w-2xl">
          Paste any LinkedIn, Naukri, or career page URL, paste raw text, or upload a JD document.
          Agent KitKat verifies graduation eligibility and calculates resume match score.
        </p>
      </div>

      {/* Input Mode Selector & Form */}
      <div className="rounded-xl bg-zinc-900/40 border border-zinc-800 p-4 sm:p-6 space-y-5">
        {/* Mode Tabs */}
        <div className="flex border-b border-zinc-800 space-x-4 sm:space-x-6 text-xs sm:text-sm">
          {[
            { id: 'url', label: 'Paste Job URL', icon: Link },
            { id: 'text', label: 'Paste Job Text', icon: FileText },
            { id: 'file', label: 'Upload JD File', icon: Upload },
          ].map((tab) => {
            const Icon = tab.icon;
            const isActive = activeMode === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => {
                  setActiveMode(tab.id);
                  setError(null);
                }}
                className={`flex items-center space-x-2 pb-2.5 border-b-2 transition-colors ${
                  isActive
                    ? 'border-zinc-200 text-zinc-100 font-medium'
                    : 'border-transparent text-zinc-500 hover:text-zinc-300'
                }`}
              >
                <Icon className="w-3.5 h-3.5" />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </div>

        {/* Form Inputs */}
        <form onSubmit={handleAnalyze} className="space-y-4">
          {activeMode === 'url' && (
            <div>
              <label className="block text-xs font-medium text-zinc-300 mb-1.5">
                Public Job Posting URL
              </label>
              <div className="flex flex-col sm:flex-row gap-2.5">
                <input
                  type="url"
                  placeholder="https://www.linkedin.com/jobs/view/... or careers page URL"
                  value={urlInput}
                  onChange={(e) => setUrlInput(e.target.value)}
                  className="flex-1 px-3.5 py-2 rounded-lg bg-zinc-900 border border-zinc-800 text-xs sm:text-sm text-zinc-100 placeholder-zinc-500 focus:outline-none focus:border-zinc-600 focus:ring-1 focus:ring-zinc-600"
                />
                <button
                  type="submit"
                  disabled={loading}
                  className="px-4 py-2 rounded-lg text-xs sm:text-sm font-medium bg-zinc-100 hover:bg-zinc-200 text-zinc-950 transition-colors disabled:opacity-50 whitespace-nowrap"
                >
                  {loading ? 'Analyzing with Local AI...' : 'Analyze URL'}
                </button>
              </div>
            </div>
          )}

          {activeMode === 'text' && (
            <div className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-zinc-300 mb-1.5">
                    Job Title (Optional)
                  </label>
                  <input
                    type="text"
                    placeholder="e.g. Software Engineer Intern"
                    value={titleInput}
                    onChange={(e) => setTitleInput(e.target.value)}
                    className="w-full px-3.5 py-2 rounded-lg bg-zinc-900 border border-zinc-800 text-xs sm:text-sm text-zinc-100 placeholder-zinc-500 focus:outline-none focus:border-zinc-600"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-zinc-300 mb-1.5">
                    Company Name (Optional)
                  </label>
                  <input
                    type="text"
                    placeholder="e.g. Acme Tech"
                    value={companyInput}
                    onChange={(e) => setCompanyInput(e.target.value)}
                    className="w-full px-3.5 py-2 rounded-lg bg-zinc-900 border border-zinc-800 text-xs sm:text-sm text-zinc-100 placeholder-zinc-500 focus:outline-none focus:border-zinc-600"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-zinc-300 mb-1.5">
                  Job Description Text
                </label>
                <textarea
                  rows={6}
                  placeholder="Paste complete job requirements here..."
                  value={textInput}
                  onChange={(e) => setTextInput(e.target.value)}
                  className="w-full px-3.5 py-2.5 rounded-lg bg-zinc-900 border border-zinc-800 text-xs font-mono text-zinc-200 placeholder-zinc-500 focus:outline-none focus:border-zinc-600"
                />
              </div>

              <button
                type="submit"
                disabled={loading}
                className="px-4 py-2 rounded-lg text-xs sm:text-sm font-medium bg-zinc-100 hover:bg-zinc-200 text-zinc-950 transition-colors disabled:opacity-50"
              >
                {loading ? 'Analyzing with Local AI...' : 'Analyze Text'}
              </button>
            </div>
          )}

          {activeMode === 'file' && (
            <div className="space-y-4">
              <label className="block text-xs font-medium text-zinc-300 mb-1.5">
                Upload Job Description (PDF or DOCX)
              </label>
              <div className="border border-dashed border-zinc-700 hover:border-zinc-500 rounded-xl p-6 text-center transition-colors">
                <input
                  type="file"
                  accept=".pdf,.docx"
                  onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
                  className="hidden"
                  id="jd-file-upload"
                />
                <label htmlFor="jd-file-upload" className="cursor-pointer space-y-2 flex flex-col items-center">
                  <Upload className="w-6 h-6 text-zinc-400" />
                  <span className="text-xs sm:text-sm font-medium text-zinc-300">
                    {selectedFile ? selectedFile.name : 'Select or drop PDF / DOCX file'}
                  </span>
                  <span className="text-[11px] text-zinc-500">Supports documents up to 10MB</span>
                </label>
              </div>

              <button
                type="submit"
                disabled={loading || !selectedFile}
                className="px-4 py-2 rounded-lg text-xs sm:text-sm font-medium bg-zinc-100 hover:bg-zinc-200 text-zinc-950 transition-colors disabled:opacity-50"
              >
                {loading ? 'Analyzing with Local AI...' : 'Analyze Document'}
              </button>
            </div>
          )}
        </form>

        {error && (
          <div className="p-3.5 rounded-lg bg-red-950/20 border border-red-900/40 text-red-300 text-xs flex items-start space-x-2.5">
            <XCircle className="w-4 h-4 flex-shrink-0 mt-0.5 text-red-400" />
            <div>
              <p className="font-medium">Analysis Notice</p>
              <p className="text-zinc-400 mt-0.5">{error}</p>
            </div>
          </div>
        )}
      </div>

      {/* Analysis Results View */}
      {analysisResult && (
        <div className="space-y-5">
          {/* Eligibility (every check with evidence) & explainable match score */}
          {evalResult && <EvaluationView evaluation={evalResult} />}

          {/* Extracted Details Breakdown */}
          {extracted && (
            <div className="rounded-xl bg-zinc-900/40 border border-zinc-800 p-4 sm:p-6 space-y-4">
              <h2 className="text-sm font-semibold text-zinc-100">Extracted Job Information</h2>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 text-xs">
                <div className="p-3 bg-zinc-900/80 border border-zinc-800 rounded-lg">
                  <span className="text-zinc-400 block mb-1">Company</span>
                  <span className="font-medium text-zinc-200 text-xs sm:text-sm">{extracted.company_name}</span>
                </div>
                <div className="p-3 bg-zinc-900/80 border border-zinc-800 rounded-lg">
                  <span className="text-zinc-400 block mb-1">Role Title</span>
                  <span className="font-medium text-zinc-200 text-xs sm:text-sm">{extracted.job_title}</span>
                </div>
                <div className="p-3 bg-zinc-900/80 border border-zinc-800 rounded-lg">
                  <span className="text-zinc-400 block mb-1">Work Mode & Location</span>
                  <span className="font-medium text-zinc-200 text-xs sm:text-sm">
                    {extracted.work_mode || 'Unknown'} ({extracted.work_location || 'Location not stated'})
                  </span>
                </div>
                <div className="p-3 bg-zinc-900/80 border border-zinc-800 rounded-lg">
                  <span className="text-zinc-400 block mb-1">Stipend / Salary</span>
                  <span className="font-medium text-zinc-200 text-xs sm:text-sm font-mono">
                    {extracted.salary_or_stipend || 'Not stated'}
                  </span>
                </div>
              </div>

              {/* Skills Tags */}
              <div>
                <span className="text-xs font-medium text-zinc-400 block mb-2">Required Skills</span>
                <div className="flex flex-wrap gap-1.5">
                  {extracted.required_skills?.map((s, idx) => (
                    <span
                      key={idx}
                      className="px-2 py-0.5 rounded text-xs font-mono bg-zinc-800 text-zinc-300 border border-zinc-700/50"
                    >
                      {s}
                    </span>
                  ))}
                  {(!extracted.required_skills || extracted.required_skills.length === 0) && (
                    <span className="text-xs text-zinc-500">None explicitly listed.</span>
                  )}
                </div>
              </div>

              {/* Action Buttons */}
              <div className="pt-3 border-t border-zinc-800 flex flex-wrap gap-2.5">
                <button
                  onClick={handlePrepareDraft}
                  disabled={preparingDraft}
                  className="flex items-center space-x-2 px-4 py-2 rounded-lg text-xs sm:text-sm font-medium bg-zinc-100 hover:bg-zinc-200 text-zinc-950 transition-colors disabled:opacity-50"
                >
                  <span>{preparingDraft ? 'Generating Tailored Draft...' : 'Prepare Application Draft'}</span>
                </button>
              </div>
            </div>
          )}

          {/* Prepared Draft Preview */}
          {draftResult && (
            <div className="rounded-xl bg-zinc-900/40 border border-zinc-800 p-4 sm:p-6 space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-semibold text-zinc-100">Tailored Application Prepared</h3>
                  <p className="text-xs text-zinc-400">
                    Grounded strictly in your verified profile and uploaded resume.
                  </p>
                </div>
                <button
                  onClick={copyCoverLetter}
                  className="flex items-center space-x-1.5 px-2.5 py-1.5 rounded-md text-xs font-medium bg-zinc-800 hover:bg-zinc-700 text-zinc-300 transition-colors"
                >
                  {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                  <span>{copied ? 'Copied' : 'Copy Letter'}</span>
                </button>
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-medium text-zinc-300">Generated Cover Letter</label>
                <div className="p-3.5 rounded-lg bg-zinc-950 border border-zinc-800 font-mono text-xs text-zinc-300 whitespace-pre-wrap leading-relaxed max-h-72 overflow-y-auto">
                  {draftResult.cover_letter}
                </div>
              </div>

              {/* Form Fields Mapped */}
              <div className="space-y-1.5 pt-1">
                <label className="text-xs font-medium text-zinc-300">ATS Form Fields Mapped</label>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 text-xs">
                  {Object.entries(draftResult.form_field_values || {}).map(([k, v]) => (
                    <div key={k} className="p-2.5 rounded-md bg-zinc-900 border border-zinc-800">
                      <span className="text-[10px] text-zinc-500 block uppercase font-mono">{k}</span>
                      <span className="text-zinc-200 font-medium truncate block">{String(v)}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Review & Approve Button */}
              <div className="pt-2">
                <button
                  onClick={() => onNavigateTab('approvals')}
                  className="flex items-center space-x-2 px-4 py-2 rounded-lg text-xs sm:text-sm font-medium bg-zinc-100 hover:bg-zinc-200 text-zinc-950 transition-colors"
                >
                  <span>Go to Approvals Queue</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
