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
      body: JSON.stringify({ raw_text: text, title, company }),
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

  async decideApproval(approvalId, decision, notes = '') {
    const res = await fetch(`${BASE_URL}/api/applications/approvals/${approvalId}/decide`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ decision, notes }),
    });
    return handleResponse(res);
  },

  async getTracker() {
    const res = await fetch(`${BASE_URL}/api/applications/tracker`);
    return handleResponse(res);
  },

  // Browser Automation
  async runBrowserAutomation(draftId, autoSubmit = false) {
    const res = await fetch(`${BASE_URL}/api/browser/run/${draftId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ auto_submit: autoSubmit, headless: true }),
    });
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
