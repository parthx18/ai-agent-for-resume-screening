// Global State
const state = {
  portal: 'employer',
  jobs: [],
  candidates: [],
  selectedJobId: null,
  selectedCandidateId: null,
  notifications: [],
  selectedFile: null,
  currentUser: null,
  authModalRole: 'employer',
  authModalMode: 'login'
};

// ============================================================
// INITIALIZATION
// ============================================================
document.addEventListener('DOMContentLoaded', () => {
  initDropzone();
  initAuth();
  fetchJobs();
  fetchCandidates();
  fetchNotifications();
  loadSettings();
});

// Hides or disables the Employer portal tab, Export Excel, and Outbox Log buttons
// when a candidate is logged in. Restores them for employers and guests.
function syncPortalTabsForRole() {
  const employerBtn = document.getElementById('btn-employer-role');
  const excelBtn = document.getElementById('btn-download-excel');
  const outboxBtn = document.getElementById('btn-open-outbox');

  const isCandidate = state.currentUser && state.currentUser.role === 'candidate';

  // Employer portal tab
  if (employerBtn) {
    if (isCandidate) {
      employerBtn.disabled = true;
      employerBtn.title = 'Employer Dashboard is restricted to employer accounts.';
      employerBtn.style.opacity = '0.4';
      employerBtn.style.cursor = 'not-allowed';
    } else {
      employerBtn.disabled = false;
      employerBtn.title = '';
      employerBtn.style.opacity = '';
      employerBtn.style.cursor = '';
    }
  }

  // Export Excel button — employer/guest only
  if (excelBtn) {
    excelBtn.style.display = isCandidate ? 'none' : '';
  }

  // Outbox Log button — employer/guest only
  if (outboxBtn) {
    outboxBtn.style.display = isCandidate ? 'none' : '';
  }
}

// ============================================================
// ROLE & PORTAL SWITCHING
// ============================================================
function switchPortal(target) {
  // Block candidates from accessing the employer dashboard
  if (target === 'employer' && state.currentUser && state.currentUser.role === 'candidate') {
    showToast('Access Denied: Candidates cannot access the Employer Dashboard.', 'error');
    return;
  }

  state.portal = target;
  
  const employerBtn = document.getElementById('btn-employer-role');
  const candidateBtn = document.getElementById('btn-candidate-role');
  const employerView = document.getElementById('view-employer');
  const candidateView = document.getElementById('view-candidate');

  if (target === 'employer') {
    employerBtn.classList.add('active');
    candidateBtn.classList.remove('active');
    employerView.classList.add('active');
    candidateView.classList.remove('active');
    fetchCandidates();
  } else {
    candidateBtn.classList.add('active');
    employerBtn.classList.remove('active');
    candidateView.classList.add('active');
    employerView.classList.remove('active');
    if (state.jobs.length > 0 && !state.selectedJobId) {
      selectJobForApplication(state.jobs[0].id);
    }
    updateCandidateFormAuth();
  }

  // Sync portal toggle button visibility based on role
  syncPortalTabsForRole();
}

// ============================================================
// DEDICATED PRE-ENTRY LOGIN WINDOW & SESSION MANAGEMENT
// ============================================================
function initAuth() {
  let savedUser = null;
  try {
    const raw = localStorage.getItem('talentai_user');
    if (raw) savedUser = JSON.parse(raw);
  } catch (e) {
    console.error('Failed to parse saved user:', e);
  }

  const loginScreen = document.getElementById('login-window-screen');
  const mainApp = document.getElementById('main-app-container');

  if (savedUser && savedUser.id) {
    state.currentUser = savedUser;
    if (loginScreen) loginScreen.style.display = 'none';
    if (mainApp) mainApp.style.display = 'flex';
    renderNavAuth();
    updateCandidateFormAuth();
    syncPortalTabsForRole();
    switchPortal(savedUser.role === 'candidate' ? 'candidate' : 'employer');
  } else {
    state.currentUser = null;
    if (loginScreen) loginScreen.style.display = 'flex';
    if (mainApp) mainApp.style.display = 'none';
    selectLoginRole('employer');
    setLoginMode('login');
  }
}

function selectLoginRole(role) {
  state.authModalRole = role;

  const empToggle = document.getElementById('role-toggle-employer');
  const candToggle = document.getElementById('role-toggle-candidate');
  const roleInput = document.getElementById('screen-auth-role');
  const subheading = document.getElementById('split-login-subheading');

  if (role === 'employer') {
    if (empToggle) empToggle.classList.add('active');
    if (candToggle) candToggle.classList.remove('active');
    if (roleInput) roleInput.value = 'employer';
    if (state.authModalMode === 'register' && subheading) {
      subheading.textContent = 'Enter your details to create an Employer / Hiring account.';
    }
  } else {
    if (candToggle) candToggle.classList.add('active');
    if (empToggle) empToggle.classList.remove('active');
    if (roleInput) roleInput.value = 'candidate';
    if (state.authModalMode === 'register' && subheading) {
      subheading.textContent = 'Enter your details to create your Candidate applicant account.';
    }
  }
}

function toggleAuthMode() {
  const newMode = state.authModalMode === 'login' ? 'register' : 'login';
  setLoginMode(newMode);
}

function setLoginMode(mode) {
  state.authModalMode = mode;

  const heading = document.getElementById('split-login-heading');
  const subheading = document.getElementById('split-login-subheading');
  const nameGroup = document.getElementById('screen-auth-name-group');
  const nameInput = document.getElementById('screen-auth-fullname');
  const submitBtnText = document.getElementById('screen-auth-btn-text');
  const footerPrompt = document.getElementById('split-footer-prompt');
  const footerActionBtn = document.getElementById('split-footer-action-btn');

  clearScreenAuthError();

  if (mode === 'login') {
    if (heading) heading.textContent = 'Log in to your account.';
    if (subheading) subheading.textContent = 'Enter your email address and password to log in.';
    if (nameGroup) nameGroup.style.display = 'none';
    if (nameInput) nameInput.removeAttribute('required');
    if (submitBtnText) submitBtnText.textContent = 'Login';
    if (footerPrompt) footerPrompt.textContent = "Don't you have an account?";
    if (footerActionBtn) footerActionBtn.textContent = 'Sign Up';
  } else {
    if (heading) heading.textContent = 'Create your account.';
    if (subheading) subheading.textContent = state.authModalRole === 'employer'
      ? 'Enter your details to create an Employer / Hiring account.'
      : 'Enter your details to create your Candidate applicant account.';
    if (nameGroup) nameGroup.style.display = 'block';
    if (nameInput) nameInput.setAttribute('required', 'required');
    if (submitBtnText) submitBtnText.textContent = 'Create Account';
    if (footerPrompt) footerPrompt.textContent = 'Already have an account?';
    if (footerActionBtn) footerActionBtn.textContent = 'Log In';
  }
}

function toggleScreenPasswordVisibility() {
  const pwdInput = document.getElementById('screen-auth-password');
  const eyeIcon = document.getElementById('screen-eye-icon');
  if (!pwdInput) return;

  if (pwdInput.type === 'password') {
    pwdInput.type = 'text';
    if (eyeIcon) {
      eyeIcon.innerHTML = `
        <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/>
        <line x1="1" y1="1" x2="23" y2="23"/>
      `;
    }
  } else {
    pwdInput.type = 'password';
    if (eyeIcon) {
      eyeIcon.innerHTML = `
        <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
        <circle cx="12" cy="12" r="3"/>
      `;
    }
  }
}

function showScreenAuthError(message) {
  const el = document.getElementById('login-error-alert');
  if (!el) return;
  el.textContent = message;
  el.style.display = 'block';
}

function clearScreenAuthError() {
  const el = document.getElementById('login-error-alert');
  if (!el) return;
  el.textContent = '';
  el.style.display = 'none';
}

async function handleScreenAuthSubmit(e) {
  e.preventDefault();
  clearScreenAuthError();

  const role = state.authModalRole;
  const mode = state.authModalMode;
  const email = (document.getElementById('screen-auth-email')?.value || '').trim();
  const password = (document.getElementById('screen-auth-password')?.value || '').trim();
  const fullName = (document.getElementById('screen-auth-fullname')?.value || '').trim();

  const submitBtn = document.getElementById('screen-auth-submit-btn');
  const spinner = document.getElementById('screen-auth-spinner');

  if (mode === 'register' && !fullName) {
    showScreenAuthError('Please enter your full name.');
    return;
  }
  if (!email || !password) {
    showScreenAuthError('Please enter both email address and password.');
    return;
  }
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    showScreenAuthError('Please enter a valid email address.');
    return;
  }
  if (mode === 'register' && password.length < 8) {
    showScreenAuthError('For security, your password must be at least 8 characters long.');
    return;
  }

  if (submitBtn) submitBtn.disabled = true;
  if (spinner) spinner.style.display = 'inline-block';

  try {
    const endpoint = mode === 'register' ? '/api/auth/register' : '/api/auth/login';
    const payload = mode === 'register'
      ? { role, full_name: fullName, email, password }
      : { email, password, role };

    const res = await fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    const data = await res.json();

    if (!res.ok) {
      throw new Error(data.detail || 'Authentication failed. Please check your credentials.');
    }

    // Success: store session & enter website
    state.currentUser = data.user;
    try {
      localStorage.setItem('talentai_user', JSON.stringify(data.user));
    } catch (_) {}

    document.getElementById('login-window-screen').style.display = 'none';
    document.getElementById('main-app-container').style.display = 'flex';

    renderNavAuth();
    updateCandidateFormAuth();
    syncPortalTabsForRole();
    showToast(data.message || `Welcome, ${data.user.full_name}!`, 'success');

    // Switch to target portal
    if (data.user.role === 'employer') {
      switchPortal('employer');
    } else {
      switchPortal('candidate');
    }

  } catch (err) {
    showScreenAuthError(err.message);
  } finally {
    if (submitBtn) submitBtn.disabled = false;
    if (spinner) spinner.style.display = 'none';
  }
}

function quickLoginDemoAccount(role) {
  clearScreenAuthError();
  const emailInput = document.getElementById('screen-auth-email');
  const passwordInput = document.getElementById('screen-auth-password');

  if (role === 'employer') {
    selectLoginRole('employer');
    setLoginMode('login');
    if (emailInput) emailInput.value = 'recruiter@talentai.com';
    if (passwordInput) passwordInput.value = 'admin123';
  } else {
    selectLoginRole('candidate');
    setLoginMode('login');
    if (emailInput) emailInput.value = 'candidate@demo.com';
    if (passwordInput) passwordInput.value = 'demo123';
  }

  const form = document.getElementById('screen-auth-form');
  if (form) {
    form.dispatchEvent(new Event('submit', { cancelable: true, bubbles: true }));
  }
}

function enterAsGuest() {
  document.getElementById('login-window-screen').style.display = 'none';
  document.getElementById('main-app-container').style.display = 'flex';
  state.currentUser = null;
  renderNavAuth();
  updateCandidateFormAuth();
  syncPortalTabsForRole();
  showToast('Entered workspace in Guest Preview mode. You can sign in anytime.', 'success');
  switchPortal(state.authModalRole === 'candidate' ? 'candidate' : 'employer');
}

function returnToLoginScreen() {
  document.getElementById('main-app-container').style.display = 'none';
  const loginScreen = document.getElementById('login-window-screen');
  if (loginScreen) {
    loginScreen.style.display = 'flex';
    clearScreenAuthError();
  }
}

function logoutUser() {
  const userName = state.currentUser ? state.currentUser.full_name : 'User';
  state.currentUser = null;
  try {
    localStorage.removeItem('talentai_user');
  } catch (_) {}

  returnToLoginScreen();
  showToast(`Signed out. Welcome back anytime, ${userName}.`, 'success');
}

function renderNavAuth() {
  const container = document.getElementById('nav-auth-container');
  if (!container) return;

  if (!state.currentUser) {
    container.innerHTML = `
      <button class="action-btn auth-nav-btn" id="btn-nav-login" onclick="returnToLoginScreen()" title="Go to Login Window">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4"/>
          <polyline points="10 17 15 12 10 7"/>
          <line x1="15" y1="12" x2="3" y2="12"/>
        </svg>
        <span>Login Window</span>
      </button>
    `;
    return;
  }

  const user = state.currentUser;
  const isEmployer = user.role === 'employer';
  const initials = (user.full_name || 'User')
    .split(' ')
    .filter(Boolean)
    .map(n => n[0])
    .slice(0, 2)
    .join('')
    .toUpperCase() || 'U';

  const roleTitle = isEmployer ? 'Employer' : 'Candidate';
  const roleClass = isEmployer ? 'employer' : 'candidate';

  container.innerHTML = `
    <div class="nav-user-pill" title="Signed in as ${escapeHtml(user.full_name)} (${escapeHtml(user.email)})">
      <div class="nav-user-avatar ${roleClass}">${escapeHtml(initials)}</div>
      <div class="nav-user-info">
        <span class="nav-user-name">${escapeHtml(user.full_name)}</span>
        <span class="nav-user-role-badge ${roleClass}">${roleTitle}</span>
      </div>
      <div class="nav-auth-actions">
        <button class="nav-auth-icon-btn" onclick="returnToLoginScreen()" title="Switch Account / Return to Login Window">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="16 3 21 3 21 8"/>
            <line x1="4" y1="20" x2="21" y2="3"/>
            <polyline points="21 16 21 21 16 21"/>
            <line x1="15" y1="15" x2="21" y2="21"/>
            <line x1="4" y1="4" x2="9" y2="9"/>
          </svg>
        </button>
        <button class="nav-auth-icon-btn logout" onclick="logoutUser()" title="Sign Out">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
            <polyline points="16 17 21 12 16 7"/>
            <line x1="21" y1="12" x2="9" y2="12"/>
          </svg>
        </button>
      </div>
    </div>
  `;
}

function updateCandidateFormAuth() {
  const banner = document.getElementById('candidate-auth-banner');
  const nameInput = document.getElementById('apply-name');
  const emailInput = document.getElementById('apply-email');

  if (!banner) return;

  if (state.currentUser && state.currentUser.role === 'candidate') {
    const user = state.currentUser;
    banner.style.display = 'flex';
    banner.innerHTML = `
      <div class="candidate-auth-banner-left">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
          <polyline points="22 4 12 14.01 9 11.01"/>
        </svg>
        <span>Logged in as <strong>${escapeHtml(user.full_name)}</strong> (<code>${escapeHtml(user.email)}</code>)</span>
      </div>
      <button type="button" class="switch-link" onclick="returnToLoginScreen()">Switch Account</button>
    `;
    if (nameInput && !nameInput.value) nameInput.value = user.full_name;
    if (emailInput && !emailInput.value) emailInput.value = user.email;
  } else {
    banner.style.display = 'none';
  }
}

// ============================================================
// JOB MANAGEMENT
// ============================================================
async function fetchJobs() {
  try {
    const res = await fetch('/api/jobs');
    const data = await res.json();
    state.jobs = data.jobs || [];

    // Populate Employer Filter Dropdown
    const filterSelect = document.getElementById('filter-job-select');
    filterSelect.innerHTML = '<option value="">All Job Roles</option>';
    state.jobs.forEach(job => {
      const opt = document.createElement('option');
      opt.value = job.id;
      opt.textContent = `${job.title} (${job.department || 'Tech'})`;
      filterSelect.appendChild(opt);
    });

    // Populate Candidate Job List
    renderCandidateJobList();

    // Auto select first job if none selected
    if (state.jobs.length > 0 && !state.selectedJobId) {
      selectJobForApplication(state.jobs[0].id);
    }
  } catch (err) {
    showToast('Failed to load job listings', 'error');
  }
}

function renderCandidateJobList() {
  const container = document.getElementById('candidate-job-list');
  if (!container) return;

  if (state.jobs.length === 0) {
    container.innerHTML = '<p class="empty-text">No active job openings available at the moment.</p>';
    return;
  }

  container.innerHTML = state.jobs.map(job => {
    const isSelected = job.id === state.selectedJobId;
    const reqSkills = (job.required_skills || []).slice(0, 3);
    
    return `
      <div class="job-card ${isSelected ? 'selected' : ''}" onclick="selectJobForApplication(${job.id})">
        <div class="job-card-header">
          <h3 class="job-card-title">${escapeHtml(job.title)}</h3>
          <span class="job-card-dept">${escapeHtml(job.department || 'General')}</span>
        </div>
        ${job.company_name ? `<div style="font-size:12px; font-weight:600; color:#818cf8; margin-bottom:4px; display:flex; align-items:center; gap:5px;">
          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><rect x="2" y="7" width="20" height="14" rx="2"/><path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/></svg>
          ${escapeHtml(job.company_name)}
        </div>` : ''}
        <p class="job-card-desc">${escapeHtml((job.description || '').substring(0, 100))}${(job.description || '').length > 100 ? '…' : ''}</p>
        <div class="job-card-skills">
          ${reqSkills.map(s => `<span class="skill-tag">${escapeHtml(s)}</span>`).join('')}
          <span class="skill-tag" style="background:#e0e7ff; color:#3730a3;">Min ${job.min_experience_years || 0} yrs exp</span>
        </div>
        <div style="display:flex; gap:8px; margin-top:10px;">
          <button
            class="view-btn"
            style="flex:1; font-size:12px; padding:6px 10px;"
            onclick="event.stopPropagation(); openJobDetailModal(${job.id})"
          >View Full Details</button>
          <button
            class="primary-btn"
            style="flex:1; font-size:12px; padding:6px 10px; border-radius:8px;"
            onclick="event.stopPropagation(); selectJobForApplication(${job.id}); document.getElementById('candidate-apply-form').scrollIntoView({behavior:'smooth'});"
          >Apply Now</button>
        </div>
      </div>
    `;
  }).join('');
}

// ============================================================
// JOB DETAIL POPUP
// ============================================================
function openJobDetailModal(jobId) {
  const job = state.jobs.find(j => j.id === jobId);
  if (!job) return;

  // Select this job as active
  selectJobForApplication(jobId);

  // Populate header
  document.getElementById('jd-title').textContent = job.title;
  document.getElementById('jd-dept').textContent = job.department || 'General';

  // Company name (show below title if present)
  let companyEl = document.getElementById('jd-company');
  if (!companyEl) {
    companyEl = document.createElement('div');
    companyEl.id = 'jd-company';
    companyEl.style.cssText = 'font-size:13px; font-weight:700; color:#000000; display:flex; align-items:center; gap:6px; margin-top:2px;';
    document.getElementById('jd-title').after(companyEl);
  }
  if (job.company_name) {
    companyEl.style.display = 'flex';
    companyEl.innerHTML = `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><rect x="2" y="7" width="20" height="14" rx="2"/><path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/></svg> ${escapeHtml(job.company_name)}`;
  } else {
    companyEl.style.display = 'none';
  }

  // Meta
  const exp = job.min_experience_years;
  document.getElementById('jd-exp').textContent = exp ? `${exp} year${exp !== 1 ? 's' : ''}` : 'Not specified';
  document.getElementById('jd-edu').textContent = job.min_education || 'Not specified';

  // Description
  document.getElementById('jd-description').textContent = job.description || 'No description provided.';

  // Required Skills
  const reqContainer = document.getElementById('jd-req-skills');
  const reqSkills = job.required_skills || [];
  document.getElementById('jd-req-skills-box').style.display = reqSkills.length ? '' : 'none';
  reqContainer.innerHTML = reqSkills.map(s =>
    `<span class="skill-tag" style="background:#eff6ff; color:#1e40af; border:1px solid #bfdbfe; font-weight:700;">${escapeHtml(s)}</span>`
  ).join('');

  // Preferred Skills
  const prefContainer = document.getElementById('jd-pref-skills');
  const prefSkills = job.preferred_skills || [];
  document.getElementById('jd-pref-skills-box').style.display = prefSkills.length ? '' : 'none';
  prefContainer.innerHTML = prefSkills.map(s =>
    `<span class="skill-tag" style="background:#f0fdf4; color:#166534; border:1px solid #bbf7d0; font-weight:700;">${escapeHtml(s)}</span>`
  ).join('');

  // Custom Criteria
  const criteriaBox = document.getElementById('jd-criteria-box');
  const criteriaContainer = document.getElementById('jd-criteria');
  const criteria = job.custom_criteria || [];
  if (criteria.length > 0) {
    criteriaBox.style.display = '';
    criteriaContainer.innerHTML = criteria.map(c => `
      <div style="display:flex; flex-direction:column; gap:3px;">
        <div style="display:flex; justify-content:space-between; align-items:center;">
          <span style="font-size:13px; font-weight:700; color:#000000;">${escapeHtml(c.name || c.criterion || '')}</span>
          <span style="font-size:12px; font-weight:700; color:#1e40af; background:#dbeafe; border:1px solid #bfdbfe; padding:2px 8px; border-radius:20px;">${c.weight || 0}%</span>
        </div>
        ${c.description ? `<span style="font-size:12px; font-weight:500; color:#374151;">${escapeHtml(c.description)}</span>` : ''}
      </div>
    `).join('');
  } else {
    criteriaBox.style.display = 'none';
  }

  openModal('modal-job-detail');
}

function applyFromJobDetail() {
  closeModal('modal-job-detail');
  setTimeout(() => {
    document.getElementById('candidate-apply-form')?.scrollIntoView({ behavior: 'smooth' });
  }, 200);
}

function selectJobForApplication(jobId) {
  state.selectedJobId = jobId;
  const job = state.jobs.find(j => j.id === jobId);
  
  // Update hidden input
  const hiddenInput = document.getElementById('apply-job-id');
  if (hiddenInput) hiddenInput.value = jobId;

  // Update visual badge
  const pill = document.getElementById('selected-job-pill');
  if (pill && job) {
    pill.textContent = `Applying for: ${job.title}`;
  }

  renderCandidateJobList();
}

// Post New Job Handler
async function handleCreateJob(event) {
  event.preventDefault();
  
  const title = document.getElementById('job-title').value.trim();
  const companyName = document.getElementById('job-company-name').value.trim();
  const department = document.getElementById('job-department').value.trim();
  const minExp = parseFloat(document.getElementById('job-min-exp').value) || 0;
  const description = document.getElementById('job-description').value.trim();
  const reqSkillsStr = document.getElementById('job-req-skills').value.trim();
  const prefSkillsStr = document.getElementById('job-pref-skills').value.trim();

  const reqSkills = reqSkillsStr ? reqSkillsStr.split(',').map(s => s.trim()).filter(Boolean) : [];
  const prefSkills = prefSkillsStr ? prefSkillsStr.split(',').map(s => s.trim()).filter(Boolean) : [];
  const minEdu = (document.getElementById('job-min-edu')?.value || '').trim();

  // Gather custom criteria
  const critRows = document.querySelectorAll('.criterion-row');
  const customCriteria = [];
  critRows.forEach(row => {
    const name = row.querySelector('.crit-name')?.value.trim();
    const weight = parseFloat(row.querySelector('.crit-weight')?.value) || 20;
    const desc = (row.querySelector('.crit-desc')?.value || '').trim();
    if (name) {
      customCriteria.push({ name, weight, description: desc });
    }
  });

  try {
    const res = await fetch('/api/jobs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        title,
        company_name: companyName,
        department,
        description,
        required_skills: reqSkills,
        preferred_skills: prefSkills,
        min_experience_years: minExp,
        min_education: minEdu,
        custom_criteria: customCriteria
      })
    });

    const data = await res.json();
    if (res.ok) {
      showToast('New Job posted & screening rubrics activated!', 'success');
      closeModal('modal-create-job');
      document.getElementById('create-job-form').reset();
      document.getElementById('criteria-builder').innerHTML = '';
      fetchJobs();
    } else {
      showToast(data.detail || 'Error creating job opening', 'error');
    }
  } catch (err) {
    showToast('Failed to connect to server', 'error');
  }
}

function addCriterionRow() {
  const container = document.getElementById('criteria-builder');
  const row = document.createElement('div');
  row.className = 'criterion-row';
  row.innerHTML = `
    <input type="text" class="crit-name" placeholder="Criterion name (e.g. LLM & Agent Frameworks)" required>
    <div class="weight-input-wrapper">
      <input type="number" class="crit-weight" placeholder="Weight" value="25" min="5" max="100" required>
      <span class="weight-unit">%</span>
    </div>
    <input type="text" class="crit-desc" placeholder="Evaluation rubric notes (e.g. Experience with tool calling, prompt chains...)">
    <button type="button" class="remove-crit-btn" onclick="this.parentElement.remove()" title="Remove criterion">&times;</button>
  `;
  container.appendChild(row);
}

// ============================================================
// CANDIDATES & EVALUATION DASHBOARD
// ============================================================
async function fetchCandidates() {
  const jobId = document.getElementById('filter-job-select').value;
  const tier = document.getElementById('filter-tier-select').value;

  let url = '/api/candidates';
  const params = [];
  if (jobId) params.push(`job_id=${encodeURIComponent(jobId)}`);
  if (tier) params.push(`tier=${encodeURIComponent(tier)}`);
  if (state.currentUser && state.currentUser.email) {
    params.push(`user_email=${encodeURIComponent(state.currentUser.email)}`);
  }
  if (params.length > 0) url += `?${params.join('&')}`;

  try {
    const res = await fetch(url);
    const data = await res.json();
    state.candidates = data.candidates || [];

    // Guarantee demo employer view shows only the two sample candidates
    if (state.currentUser && state.currentUser.email === 'recruiter@talentai.com') {
      state.candidates = state.candidates.filter(c => 
        c.email === 'sarah.chen@example.com' || c.email === 'david.miller@example.com'
      );
    }
    
    updateKpiStats();
    renderCandidates();
  } catch (err) {
    console.error(err);
  }
}

function updateKpiStats() {
  const total = state.candidates.length;
  const shortlisted = state.candidates.filter(c => (c.recommendation || '').toLowerCase().includes('shortlist')).length;
  const review = state.candidates.filter(c => (c.recommendation || '').toLowerCase().includes('review')).length;

  let avgScore = '--';
  if (total > 0) {
    const validScores = state.candidates.map(c => c.overall_score).filter(s => s !== null && s !== undefined);
    if (validScores.length > 0) {
      avgScore = Math.round(validScores.reduce((a, b) => a + b, 0) / validScores.length);
    }
  }

  document.getElementById('stat-total-candidates').textContent = total;
  document.getElementById('stat-shortlisted').textContent = shortlisted;
  document.getElementById('stat-review').textContent = review;
  document.getElementById('stat-avg-score').textContent = avgScore !== '--' ? `${avgScore}%` : '--';
}

function renderCandidates() {
  const tbody = document.getElementById('candidates-tbody');
  const query = (document.getElementById('candidate-search').value || '').toLowerCase().trim();

  let filtered = state.candidates;
  if (query) {
    filtered = filtered.filter(c => 
      (c.full_name || '').toLowerCase().includes(query) ||
      (c.email || '').toLowerCase().includes(query) ||
      (c.job_title || '').toLowerCase().includes(query) ||
      (c.matched_skills || []).some(s => s.toLowerCase().includes(query))
    );
  }

  document.getElementById('filtered-count-badge').textContent = `Showing ${filtered.length} candidates`;

  if (filtered.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="7" class="empty-table-state">
          <div class="empty-state-content">
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
              <circle cx="12" cy="12" r="10"/>
              <line x1="8" y1="12" x2="16" y2="12"/>
            </svg>
            <p>No candidate records found matching your filters.</p>
          </div>
        </td>
      </tr>
    `;
    return;
  }

  tbody.innerHTML = filtered.map(c => {
    const score = Math.round(c.overall_score || 0);
    const dialClass = score >= 75 ? 'high' : score >= 50 ? 'medium' : 'low';
    
    let badgeClass = 'badge-review';
    const rec = (c.recommendation || 'Under Review').toLowerCase();
    if (rec.includes('shortlist')) badgeClass = 'badge-shortlist';
    else if (rec.includes('not') || rec.includes('reject')) badgeClass = 'badge-reject';

    return `
      <tr>
        <td>
          <div class="candidate-cell">
            <span class="candidate-name">${escapeHtml(c.full_name)}</span>
            <span class="candidate-email">${escapeHtml(c.email)}</span>
          </div>
        </td>
        <td>
          <strong>${escapeHtml(c.job_title || 'Software Role')}</strong>
          <div style="font-size:12px; color:#94a3b8;">${escapeHtml(c.job_department || 'Engineering')}</div>
        </td>
        <td>
          <div class="score-cell">
            <div class="score-dial ${dialClass}">${score}</div>
            <span style="font-weight:700; font-size:13px;">${score}/100</span>
          </div>
        </td>
        <td>
          <div style="font-size:13px; font-weight:600;">${c.skills_match_score || 0}% Match</div>
          <div style="font-size:11.5px; color:#64748b;">${(c.matched_skills || []).length} skills matched</div>
        </td>
        <td>
          <div style="font-size:13px; font-weight:600;">${c.experience_score || 0}% Fit</div>
        </td>
        <td>
          <span class="badge ${badgeClass}">${escapeHtml(c.recommendation || 'Under Review')}</span>
        </td>
        <td>
          <button class="view-btn" onclick="openCandidateDetail(${c.id})">Inspect Scorecard</button>
        </td>
      </tr>
    `;
  }).join('');
}

// Candidate Deep-Dive Modal
async function openCandidateDetail(candidateId) {
  state.selectedCandidateId = candidateId;
  try {
    const res = await fetch(`/api/candidates/${candidateId}`);
    const data = await res.json();
    const c = data.candidate;
    if (!c) return;

    // Header
    document.getElementById('detail-name').textContent = c.full_name;
    const scorePill = document.getElementById('detail-score-pill');
    scorePill.textContent = `${Math.round(c.overall_score || 0)} / 100`;

    const tierBadge = document.getElementById('detail-tier-badge');
    tierBadge.textContent = c.recommendation || 'Under Review';
    tierBadge.className = 'badge ' + (
      (c.recommendation || '').toLowerCase().includes('shortlist') ? 'badge-shortlist' :
      (c.recommendation || '').toLowerCase().includes('not') ? 'badge-reject' : 'badge-review'
    );

    // Metadata
    document.getElementById('detail-email').textContent = c.email;
    document.getElementById('detail-phone').textContent = c.phone || 'None provided';
    document.getElementById('detail-job').textContent = c.job_title;
    document.getElementById('detail-provider').textContent = c.provider_used || 'AI Engine';

    // Strengths
    const strengthsContainer = document.getElementById('detail-strengths');
    strengthsContainer.innerHTML = (c.strengths || []).length > 0 
      ? c.strengths.map(s => `<li>${escapeHtml(s)}</li>`).join('')
      : '<li>No explicit strengths flagged.</li>';

    // Gaps
    const gapsContainer = document.getElementById('detail-gaps');
    gapsContainer.innerHTML = (c.gaps_and_flags || []).length > 0
      ? c.gaps_and_flags.map(g => `<li>${escapeHtml(g)}</li>`).join('')
      : '<li>No major blockers identified.</li>';

    // Interview Questions
    const questionsContainer = document.getElementById('detail-questions');
    questionsContainer.innerHTML = (c.suggested_questions || []).length > 0
      ? c.suggested_questions.map(q => `<li>${escapeHtml(q)}</li>`).join('')
      : '<li>Technical competency verification.</li>';

    // Matched skills tags
    const matchedContainer = document.getElementById('detail-matched-skills');
    matchedContainer.innerHTML = (c.matched_skills || []).length > 0
      ? c.matched_skills.map(s => `<span class="tag">${escapeHtml(s)}</span>`).join('')
      : '<span style="font-size:12px; color:#94a3b8;">None recorded</span>';

    // Missing skills tags
    const missingContainer = document.getElementById('detail-missing-skills');
    missingContainer.innerHTML = (c.missing_skills || []).length > 0
      ? c.missing_skills.map(s => `<span class="tag">${escapeHtml(s)}</span>`).join('')
      : '<span style="font-size:12px; color:#10b981;">No critical skills missing</span>';

    // Custom Criteria breakdown
    const critContainer = document.getElementById('detail-criteria-breakdown');
    if (c.criteria_breakdown && c.criteria_breakdown.length > 0) {
      critContainer.innerHTML = c.criteria_breakdown.map(crit => `
        <div class="criteria-item">
          <div class="criteria-row-header">
            <span>${escapeHtml(crit.criterion)} <small style="color:#94a3b8;">(${crit.weight}%)</small></span>
            <span><strong>${crit.score}%</strong></span>
          </div>
          <div class="criteria-bar-track">
            <div class="criteria-bar-val" style="width: ${crit.score}%;"></div>
          </div>
          <div style="font-size:11.5px; color:#64748b; margin-top:2px;">${escapeHtml(crit.notes || '')}</div>
        </div>
      `).join('');
    } else {
      critContainer.innerHTML = '<div style="font-size:12px; color:#94a3b8;">Evaluated against general job profile.</div>';
    }

    // AI Summary
    document.getElementById('detail-summary-text').textContent = c.summary_feedback || 'Screening analysis complete.';

    openModal('modal-candidate-detail');
  } catch (err) {
    showToast('Failed to load candidate details', 'error');
  }
}

// Resend Candidate Notification
async function resendCandidateNotification() {
  if (!state.selectedCandidateId) return;
  try {
    const res = await fetch(`/api/notifications/resend/${state.selectedCandidateId}`, { method: 'POST' });
    const data = await res.json();
    if (res.ok) {
      showToast('Notification re-sent successfully!', 'success');
      fetchNotifications();
    } else {
      showToast('Failed to resend notification', 'error');
    }
  } catch (err) {
    showToast('Network error resending notification', 'error');
  }
}

// ============================================================
// CANDIDATE APPLICATION SUBMISSION & AI SCREENING
// ============================================================
function initDropzone() {
  const dropzone = document.getElementById('dropzone');
  if (!dropzone) return;

  ['dragenter', 'dragover'].forEach(eventName => {
    dropzone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.add('dragover');
    });
  });

  ['dragleave', 'drop'].forEach(eventName => {
    dropzone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.remove('dragover');
    });
  });

  dropzone.addEventListener('drop', (e) => {
    const dt = e.dataTransfer;
    const files = dt.files;
    if (files.length > 0) {
      setCandidateFile(files[0]);
    }
  });
}

function handleFileSelected(event) {
  const files = event.target.files;
  if (files.length > 0) {
    setCandidateFile(files[0]);
  }
}

function setCandidateFile(file) {
  state.selectedFile = file;
  document.getElementById('dropzone-content').style.display = 'none';
  const pill = document.getElementById('file-preview-pill');
  pill.style.display = 'inline-flex';
  document.getElementById('preview-filename').textContent = `${file.name} (${Math.round(file.size / 1024)} KB)`;
}

function clearSelectedFile(event) {
  if (event) event.stopPropagation();
  state.selectedFile = null;
  document.getElementById('apply-resume-file').value = '';
  document.getElementById('file-preview-pill').style.display = 'none';
  document.getElementById('dropzone-content').style.display = 'flex';
}

async function handleCandidateSubmit(event) {
  event.preventDefault();

  if (!state.selectedJobId) {
    showToast('Please select a job opening from the list first.', 'error');
    return;
  }

  if (!state.selectedFile) {
    showToast('Please upload your resume document (PDF, DOCX, TXT).', 'error');
    return;
  }

  const name = document.getElementById('apply-name').value.trim();
  const email = document.getElementById('apply-email').value.trim();
  const phone = document.getElementById('apply-phone').value.trim();
  const links = document.getElementById('apply-links').value.trim();

  const formData = new FormData();
  formData.append('job_id', state.selectedJobId);
  formData.append('full_name', name);
  formData.append('email', email);
  formData.append('phone', phone);
  formData.append('linkedin_or_portfolio', links);
  formData.append('resume_file', state.selectedFile);

  // Show progress animation
  const progressContainer = document.getElementById('screening-progress');
  const progressFill = document.getElementById('progress-bar-fill');
  const stepText = document.getElementById('progress-step-text');
  const submitBtn = document.getElementById('btn-submit-application');

  progressContainer.style.display = 'block';
  submitBtn.disabled = true;

  // Animate steps
  progressFill.style.width = '20%';
  stepText.textContent = 'Reading & parsing resume document...';

  const t1 = setTimeout(() => {
    progressFill.style.width = '55%';
    stepText.textContent = 'AI Screening Agent evaluating against job criteria...';
  }, 900);

  const t2 = setTimeout(() => {
    progressFill.style.width = '85%';
    stepText.textContent = 'Writing to Excel spreadsheet & generating notification...';
  }, 2200);

  try {
    const res = await fetch('/api/apply', {
      method: 'POST',
      body: formData
    });

    clearTimeout(t1);
    clearTimeout(t2);

    const data = await res.json();

    if (res.ok) {
      progressFill.style.width = '100%';
      stepText.textContent = 'Screening complete! Automated notification dispatched.';

      showToast(`Application processed! Screening Score: ${data.overall_score}/100`, 'success');
      
      // Reset form
      document.getElementById('candidate-apply-form').reset();
      clearSelectedFile();
      progressContainer.style.display = 'none';
      submitBtn.disabled = false;

      // Refresh candidates & notifications
      fetchCandidates();
      fetchNotifications();

      // Open Candidate Deep Dive for instant feedback
      openCandidateDetail(data.candidate_id);
    } else {
      progressContainer.style.display = 'none';
      submitBtn.disabled = false;
      showToast(data.detail || 'Screening failed', 'error');
    }
  } catch (err) {
    clearTimeout(t1);
    clearTimeout(t2);
    progressContainer.style.display = 'none';
    submitBtn.disabled = false;
    showToast('Network error during screening submission', 'error');
  }
}

// ============================================================
// EXCEL EXPORT & DOWNLOAD
// ============================================================
function downloadExcel() {
  showToast('Preparing live Excel spreadsheet...', 'success');
  let url = '/api/excel/download';
  if (state.currentUser && state.currentUser.email) {
    url += `?user_email=${encodeURIComponent(state.currentUser.email)}`;
  }
  window.location.href = url;
}

// ============================================================
// NOTIFICATION OUTBOX
// ============================================================
async function fetchNotifications() {
  try {
    let url = '/api/notifications';
    if (state.currentUser && state.currentUser.email) {
      url += `?user_email=${encodeURIComponent(state.currentUser.email)}`;
    }
    const res = await fetch(url);
    const data = await res.json();
    state.notifications = data.notifications || [];

    if (state.currentUser && state.currentUser.email === 'recruiter@talentai.com') {
      state.notifications = state.notifications.filter(n =>
        n.recipient_email === 'sarah.chen@example.com' || n.recipient_email === 'david.miller@example.com'
      );
    }

    const badge = document.getElementById('outbox-count');
    if (badge) badge.textContent = state.notifications.length;

    renderOutboxTable();
  } catch (err) {
    console.error(err);
  }
}

function renderOutboxTable() {
  const tbody = document.getElementById('outbox-tbody');
  if (!tbody) return;

  if (state.notifications.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="6" style="text-align:center; padding:30px; color:#94a3b8;">
          No automated notifications dispatched yet. Apply with a resume to trigger automated notifications.
        </td>
      </tr>
    `;
    return;
  }

  tbody.innerHTML = state.notifications.map(n => {
    const timeStr = n.sent_at ? new Date(n.sent_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '';
    const isEmail = n.channel === 'email';

    return `
      <tr>
        <td style="font-size:12px; font-family:var(--font-mono);">${timeStr}</td>
        <td>
          <strong>${escapeHtml(n.candidate_name || 'Applicant')}</strong>
          <div style="font-size:11.5px; color:#94a3b8;">${escapeHtml(n.recipient_email || n.recipient_phone || '')}</div>
        </td>
        <td>
          <span style="font-size:11px; font-weight:700; text-transform:uppercase; padding:2px 8px; border-radius:4px; background:${isEmail ? '#eff6ff; color:#1d4ed8;' : '#f5f3ff; color:#6d28d9;'}">${n.channel}</span>
        </td>
        <td>
          <div style="font-weight:600; font-size:13px;">${escapeHtml(n.subject || 'Application Screening Notification')}</div>
          <div style="font-size:12px; color:#64748b; max-width:320px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">
            ${escapeHtml(n.message_body.replace(/<[^>]*>?/gm, ''))}
          </div>
        </td>
        <td>
          <span class="badge ${n.status.includes('sent') ? 'badge-shortlist' : 'badge-review'}">
            ${escapeHtml(n.status)}
          </span>
        </td>
        <td>
          ${isEmail ? `<button class="view-btn" onclick="openEmailPreviewModal(${n.id})">View Email</button>` : ''}
        </td>
      </tr>
    `;
  }).join('');
}

function openEmailPreviewModal(notificationId) {
  const notif = state.notifications.find(n => n.id === notificationId);
  if (!notif) return;

  document.getElementById('preview-subject').textContent = notif.subject;
  document.getElementById('email-preview-frame').innerHTML = notif.message_body;
  openModal('modal-email-preview');
}

// ============================================================
// SETTINGS
// ============================================================
async function loadSettings() {
  try {
    const res = await fetch('/api/settings');
    const data = await res.json();
    state.settings = data;

    if (data.ai_provider) document.getElementById('setting-ai-provider').value = data.ai_provider;
    if (data.smtp_host) document.getElementById('setting-smtp-host').value = data.smtp_host;
    if (data.smtp_port) document.getElementById('setting-smtp-port').value = data.smtp_port;
    if (data.smtp_user) document.getElementById('setting-smtp-user').value = data.smtp_user;
    if (data.enable_real_email !== undefined) document.getElementById('setting-enable-email').checked = data.enable_real_email;

    if (data.gemini_configured) {
      document.getElementById('setting-gemini-key').placeholder = '•••••••••••••••••••••••• (Configured)';
    }
    if (data.groq_configured) {
      document.getElementById('setting-groq-key').placeholder = '•••••••••••••••••••••••• (Configured)';
    }
  } catch (err) {
    console.error('Failed to load settings', err);
  }
}

async function handleSaveSettings(event) {
  event.preventDefault();

  const provider = document.getElementById('setting-ai-provider').value;
  const geminiKey = document.getElementById('setting-gemini-key').value.trim();
  const groqKey = document.getElementById('setting-groq-key').value.trim();
  const enableEmail = document.getElementById('setting-enable-email').checked;
  const smtpHost = document.getElementById('setting-smtp-host').value.trim();
  const smtpPort = parseInt(document.getElementById('setting-smtp-port').value) || 587;
  const smtpUser = document.getElementById('setting-smtp-user').value.trim();
  const smtpPassword = document.getElementById('setting-smtp-password').value.trim();

  const payload = {
    ai_provider: provider,
    enable_real_email: enableEmail,
    smtp_host: smtpHost,
    smtp_port: smtpPort,
    smtp_user: smtpUser
  };

  if (geminiKey) payload.gemini_api_key = geminiKey;
  if (groqKey) payload.groq_api_key = groqKey;
  if (smtpPassword) payload.smtp_password = smtpPassword;

  try {
    const res = await fetch('/api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (res.ok) {
      showToast('Settings saved successfully!', 'success');
      closeModal('modal-settings');
      loadSettings();
    } else {
      showToast('Error saving settings', 'error');
    }
  } catch (err) {
    showToast('Failed to save settings', 'error');
  }
}

// ============================================================
// MODAL & UTILITY HELPERS
// ============================================================
function openModal(id) {
  const modal = document.getElementById(id);
  if (modal) modal.classList.add('open');
}

function closeModal(id) {
  const modal = document.getElementById(id);
  if (modal) modal.classList.remove('open');
}

// Close modals when clicking backdrop
document.addEventListener('click', (e) => {
  if (e.target.classList.contains('modal-backdrop')) {
    e.target.classList.remove('open');
  }
});

function showToast(message, type = 'success') {
  const container = document.getElementById('toast-container');
  if (!container) return;

  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.innerHTML = `
    <span>${escapeHtml(message)}</span>
  `;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(10px)';
    toast.style.transition = 'all 0.3s ease';
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}
