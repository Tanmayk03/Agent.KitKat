/**
 * Agent KitKat - API Client Service
 * Centralized HTTP communication with FastAPI backend endpoints.
 */

const BASE_URL = '';

async function handleResponse(response) {
  if (!response.ok) {
    let errorDetail = `HTTP ${response.status}: ${response.statusText}`;
    try {
      const data = await response.json();
      if (data && data.detail) {
        errorDetail = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail);
      }
    } catch {
      // Non-JSON error body
    }
    throw new Error(errorDetail);
  }
  return response.json();
}

export const api = {
  // System Health
  async getHealth() {
    const res = await fetch(`${BASE_URL}/api/health`);
    return handleResponse(res);
  },

  // Candidate Profile
  async getProfile() {
    const res = await fetch(`${BASE_URL}/api/profile`);
    return handleResponse(res);
  },

  async updateProfile(profileData) {
    const res = await fetch(`${BASE_URL}/api/profile`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(profileData),
    });
    return handleResponse(res);
  },

  async getProfileCompleteness() {
    const res = await fetch(`${BASE_URL}/api/profile/completeness`);
    return handleResponse(res);
  },

  async getResumeSuggestions(resumeId) {
    const res = await fetch(`${BASE_URL}/api/profile/resume-suggestions/${resumeId}`);
    return handleResponse(res);
  },

  async applyResumeSuggestions(resumeId, fields) {
    const res = await fetch(`${BASE_URL}/api/profile/apply-resume-suggestions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ resume_id: resumeId, fields }),
    });
    return handleResponse(res);
  },

  // Resumes
  async getResumes() {
    const res = await fetch(`${BASE_URL}/api/resumes`);
    return handleResponse(res);
  },

  async uploadResume(file) {
    const formData = new FormData();
    formData.append('file', file);
    const res = await fetch(`${BASE_URL}/api/resumes/upload`, {
      method: 'POST',
      body: formData,
    });
    return handleResponse(res);
  },

  async activateResume(id) {
    const res = await fetch(`${BASE_URL}/api/resumes/${id}/activate`, {
      method: 'PUT',
    });
    return handleResponse(res);
  },

  async deleteResume(id) {
    const res = await fetch(`${BASE_URL}/api/resumes/${id}`, {
      method: 'DELETE',
    });
    return handleResponse(res);
  },

  // Mode B: Job Analysis
  async analyzeJobUrl(url) {
    const res = await fetch(`${BASE_URL}/api/jobs/analyze-url`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url }),
    });
    return handleResponse(res);
  },

  async analyzeJobText(text, title = null, company = null) {
    const res = await fetch(`${BASE_URL}/api/jobs/analyze-text`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, title, company }),
    });
    return handleResponse(res);
  },

  async analyzeJobFile(file) {
    const formData = new FormData();
    formData.append('file', file);
    const res = await fetch(`${BASE_URL}/api/jobs/analyze-file`, {
      method: 'POST',
      body: formData,
    });
    return handleResponse(res);
  },

  async getJobs() {
    const res = await fetch(`${BASE_URL}/api/jobs`);
    return handleResponse(res);
  },

  async getJob(id) {
    const res = await fetch(`${BASE_URL}/api/jobs/${id}`);
    return handleResponse(res);
  },

  // Matching & Eligibility
  async evaluateJob(jobId) {
    const res = await fetch(`${BASE_URL}/api/matching/evaluate/${jobId}`, {
      method: 'POST',
    });
    return handleResponse(res);
  },

  async getRankings() {
    const res = await fetch(`${BASE_URL}/api/matching/rankings`);
    return handleResponse(res);
  },

  // Application Preparation & Approvals
  async prepareApplication(jobId) {
    const res = await fetch(`${BASE_URL}/api/applications/prepare/${jobId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
    });
    return handleResponse(res);
  },

  async getDraft(draftId) {
    const res = await fetch(`${BASE_URL}/api/applications/drafts/${draftId}`);
    return handleResponse(res);
  },

  async updateDraft(draftId, data) {
    const res = await fetch(`${BASE_URL}/api/applications/drafts/${draftId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    return handleResponse(res);
  },

  async getApprovals() {
    const res = await fetch(`${BASE_URL}/api/applications/approvals`);
    return handleResponse(res);
  },

  // decision: 'approve' | 'reject' (also accepts 'approved' / 'rejected')
  async decideApproval(approvalId, decision, notes = '', acknowledgeUnverifiedClaims = false) {
    const action = decision.startsWith('approve') ? 'approve' : decision.startsWith('reject') ? 'reject' : decision;
    const res = await fetch(`${BASE_URL}/api/applications/approvals/${approvalId}/decide`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action, decision_notes: notes || null, acknowledge_unverified_claims: acknowledgeUnverifiedClaims }),
    });
    return handleResponse(res);
  },

  async getDraftVersions(draftId) {
    const res = await fetch(`${BASE_URL}/api/applications/drafts/${draftId}/versions`);
    return handleResponse(res);
  },

  async restoreDraftVersion(draftId, version) {
    const res = await fetch(`${BASE_URL}/api/applications/drafts/${draftId}/versions/${version}/restore`, { method: 'POST' });
    return handleResponse(res);
  },

  // Tracker: { stage, q, sort, page, page_size } -> { items, total, page, page_size, stage_counts }
  async getApplications(params = {}) {
    const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== ''));
    const res = await fetch(`${BASE_URL}/api/applications?${qs.toString()}`);
    return handleResponse(res);
  },

  async getStages() {
    const res = await fetch(`${BASE_URL}/api/applications/stages`);
    return handleResponse(res);
  },

  async shortlistJob(jobId) {
    const res = await fetch(`${BASE_URL}/api/applications/shortlist/${jobId}`, { method: 'POST' });
    return handleResponse(res);
  },

  async updateApplication(appId, patch) {
    const res = await fetch(`${BASE_URL}/api/applications/${appId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(patch),
    });
    return handleResponse(res);
  },

  async getApplicationEvents(appId) {
    const res = await fetch(`${BASE_URL}/api/applications/${appId}/events`);
    return handleResponse(res);
  },

  async getTracker() {
    const res = await fetch(`${BASE_URL}/api/applications/tracker`);
    return handleResponse(res);
  },

  // Browser Automation
  // autoSubmit=false: fill the form and take a screenshot only (safe default).
  // autoSubmit=true is accepted by the server only for drafts you approved AND with confirmSubmit=true.
  async runBrowserAutomation(draftId, autoSubmit = false, confirmSubmit = false) {
    const res = await fetch(`${BASE_URL}/api/browser/run/${draftId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ auto_submit: autoSubmit, confirm_submit: confirmSubmit, headless: true }),
    });
    return handleResponse(res);
  },

  // Map the application form and show what would be filled. Types nothing.
  async previewApplicationForm(draftId) {
    const res = await fetch(`${BASE_URL}/api/browser/preview/${draftId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ headless: true }),
    });
    return handleResponse(res);
  },

  async getDraftExport(draftId) {
    const res = await fetch(`${BASE_URL}/api/applications/drafts/${draftId}/export`);
    if (!res.ok) return handleResponse(res);
    return res.text();
  },

  async resumeAutomation() {
    const res = await fetch(`${BASE_URL}/api/browser/resume`, { method: 'POST' });
    return handleResponse(res);
  },

  async emergencyStop() {
    const res = await fetch(`${BASE_URL}/api/browser/emergency-stop`, {
      method: 'POST',
    });
    return handleResponse(res);
  },

  async getBrowserStatus() {
    const res = await fetch(`${BASE_URL}/api/browser/status`);
    return handleResponse(res);
  },

  // Mode A: Discovery & Scheduler
  async triggerDiscovery(payload = {}) {
    const res = await fetch(`${BASE_URL}/api/discovery/search`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    return handleResponse(res);
  },

  // Background discovery run: returns { run_id } immediately; poll getDiscoveryRun(run_id)
  async startDiscoveryRun(payload = {}) {
    const res = await fetch(`${BASE_URL}/api/discovery/runs`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    return handleResponse(res);
  },

  async getDiscoveryRun(runId) {
    const res = await fetch(`${BASE_URL}/api/discovery/runs/${runId}`);
    return handleResponse(res);
  },

  async getDiscoveryRuns(limit = 10) {
    const res = await fetch(`${BASE_URL}/api/discovery/runs?limit=${limit}`);
    return handleResponse(res);
  },

  async getSourceHealth() {
    const res = await fetch(`${BASE_URL}/api/discovery/health`);
    return handleResponse(res);
  },

  async getCareerBoards() {
    const res = await fetch(`${BASE_URL}/api/discovery/boards`);
    return handleResponse(res);
  },

  async addCareerBoard(url, company = '') {
    const res = await fetch(`${BASE_URL}/api/discovery/boards`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url, company: company || null }),
    });
    return handleResponse(res);
  },

  async removeCareerBoard(ats, token) {
    const res = await fetch(`${BASE_URL}/api/discovery/boards/${encodeURIComponent(ats)}/${encodeURIComponent(token)}`, {
      method: 'DELETE',
    });
    return handleResponse(res);
  },

  async getDiscoverySources() {
    const res = await fetch(`${BASE_URL}/api/discovery/sources`);
    return handleResponse(res);
  },

  async getSchedulerStatus() {
    const res = await fetch(`${BASE_URL}/api/scheduler/status`);
    return handleResponse(res);
  },

  async startScheduler(hour = 9, minute = 0) {
    const res = await fetch(`${BASE_URL}/api/scheduler/start?hour=${hour}&minute=${minute}`, {
      method: 'POST',
    });
    return handleResponse(res);
  },

  async stopScheduler() {
    const res = await fetch(`${BASE_URL}/api/scheduler/stop`, {
      method: 'POST',
    });
    return handleResponse(res);
  },

  async triggerSchedulerNow() {
    const res = await fetch(`${BASE_URL}/api/scheduler/trigger`, {
      method: 'POST',
    });
    return handleResponse(res);
  },

  // Daily Reports
  async getDailyReport(targetDate = null) {
    const url = targetDate ? `${BASE_URL}/api/reports/daily?target_date=${targetDate}` : `${BASE_URL}/api/reports/daily`;
    const res = await fetch(url);
    return handleResponse(res);
  },

  async getReportHistory() {
    const res = await fetch(`${BASE_URL}/api/reports/history`);
    return handleResponse(res);
  },

  // Mobile & Network Info
  async getNetworkInfo() {
    const res = await fetch(`${BASE_URL}/api/network/info`);
    return handleResponse(res);
  },
};
