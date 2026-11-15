import React, { useState } from 'react';
import {
  Link,
  FileText,
  Upload,
  Sparkles,
  CheckCircle2,
  XCircle,
  HelpCircle,
  Play,
  ArrowRight,
  Shield,
  Layers,
  Copy,
  Check,
} from 'lucide-react';
import { api } from '../services/api';

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

      // If job was saved successfully, evaluate matching & eligibility
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
    <div className="space-y-6 pb-16">
      {/* Header */}
      <div>
        <div className="inline-flex items-center space-x-2 px-3 py-1 rounded-full text-xs font-mono bg-amber-500/10 border border-amber-500/20 text-amber-300 mb-2">
          <span>Mode B: Targeted Opportunity Analysis</span>
        </div>
        <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
          Analyze Any Job Opportunity
        </h1>
        <p className="text-sm text-slate-400">
          Paste any LinkedIn, Naukri, or career page URL, paste raw text, or upload a JD document.
          Agent KitKat will verify your 2027 graduation eligibility and calculate your resume match score.
        </p>
      </div>

      {/* Input Mode Selector & Form */}
      <div className="rounded-2xl bg-slate-900/90 border border-slate-800 p-6 shadow-xl space-y-6">
        {/* Mode Tabs */}
        <div className="flex border-b border-slate-800 space-x-6 text-sm font-medium">
          {[
            { id: 'url', label: 'Paste Job URL', icon: Link },
            { id: 'text', label: 'Paste Job Description', icon: FileText },
            { id: 'file', label: 'Upload JD Document', icon: Upload },
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
                className={`flex items-center space-x-2 pb-3 border-b-2 transition-all ${
                  isActive
                    ? 'border-amber-500 text-amber-400 font-semibold'
                    : 'border-transparent text-slate-400 hover:text-slate-200'
                }`}
              >
                <Icon className="w-4 h-4" />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </div>

        {/* Form Inputs */}
        <form onSubmit={handleAnalyze} className="space-y-4">
          {activeMode === 'url' && (
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-2">
                Public Job Posting URL
              </label>
              <div className="flex flex-col sm:flex-row gap-3">
                <input
                  type="url"
                  placeholder="https://www.linkedin.com/jobs/view/... or https://careers.company.com/..."
                  value={urlInput}
                  onChange={(e) => setUrlInput(e.target.value)}
                  className="flex-1 px-4 py-2.5 rounded-xl bg-slate-800/80 border border-slate-700 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-amber-500 focus:ring-1 focus:ring-amber-500"
                />
                <button
                  type="submit"
                  disabled={loading}
                  className="px-6 py-2.5 rounded-xl text-sm font-semibold bg-amber-500 hover:bg-amber-400 text-slate-950 shadow-md shadow-amber-500/20 active:scale-95 transition-all disabled:opacity-50 whitespace-nowrap"
                >
                  {loading ? 'Analyzing with Local AI...' : 'Analyze URL'}
                </button>
              </div>
            </div>
          )}

          {activeMode === 'text' && (
            <div className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                    Job Title (Optional)
                  </label>
                  <input
                    type="text"
                    placeholder="e.g. Software Engineer Intern"
                    value={titleInput}
                    onChange={(e) => setTitleInput(e.target.value)}
                    className="w-full px-3.5 py-2 rounded-xl bg-slate-800/80 border border-slate-700 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-amber-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                    Company Name (Optional)
                  </label>
                  <input
                    type="text"
                    placeholder="e.g. Acme Cloud Corp"
                    value={companyInput}
                    onChange={(e) => setCompanyInput(e.target.value)}
                    className="w-full px-3.5 py-2 rounded-xl bg-slate-800/80 border border-slate-700 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-amber-500"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                  Job Description Text
                </label>
                <textarea
                  rows={6}
                  placeholder="Paste complete job description requirements here..."
                  value={textInput}
                  onChange={(e) => setTextInput(e.target.value)}
                  className="w-full px-4 py-3 rounded-xl bg-slate-800/80 border border-slate-700 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-amber-500 font-mono text-xs"
                />
              </div>

              <button
                type="submit"
                disabled={loading}
                className="px-6 py-2.5 rounded-xl text-sm font-semibold bg-amber-500 hover:bg-amber-400 text-slate-950 shadow-md shadow-amber-500/20 active:scale-95 transition-all disabled:opacity-50"
              >
                {loading ? 'Analyzing with Local AI...' : 'Analyze Text'}
              </button>
            </div>
          )}

          {activeMode === 'file' && (
            <div className="space-y-4">
              <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                Upload Job Description (PDF or DOCX)
              </label>
              <div className="border-2 border-dashed border-slate-700 hover:border-amber-500/50 rounded-2xl p-6 text-center transition-colors">
                <input
                  type="file"
                  accept=".pdf,.docx"
                  onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
                  className="hidden"
                  id="jd-file-upload"
                />
                <label htmlFor="jd-file-upload" className="cursor-pointer space-y-2 flex flex-col items-center">
                  <Upload className="w-8 h-8 text-amber-400" />
                  <span className="text-sm font-medium text-slate-300">
                    {selectedFile ? selectedFile.name : 'Click to browse or drop PDF / DOCX'}
                  </span>
                  <span className="text-xs text-slate-500">Supports up to 10MB</span>
                </label>
              </div>

              <button
                type="submit"
                disabled={loading || !selectedFile}
                className="px-6 py-2.5 rounded-xl text-sm font-semibold bg-amber-500 hover:bg-amber-400 text-slate-950 shadow-md shadow-amber-500/20 active:scale-95 transition-all disabled:opacity-50"
              >
                {loading ? 'Analyzing with Local AI...' : 'Analyze Document'}
              </button>
            </div>
          )}
        </form>

        {error && (
          <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-sm flex items-start space-x-3">
            <XCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />
            <div>
              <p className="font-semibold">Analysis Notice</p>
              <p className="text-xs mt-0.5">{error}</p>
            </div>
          </div>
        )}
      </div>

      {/* Analysis Results View */}
      {analysisResult && (
        <div className="space-y-6">
          {/* Top Overview Cards: Eligibility & Match Score */}
          {evalResult && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Eligibility Card */}
              <div
                className={`rounded-2xl border p-5 ${
                  evalResult.eligibility?.overall_status === 'PASS'
                    ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
                    : evalResult.eligibility?.overall_status === 'FAIL'
                    ? 'bg-rose-500/10 border-rose-500/30 text-rose-300'
                    : 'bg-amber-500/10 border-amber-500/30 text-amber-300'
                }`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <Shield className="w-5 h-5" />
                    <span className="font-bold text-sm">Eligibility Verification</span>
                  </div>
                  <span className="px-3 py-1 rounded-full text-xs font-mono font-bold uppercase tracking-wider bg-slate-950/60 border border-current">
                    {evalResult.eligibility?.overall_status}
                  </span>
                </div>
                <div className="mt-4 space-y-2 text-xs">
                  <div className="flex justify-between">
                    <span className="text-slate-400">Graduation Year (2027)</span>
                    <span className="font-mono font-semibold">{evalResult.eligibility?.graduation_year?.status}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">Degree (B.Tech)</span>
                    <span className="font-mono font-semibold">{evalResult.eligibility?.degree?.status}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">CGPA (8.44)</span>
                    <span className="font-mono font-semibold">{evalResult.eligibility?.cgpa?.status}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">Work Mode</span>
                    <span className="font-mono font-semibold">{evalResult.eligibility?.work_mode?.status}</span>
                  </div>
                </div>

                {evalResult.eligibility?.rejection_reasons?.length > 0 && (
                  <div className="mt-3 pt-3 border-t border-rose-500/20 text-xs text-rose-400">
                    <span className="font-semibold">Rejection Reason: </span>
                    {evalResult.eligibility.rejection_reasons.join(', ')}
                  </div>
                )}
              </div>

              {/* Match Score Card */}
              <div className="rounded-2xl bg-slate-900/90 border border-slate-800 p-5 space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2 text-slate-300 text-sm font-bold">
                    <Sparkles className="w-5 h-5 text-amber-400" />
                    <span>Weighted Resume Match</span>
                  </div>
                  <span className="text-2xl font-extrabold text-amber-400 font-mono">
                    {evalResult.overall_score}%
                  </span>
                </div>

                <div className="space-y-1.5 text-xs">
                  <div className="flex justify-between text-slate-400">
                    <span>Technical Skills (Weight: 35%)</span>
                    <span className="font-mono text-slate-200">
                      {evalResult.category_scores?.technical_skills} / 35
                    </span>
                  </div>
                  <div className="w-full bg-slate-800 rounded-full h-1.5 overflow-hidden">
                    <div
                      className="bg-amber-400 h-full rounded-full"
                      style={{ width: `${(evalResult.category_scores?.technical_skills / 35) * 100}%` }}
                    />
                  </div>
                </div>

                <div className="pt-2 flex items-center justify-between text-xs">
                  <span className="text-slate-400">Recommendation</span>
                  <span className="font-mono font-semibold text-amber-300">
                    {evalResult.recommendation}
                  </span>
                </div>
              </div>
            </div>
          )}

          {/* Extracted Details Breakdown */}
          {extracted && (
            <div className="rounded-2xl bg-slate-900/90 border border-slate-800 p-6 space-y-4">
              <h2 className="text-base font-bold text-white">Extracted Job Information</h2>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 text-xs">
                <div className="p-3 bg-slate-800/50 rounded-xl">
                  <span className="text-slate-400 block mb-1">Company</span>
                  <span className="font-semibold text-slate-200 text-sm">{extracted.company_name}</span>
                </div>
                <div className="p-3 bg-slate-800/50 rounded-xl">
                  <span className="text-slate-400 block mb-1">Role Title</span>
                  <span className="font-semibold text-slate-200 text-sm">{extracted.job_title}</span>
                </div>
                <div className="p-3 bg-slate-800/50 rounded-xl">
                  <span className="text-slate-400 block mb-1">Work Mode & Location</span>
                  <span className="font-semibold text-slate-200 text-sm">
                    {extracted.work_mode || 'Remote'} ({extracted.work_location || 'India'})
                  </span>
                </div>
                <div className="p-3 bg-slate-800/50 rounded-xl">
                  <span className="text-slate-400 block mb-1">Stipend / Salary</span>
                  <span className="font-semibold text-amber-400 text-sm font-mono">
                    {extracted.salary_or_stipend || 'Competitive'}
                  </span>
                </div>
              </div>

              {/* Skills Tags */}
              <div>
                <span className="text-xs font-semibold text-slate-300 block mb-2">Required Skills</span>
                <div className="flex flex-wrap gap-1.5">
                  {extracted.required_skills?.map((s, idx) => (
                    <span
                      key={idx}
                      className="px-2.5 py-1 rounded-md text-xs font-mono bg-slate-800 text-slate-300 border border-slate-700"
                    >
                      {s}
                    </span>
                  ))}
                  {(!extracted.required_skills || extracted.required_skills.length === 0) && (
                    <span className="text-xs text-slate-500">None explicitly listed.</span>
                  )}
                </div>
              </div>

              {/* Action Buttons */}
              <div className="pt-4 border-t border-slate-800 flex flex-wrap gap-3">
                <button
                  onClick={handlePrepareDraft}
                  disabled={preparingDraft}
                  className="flex items-center space-x-2 px-5 py-2.5 rounded-xl text-sm font-semibold bg-amber-500 hover:bg-amber-400 text-slate-950 shadow-md shadow-amber-500/20 active:scale-95 transition-all disabled:opacity-50"
                >
                  <Sparkles className="w-4 h-4" />
                  <span>{preparingDraft ? 'Generating Tailored Draft...' : 'Prepare Application Draft'}</span>
                </button>
              </div>
            </div>
          )}

          {/* Prepared Draft Preview */}
          {draftResult && (
            <div className="rounded-2xl bg-slate-900/90 border border-slate-800 p-6 space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-base font-bold text-white">Tailored Application Prepared</h3>
                  <p className="text-xs text-slate-400">
                    Grounded strictly in your verified profile and uploaded resume.
                  </p>
                </div>
                <button
                  onClick={copyCoverLetter}
                  className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-slate-800 hover:bg-slate-700 text-slate-300 transition-colors"
                >
                  {copied ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
                  <span>{copied ? 'Copied!' : 'Copy Cover Letter'}</span>
                </button>
              </div>

              <div className="space-y-2">
                <label className="text-xs font-semibold text-slate-300">Generated Cover Letter</label>
                <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 font-mono text-xs text-slate-300 whitespace-pre-wrap leading-relaxed max-h-80 overflow-y-auto">
                  {draftResult.cover_letter}
                </div>
              </div>

              {/* Form Fields Mapped */}
              <div className="space-y-2 pt-2">
                <label className="text-xs font-semibold text-slate-300">ATS Form Fields Mapped</label>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 text-xs">
                  {Object.entries(draftResult.form_field_values || {}).map(([k, v]) => (
                    <div key={k} className="p-2.5 rounded-lg bg-slate-800/60 border border-slate-800">
                      <span className="text-[10px] text-slate-400 block uppercase font-mono">{k}</span>
                      <span className="text-slate-200 font-medium truncate block">{String(v)}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Review & Approve Button */}
              <div className="pt-3">
                <button
                  onClick={() => onNavigateTab('approvals')}
                  className="flex items-center space-x-2 px-5 py-2.5 rounded-xl text-sm font-semibold bg-emerald-500 hover:bg-emerald-400 text-slate-950 shadow-md shadow-emerald-500/20 transition-all"
                >
                  <span>Go to Approvals Queue</span>
                  <ArrowRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
