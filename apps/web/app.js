/* NOVARA ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â unified web application
   Vanilla JS single-page app. No build step, no external dependencies.
   Every record shown here comes from the NOVARA API. */

/* ------------------------------------------------------------------ *
 * Configuration
 * ------------------------------------------------------------------ */

// When the API serves the SPA (normal local and deployed runs) call it on the
// same origin. The absolute fallback is only for opening index.html directly
// from disk, where there is no API origin to inherit.
const API_BASE = (location.protocol === 'http:' || location.protocol === 'https:')
  ? ''
  : 'http://localhost:8000';

const KEYS = {
  access: 'novara.access_token',
  refresh: 'novara.refresh_token',
  workspace: 'novara.workspace_id',
};

const AUTH_ROUTES = ['login', 'register', 'bootstrap', 'reset-request', 'reset-confirm'];

const P = {
  workspaceManage: 'workspace:manage',
  memberManage: 'member:manage',
  memberInvite: 'member:invite',
  contactRead: 'contact:read',
  contactWrite: 'contact:write',
  contactArchive: 'contact:archive',
  contactDelete: 'contact:delete',
  companyRead: 'company:read',
  companyWrite: 'company:write',
  leadRead: 'lead:read',
  leadWrite: 'lead:write',
  taskRead: 'task:read',
  taskWrite: 'task:write',
  noteWrite: 'note:write',
  eventRead: 'event:read',
  notificationRead: 'notification:read',
  outreachRead: 'outreach:read',
  outreachApprove: 'outreach:approve',
  documentRead: 'document:read',
  documentWrite: 'document:write',
  documentAdmin: 'document:admin',
};

/* ------------------------------------------------------------------ *
 * State
 * ------------------------------------------------------------------ */

const state = {
  access: localStorage.getItem(KEYS.access) || '',
  refresh: localStorage.getItem(KEYS.refresh) || '',
  workspaceId: localStorage.getItem(KEYS.workspace) || '',
  me: null,
  workspaces: [],
  workspaceError: '',
  viewToken: 0,
  pendingConfirm: null,
  contactFilters: {
    search: '', lifecycle_stage: '', tag: '', archived: 'false',
    sort: 'created_at:desc', skip: 0, limit: 25,
  },
  contactsPage: 0,
  contactsHasMore: false,
  leadStatus: '',
  taskStatus: 'all',
  ticketStatus: 'all',
  ticketOwner: 'all',
  ticketTeam: '',
  ticketInbox: '',
  ticketLabel: '',
  ticketSegment: '',
  ticketSegmentContactIds: null,
  ticketSegmentInfo: null,
  pendingExpandedReply: null,
  itemFilter: 'all',
  itemPriority: '',
  flagEnvironment: 'production',
  selectedFlag: '',
  campaignStatus: 'all',
  dealStage: 'all',
  eventFilter: '',
  searchQuery: '',
  searchType: 'all',
  lastSearchQuery: '',
  lastSearchResult: null,
  caches: {
    contacts: [], leads: [], tasks: [], tickets: [], notifications: [], drafts: [], events: [], companies: [],
    campaigns: [], deals: [], surveys: [],
    agents: [], agentRuns: [], integrations: [], integrationCatalog: null,
    supportSegments: [],
  },
  dashboards: null,
  notifCounts: null,
  notifStreamAbort: null,
  ticketCounts: null,
  ticketStreamAbort: null,
};

/* ------------------------------------------------------------------ *
 * Icons ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â professional inline SVG, no fonts or emoji
 * ------------------------------------------------------------------ */

const ICONS = {
  home: '<path d="m3 10 9-7 9 7v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><path d="M9 21v-7h6v7"/>',
  users: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
  building: '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M9 21v-4h6v4"/><path d="M7 8h2m6 0h2M7 12h2m6 0h2"/>',
  target: '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1"/>',
  checkSquare: '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="m8 12 3 3 5-6"/>',
  mail: '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 7 9 6 9-6"/>',
  activity: '<path d="M3 12h4l3-8 4 16 3-8h4"/>',
  settings: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .34 1.87l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06A1.7 1.7 0 0 0 15 19.4a1.7 1.7 0 0 0-1 1.56V21a2 2 0 1 1-4 0v-.09A1.7 1.7 0 0 0 9 19.4a1.7 1.7 0 0 0-1.87.34l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.7 1.7 0 0 0 4.6 15a1.7 1.7 0 0 0-1.56-1H3a2 2 0 1 1 0-4h.09A1.7 1.7 0 0 0 4.6 9a1.7 1.7 0 0 0-.34-1.87l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.7 1.7 0 0 0 9 4.6a1.7 1.7 0 0 0 1-1.56V3a2 2 0 1 1 4 0v.09A1.7 1.7 0 0 0 15 4.6a1.7 1.7 0 0 0 1.87-.34l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.7 1.7 0 0 0 19.4 9v.01a1.7 1.7 0 0 0 1.56 1H21a2 2 0 1 1 0 4h-.09a1.7 1.7 0 0 0-1.51 1z"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
  bell: '<path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9"/><path d="M13.7 21a2 2 0 0 1-3.4 0"/>',
  chevronDown: '<path d="m6 9 6 6 6-6"/>',
  chevronLeft: '<path d="m15 18-6-6 6-6"/>',
  chevronRight: '<path d="m9 18 6-6-6-6"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  edit: '<path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z"/>',
  archive: '<rect x="3" y="4" width="18" height="4" rx="1"/><path d="M5 8v11a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8"/><path d="M10 12h4"/>',
  restore: '<path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5"/>',
  trash: '<path d="M3 6h18"/><path d="M8 6V4a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v2"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>',
  note: '<path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><path d="M14 3v6h6M8 13h8M8 17h5"/>',
  logout: '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="m16 17 5-5-5-5"/><path d="M21 12H9"/>',
  menu: '<path d="M3 6h18M3 12h18M3 18h18"/>',
  close: '<path d="M18 6 6 18M6 6l12 12"/>',
  arrowRight: '<path d="M5 12h14M13 6l6 6-6 6"/>',
  shield: '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="m9 12 2 2 4-4"/>',
  lock: '<rect x="4" y="10" width="16" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/>',
  refresh: '<path d="M3 12a9 9 0 0 1 15.5-6.2L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-15.5 6.2L3 16"/><path d="M3 21v-5h5"/>',
  copy: '<rect x="8" y="8" width="13" height="13" rx="2"/><path d="M16 8V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h3"/>',
  check: '<path d="m5 12 4 4L19 6"/>',
  alert: '<path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/><path d="M12 9v4m0 4h.01"/>',
  inbox: '<path d="M4 4h16l2 10v6H2v-6z"/><path d="M2 14h6l2 3h4l2-3h6"/>',
  calendar: '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M7 3v4m10-4v4M3 10h18"/>',
  filter: '<path d="M4 5h16l-6 7v6l-4 2v-8z"/>',
  zap: '<path d="M13 2 4 14h7l-1 8 9-12h-7z"/>',
  grid: '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
  user: '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
  key: '<circle cx="7.5" cy="15.5" r="4.5"/><path d="m11 12 9-9 2 2-2 2 2 2-3 3-2-2-2 2"/>',
  link: '<path d="M10 13a5 5 0 0 0 7.1 0l2-2a5 5 0 0 0-7.1-7.1l-1.1 1.1"/><path d="M14 11a5 5 0 0 0-7.1 0l-2 2a5 5 0 0 0 7.1 7.1l1.1-1.1"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  tag: '<path d="M20.6 13.4 12 22l-9-9V4a1 1 0 0 1 1-1h9z"/><circle cx="7.5" cy="7.5" r="1"/>',
  eye: '<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7z"/><circle cx="12" cy="12" r="3"/>',
  layers: '<path d="m12 2 9 5-9 5-9-5z"/><path d="m3 12 9 5 9-5M3 17l9 5 9-5"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v5m0-8h.01"/>',
  dot: '<circle cx="12" cy="12" r="3"/>',
};

function icon(name, size = 18, cls = '') {
  return '<svg class="' + cls + '" width="' + size + '" height="' + size +
    '" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" ' +
    'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
    (ICONS[name] || ICONS.dot) + '</svg>';
}

/* ------------------------------------------------------------------ *
 * Small utilities
 * ------------------------------------------------------------------ */

const HTML_ENTITIES = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
function esc(value) {
  return String(value === null || value === undefined ? '' : value).replace(/[&<>"']/g, function (c) {
    return HTML_ENTITIES[c];
  });
}
const attr = esc;

function debounce(fn, ms) {
  let timer = null;
  return function () {
    const args = arguments;
    clearTimeout(timer);
    timer = setTimeout(function () { fn.apply(null, args); }, ms);
  };
}

function cap(value) {
  return String(value || '').replace(/[._-]/g, ' ').replace(/\b\w/g, function (m) { return m.toUpperCase(); });
}

function errMessage(err) {
  let detail = err && err.detail !== undefined ? err.detail : null;
  if (detail && typeof detail === 'object') {
    if (detail.dependent_records) {
      return 'Remove dependent records first: ' + Object.keys(detail.dependent_records)
        .map(function (k) { return k + ' (' + detail.dependent_records[k] + ')'; }).join(', ');
    }
    if (Array.isArray(detail)) {
      const messages = detail.map(function (item) {
        if (typeof item === 'string') return item;
        if (item && typeof item === 'object') {
          if (typeof item.msg === 'string') return item.msg;
          if (typeof item.message === 'string') return item.message;
        }
        return '';
      }).filter(Boolean);
      if (messages.length) return messages.join('; ');
    }
    detail = JSON.stringify(detail);
  }
  if (detail) return String(detail);
  return (err && err.message) || String(err || 'Unexpected error');
}

function fmtDate(value) {
  if (!value) return 'ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â';
  const d = new Date(value);
  if (isNaN(d.getTime())) return 'ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â';
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
}

function dateValue(value) {
  const raw = String(value || '').trim();
  return /^\d{4}-\d{2}-\d{2}$/.test(raw) ? raw + 'T00:00:00Z' : (raw || null);
}

function fmtDateTime(value) {
  if (!value) return 'ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â';
  const d = new Date(value);
  if (isNaN(d.getTime())) return 'ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â';
  return d.toLocaleString(undefined, { month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit' });
}

function relTime(value) {
  if (!value) return 'ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â';
  const d = new Date(value);
  if (isNaN(d.getTime())) return 'ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â';
  const seconds = Math.round((Date.now() - d.getTime()) / 1000);
  if (seconds < 0) return fmtDate(value);
  if (seconds < 60) return 'just now';
  if (seconds < 3600) return Math.floor(seconds / 60) + 'm ago';
  if (seconds < 86400) return Math.floor(seconds / 3600) + 'h ago';
  if (seconds < 604800) return Math.floor(seconds / 86400) + 'd ago';
  return fmtDate(value);
}

function initials(value) {
  const source = String(value || '?').trim();
  if (!source) return '?';
  const parts = source.split(/[\s@._-]+/).filter(Boolean);
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[1][0]).toUpperCase();
}

function avatar(value, size) {
  return '<div class="avatar' + (size ? ' avatar--' + size : '') + '">' + esc(initials(value)) + '</div>';
}

function safeUrl(value) {
  try {
    const u = new URL(String(value));
    return (u.protocol === 'http:' || u.protocol === 'https:') ? u.href : '';
  } catch (e) { return ''; }
}

function currentRoute() {
  return String(location.hash || '').replace(/^#\/?/, '').split('?')[0];
}

function navigate(route) { location.hash = '#/' + String(route).replace(/^\//, ''); }

function ws() { return state.workspaceId || (state.me && state.me.workspace_id) || ''; }
function apiW(path) { return '/api/v1/workspaces/' + encodeURIComponent(ws()) + path; }

function can(permission) {
  if (!state.me) return false;
  const granted = state.me.permissions || [];
  return granted.indexOf('*') !== -1 || granted.indexOf(permission) !== -1;
}

function statusBadge(status) {
  const s = String(status || 'unknown').toLowerCase();
  let cls = '';
  if (['done', 'qualified', 'converted', 'approved', 'active', 'verified', 'succeeded', 'recorded', 'completed'].indexOf(s) !== -1) cls = 'badge--green';
  else if (['new', 'draft', 'open', 'lead', 'pending', 'queued', 'running', 'not_configured'].indexOf(s) !== -1) cls = 'badge--amber';
  else if (['archived', 'deleted', 'rejected', 'dead_letter', 'cancelled', 'failed', 'blocked', 'disabled', 'dnc', 'suspended'].indexOf(s) !== -1) cls = 'badge--red';
  else if (['contact', 'customer', 'opportunity', 'configured', 'local', 'stopped'].indexOf(s) !== -1) cls = 'badge--blue';
  return '<span class="badge ' + cls + '">' + esc(cap(s)) + '</span>';
}

function eventIcon(type) {
  const t = String(type || '');
  if (t.indexOf('contact') === 0) return 'users';
  if (t.indexOf('task') === 0) return 'checkSquare';
  if (t.indexOf('lead') === 0) return 'target';
  if (t.indexOf('outreach') === 0) return 'mail';
  if (t.indexOf('member') === 0) return 'user';
  if (t.indexOf('notification') === 0) return 'bell';
  return 'activity';
}

function emptyState(iconName, title, text, action) {
  return '<div class="empty"><div class="empty-icon">' + icon(iconName, 22) + '</div>' +
    '<div class="empty-title">' + esc(title) + '</div>' +
    '<div class="empty-text">' + esc(text) + '</div>' + (action || '') + '</div>';
}

function errorBlock(message) {
  return '<div class="error-banner">' + icon('alert', 16) + '<div>' + esc(message) + '</div></div>';
}

function pageHead(eyebrowText, title, sub, actions) {
  return '<div class="page-head"><div class="page-head-main">' +
    '<div class="eyebrow">' + esc(eyebrowText) + '</div>' +
    '<h1 class="page-title">' + esc(title) + '</h1>' +
    (sub ? '<p class="page-sub">' + esc(sub) + '</p>' : '') +
    '</div>' + (actions ? '<div class="page-actions">' + actions + '</div>' : '') + '</div>';
}

function renderViewHtml(html) {
  const view = document.getElementById('view');
  if (view) view.innerHTML = html;
}

function loadingView(title, sub) {
  renderViewHtml(pageHead('Workspace', title, sub) +
    '<div class="loading-grid">' +
    Array.from({ length: 5 }, function () {
      return '<div class="loading-card"><div class="skeleton skeleton-line" style="width:60%"></div>' +
        '<div class="skeleton skeleton-line" style="width:35%;height:26px;margin-top:18px"></div></div>';
    }).join('') +
    '</div><div class="card"><div class="card-body"><div class="skeleton skeleton-line" style="width:40%"></div>' +
    '<div class="skeleton skeleton-line" style="width:90%"></div>' +
    '<div class="skeleton skeleton-line" style="width:75%"></div></div></div>');
}

/* Toast */
let toastTimer = null;
function toast(message, kind) {
  const el = document.getElementById('toast');
  if (!el) return;
  el.className = 'toast show' + (kind ? ' ' + kind : '');
  el.textContent = message;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(function () { el.className = 'toast'; }, 4200);
}

/* ------------------------------------------------------------------ *
 * API layer ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â bearer auth, one refresh attempt, honest errors
 * ------------------------------------------------------------------ */

async function refreshAccess() {
  if (!state.refresh) return false;
  const res = await fetch(API_BASE + '/api/v1/auth/refresh', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: state.refresh }),
  }).catch(function () { return null; });
  if (!res || !res.ok) {
    clearTokens();
    state.me = null;
    toast('Your session has expired. Please sign in again.', 'error');
    if (currentRoute() !== 'login') navigate('login');
    return false;
  }
  const data = await res.json().catch(function () { return null; });
  if (!data || !data.access_token) return false;
  storeTokens(data);
  return true;
}

let refreshInFlight = null;
function refreshOnce() {
  if (!refreshInFlight) {
    refreshInFlight = refreshAccess().then(function (v) { refreshInFlight = null; return v; },
      function () { refreshInFlight = null; return false; });
  }
  return refreshInFlight;
}

async function api(path, options) {
  options = options || {};
  const headers = {};
  if (options.body !== undefined) headers['Content-Type'] = 'application/json';
  if (state.access && !options.noAuth) headers.Authorization = 'Bearer ' + state.access;

  let response;
  try {
    response = await fetch(API_BASE + path, {
      method: options.method || 'GET',
      headers: headers,
      body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
    });
  } catch (e) {
    throw new Error('Cannot reach the NOVARA API at ' + API_BASE + '. Check that the API server is running.');
  }

  if (response.status === 401 && !options.skipRefresh && !options._retried && state.refresh) {
    const refreshed = await refreshOnce();
    if (refreshed) {
      const retry = Object.assign({}, options, { _retried: true });
      return api(path, retry);
    }
  }

  if (!response.ok) {
    let raw = null;
    try { raw = await response.json(); } catch (e) { /* keep status text */ }
    let detail = raw && raw.detail !== undefined ? raw.detail : (raw && raw.message) || response.statusText;
    const error = new Error(errMessage({ detail: detail, message: '' }));
    error.status = response.status;
    error.detail = detail;
    throw error;
  }
  if (response.status === 204) return null;
  const text = await response.text();
  return text ? JSON.parse(text) : null;
}

async function fetchAll(path, pageSize) {
  pageSize = pageSize || 100;
  const separator = path.indexOf('?') === -1 ? '?' : '&';
  const all = [];
  for (let page = 0; page < 50; page += 1) {
    const rows = await api(path + separator + 'skip=' + (page * pageSize) + '&limit=' + pageSize);
    if (!Array.isArray(rows)) break;
    all.push.apply(all, rows);
    if (rows.length < pageSize) break;
  }
  return all;
}

/* ------------------------------------------------------------------ *
 * Token storage and identity
 * ------------------------------------------------------------------ */

function storeTokens(data) {
  state.access = data.access_token || '';
  state.refresh = data.refresh_token || '';
  if (data.workspace_id) state.workspaceId = data.workspace_id;
  localStorage.setItem(KEYS.access, state.access);
  localStorage.setItem(KEYS.refresh, state.refresh);
  localStorage.setItem(KEYS.workspace, state.workspaceId);
}

function clearTokens() {
  stopNotificationStream();
  stopTicketStream();
  state.access = '';
  state.refresh = '';
  state.workspaceId = '';
  localStorage.removeItem(KEYS.access);
  localStorage.removeItem(KEYS.refresh);
  localStorage.removeItem(KEYS.workspace);
}

async function loadMyWorkspaces() {
  try {
    state.workspaces = await api('/api/v1/workspaces') || [];
    state.workspaceError = '';
  } catch (e) {
    state.workspaces = [];
    state.workspaceError = errMessage(e);
  }
}

/* ------------------------------------------------------------------ *
 * Form building helpers
 * ------------------------------------------------------------------ */

function field(name, label, options) {
  options = options || {};
  const type = options.type || 'text';
  let control;
  if (type === 'textarea') {
    control = '<textarea class="textarea" id="' + attr(name) + '" name="' + attr(name) +
      '" placeholder="' + attr(options.placeholder || '') + '"' + (options.required ? ' required' : '') +
      '>' + esc(options.value || '') + '</textarea>';
  } else if (type === 'select') {
    control = '<select class="select" id="' + attr(name) + '" name="' + attr(name) + '"' +
      (options.required ? ' required' : '') + '>' + (options.options || '') + '</select>';
  } else {
    control = '<input class="input" type="' + attr(type) + '" id="' + attr(name) + '" name="' + attr(name) +
      '" value="' + attr(options.value || '') + '" placeholder="' + attr(options.placeholder || '') + '"' +
      (options.required ? ' required' : '') + (options.min ? ' min="' + attr(options.min) + '"' : '') +
      (options.step ? ' step="' + attr(options.step) + '"' : '') +
      (options.autocomplete ? ' autocomplete="' + attr(options.autocomplete) + '"' : '') + '>';
  }
  return '<div class="field' + (options.span ? ' span-2' : '') + '"><label for="' + attr(name) + '">' +
    esc(label) + '</label>' + control + (options.hint ? '<div class="hint">' + esc(options.hint) + '</div>' : '') + '</div>';
}

function checkboxField(name, label, checked, hint) {
  return '<div class="field span-2"><label class="checkbox" for="' + attr(name) + '">' +
    '<input type="checkbox" id="' + attr(name) + '" name="' + attr(name) + '"' + (checked ? ' checked' : '') + '> ' +
    esc(label) + '</label>' + (hint ? '<div class="hint">' + esc(hint) + '</div>' : '') + '</div>';
}

function selectOptions(items, selected) {
  return items.map(function (item) {
    const value = Array.isArray(item) ? item[0] : item;
    const label = Array.isArray(item) ? item[1] : item;
    return '<option value="' + attr(value) + '"' + (String(selected) === String(value) ? ' selected' : '') +
      '>' + esc(label) + '</option>';
  }).join('');
}

function clearFormError(form) {
  if (!form) return;
  const old = form.querySelector('.form-error');
  if (old) old.remove();
}

function setFormError(form, message) {
  if (!form) return;
  clearFormError(form);
  const div = document.createElement('div');
  div.className = 'form-error';
  div.textContent = message;
  form.insertBefore(div, form.firstChild);
}

/* ------------------------------------------------------------------ *
 * Modal system
 * ------------------------------------------------------------------ */

function openModal(options) {
  const root = document.getElementById('modal-root');
  if (!root) return;
  root.innerHTML = '<div class="modal-backdrop" data-action="close-modal"></div>' +
    '<div class="modal' + (options.wide ? ' modal--wide' : '') + '" role="dialog" aria-modal="true" aria-label="' +
    attr(options.title) + '"><div class="modal-head"><div class="modal-head-main">' +
    '<div class="modal-title">' + esc(options.title) + '</div>' +
    (options.sub ? '<div class="modal-sub">' + esc(options.sub) + '</div>' : '') +
    '</div><button class="modal-close" data-action="close-modal" aria-label="Close dialog">' +
    icon('close', 18) + '</button></div><div class="modal-body">' + (options.body || '') + '</div></div>';
  document.body.classList.add('modal-open');
  const first = root.querySelector('input, select, textarea');
  if (first) first.focus();
}

function closeModal() {
  const root = document.getElementById('modal-root');
  if (root) root.innerHTML = '';
  document.body.classList.remove('modal-open');
}

function openConfirm(title, message, label, onConfirm, danger) {
  state.pendingConfirm = onConfirm;
  openModal({
    title: title,
    body: '<p class="small muted">' + esc(message) + '</p><form data-form="confirm">' +
      '<div class="form-actions"><button type="button" class="btn" data-action="close-modal">Cancel</button>' +
      '<button type="submit" class="btn ' + (danger ? 'btn--danger' : 'btn--primary') + '">' +
      esc(label) + '</button></div></form>',
  });
}

/* ------------------------------------------------------------------ *
 * Authentication screens
 * ------------------------------------------------------------------ */

const AUTH_PAGES = {
  login: {
    form: 'login',
    title: 'Welcome back',
    sub: 'Sign in to your NOVARA workspace.',
    submit: 'Sign in',
    fields: field('email', 'Email', { type: 'email', required: true, placeholder: 'you@company.com', autocomplete: 'email' }) +
      field('password', 'Password', { type: 'password', required: true, placeholder: 'Your password', autocomplete: 'current-password' }),
    links: '<a href="#/reset-request">Forgot password?</a><a href="#/register">Create an account</a>',
    note: 'Fresh installation? <a href="#/bootstrap">Complete first-run setup</a>.',
  },
  register: {
    form: 'register',
    title: 'Create your account',
    sub: 'A personal workspace is created for you automatically.',
    submit: 'Create account',
    fields: field('display_name', 'Full name', { required: true, placeholder: 'Alex Morgan', autocomplete: 'name' }) +
      field('email', 'Work email', { type: 'email', required: true, placeholder: 'you@company.com', autocomplete: 'email' }) +
      field('password', 'Password', { type: 'password', required: true, min: '8', placeholder: 'At least 8 characters', autocomplete: 'new-password' }),
    links: '<a href="#/login">Already have an account? Sign in</a>',
    note: 'Registration creates a new workspace owned by your account.',
  },
  bootstrap: {
    form: 'bootstrap',
    title: 'Set up NOVARA',
    sub: 'First-run setup creates the owner account and the first workspace.',
    submit: 'Complete setup',
    fields: field('workspace_name', 'Workspace name', { required: true, placeholder: 'Acme Inc.', span: true }) +
      field('display_name', 'Your name', { required: true, placeholder: 'Alex Morgan' }) +
      field('email', 'Owner email', { type: 'email', required: true, placeholder: 'you@company.com', autocomplete: 'email' }) +
      field('password', 'Password', { type: 'password', required: true, min: '8', placeholder: 'At least 8 characters', autocomplete: 'new-password', span: true }),
    links: '<a href="#/login">Back to sign in</a>',
    note: 'Setup can only be completed once. Existing installations return an error here.',
  },
  'reset-request': {
    form: 'reset-request',
    title: 'Reset your password',
    sub: 'We will create a single-use reset token for your account.',
    submit: 'Request reset token',
    fields: field('email', 'Account email', { type: 'email', required: true, placeholder: 'you@company.com', autocomplete: 'email', span: true }),
    links: '<a href="#/login">Back to sign in</a>',
    note: 'No email is sent by the API. In development mode the token is returned on screen.',
  },
  'reset-confirm': {
    form: 'reset-confirm',
    title: 'Choose a new password',
    sub: 'Enter the single-use token and a new password.',
    submit: 'Reset password',
    fields: field('token', 'Reset token', { required: true, placeholder: 'Paste your token', span: true }) +
      field('new_password', 'New password', { type: 'password', required: true, min: '8', placeholder: 'At least 8 characters', autocomplete: 'new-password', span: true }),
    links: '<a href="#/login">Back to sign in</a>',
    note: 'Resetting your password revokes every active session.',
  },
};

const STORY_FEATURES = [
  ['layers', 'One customer record', 'Contacts, leads, tasks and notes share a single identity.'],
  ['activity', 'A real audit trail', 'Every consequential action is an append-only event.'],
  ['shield', 'Authority, scoped', 'Workspace roles decide exactly what each person can do.'],
];

function renderAuth(route, initialError) {
  const page = AUTH_PAGES[route] || AUTH_PAGES.login;
  const app = document.getElementById('app');
  app.innerHTML = '<div class="auth-shell">' +
    '<section class="auth-story"><div class="auth-story-inner">' +
    '<div class="brand"><div class="brand-mark">N</div><div><div class="brand-name">NOVARA</div>' +
    '<div class="brand-sub">Business operating system</div></div></div>' +
    '<div style="margin-top:72px"><h2 class="auth-claim">Everything Connected.<br><em>Everything Under Control.</em></h2>' +
    '<p class="auth-lede">One calm place for your customer records, follow-up work and the events that connect them.</p>' +
    '<div class="auth-features">' + STORY_FEATURES.map(function (f) {
      return '<div class="auth-feature"><div class="auth-feature-icon">' + icon(f[0], 17) + '</div><div>' +
        '<div class="auth-feature-title">' + esc(f[1]) + '</div><div class="auth-feature-text">' + esc(f[2]) + '</div></div></div>';
    }).join('') + '</div></div></div>' +
    '<div class="auth-story-foot">' + icon('shield', 14) + ' NOVARA Ãƒâ€šÃ‚Â· Everything Connected. Everything Under Control.</div>' +
    '</section><main class="auth-panel"><div class="auth-card">' +
    '<div class="brand"><div class="brand-mark">N</div><div><div class="brand-name">NOVARA</div>' +
    '<div class="brand-sub">Business operating system</div></div></div>' +
    '<h1 class="auth-title">' + esc(page.title) + '</h1><p class="auth-sub">' + esc(page.sub) + '</p>' +
    '<form class="auth-form" data-form="' + attr(page.form) + '">' + page.fields +
    '<button class="btn btn--primary btn--block" type="submit">' + esc(page.submit) + icon('arrowRight', 16) + '</button>' +
    '</form><div class="auth-links">' + page.links + '</div>' +
    '<div class="auth-alt">' + page.note + '</div></div></main></div><div id="modal-root"></div>';
  if (initialError) setFormError(document.querySelector('.auth-form'), initialError);
}

/* ------------------------------------------------------------------ *
 * Application shell
 * ------------------------------------------------------------------ */

const NAV = [
  { group: 'Workspace', items: [
    { route: 'dashboard', label: 'Overview', icon: 'home' },
    { route: 'search', label: 'Universal search', icon: 'search', perm: P.contactRead },
    { route: 'insights', label: 'Insights', icon: 'target', perm: P.eventRead },
    { route: 'activity', label: 'Agent activity', icon: 'activity', perm: P.eventRead },
  ] },
  { group: 'Relationships', items: [
    { route: 'contacts', label: 'Contacts', icon: 'users', perm: P.contactRead },
    { route: 'companies', label: 'Companies', icon: 'building', perm: P.companyRead },
    { route: 'leads', label: 'Leads', icon: 'target', perm: P.leadRead },
    { route: 'deals', label: 'Sales pipeline', icon: 'tag', perm: P.contactRead },
    { route: 'inbox', label: 'Customer inbox', icon: 'mail', perm: P.contactRead },
    { route: 'documents', label: 'Documents', icon: 'archive', perm: P.documentRead },
    { route: 'document-engagement', label: 'Document engagement', icon: 'insights', perm: P.documentRead },
  ] },
  { group: 'Operations', items: [
    { route: 'tasks', label: 'Tasks', icon: 'checkSquare', perm: P.taskRead },
    { route: 'projects', label: 'Projects', icon: 'folder', perm: P.taskRead },
    { route: 'wiki-pages', label: 'Wiki pages', icon: 'note', perm: P.taskRead },
    { route: 'work-item-planning', label: 'Work-item planning', icon: 'layers', perm: P.taskRead },
    { route: 'work-collab', label: 'Work collaboration', icon: 'user', perm: P.taskRead },
    { route: 'advanced-experiments', label: 'Advanced experimentation', icon: 'insights', perm: P.contactRead },
    { route: 'flag-governance', label: 'Flag governance', icon: 'toggleLeft', perm: P.manageSettings },
    { route: 'access-governance', label: 'Access governance', icon: 'shield', perm: P.manageSettings },
    { route: 'support-reporting', label: 'Support reporting', icon: 'insights', perm: P.contactRead },
    { route: 'campaigns', label: 'Campaign Studio', icon: 'layers', perm: P.contactRead },
    { route: 'marketing-content', label: 'Marketing content', icon: 'layers', perm: P.contactRead },
    { route: 'surveys', label: 'Feedback Studio', icon: 'note', perm: P.contactRead },
    { route: 'search-indexes', label: 'Search indexes', icon: 'search', perm: P.contactRead },
    { route: 'search-advanced', label: 'Advanced search', icon: 'insights', perm: P.contactRead },
    { route: 'notification-workflows', label: 'Notification workflows', icon: 'bell', perm: P.contactRead },
    { route: 'notification-automation', label: 'Notification automation', icon: 'activity', perm: P.contactRead },
    { route: 'sales-engagement', label: 'Sales engagement', icon: 'target', perm: P.contactRead },
    { route: 'conversation-ops', label: 'Conversation ops', icon: 'inbox', perm: P.contactRead },
    { route: 'experiment-exposure', label: 'Experiment exposure', icon: 'zap', perm: P.contactRead },
    { route: 'email-engagement', label: 'Email engagement', icon: 'mail', perm: P.contactRead },
    { route: 'feedback-intelligence', label: 'Feedback intelligence', icon: 'layers', perm: P.contactRead },
    { route: 'experiment-stats', label: 'Experiment statistics', icon: 'insights', perm: P.contactRead },
    { route: 'experiment-ops', label: 'Experiment operations', icon: 'layers', perm: P.contactRead },
    { route: 'experiment-queries', label: 'Experiment queries', icon: 'search', perm: P.contactRead },
    { route: 'experiment-platform', label: 'Experiment platform', icon: 'settings', perm: P.contactRead },
    { route: 'experiment-delivery', label: 'Experiment delivery', icon: 'activity', perm: P.contactRead },
    { route: 'survey-delivery', label: 'Survey delivery', icon: 'checkSquare', perm: P.contactRead },
    { route: 'drafts', label: 'Outreach drafts', icon: 'mail', perm: P.outreachRead },
    { route: 'agents', label: 'Agent center', icon: 'zap', perm: P.eventRead },
    { route: 'jobs', label: 'Job queue', icon: 'activity', perm: P.eventRead },
    { route: 'adapters', label: 'Adapters', icon: 'link', perm: P.eventRead },
    { route: 'operations', label: 'System health', icon: 'settings', perm: P.eventRead },
    { route: 'integrations', label: 'Integrations', icon: 'link', perm: P.contactRead },
    { route: 'notifications', label: 'Notifications', icon: 'bell', perm: P.notificationRead, unread: true },
  ] },
  { group: 'Account', items: [
    { route: 'workspaces', label: 'Workspaces', icon: 'grid' },
    { route: 'profile', label: 'My profile', icon: 'user' },
    { route: 'settings', label: 'Settings', icon: 'settings' },
  ] },
];

const ROUTE_META = {
  dashboard: ['Overview', 'Workspace'],
  search: ['Universal search', 'Workspace'],
  insights: ['Insights', 'Workspace'],
  contacts: ['Contacts', 'Relationships'],
  companies: ['Companies', 'Relationships'],
  leads: ['Leads', 'Relationships'],
  deals: ['Sales pipeline', 'Relationships'],
  inbox: ['Customer inbox', 'Relationships'],
  tasks: ['Tasks', 'Operations'],
  projects: ['Projects', 'Operations'],
  'wiki-pages': ['Wiki pages', 'Operations'],
  'work-item-planning': ['Work-item planning', 'Operations'],
  'work-collab': ['Work collaboration', 'Operations'],
  'advanced-experiments': ['Advanced experimentation', 'Operations'],
  'flag-governance': ['Flag governance', 'Operations'],
  'access-governance': ['Access governance', 'Operations'],
  'support-reporting': ['Support reporting', 'Operations'],
  campaigns: ['Campaign Studio', 'Operations'],
  'marketing-content': ['Marketing content', 'Operations'],
  surveys: ['Feedback Studio', 'Operations'],
  'search-indexes': ['Search indexes', 'Operations'],
  'search-advanced': ['Advanced search', 'Operations'],
  'notification-workflows': ['Notification workflows', 'Operations'],
  'notification-automation': ['Notification automation', 'Operations'],
  'sales-engagement': ['Sales engagement', 'Operations'],
  'conversation-ops': ['Conversation ops', 'Operations'],
  'experiment-exposure': ['Experiment exposure', 'Operations'],
  'email-engagement': ['Email engagement', 'Operations'],
  'feedback-intelligence': ['Feedback intelligence', 'Operations'],
  'experiment-stats': ['Experiment statistics', 'Operations'],
  'experiment-ops': ['Experiment operations', 'Operations'],
  'experiment-queries': ['Experiment queries', 'Operations'],
  'experiment-platform': ['Experiment platform', 'Operations'],
  'experiment-delivery': ['Experiment delivery', 'Operations'],
  'survey-delivery': ['Survey delivery', 'Operations'],
  'document-engagement': ['Document engagement', 'Operations'],
  drafts: ['Outreach drafts', 'Operations'],
  agents: ['Agent center', 'Operations'],
  jobs: ['Job queue', 'Operations'],
  adapters: ['Adapters', 'Operations'],
  operations: ['System health', 'Operations'],
  integrations: ['Integrations', 'Operations'],
  notifications: ['Notifications', 'Operations'],
  activity: ['Agent activity', 'Workspace'],
  workspaces: ['Workspaces', 'Account'],
  profile: ['My profile', 'Account'],
  settings: ['Settings', 'Account'],
};

function routeMeta(route) {
  if (route.indexOf('contacts/') === 0) return ['Contact detail', 'Relationships'];
  if (route.indexOf('deals/') === 0) return ['Deal detail', 'Relationships'];
  if (route.indexOf('inbox/') === 0) return ['Ticket detail', 'Relationships'];
  if (route.indexOf('campaigns/') === 0) return ['Campaign detail', 'Operations'];
  if (route.indexOf('surveys/') === 0) return ['Survey detail', 'Operations'];
  if (route.indexOf('search-indexes/') === 0) return ['Search index', 'Operations'];
  return ROUTE_META[route] || ['Overview', 'Workspace'];
}

function renderNav(route) {
  return NAV.map(function (group) {
    const items = group.items.filter(function (item) { return !item.perm || can(item.perm); });
    if (!items.length) return '';
    return '<div class="nav-group-label">' + esc(group.group) + '</div>' + items.map(function (item) {
      const active = route === item.route || (item.route === 'contacts' && route.indexOf('contacts/') === 0);
      let count = '';
      if (item.unread) {
        const unread = state.caches.notifications.filter(function (n) { return !n.read; }).length;
        if (unread) count = '<span class="nav-count" data-unread-count>' + unread + '</span>';
      }
      return '<a class="nav-item' + (active ? ' active' : '') + '" href="#/' + item.route + '">' +
        '<span class="nav-icon">' + icon(item.icon, 17) + '</span><span>' + esc(item.label) + '</span>' + count + '</a>';
    }).join('');
  }).join('');
}

function renderApp() {
  const route = currentRoute();
  const meta = routeMeta(route);
  const user = state.me ? state.me.user : { display_name: 'User', email: '' };
  const workspaceName = state.me ? state.me.workspace_name : 'Workspace';
  const unread = state.caches.notifications.filter(function (n) { return !n.read; }).length;
  const app = document.getElementById('app');
  app.innerHTML = '<div class="app">' +
    '<aside class="sidebar"><div class="brand"><div class="brand-mark">N</div><div>' +
    '<div class="brand-name">NOVARA</div><div class="brand-sub">Business operating system</div></div></div>' +
    '<nav class="nav-scroll">' + renderNav(route) + '</nav>' +
    '<div class="sidebar-foot"><button class="side-user" data-action="nav" data-route="profile">' +
    avatar(user.display_name || user.email, 'sm') + '<div style="min-width:0">' +
    '<div class="side-user-name">' + esc(user.display_name || 'User') + '</div>' +
    '<div class="side-user-mail">' + esc(user.email || '') + '</div></div>' +
    '<span class="chev">' + icon('chevronRight', 15) + '</span></button></div></aside>' +
    '<div class="scrim" data-action="close-sidebar"></div>' +
    '<div class="main-wrap"><header class="topbar">' +
    '<button class="topbar-btn menu-btn" data-action="toggle-sidebar" aria-label="Open navigation">' + icon('menu', 18) + '</button>' +
    '<div><div class="topbar-title">' + esc(meta[0]) + '</div><div class="topbar-crumb">' + esc(meta[1]) + ' Ãƒâ€šÃ‚Â· ' +
    esc(state.me ? cap(state.me.role) : '') + '</div></div><div class="topbar-spacer"></div>' +
    '<div class="search-box"><div class="search-input-wrap">' + icon('search', 16) +
    '<input id="global-search" type="search" placeholder="Search everythingÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦" autocomplete="off" data-input="global-search" aria-label="Global search">' +
    '<span class="search-kbd">/</span></div><div id="search-results-host"></div></div>' +
    '<button class="workspace-chip" data-action="nav" data-route="workspaces" title="Switch workspace">' +
    '<span class="workspace-chip-icon">' + icon('grid', 14) + '</span>' +
    '<span class="workspace-chip-name">' + esc(workspaceName) + '</span>' + icon('chevronDown', 14) + '</button>' +
    (can(P.notificationRead) ? '<a class="topbar-btn" href="#/notifications" aria-label="Notifications">' + icon('bell', 18) +
      (unread ? '<span class="dot-unread" data-unread-dot></span>' : '') + '</a>' : '') +
    '<button class="topbar-btn" data-action="nav" data-route="profile" aria-label="My profile">' +
    avatar(user.display_name || user.email, 'sm') + '</button>' +
    '</header><main class="view" id="view"></main></div></div><div id="modal-root"></div>';
}

function updateUnreadBadge() {
  const unread = state.caches.notifications.filter(function (n) { return !n.read; }).length;
  document.querySelectorAll('[data-unread-count]').forEach(function (el) {
    el.textContent = unread;
    if (!unread) el.remove();
  });
  document.querySelectorAll('[data-unread-dot]').forEach(function (el) { if (!unread) el.remove(); });
}

async function loadNotificationsSilently() {
  if (!can(P.notificationRead)) return;
  try {
    state.caches.notifications = await api(apiW('/notifications')) || [];
    updateUnreadBadge();
  } catch (e) { /* the notifications screen shows its own error */ }
}

function stopNotificationStream() {
  if (state.notifStreamAbort) {
    try { state.notifStreamAbort.abort(); } catch (e) { /* already closed */ }
    state.notifStreamAbort = null;
  }
}

/* Real-time notification counts. Auth stays in the header, so native EventSource
 * cannot be used; a streaming fetch reads the server-sent feed instead. */
async function subscribeNotificationStream() {
  stopNotificationStream();
  if (!state.access || !state.workspaceId || !can(P.notificationRead)) return;
  const controller = new AbortController();
  state.notifStreamAbort = controller;
  try {
    const response = await fetch(apiW('/notifications/stream'), {
      headers: { Authorization: 'Bearer ' + state.access, Accept: 'text/event-stream' },
      signal: controller.signal,
      cache: 'no-store',
    });
    if (!response.ok || !response.body) return;
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    for (;;) {
      const chunk = await reader.read();
      if (chunk.done) break;
      buffer += decoder.decode(chunk.value, { stream: true });
      const blocks = buffer.split('\n\n');
      buffer = blocks.pop() || '';
      for (const block of blocks) {
        const dataLine = block.split('\n').find(function (line) { return line.indexOf('data:') === 0; });
        if (!dataLine) continue;
        try {
          const snapshot = JSON.parse(dataLine.slice(5).trim());
          const previous = state.notifCounts || {};
          state.notifCounts = snapshot;
          if (snapshot.unread !== previous.unread || snapshot.unseen !== previous.unseen) {
            loadNotificationsSilently();
          }
        } catch (e) { /* ignore malformed heartbeat */ }
      }
    }
  } catch (e) { /* stream closed on navigation or sign-out */ }
  finally {
    if (state.notifStreamAbort === controller) state.notifStreamAbort = null;
  }
}

function stopTicketStream() {
  if (state.ticketStreamAbort) {
    try { state.ticketStreamAbort.abort(); } catch (e) { /* already closed */ }
    state.ticketStreamAbort = null;
  }
}

/* Real-time queue counts for the shared inbox. The bearer token stays in the
 * header, so this uses a streaming fetch rather than native EventSource. */
async function subscribeTicketStream() {
  stopTicketStream();
  if (!state.access || !state.workspaceId || !can(P.contactRead)) return;
  const controller = new AbortController();
  state.ticketStreamAbort = controller;
  try {
    const response = await fetch(apiW('/tickets/stream'), {
      headers: { Authorization: 'Bearer ' + state.access, Accept: 'text/event-stream' },
      signal: controller.signal,
      cache: 'no-store',
    });
    if (!response.ok || !response.body) return;
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    for (;;) {
      const chunk = await reader.read();
      if (chunk.done) break;
      buffer += decoder.decode(chunk.value, { stream: true });
      const blocks = buffer.split('\n\n');
      buffer = blocks.pop() || '';
      for (const block of blocks) {
        const dataLine = block.split('\n').find(function (line) { return line.indexOf('data:') === 0; });
        if (!dataLine) continue;
        try {
          const snapshot = JSON.parse(dataLine.slice(5).trim());
          state.ticketCounts = snapshot;
          const label = document.querySelector('[data-ticket-counts]');
          if (label) label.textContent = ticketCountSummary(snapshot);
          if (currentRoute().indexOf('inbox') === 0) loadView();
        } catch (e) { /* ignore malformed heartbeat */ }
      }
    }
  } catch (e) { /* stream closed on navigation or sign-out */ }
  finally {
    if (state.ticketStreamAbort === controller) state.ticketStreamAbort = null;
  }
}

function ticketCountSummary(counts) {
  if (!counts) return '';
  return counts.open + ' open, ' + counts.pending + ' pending, ' +
    counts.unassigned + ' unassigned of ' + counts.total + '.';
}

/* ------------------------------------------------------------------ *
 * View router
 * ------------------------------------------------------------------ */

async function loadView() {
  const route = currentRoute();
  const token = ++state.viewToken;
  const parts = route.split('/');

  if (parts[0] === 'contacts' && parts[1]) return loadContactDetail(parts[1], token);
  if (parts[0] === 'deals' && parts[1]) return loadDealDetail(parts[1], token);
  if (parts[0] === 'inbox' && parts[1]) return loadTicketDetail(parts[1], token);
  if (parts[0] === 'projects' && parts[1]) return loadProjectDetail(parts[1], token);
  if (parts[0] === 'documents' && parts[1]) return loadDocumentDetail(parts[1], token);
  if (parts[0] === 'campaigns' && parts[1]) return loadCampaignDetail(parts[1], token);
  if (parts[0] === 'surveys' && parts[1]) return loadSurveyDetail(parts[1], token);
  switch (parts[0]) {
    case 'dashboard': return loadDashboard(token);
    case 'search': return loadSearch(token);
    case 'insights': return loadInsights(token);
    case 'contacts': return loadContactsPage(token);
    case 'companies': return loadCompanies(token);
    case 'leads': return loadLeads(token);
    case 'deals': return loadDeals(token);
    case 'inbox': return loadInbox(token);
    case 'tasks': return loadTasks(token);
    case 'projects': return loadProjects(token);
    case 'wiki-pages': return loadWikiPages(token);
    case 'work-item-planning': return loadWorkItemPlanning(token);
    case 'work-collab': return loadWorkCollaboration(token);
    case 'advanced-experiments': return loadAdvancedExperiments(token);
    case 'flag-governance': return loadFlagGovernance(token);
    case 'access-governance': return loadAccessGovernance(token);
    case 'support-reporting': return loadSupportReporting(token);
    case 'documents': return loadDocuments(token);
    case 'document-engagement': return loadDocumentEngagement(token);
    case 'campaigns': return loadCampaigns(token);
    case 'marketing-content': return loadMarketingContent(token);
    case 'surveys': return loadSurveys(token);
    case 'search-indexes': return loadSearchIndexes(token);
    case 'search-advanced': return loadSearchAdvanced(token);
    case 'notification-workflows': return loadNotificationWorkflows(token);
    case 'notification-automation': return loadNotificationAutomation(token);
    case 'sales-engagement': return loadSalesEngagement(token);
    case 'conversation-ops': return loadConversationOps(token);
    case 'experiment-exposure': return loadExperimentExposure(token);
    case 'email-engagement': return loadEmailEngagement(token);
    case 'feedback-intelligence': return loadFeedbackIntelligence(token);
    case 'experiment-stats': return loadExperimentStats(token);
    case 'experiment-ops': return loadExperimentOps(token);
    case 'experiment-queries': return loadExperimentQueries(token);
    case 'experiment-platform': return loadExperimentPlatform(token);
    case 'experiment-delivery': return loadExperimentDelivery(token);
    case 'survey-delivery': return loadSurveyDelivery(token);
    case 'notifications': return loadNotifications(token);
    case 'activity': return loadActivity(token);
    case 'drafts': return loadDrafts(token);
    case 'agents': return loadAgents(token);
    case 'jobs': return loadJobs(token);
    case 'adapters': return loadAdapters(token);
    case 'operations': return loadOperations(token);
    case 'integrations': return loadIntegrations(token);
    case 'workspaces': return loadWorkspacesPage(token);
    case 'profile': return loadProfile(token);
    case 'settings': return loadSettings(token);
    default: return loadDashboard(token);
  }
}

/* ------------------------------------------------------------------ *
 * Governance notices ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â shown wherever a build makes no external calls
 * ------------------------------------------------------------------ */

function governanceNote(text) {
  return '<div class="info-banner">' + icon('info', 16) + '<div>' + esc(text) + '</div></div>';
}

/* ------------------------------------------------------------------ *
 * Agent center ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â governed configuration and runs, no external AI calls
 * ------------------------------------------------------------------ */

async function loadAgents(token) {
  if (!can(P.eventRead)) {
    renderViewHtml(pageHead('Operations', 'Agent center', '') +
      errorBlock('Your role does not include event access, which is required to view the agent center.'));
    return;
  }
  loadingView('Agent center', 'Governed agent configuration and runs');
  const results = await Promise.allSettled([
    api(apiW('/agents')),
    api(apiW('/agents/runs')),
  ]);
  if (token !== state.viewToken) return;
  if (results[0].status === 'rejected') {
    renderViewHtml(pageHead('Operations', 'Agent center', '') + errorBlock(errMessage(results[0].reason)));
    return;
  }
  const agents = results[0].value || [];
  const runs = results[1].status === 'fulfilled' ? (results[1].value || []) : [];
  state.caches.agents = agents;
  state.caches.agentRuns = runs;
  const manage = can(P.outreachApprove);
  const runError = results[1].status === 'rejected'
    ? errorBlock('Runs could not be loaded: ' + errMessage(results[1].reason)) : '';

  const nameOf = function (agentId) {
    const found = agents.find(function (a) { return a.id === agentId; });
    return found ? found.name : 'Agent ' + String(agentId || '').slice(0, 8);
  };

  let html = pageHead('Operations', 'Agent center',
    'Configuration and run history recorded for this workspace.',
    manage ? '<button class="btn btn--primary" data-action="create-agent">' + icon('plus', 16) + ' New agent</button>' : '');
  html += governanceNote('No external AI provider is called in this build. The agent center records and governs agent activity; it does not fabricate AI output.');
  html += '<div class="stats">' +
    statCard('zap', 'Configured agents', String(agents.length), 'In this workspace') +
    statCard('check', 'Active', String(agents.filter(function (a) { return a.status === 'active'; }).length), 'Can accept runs') +
    statCard('clock', 'Awaiting approval', String(runs.filter(function (r) { return r.status === 'awaiting_approval'; }).length), 'Need a decision', 'amber') +
    statCard('activity', 'Total runs', String(runs.length), 'Retained for audit', 'blue') +
    '</div>' + runError + '<div class="stack">';

  html += '<section class="card"><div class="card-head"><div class="card-head-main">' +
    '<div class="card-title">Agent configurations</div>' +
    '<div class="card-sub">Purpose, model and boundary are recorded before any run is allowed</div></div>' +
    (manage ? '<button class="btn btn--sm" data-action="create-agent">' + icon('plus', 14) + ' New agent</button>' : '') +
    '</div>' + (agents.length
      ? '<div class="table-wrap"><table class="data"><thead><tr><th>Agent</th><th>Purpose</th><th>Model</th><th>Status</th><th>Limit</th><th>Added</th><th></th></tr></thead><tbody>' +
        agents.map(function (a) {
          const buttons = [];
          if (manage) {
            buttons.push('<button class="btn btn--sm" data-action="request-agent-run" data-id="' + attr(a.id) + '" title="Request a run">' + icon('zap', 14) + ' Run</button>');
            buttons.push('<button class="btn btn--sm btn--ghost" data-action="agent-status" data-id="' + attr(a.id) + '" data-status="' + attr(a.status === 'active' ? 'paused' : 'active') + '" title="' + (a.status === 'active' ? 'Pause agent' : 'Resume agent') + '">' + icon(a.status === 'active' ? 'clock' : 'check', 14) + '</button>');
            buttons.push('<button class="btn btn--sm btn--ghost" data-action="edit-agent" data-id="' + attr(a.id) + '" title="Edit agent">' + icon('edit', 14) + '</button>');
            buttons.push('<button class="btn btn--sm btn--ghost" data-action="delete-agent" data-id="' + attr(a.id) + '" title="Delete agent">' + icon('trash', 14) + '</button>');
          }
          return '<tr><td><div class="cell-primary"><div class="cell-title">' + esc(a.name) + '</div>' +
            '<div class="cell-sub mono">' + esc(String(a.id).slice(0, 8)) + '</div></div></td>' +
            '<td class="muted small">' + esc(a.purpose) + '</td>' +
            '<td class="small">' + esc(cap(a.model_provider)) + ' Ãƒâ€šÃ‚Â· ' + esc(a.model_name) + '</td>' +
            '<td>' + statusBadge(a.status) + (a.requires_approval ? ' <span class="badge badge--amber">approval</span>' : '') + '</td>' +
            '<td class="muted small">' + esc(a.max_steps) + ' steps</td>' +
            '<td class="muted small">' + esc(fmtDate(a.created_at)) + '</td>' +
            '<td><div class="row">' + buttons.join('') + '</div></td></tr>';
        }).join('') + '</tbody></table></div>'
      : emptyState('zap', 'No agents configured', 'Add an agent to record its purpose, model and operating boundary.',
        manage ? '<button class="btn btn--primary btn--sm" data-action="create-agent">New agent</button>' : '')) +
    '</section>';

  html += '<section class="card"><div class="card-head"><div class="card-head-main">' +
    '<div class="card-title">Agent runs</div>' +
    '<div class="card-sub">Run records are kept for audit, including approval decisions</div></div></div>' +
    (runs.length
      ? '<div class="table-wrap"><table class="data"><thead><tr><th>Task</th><th>Agent</th><th>Status</th><th>Steps</th><th>Requested</th><th>Finished</th><th></th></tr></thead><tbody>' +
        runs.map(function (r) {
          const buttons = [];
          if (manage && (r.status === 'queued' || r.status === 'running')) {
            buttons.push('<button class="btn btn--sm" data-action="agent-progress" data-id="' + attr(r.id) + '" data-agent="' + attr(r.agent_id) + '">' + icon('activity', 14) + ' Progress</button>');
          }
          if (manage && r.status === 'awaiting_approval') {
            buttons.push('<button class="btn btn--sm btn--primary" data-action="approve-agent-run" data-id="' + attr(r.id) + '" data-agent="' + attr(r.agent_id) + '">' + icon('check', 14) + ' Approve</button>');
          }
          return '<tr><td><div class="cell-title">' + esc(r.task) + '</div>' +
            (r.error ? '<div class="cell-sub">' + esc(r.error) + '</div>' : '') + '</td>' +
            '<td class="small">' + esc(nameOf(r.agent_id)) + '</td>' +
            '<td>' + statusBadge(r.status) + '</td>' +
            '<td class="muted small">' + esc(r.steps_taken) + '</td>' +
            '<td class="muted small">' + esc(fmtDateTime(r.requested_at)) + '</td>' +
            '<td class="muted small">' + esc(r.finished_at ? fmtDateTime(r.finished_at) : 'ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â') + '</td>' +
            '<td><div class="row">' + (buttons.length ? buttons.join('') : '<span class="faint small">ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â</span>') + '</div></td></tr>';
        }).join('') + '</tbody></table></div>'
      : emptyState('activity', 'No runs yet', 'Request a run from an active agent to record governed activity.')) +
    '</section>';

  html += '</div>';
  renderViewHtml(html);
}

/* ------------------------------------------------------------------ *
 * Integrations ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â non-sensitive settings and an honest capability catalog
 * ------------------------------------------------------------------ */

async function loadIntegrations(token) {
  if (!can(P.contactRead)) {
    renderViewHtml(pageHead('Operations', 'Integrations', '') +
      errorBlock('Your role does not include contact access, which is required to view integrations.'));
    return;
  }
  loadingView('Integrations', 'Capability catalog and recording settings');
  const results = await Promise.allSettled([
    api(apiW('/integrations/capabilities')),
    api(apiW('/integrations')),
  ]);
  if (token !== state.viewToken) return;
  if (results[0].status === 'rejected') {
    renderViewHtml(pageHead('Operations', 'Integrations', '') + errorBlock(errMessage(results[0].reason)));
    return;
  }
  const catalog = results[0].value || { providers: [] };
  const configured = results[1].status === 'fulfilled' ? (results[1].value || []) : [];
  const providers = catalog.providers || [];
  state.caches.integrationCatalog = catalog;
  state.caches.integrations = configured;
  const manage = can(P.workspaceManage);
  const byProvider = {};
  configured.forEach(function (row) { byProvider[row.provider] = row; });

  let html = pageHead('Operations', 'Integrations',
    'Providers available to this workspace and the settings recorded for them.',
    '<button class="btn" data-action="refresh-view">' + icon('refresh', 15) + ' Refresh</button>');
  html += governanceNote('No outbound network call is made in this build. Only non-sensitive settings are stored; API keys, tokens, passwords and credentials are never accepted.');
  html += '<div class="stats">' +
    statCard('link', 'Catalog providers', String(providers.length), 'Supported in this build') +
    statCard('check', 'Configured', String(providers.filter(function (p) { return p.configured; }).length), 'Settings recorded', 'green') +
    statCard('clock', 'Disabled', String(providers.filter(function (p) { return p.status === 'disabled'; }).length), 'Not active', 'amber') +
    '</div>' + (results[1].status === 'rejected' ? errorBlock('Saved settings could not be loaded: ' + errMessage(results[1].reason)) : '');

  html += '<section class="card"><div class="card-head"><div class="card-head-main">' +
    '<div class="card-title">Capability catalog</div>' +
    '<div class="card-sub">A recorded setting is not a live adapter</div></div></div>' +
    (providers.length ? '<div class="table-wrap"><table class="data"><thead><tr><th>Provider</th><th>Status</th><th>Configured</th><th>Settings</th><th>Notes</th><th></th></tr></thead><tbody>' +
      providers.map(function (entry) {
        const row = byProvider[entry.provider];
        const keys = row && row.config ? Object.keys(row.config) : [];
        const buttons = [];
        if (manage) {
          buttons.push('<button class="btn btn--sm" data-action="configure-integration" data-provider="' + attr(entry.provider) + '">' + icon(row ? 'edit' : 'plus', 14) + ' ' + (row ? 'Edit' : 'Configure') + '</button>');
          if (row && entry.status !== 'disabled') {
            buttons.push('<button class="btn btn--sm btn--ghost" data-action="disable-integration" data-provider="' + attr(entry.provider) + '" title="Disable integration">' + icon('close', 14) + '</button>');
          }
        }
        return '<tr><td><div class="cell-title">' + esc(entry.display_name) + '</div>' +
          '<div class="cell-sub mono">' + esc(entry.provider) + '</div></td>' +
          '<td>' + statusBadge(entry.status) + '</td>' +
          '<td class="small">' + (entry.configured ? 'Yes' : 'No') + '</td>' +
          '<td class="small">' + (keys.length ? '<span class="mono">' + esc(keys.join(', ')) + '</span>' : '<span class="faint">ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â</span>') + '</td>' +
          '<td class="muted small">' + esc(entry.notes) + '</td>' +
          '<td><div class="row">' + (buttons.length ? buttons.join('') : '<span class="faint small">ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â</span>') + '</div></td></tr>';
      }).join('') + '</tbody></table></div>'
      : emptyState('link', 'No providers listed', 'The capability catalog is empty for this workspace.')) +
    '</section>';

  renderViewHtml(html);
}

/* ------------------------------------------------------------------ *
 * Phase 3 ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â business intelligence aggregates
 * ------------------------------------------------------------------ */

async function loadInsights(token) {
  if (!can(P.eventRead)) { eventAccessBlocked('Insights'); return; }
  loadingView('Insights', 'Business aggregates computed from stored records');
  const results = await Promise.allSettled([
    api(apiW('/analytics/funnel')),
    api(apiW('/analytics/events/volume')),
    api(apiW('/analytics')),
  ]);
  if (token !== state.viewToken) return;
  if (results[0].status === 'rejected') {
    renderViewHtml(pageHead('Workspace', 'Insights', '') + errorBlock(errMessage(results[0].reason)));
    return;
  }
  const funnel = results[0].value || {};
  const volume = results[1].status === 'fulfilled' ? (results[1].value || []) : [];
  const experiments = results[2].status === 'fulfilled' ? (results[2].value || []) : [];
  state.caches.funnel = funnel;
  state.caches.eventVolume = volume;
  state.caches.experiments = experiments;
  const manageExperiments = can(P.workspaceManage);

  const contacts = Number(funnel.contacts || 0);
  const leads = Number(funnel.leads || 0);
  const converted = Number(funnel.converted_leads || 0);
  const tasks = Number(funnel.tasks || 0);
  const rate = leads ? (converted / leads * 100).toFixed(1) + '%' : 'ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â';
  const maxCount = volume.reduce(function (max, row) { return Math.max(max, Number(row.count || 0)); }, 0);

  let html = pageHead('Workspace', 'Insights',
    'Counts are calculated by the API from current workspace rows ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â not cached or estimated.',
    '<button class="btn" data-action="refresh-view">' + icon('refresh', 15) + ' Refresh</button>');
  html += governanceNote('These are descriptive counts of recorded activity. They are not a forecast, and no external analytics service receives data.');
  html += '<div class="stats">' +
    statCard('users', 'Contacts', String(contacts), 'Identities in workspace') +
    statCard('target', 'Leads', String(leads), 'Qualified opportunities') +
    statCard('check', 'Converted leads', String(converted), 'Closed as customers', 'blue') +
    statCard('activity', 'Lead conversion', rate, converted + ' of ' + leads + ' leads') +
    statCard('checkSquare', 'Tasks', String(tasks), 'All workflow tasks') +
    '</div>';

  html += '<div class="stack">';
  html += '<section class="card"><div class="card-head"><div class="card-head-main">' +
    '<div class="card-title">Workflow funnel</div>' +
    '<div class="card-sub">Each stage is an independent count, not a time-series conversion</div></div></div>' +
    '<div class="card-body"><dl class="kv">' +
    '<dt>Contacts identified</dt><dd>' + contacts + '</dd>' +
    '<dt>Leads created</dt><dd>' + leads + '</dd>' +
    '<dt>Leads converted</dt><dd>' + converted + '</dd>' +
    '<dt>Tasks recorded</dt><dd>' + tasks + '</dd>' +
    '</dl></div></section>';

  html += '<section class="card"><div class="card-head"><div class="card-head-main">' +
    '<div class="card-title">Event volume by type</div>' +
    '<div class="card-sub">Grouped from the append-only audit log</div></div></div>' +
    (results[1].status === 'rejected'
      ? errorBlock('Event volume could not be loaded: ' + errMessage(results[1].reason))
      : (volume.length ? '<div class="card-body stack">' + volume.map(function (row) {
          const count = Number(row.count || 0);
          const pct = maxCount ? Math.max(3, Math.round(count / maxCount * 100)) : 0;
          return '<div class="bar-row"><div class="bar-label mono">' + esc(row.event_type) + '</div>' +
            '<div class="bar-track"><div class="bar-fill" style="width:' + pct + '%"></div></div>' +
            '<div class="bar-value">' + count + '</div></div>';
        }).join('') + '</div>'
        : emptyState('activity', 'No events yet', 'Event volume will appear as workflows run.'))) +
    '</section></div>';

  html += '<section class="card"><div class="card-head"><div class="card-head-main">' +
    '<div class="card-title">Experiments</div>' +
    '<div class="card-sub">A hypothesis, a metric and measured results ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â stored in this workspace only</div></div>' +
    (manageExperiments ? '<button class="btn btn--sm btn--primary" data-action="experiment-create">' +
      icon('plus', 14) + ' New experiment</button>' : '') + '</div>' +
    (results[2].status === 'rejected'
      ? errorBlock('Experiments could not be loaded: ' + errMessage(results[2].reason))
      : (experiments.length
        ? '<div class="table-wrap"><table class="data"><thead><tr><th>Name</th><th>Status</th>' +
          '<th>Metric</th><th>Target</th><th></th></tr></thead><tbody>' +
          experiments.map(function (e) {
            return '<tr><td><div class="cell-title">' + esc(e.name) + '</div>' +
              (e.hypothesis ? '<div class="small muted">' + esc(e.hypothesis) + '</div>' : '') + '</td>' +
              '<td>' + statusBadge(e.status) + '</td>' +
              '<td class="mono small">' + esc(e.metric_name) + '</td>' +
              '<td class="small">' + (e.target == null ? 'ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â' : esc(String(e.target))) + '</td>' +
              '<td><div class="cell-actions">' +
              '<button class="btn btn--sm" data-action="experiment-results" data-id="' + attr(e.id) + '">' +
                icon('activity', 13) + ' Results</button>' +
              (manageExperiments
                ? '<button class="btn btn--sm btn--ghost" data-action="experiment-status" data-id="' + attr(e.id) +
                    '" data-status="' + attr(e.status) + '" title="Change status">' + icon('refresh', 13) + '</button>' +
                  '<button class="btn btn--sm btn--ghost" data-action="experiment-edit" data-id="' + attr(e.id) +
                    '" title="Edit experiment">' + icon('edit', 13) + '</button>' +
                  '<button class="btn btn--sm btn--ghost" data-action="experiment-delete" data-id="' + attr(e.id) +
                    '" title="Delete experiment">' + icon('trash', 13) + '</button>'
                : '') + '</div></td></tr>';
          }).join('') + '</tbody></table></div>'
        : emptyState('target', 'No experiments',
            'Create an experiment to record a hypothesis and its measured results.',
            manageExperiments ? '<button class="btn btn--primary" data-action="experiment-create">' +
              icon('plus', 14) + ' New experiment</button>' : ''))) +
    '</section>';
  renderViewHtml(html);
}

/* ------------------------------------------------------------------ *
 * Phase 3 ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â durable jobs, local adapters and system health
 * ------------------------------------------------------------------ */

function eventAccessBlocked(title) {
  renderViewHtml(pageHead('Operations', title, '') +
    errorBlock('Your role does not include event access, which is required for this view.'));
}

async function loadJobs(token) {
  if (!can(P.eventRead)) { eventAccessBlocked('Job queue'); return; }
  loadingView('Job queue', 'Durable local work with retries and dead-lettering');
  const results = await Promise.allSettled([
    api(apiW('/jobs/stats')),
    api(apiW('/jobs?limit=100')),
    api(apiW('/jobs/handlers')),
  ]);
  if (token !== state.viewToken) return;
  if (results[0].status === 'rejected') {
    renderViewHtml(pageHead('Operations', 'Job queue', '') + errorBlock(errMessage(results[0].reason)));
    return;
  }
  const stats = results[0].value || {};
  const jobs = results[1].status === 'fulfilled' ? (results[1].value || []) : [];
  const handlers = results[2].status === 'fulfilled' ? (results[2].value || []) : [];
  state.caches.jobs = jobs;
  state.caches.jobStats = stats;

  let html = pageHead('Operations', 'Job queue',
    'Background work recorded in this workspace and processed by local handlers.',
    '<button class="btn" data-action="job-recover">' + icon('refresh', 15) + ' Recover stale</button>' +
    '<button class="btn btn--primary" data-action="job-run">' + icon('zap', 15) + ' Run worker</button>');
  html += governanceNote('Jobs are durable rows. Retries use exponential backoff and exhausted jobs move to dead-letter. Every handler is local ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â no external system is contacted.');
  html += '<div class="stats">' +
    statCard('clock', 'Queued', String(stats.queued == null ? 'ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â' : stats.queued), 'Waiting for a worker', 'amber') +
    statCard('activity', 'Running', String(stats.running == null ? 'ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â' : stats.running), 'Claimed by a worker', 'blue') +
    statCard('check', 'Succeeded', String(stats.succeeded == null ? 'ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â' : stats.succeeded), 'Completed locally') +
    statCard('alert', 'Dead letter', String(stats.dead_letter == null ? 'ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â' : stats.dead_letter), 'Needs attention', 'amber') +
    statCard('grid', 'Total', String(stats.total == null ? 'ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â' : stats.total), 'All job records') +
    '</div>' + (results[1].status === 'rejected' ? errorBlock('Jobs could not be loaded: ' + errMessage(results[1].reason)) : '');

  html += '<div class="stack">';
  html += '<section class="card"><div class="card-head"><div class="card-head-main">' +
    '<div class="card-title">Registered local handlers</div>' +
    '<div class="card-sub">Only these job types can be processed</div></div></div>' +
    (handlers.length ? '<div class="row">' + handlers.map(function (name) {
      return '<span class="badge badge--blue mono">' + esc(name) + '</span>';
    }).join('') + '</div>' : emptyState('zap', 'No handlers', 'No local job handlers are registered.')) +
    '</section>';

  html += '<section class="card"><div class="card-head"><div class="card-head-main">' +
    '<div class="card-title">Job records</div>' +
    '<div class="card-sub">Newest first Ãƒâ€šÃ‚Â· up to 100 records</div></div></div>' +
    (jobs.length ? '<div class="table-wrap"><table class="data"><thead><tr><th>Type</th><th>Status</th>' +
      '<th>Attempts</th><th>Run at</th><th>Correlation</th><th>Last error</th><th></th></tr></thead><tbody>' +
      jobs.map(function (job) {
        const buttons = [];
        if (job.status === 'queued' || job.status === 'running') {
          buttons.push('<button class="btn btn--sm btn--ghost" data-action="job-cancel" data-id="' + attr(job.id) + '" title="Cancel job">' + icon('close', 14) + '</button>');
        }
        if (job.status === 'dead_letter' || job.status === 'cancelled') {
          buttons.push('<button class="btn btn--sm" data-action="job-retry" data-id="' + attr(job.id) + '">' + icon('refresh', 14) + ' Retry</button>');
        }
        return '<tr><td><div class="cell-title mono">' + esc(job.job_type) + '</div>' +
          '<div class="cell-sub mono">' + esc(String(job.id).slice(0, 8)) + '</div></td>' +
          '<td>' + statusBadge(job.status) + '</td>' +
          '<td class="muted small">' + esc(job.attempts) + ' / ' + esc(job.max_attempts) + '</td>' +
          '<td class="muted small">' + esc(fmtDateTime(job.run_at)) + '</td>' +
          '<td class="muted small mono">' + esc(String(job.correlation_id || '').slice(0, 8)) + '</td>' +
          '<td class="muted small">' + (job.last_error ? esc(String(job.last_error).slice(0, 60)) : '<span class="faint">ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â</span>') + '</td>' +
          '<td><div class="row">' + (buttons.length ? buttons.join('') : '<span class="faint small">ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â</span>') + '</div></td></tr>';
      }).join('') + '</tbody></table></div>'
      : emptyState('activity', 'No jobs yet', 'Jobs appear here when a workflow enqueues durable work.')) +
    '</section></div>';
  renderViewHtml(html);
}

async function loadAdapters(token) {
  if (!can(P.eventRead)) { eventAccessBlocked('Adapters'); return; }
  loadingView('Adapters', 'Local mock integrations and their recorded calls');
  const results = await Promise.allSettled([
    api(apiW('/adapters')),
    api(apiW('/adapters/calls?limit=100')),
  ]);
  if (token !== state.viewToken) return;
  if (results[0].status === 'rejected') {
    renderViewHtml(pageHead('Operations', 'Adapters', '') + errorBlock(errMessage(results[0].reason)));
    return;
  }
  const catalog = results[0].value || { providers: [] };
  const calls = results[1].status === 'fulfilled' ? (results[1].value || []) : [];
  const providers = catalog.providers || [];
  state.caches.adapters = providers;
  state.caches.adapterCalls = calls;
  const manage = can(P.workspaceManage);

  let html = pageHead('Operations', 'Adapters',
    'Provider seam for future integrations. This build records calls locally.',
    '<button class="btn" data-action="refresh-view">' + icon('refresh', 15) + ' Refresh</button>');
  html += governanceNote('Every adapter is a local mock. Invoking one records a call with delivered = false and no output. No credential is used and no message leaves this machine.');
  html += '<div class="stats">' +
    statCard('link', 'Providers', String(providers.length), 'In the catalog') +
    statCard('activity', 'Calls recorded', String(calls.length), 'Local only', 'blue') +
    statCard('check', 'Configured', String(providers.filter(function (p) { return p.status === 'configured'; }).length), 'Non-sensitive settings only') +
    statCard('alert', 'Blocked', String(providers.filter(function (p) { return p.status === 'blocked'; }).length), 'Not callable', 'amber') +
    '</div>' + (results[1].status === 'rejected' ? errorBlock('Call history could not be loaded: ' + errMessage(results[1].reason)) : '');

  html += '<div class="stack">';
  html += '<section class="card"><div class="card-head"><div class="card-head-main">' +
    '<div class="card-title">Adapter catalog</div>' +
    '<div class="card-sub">Status is not proof of a live provider connection</div></div></div>' +
    (providers.length ? '<div class="table-wrap"><table class="data"><thead><tr><th>Provider</th><th>Kind</th>' +
      '<th>Status</th><th>Local mock</th><th></th></tr></thead><tbody>' +
      providers.map(function (provider) {
        return '<tr><td><div class="cell-title">' + esc(provider.display_name) + '</div>' +
          '<div class="cell-sub mono">' + esc(provider.provider) + '</div></td>' +
          '<td class="small">' + esc(cap(provider.kind)) + '</td>' +
          '<td>' + statusBadge(provider.status) + '</td>' +
          '<td class="small">' + (provider.local_mock_available ? 'Yes' : 'No') + '</td>' +
          '<td>' + (manage && provider.local_mock_available
            ? '<button class="btn btn--sm" data-action="adapter-test" data-provider="' + attr(provider.provider) + '">' + icon('zap', 14) + ' Test mock</button>'
            : '<span class="faint small">ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â</span>') + '</td></tr>';
      }).join('') + '</tbody></table></div>'
      : emptyState('link', 'No adapters listed', 'The adapter catalog is empty for this workspace.')) +
    '</section>';

  html += '<section class="card"><div class="card-head"><div class="card-head-main">' +
    '<div class="card-title">Recorded calls</div>' +
    '<div class="card-sub">Redacted summaries only ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â no request bodies or secrets</div></div></div>' +
    (calls.length ? '<div class="table-wrap"><table class="data"><thead><tr><th>Provider</th><th>Operation</th>' +
      '<th>Status</th><th>Result note</th><th>Recorded</th></tr></thead><tbody>' +
      calls.map(function (call) {
        return '<tr><td><div class="cell-title">' + esc(call.provider) + '</div>' +
          '<div class="cell-sub mono">' + esc(call.kind) + '</div></td>' +
          '<td class="small">' + esc(call.operation) + '</td>' +
          '<td>' + statusBadge(call.status) + '</td>' +
          '<td class="muted small">' + esc(call.note) + '</td>' +
          '<td class="muted small">' + esc(fmtDateTime(call.created_at)) + '</td></tr>';
      }).join('') + '</tbody></table></div>'
      : emptyState('activity', 'No calls recorded', 'Test a local mock to create a recorded call.')) +
    '</section></div>';
  renderViewHtml(html);
}

async function loadOperations(token) {
  if (!can(P.eventRead)) { eventAccessBlocked('System health'); return; }
  loadingView('System health', 'Real aggregates and component states for this workspace');
  const results = await Promise.allSettled([
    api(apiW('/operations/summary')),
    api(apiW('/operations/components')),
    api(apiW('/operations/audit?limit=25')),
  ]);
  if (token !== state.viewToken) return;
  if (results[0].status === 'rejected' || results[1].status === 'rejected') {
    renderViewHtml(pageHead('Operations', 'System health', '') +
      errorBlock(errMessage((results[0].status === 'rejected' ? results[0].reason : results[1].reason))));
    return;
  }
  const summary = results[0].value || {};
  const components = (results[1].value || {}).components || [];
  const audit = results[2].status === 'fulfilled' ? (results[2].value || []) : [];

  let html = pageHead('Operations', 'System health',
    'Counts are computed from stored workspace rows at request time.',
    '<button class="btn" data-action="refresh-view">' + icon('refresh', 15) + ' Refresh</button>');
  html += governanceNote(summary.notes || 'All counts come from stored rows. No external system is queried.');
  html += '<div class="stats">' +
    statCard('users', 'Contacts', String(summary.contacts == null ? 'ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â' : summary.contacts), 'Stored records') +
    statCard('target', 'Leads', String(summary.leads == null ? 'ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â' : summary.leads), 'All stages') +
    statCard('checkSquare', 'Open tasks', String(summary.open_tasks == null ? 'ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â' : summary.open_tasks), 'Not complete', 'amber') +
    statCard('mail', 'Pending drafts', String(summary.pending_drafts == null ? 'ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â' : summary.pending_drafts), 'Awaiting approval', 'amber') +
    statCard('activity', 'Audit events', String(summary.events_total == null ? 'ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â' : summary.events_total), 'Append-only', 'blue') +
    statCard('clock', 'Queued jobs', String(summary.jobs_queued == null ? 'ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â' : summary.jobs_queued), 'Awaiting a worker') +
    '</div>';

  html += '<div class="stack">';
  html += '<section class="card"><div class="card-head"><div class="card-head-main">' +
    '<div class="card-title">Component states</div>' +
    '<div class="card-sub">Local, mock and blocked are reported separately</div></div></div>' +
    (components.length ? '<div class="table-wrap"><table class="data"><thead><tr><th>Component</th><th>State</th><th>Detail</th></tr></thead><tbody>' +
      components.map(function (item) {
        return '<tr><td class="cell-title">' + esc(item.name) + '</td>' +
          '<td>' + statusBadge(item.state) + '</td>' +
          '<td class="muted small">' + esc(item.detail) + '</td></tr>';
      }).join('') + '</tbody></table></div>'
      : emptyState('settings', 'No components', 'Component states are unavailable.')) +
    '</section>';

  html += '<section class="card"><div class="card-head"><div class="card-head-main">' +
    '<div class="card-title">Recent audit entries</div>' +
    '<div class="card-sub">Newest first Ãƒâ€šÃ‚Â· up to 25 entries</div></div></div>' +
    (audit.length ? '<div class="timeline">' + audit.slice(0, 12).map(function (event) {
      return eventItem(event, true);
    }).join('') + '</div>' : emptyState('activity', 'No audit entries', 'Workspace actions are recorded here.')) +
    '</section></div>';
  renderViewHtml(html);
}

/* ------------------------------------------------------------------ *
 * Dashboard ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â all numbers are derived from live API lists
 * ------------------------------------------------------------------ */

function statCard(iconName, label, value, note, tone) {
  return '<div class="card stat"><div class="stat-top"><div class="stat-icon' +
    (tone ? ' stat-icon--' + tone : '') + '">' + icon(iconName, 17) + '</div></div>' +
    '<div><div class="stat-value">' + esc(value) + '</div><div class="stat-label">' + esc(label) + '</div>' +
    (note ? '<div class="stat-note">' + esc(note) + '</div>' : '') + '</div></div>';
}

function eventItem(event, compact) {
  const type = String(event.event_type || 'event');
  const payload = event.payload && typeof event.payload === 'object' ? JSON.stringify(event.payload) : '';
  return '<div class="timeline-item"><div class="timeline-dot">' + icon(eventIcon(type), 14) + '</div>' +
    '<div class="timeline-body"><div class="timeline-title">' + esc(cap(type)) + '</div>' +
    '<div class="timeline-meta">' + esc(relTime(event.occurred_at)) +
    (event.entity_id ? ' Ãƒâ€šÃ‚Â· Record ' + esc(String(event.entity_id).slice(0, 8)) : '') +
    (compact ? '' : ' Ãƒâ€šÃ‚Â· Correlation ' + esc(String(event.correlation_id || '').slice(0, 8))) + '</div>' +
    (payload && !compact ? '<div class="timeline-payload mono">' + esc(payload) + '</div>' : '') +
    '</div></div>';
}

async function loadDashboard(token) {
  loadingView('Overview', 'The connected state of your workspace');
  const keys = [], jobs = [];
  if (can(P.contactRead)) { keys.push('contacts'); jobs.push(fetchAll(apiW('/contacts'), 100)); }
  if (can(P.leadRead)) { keys.push('leads'); jobs.push(api(apiW('/leads'))); }
  if (can(P.taskRead)) { keys.push('tasks'); jobs.push(api(apiW('/tasks'))); }
  if (can(P.notificationRead)) { keys.push('notifications'); jobs.push(api(apiW('/notifications'))); }
  if (can(P.outreachRead)) { keys.push('drafts'); jobs.push(api(apiW('/outreach-drafts'))); }
  if (can(P.eventRead)) { keys.push('events'); jobs.push(fetchAll(apiW('/events'), 500)); }
  if (can(P.eventRead)) { keys.push('operations'); jobs.push(api(apiW('/operations/summary'))); }

  const settled = await Promise.allSettled(jobs);
  if (token !== state.viewToken) return;
  const labels = {
    contacts: 'Contacts', leads: 'Leads', tasks: 'Tasks', notifications: 'Notifications',
    drafts: 'Outreach drafts', events: 'Audit events', operations: 'System health',
  };
  const data = {}, errors = [];
  settled.forEach(function (result, i) {
    if (result.status === 'fulfilled') {
      // Most dashboard feeds are lists; the operations summary is an object.
      data[keys[i]] = keys[i] === 'operations'
        ? (result.value || {})
        : (Array.isArray(result.value) ? result.value : []);
    } else {
      errors.push(labels[keys[i]] + ': ' + errMessage(result.reason));
    }
  });
  Object.keys(data).forEach(function (key) {
    if (key === 'events') state.caches.events = data[key];
    else state.caches[key] = data[key];
  });
  updateUnreadBadge();

  const value = function (key) { return Object.prototype.hasOwnProperty.call(data, key) ? String(data[key].length) : 'ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â'; };
  const openTasks = (data.tasks || []).filter(function (t) { return t.status !== 'done'; });
  const pendingDrafts = (data.drafts || []).filter(function (d) { return d.status === 'draft'; });
  const unread = (data.notifications || []).filter(function (n) { return !n.read; }).length;
  const recentEvents = (data.events || []).slice().reverse().slice(0, 6);
  const recentContacts = (data.contacts || []).slice(0, 5);
  const nextTasks = openTasks.slice(0, 5);

  const actions = '' +
    (can(P.contactWrite) ? '<button class="btn btn--primary" data-action="create-contact">' + icon('plus', 16) + ' Add contact</button>' : '') +
    (can(P.taskWrite) ? '<button class="btn" data-action="create-task">' + icon('plus', 16) + ' New task</button>' : '') +
    (can(P.contactWrite) ? '<button class="btn" data-action="record-intake">' + icon('inbox', 16) + ' Record intake</button>' : '') +
    (can(P.eventRead) ? '<a class="btn" href="#/activity">' + icon('activity', 16) + ' Activity feed</a>' : '');

  let html = pageHead('Workspace', 'Overview', 'A live view of ' + (state.me ? state.me.workspace_name : 'your workspace') + '.', actions);
  if (errors.length) html += errorBlock('Could not load part of the dashboard ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â ' + errors.join(' Ãƒâ€šÃ‚Â· '));
  html += '<div class="stats">' +
    statCard('users', 'Contacts', value('contacts'), can(P.contactRead) ? 'Active records' : 'No access') +
    statCard('target', 'Leads', value('leads'), can(P.leadRead) ? 'Across all stages' : 'No access') +
    statCard('checkSquare', 'Open tasks', data.tasks ? String(openTasks.length) : 'ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â', can(P.taskRead) ? 'Not completed' : 'No access', 'amber') +
    statCard('bell', 'Unread notifications', data.notifications ? String(unread) : 'ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â', can(P.notificationRead) ? 'Waiting for you' : 'No access', 'blue') +
    statCard('mail', 'Pending drafts', data.drafts ? String(pendingDrafts.length) : 'ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â', can(P.outreachRead) ? 'Awaiting approval' : 'No access', 'amber') +
    '</div>';

  html += '<div class="detail-grid"><div class="stack">';

  html += '<section class="card"><div class="card-head"><div class="card-head-main">' +
    '<div class="card-title">Recent audit events</div><div class="card-sub">Append-only activity published by your workflows</div></div>' +
    (can(P.eventRead) ? '<a class="btn btn--sm btn--ghost" href="#/activity">View all ' + icon('arrowRight', 14) + '</a>' : '') +
    '</div>' + (data.events
      ? (recentEvents.length ? '<div class="timeline">' + recentEvents.map(function (e) { return eventItem(e, true); }).join('') + '</div>'
        : emptyState('activity', 'No activity yet', 'Actions in this workspace will appear here as they happen.'))
      : errorBlock('Audit events could not be loaded.')) + '</section>';

  if (can(P.contactRead)) {
    html += '<section class="card"><div class="card-head"><div class="card-head-main">' +
      '<div class="card-title">Recent contacts</div><div class="card-sub">Newest contacts in this workspace</div></div>' +
      '<a class="btn btn--sm btn--ghost" href="#/contacts">All contacts ' + icon('arrowRight', 14) + '</a></div>' +
      (recentContacts.length ? '<div class="table-wrap"><table class="data"><thead><tr><th>Contact</th><th>Stage</th><th>Source</th><th>Added</th></tr></thead><tbody>' +
        recentContacts.map(function (c) {
          return '<tr class="clickable" data-action="open-contact" data-id="' + attr(c.id) + '">' +
            '<td><div class="cell-primary">' + avatar(c.full_name || c.email, 'sm') + '<div><div class="cell-title">' +
            esc(c.full_name || c.email) + '</div><div class="cell-sub">' + esc(c.email) + '</div></div></div></td>' +
            '<td>' + statusBadge(c.lifecycle_stage) + '</td><td class="muted small">' + esc(cap(c.source)) + '</td>' +
            '<td class="muted small">' + esc(relTime(c.created_at)) + '</td></tr>';
        }).join('') + '</tbody></table></div>'
        : emptyState('users', 'No contacts yet', 'Add a contact or record a website form submission to get started.',
          can(P.contactWrite) ? '<button class="btn btn--primary btn--sm" data-action="create-contact">Add contact</button>' : '')) +
      '</section>';
  }
  html += '</div><div class="stack">';

  if (can(P.taskRead)) {
    html += '<section class="card"><div class="card-head"><div class="card-head-main"><div class="card-title">Next up</div>' +
      '<div class="card-sub">Open tasks, oldest first</div></div></div>' +
      (nextTasks.length ? nextTasks.map(function (t) {
        return '<div class="list-row"><div class="list-row-main"><div class="list-row-title">' + esc(t.title) + '</div>' +
          '<div class="list-row-sub">' + esc(t.due_at ? 'Due ' + fmtDate(t.due_at) : cap(t.priority) + ' priority') + '</div></div>' +
          (can(P.taskWrite) ? '<button class="btn btn--sm btn--ghost" data-action="complete-task" data-id="' + attr(t.id) + '" title="Complete task">' + icon('check', 15) + '</button>' : '') +
          '</div>';
      }).join('') : emptyState('checkSquare', 'Nothing open', 'Every task is complete, or none have been created yet.')) + '</section>';
  }

  if (can(P.eventRead) && data.operations) {
    const ops = data.operations;
    html += '<section class="card"><div class="card-head"><div class="card-head-main">' +
      '<div class="card-title">System health</div>' +
      '<div class="card-sub">Computed from stored rows ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â no external calls</div></div>' +
      '<a class="btn btn--sm btn--ghost" href="#/operations">' + icon('arrowRight', 14) + '</a></div>' +
      '<div class="card-body"><dl class="kv">' +
      '<dt>Queued jobs</dt><dd>' + esc(ops.jobs_queued) + '</dd>' +
      '<dt>Dead-letter jobs</dt><dd>' + esc(ops.jobs_dead_letter) + '</dd>' +
      '<dt>Local adapter calls</dt><dd>' + esc(ops.adapter_calls_recorded) + '</dd>' +
      '<dt>Configured integrations</dt><dd>' + esc(ops.integrations_configured) + '</dd>' +
      '</dl><div class="divider"></div><div class="row">' +
      '<a class="btn btn--sm" href="#/jobs">Job queue</a>' +
      '<a class="btn btn--sm btn--ghost" href="#/adapters">Adapters</a></div></div></section>';
  }

  html += '<section class="card"><div class="card-head"><div class="card-head-main"><div class="card-title">Workspace</div></div></div>' +
    '<div class="card-body"><dl class="kv"><dt>Name</dt><dd>' + esc(state.me ? state.me.workspace_name : 'ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â') + '</dd>' +
    '<dt>Workspace ID</dt><dd class="mono">' + esc(String(ws()).slice(0, 12)) + 'ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦</dd>' +
    '<dt>Your role</dt><dd>' + esc(cap(state.me ? state.me.role : '')) + '</dd>' +
    '<dt>Permissions</dt><dd>' + esc((state.me ? state.me.permissions : []).length) + ' granted</dd></dl>' +
    '<div class="divider"></div><a class="btn btn--sm" href="#/settings">' + icon('settings', 15) + ' Open settings</a></div></section>';
  html += '</div></div>';
  renderViewHtml(html);
}

/* ------------------------------------------------------------------ *
 * Contacts
 * ------------------------------------------------------------------ */

function contactQuery(pageSize) {
  const f = state.contactFilters;
  const sortParts = f.sort.split(':');
  const params = new URLSearchParams();
  if (f.search) params.set('search', f.search);
  if (f.lifecycle_stage) params.set('lifecycle_stage', f.lifecycle_stage);
  if (f.tag) params.set('tag', f.tag);
  params.set('archived', f.archived);
  params.set('sort', sortParts[0] || 'created_at');
  params.set('order', sortParts[1] || 'desc');
  params.set('skip', String(f.skip));
  params.set('limit', String(pageSize));
  return params.toString();
}

function renderContactsPage(token) {
  const f = state.contactFilters;
  const actions = (can(P.contactWrite) ? '<button class="btn btn--primary" data-action="create-contact">' + icon('plus', 16) + ' Add contact</button>' : '') +
    (can(P.contactWrite) ? '<button class="btn" data-action="record-intake">' + icon('inbox', 16) + ' Record intake</button>' : '');
  renderViewHtml(pageHead('Relationships', 'Contacts',
    'One customer identity shared by leads, tasks, notes and events.', actions) +
    '<section class="card"><div class="toolbar">' +
    '<div class="toolbar-search">' + icon('search', 15) +
    '<input class="input" type="search" placeholder="Search name, email, companyÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦" value="' + attr(f.search) + '" data-input="contact-search" aria-label="Search contacts"></div>' +
    '<select class="select" data-change="contact-filter" data-key="lifecycle_stage" aria-label="Lifecycle stage">' +
    selectOptions([['', 'All stages'], ['lead', 'Lead'], ['qualified', 'Qualified'], ['customer', 'Customer']], f.lifecycle_stage) + '</select>' +
    '<input class="input" type="search" style="max-width:150px" placeholder="Filter by tag" value="' + attr(f.tag) + '" data-input="contact-tag" aria-label="Filter by tag">' +
    '<select class="select" data-change="contact-filter" data-key="archived" aria-label="Archive status">' +
    selectOptions([['false', 'Active'], ['true', 'Archived']], f.archived) + '</select>' +
    '<select class="select" data-change="contact-filter" data-key="sort" aria-label="Sort order">' +
    selectOptions([['created_at:desc', 'Newest first'], ['created_at:asc', 'Oldest first'], ['updated_at:desc', 'Recently updated'],
      ['full_name:asc', 'Name AÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Å“Z'], ['full_name:desc', 'Name ZÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Å“A'], ['email:asc', 'Email AÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Å“Z']], f.sort) + '</select>' +
    '</div><div id="contacts-results"><div class="card-body"><div class="skeleton skeleton-line" style="width:80%"></div>' +
    '<div class="skeleton skeleton-line" style="width:65%"></div></div></div></section>');
  return refreshContactsTable(token);
}

async function refreshContactsTable(token) {
  const host = document.getElementById('contacts-results');
  if (!host) return;
  try {
    const rows = await api(apiW('/contacts') + '?' + contactQuery(state.contactFilters.limit + 1));
    if (token !== undefined && token !== state.viewToken) return;
    const hasMore = rows.length > state.contactFilters.limit;
    const list = rows.slice(0, state.contactFilters.limit);
    state.contactsHasMore = hasMore;
    state.caches.contacts = list;
    const page = Math.floor(state.contactFilters.skip / state.contactFilters.limit) + 1;
    let html;
    if (!list.length) {
      html = emptyState('users', 'No contacts found',
        'Try different filters, or add the first contact in this workspace.',
        can(P.contactWrite) ? '<button class="btn btn--primary btn--sm" data-action="create-contact">Add contact</button>' : '');
    } else {
      html = '<div class="table-wrap"><table class="data"><thead><tr><th>Contact</th><th>Company</th><th>Stage</th><th>Tags</th><th>Updated</th><th></th></tr></thead><tbody>' +
        list.map(function (c) {
          const tags = (c.tags || []).slice(0, 2).map(function (t) { return '<span class="chip">' + esc(t) + '</span>'; }).join('');
          const more = (c.tags || []).length > 2 ? '<span class="chip">+' + ((c.tags || []).length - 2) + '</span>' : '';
          return '<tr class="clickable" data-action="open-contact" data-id="' + attr(c.id) + '">' +
            '<td><div class="cell-primary">' + avatar(c.full_name || c.email, 'sm') + '<div><div class="cell-title">' +
            esc(c.full_name || c.email) + '</div><div class="cell-sub">' + esc(c.email) + '</div></div></div></td>' +
            '<td class="muted small">' + esc(c.company_name || 'ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â') + '</td><td>' + statusBadge(c.lifecycle_stage) + '</td>' +
            '<td><div class="chips">' + (tags + more || '<span class="faint tiny">ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â</span>') + '</div></td>' +
            '<td class="muted small">' + esc(relTime(c.updated_at)) + '</td>' +
            '<td><div class="cell-actions"><a class="btn btn--sm btn--ghost" href="#/contacts/' + encodeURIComponent(c.id) + '" aria-label="Open contact">' + icon('chevronRight', 15) + '</a></div></td></tr>';
        }).join('') + '</tbody></table></div>';
    }
    html += '<div class="card-foot"><span class="pager-label">Page ' + page + '</span><span class="pager">' +
      '<button class="btn btn--sm" data-action="contacts-prev"' + (state.contactFilters.skip === 0 ? ' disabled' : '') + '>' +
      icon('chevronLeft', 14) + ' Previous</button>' +
      '<button class="btn btn--sm" data-action="contacts-next"' + (hasMore ? '' : ' disabled') + '>Next ' + icon('chevronRight', 14) + '</button>' +
      '</span><span class="muted tiny">' + list.length + ' shown on this page</span></div>';
    host.innerHTML = html;
  } catch (err) {
    host.innerHTML = errorBlock(errMessage(err));
  }
}

async function loadContactsPage(token) {
  if (!can(P.contactRead)) {
    renderViewHtml(pageHead('Relationships', 'Contacts', '') + errorBlock('Your role does not include contact access.'));
    return;
  }
  renderContactsPage(token);
}

/* ------------------------------------------------------------------ *
 * Contact detail ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â record, notes, unified timeline
 * ------------------------------------------------------------------ */

async function consentTokens(contactId) {
  const data = await api(apiW('/email/consent-links') + '?contact_id=' + encodeURIComponent(contactId));
  return data.links;
}

async function loadContactDetail(id, token) {
  if (!can(P.contactRead)) {
    renderViewHtml(errorBlock('Your role does not include contact access.'));
    return;
  }
  loadingView('Contact', 'Loading contact record');
  const base = apiW('/contacts/' + encodeURIComponent(id));
  const results = await Promise.allSettled([
    api(base), api(base + '/notes'), api(base + '/timeline'),
    api(apiW('/tickets') + '?contact_id=' + encodeURIComponent(id)),
    api(apiW('/email/consent-links') + '?contact_id=' + encodeURIComponent(id)),
  ]);
  if (token !== state.viewToken) return;
  if (results[0].status === 'rejected') {
    renderViewHtml(pageHead('Relationships', 'Contact', '') + errorBlock(errMessage(results[0].reason)) +
      '<a class="btn" href="#/contacts">' + icon('chevronLeft', 15) + ' Back to contacts</a>');
    return;
  }
  const c = results[0].value;
  const notes = results[1].status === 'fulfilled' ? results[1].value : null;
  const timeline = results[2].status === 'fulfilled' ? results[2].value : null;
  const conversations = results[3].status === 'fulfilled' ? results[3].value : null;
  const consent = results[4].status === 'fulfilled' ? results[4].value : null;
  state.caches.contact = c;

  const actions = '<a class="btn" href="#/contacts">' + icon('chevronLeft', 15) + ' Back</a>' +
    (can(P.contactWrite) ? '<button class="btn btn--primary" data-action="edit-contact" data-id="' + attr(c.id) + '">' + icon('edit', 15) + ' Edit</button>' : '') +
    (can(P.contactArchive) ? (c.archived
      ? '<button class="btn" data-action="restore-contact" data-id="' + attr(c.id) + '">' + icon('restore', 15) + ' Restore</button>'
      : '<button class="btn" data-action="archive-contact" data-id="' + attr(c.id) + '">' + icon('archive', 15) + ' Archive</button>') : '') +
    (can(P.contactDelete) && c.archived ? '<button class="btn btn--danger" data-action="delete-contact" data-id="' + attr(c.id) + '">' + icon('trash', 15) + ' Delete</button>' : '');

  let html = pageHead('Relationships', c.full_name || c.email, c.email, actions);
  html += '<div class="detail-grid"><div class="stack">';

  html += '<section class="card"><div class="card-head"><div class="card-head-main"><div class="card-title">Contact profile</div></div>' +
    statusBadge(c.archived ? 'archived' : c.lifecycle_stage) + '</div><div class="card-body">' +
    '<div class="ident-head" style="margin-bottom:24px">' + avatar(c.full_name || c.email, 'lg') + '<div>' +
    '<div class="ident-name">' + esc(c.full_name || c.email) + '</div><div class="ident-mail">' + esc(c.email) + '</div></div></div>' +
    '<dl class="kv"><dt>Company</dt><dd>' + esc(c.company_name || 'ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â') + '</dd>' +
    '<dt>Phone</dt><dd>' + esc(c.phone || 'ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â') + '</dd>' +
    '<dt>Source</dt><dd>' + esc(cap(c.source)) + '</dd>' +
    '<dt>Lifecycle</dt><dd>' + esc(cap(c.lifecycle_stage)) + '</dd>' +
    '<dt>Added</dt><dd>' + esc(fmtDateTime(c.created_at)) + '</dd>' +
    '<dt>Updated</dt><dd>' + esc(fmtDateTime(c.updated_at)) + '</dd></dl>' +
    '<div class="divider"></div><div class="field"><label>Tags</label><div class="chips">' +
    ((c.tags || []).length ? c.tags.map(function (t) { return '<span class="chip chip--green">' + esc(t) + '</span>'; }).join('')
      : '<span class="muted small">No tags</span>') + '</div></div></div></section>';

  html += '<section class="card"><div class="card-head"><div class="card-head-main"><div class="card-title">Support conversations</div>' +
    '<div class="card-sub">Conversations linked to this one CRM identity</div></div></div>' +
    (conversations === null ? errorBlock('Conversations could not be loaded.')
      : (conversations.length ? conversations.map(function (t) {
        return '<a class="list-row" href="#/inbox/' + attr(t.id) + '">' + icon('mail', 15) +
          '<div class="list-row-main"><div class="list-row-title">' + esc(t.subject) + '</div>' +
          '<div class="list-row-sub">' + esc(cap(t.status)) + ' Ãƒâ€šÃ‚Â· ' + esc(cap(t.priority)) +
          ' Ãƒâ€šÃ‚Â· opened ' + esc(relTime(t.created_at)) + '</div></div>' + icon('chevronRight', 15) + '</a>';
      }).join('')
        : emptyState('mail', 'No conversations yet',
          'Support requests from this contact will appear here without a duplicate identity.'))) +
    '</section>';

  html += '<section class="card"><div class="card-head"><div class="card-head-main"><div class="card-title">Consent & preferences</div>' +
    '<div class="card-sub">Signed links update real consent records; no email is sent</div></div></div>' +
    (consent === null ? errorBlock('Consent state could not be loaded.') :
      '<div class="card-body"><dl class="kv"><dt>Global do-not-contact</dt><dd>' +
      (consent.do_not_contact ? statusBadge('dnc') : 'Not set') + '</dd>' +
      '<dt>External identity</dt><dd>' + (c.external_id
        ? esc(c.external_source) + ': <span class="mono">' + esc(c.external_id) + '</span>'
        : '<span class="muted">Not linked</span>') + '</dd></dl>' +
      '<div class="divider"></div><div class="row wrap">' +
      '<button class="btn btn--sm" data-action="consent-unsubscribe" data-id="' + attr(c.id) + '">Unsubscribe email</button>' +
      '<button class="btn btn--sm" data-action="consent-resubscribe" data-id="' + attr(c.id) + '">Resubscribe</button>' +
      '<button class="btn btn--sm" data-action="consent-dnc" data-id="' + attr(c.id) + '">Set global DNC</button>' +
      '<button class="btn btn--sm" data-action="consent-preferences" data-id="' + attr(c.id) + '">Manage preferences</button>' +
      '</div><p class="tiny faint" style="margin-top:12px">Tokens are generated when a control is used and are never shown on screen.</p></div>') +
    '</section>';

  html += '<section class="card"><div class="card-head"><div class="card-head-main"><div class="card-title">Notes</div>' +
    '<div class="card-sub">Internal context written by your team</div></div></div>' +
    (notes === null ? errorBlock('Notes could not be loaded.')
      : (notes.length ? notes.map(function (n) {
        return '<div class="note-item"><div class="row-between"><div class="row">' + avatar(n.author_id, 'sm') +
          '<span class="tiny muted">Recorded by ' + esc(String(n.author_id).slice(0, 8)) + ' Ãƒâ€šÃ‚Â· ' + esc(relTime(n.created_at)) + '</span></div></div>' +
          '<div class="note-body" style="margin-top:8px">' + esc(n.body) + '</div></div>';
      }).join('') : emptyState('note', 'No notes yet', 'Add the first note to keep context with this contact.'))) +
    (can(P.noteWrite) ? '<form class="card-body" data-form="add-note" data-contact-id="' + attr(c.id) + '" style="border-top:1px solid var(--line-soft)">' +
      field('note_body', 'New note', { type: 'textarea', placeholder: 'What should the team know?', span: true, required: true }) +
      '<div class="form-actions"><button class="btn btn--primary btn--sm" type="submit">' + icon('plus', 15) + ' Add note</button></div></form>' : '') +
    '</section>';

  html += '<section class="card"><div class="card-head"><div class="card-head-main"><div class="card-title">Unified timeline</div>' +
    '<div class="card-sub">Cross-module events linked by correlation id</div></div></div>' +
    (timeline === null ? errorBlock('Timeline could not be loaded.')
      : (timeline.length ? '<div class="timeline">' + timeline.map(function (e) { return eventItem(e, false); }).join('') + '</div>'
        : emptyState('activity', 'No linked events', 'Events from forms, tasks and notes involving this contact will appear here.'))) +
    '</section></div><div class="stack">';

  html += '<section class="card"><div class="card-head"><div class="card-head-main"><div class="card-title">Record details</div></div></div>' +
    '<div class="card-body"><dl class="kv"><dt>Contact ID</dt><dd class="mono">' + esc(c.id) + '</dd>' +
    '<dt>Archived</dt><dd>' + (c.archived ? 'Yes' : 'No') + '</dd>' +
    '<dt>Owner</dt><dd class="mono">' + esc(c.owner_id ? String(c.owner_id).slice(0, 12) + 'ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦' : 'Unassigned') + '</dd></dl>' +
    (Object.keys(c.custom_fields || {}).length ? '<div class="divider"></div><div class="field"><label>Custom fields</label>' +
      '<div class="mono small">' + esc(JSON.stringify(c.custom_fields)) + '</div></div>' : '') +
    '</div></section>';

  if (can(P.contactWrite) || can(P.contactArchive) || can(P.contactDelete)) {
    html += '<section class="card"><div class="card-head"><div class="card-head-main"><div class="card-title">Record actions</div></div></div>' +
      '<div class="card-body stack-sm">' +
      (can(P.contactWrite) ? '<button class="btn btn--block" data-action="edit-contact" data-id="' + attr(c.id) + '">' + icon('edit', 15) + ' Edit details</button>' : '') +
      (can(P.contactArchive) ? (c.archived
        ? '<button class="btn btn--block" data-action="restore-contact" data-id="' + attr(c.id) + '">' + icon('restore', 15) + ' Restore contact</button>'
        : '<button class="btn btn--block" data-action="archive-contact" data-id="' + attr(c.id) + '">' + icon('archive', 15) + ' Archive contact</button>') : '') +
      (can(P.contactDelete) && c.archived ? '<button class="btn btn--danger btn--block" data-action="delete-contact" data-id="' + attr(c.id) + '">' + icon('trash', 15) + ' Delete permanently</button>' : '') +
      '<p class="tiny faint">Deletion is only available for archived contacts with no dependent records.</p>' +
      '</div></section>';
  }
  html += '</div></div>';
  renderViewHtml(html);
}

/* ------------------------------------------------------------------ *
 * Companies
 * ------------------------------------------------------------------ */

async function loadCompanies(token) {
  if (!can(P.companyRead)) {
    renderViewHtml(pageHead('Relationships', 'Companies', '') + errorBlock('Your role does not include company access.'));
    return;
  }
  loadingView('Companies', 'Organisations in this workspace');
  try {
    const rows = await api(apiW('/companies'));
    if (token !== state.viewToken) return;
    state.caches.companies = rows || [];
    const actions = can(P.companyWrite) ? '<button class="btn btn--primary" data-action="create-company">' + icon('plus', 16) + ' Add company</button>' : '';
    let html = pageHead('Relationships', 'Companies', 'Organisation records linked to your contacts.', actions);
    if (!state.caches.companies.length) {
      html += '<section class="card">' + emptyState('building', 'No companies yet',
        'Add an organisation to group the contacts that belong to it.',
        can(P.companyWrite) ? '<button class="btn btn--primary btn--sm" data-action="create-company">Add company</button>' : '') + '</section>';
    } else {
      html += '<section class="card"><div class="table-wrap"><table class="data"><thead><tr><th>Company</th><th>Industry</th><th>Website</th><th>Location</th><th>Added</th></tr></thead><tbody>' +
        state.caches.companies.map(function (c) {
          const url = safeUrl(c.website);
          return '<tr><td><div class="cell-primary">' + avatar(c.name, 'sm') + '<div><div class="cell-title">' + esc(c.name) +
            '</div></div></div></td><td class="muted small">' + esc(c.industry || 'ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â') + '</td><td class="small">' +
            (url ? '<a href="' + attr(url) + '" target="_blank" rel="noopener noreferrer">' + esc(url.replace(/^https?:\/\//, '')) + '</a>' : (c.website ? '<span class="muted small">' + esc(c.website) + '</span>' : '<span class="faint">ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â</span>')) +
            '</td><td class="muted small">' + esc(c.location || 'ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â') + '</td><td class="muted small">' + esc(fmtDate(c.created_at)) + '</td></tr>';
        }).join('') + '</tbody></table></div></section>';
    }
    renderViewHtml(html);
  } catch (err) {
    if (token !== state.viewToken) return;
    renderViewHtml(pageHead('Relationships', 'Companies', '') + errorBlock(errMessage(err)));
  }
}

/* ------------------------------------------------------------------ *
 * Leads
 * ------------------------------------------------------------------ */

function contactLabel(map, id) {
  const c = map[id];
  return c ? (c.full_name || c.email) : (id ? 'Contact ' + String(id).slice(0, 8) : 'ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â');
}

async function loadLeads(token) {
  if (!can(P.leadRead)) {
    renderViewHtml(pageHead('Relationships', 'Leads', '') + errorBlock('Your role does not include lead access.'));
    return;
  }
  loadingView('Leads', 'Qualification pipeline');
  const query = state.leadStatus ? '?status=' + encodeURIComponent(state.leadStatus) : '';
  const results = await Promise.allSettled([
    api(apiW('/leads') + query),
    can(P.contactRead) ? fetchAll(apiW('/contacts'), 100) : Promise.resolve([]),
  ]);
  if (token !== state.viewToken) return;
  if (results[0].status === 'rejected') {
    renderViewHtml(pageHead('Relationships', 'Leads', '') + errorBlock(errMessage(results[0].reason)));
    return;
  }
  const leads = results[0].value || [];
  const contacts = results[1].status === 'fulfilled' ? results[1].value : [];
  state.caches.leads = leads;
  const contactError = results[1].status === 'rejected' ? errorBlock('Contacts could not be loaded: ' + errMessage(results[1].reason)) : '';
  const map = {};
  contacts.forEach(function (c) { map[c.id] = c; });
  state.caches.contacts = contacts;

  const actions = can(P.leadWrite) ? '<button class="btn btn--primary" data-action="create-lead">' + icon('plus', 16) + ' Add lead</button>' : '';
  let html = pageHead('Relationships', 'Leads', 'Each lead points at one shared contact record.', actions);
  html += contactError;
  html += '<section class="card"><div class="toolbar"><select class="select" data-change="lead-status" aria-label="Filter by status">' +
    selectOptions([['', 'All statuses'], ['new', 'New'], ['qualified', 'Qualified'], ['converted', 'Converted']], state.leadStatus) + '</select>' +
    '<span class="muted tiny">' + leads.length + ' ' + (leads.length === 1 ? 'lead' : 'leads') + '</span></div>';
  if (!leads.length) {
    html += emptyState('target', 'No leads found', 'Create a lead from a contact, or change the status filter.',
      can(P.leadWrite) ? '<button class="btn btn--primary btn--sm" data-action="create-lead">Add lead</button>' : '');
  } else {
    html += '<div class="table-wrap"><table class="data"><thead><tr><th>Contact</th><th>Status</th><th>Priority</th><th>Score</th><th>Source</th><th>Created</th><th></th></tr></thead><tbody>' +
      leads.map(function (l) {
        const c = map[l.contact_id];
        const buttons = [];
        if (can(P.leadWrite) && l.status === 'new') buttons.push('<button class="btn btn--sm" data-action="qualify-lead" data-id="' + attr(l.id) + '">' + icon('check', 14) + ' Qualify</button>');
        if (can(P.leadWrite) && l.status === 'qualified') buttons.push('<button class="btn btn--sm btn--accent" data-action="convert-lead" data-id="' + attr(l.id) + '">' + icon('arrowRight', 14) + ' Convert</button>');
        if (can(P.leadWrite)) buttons.push('<button class="btn btn--sm btn--ghost" data-action="edit-lead" data-id="' + attr(l.id) + '" aria-label="Edit lead">' + icon('edit', 14) + '</button>');
        return '<tr><td><div class="cell-primary">' + avatar(contactLabel(map, l.contact_id), 'sm') + '<div><div class="cell-title">' +
          esc(contactLabel(map, l.contact_id)) + '</div><div class="cell-sub">' + esc(c ? c.email : l.contact_id) + '</div></div></div></td>' +
          '<td>' + statusBadge(l.status) + '</td><td class="small">' + esc(cap(l.priority)) + '</td><td class="small">' + esc(l.score) + '</td>' +
          '<td class="muted small">' + esc(cap(l.source)) + '</td><td class="muted small">' + esc(relTime(l.created_at)) + '</td>' +
          '<td><div class="cell-actions">' + buttons.join('') + '</div></td></tr>';
      }).join('') + '</tbody></table></div>';
  }
  html += '</section>';
  renderViewHtml(html);
}

/* ------------------------------------------------------------------ *
 * Tasks
 * ------------------------------------------------------------------ */

/* PL-021: work-item-aware grouped list. All rows come from the real project
 * item API; a failed project fetch is skipped rather than breaking the view. */
async function loadWorkItemGroups() {
  const projects = await api(apiW('/projects')) || [];
  const support = await Promise.allSettled([
    api(apiW('/projects/states')), api(apiW('/projects/assignees')),
  ]);
  const states = support[0].status === 'fulfilled' ? (support[0].value || []) : [];
  const assignees = support[1].status === 'fulfilled' ? (support[1].value || []) : [];
  const assigneeMap = {};
  assignees.forEach(function (a) { assigneeMap[a.id] = a; });
  const itemResults = await Promise.allSettled(projects.map(function (p) {
    return api(apiW('/projects/' + encodeURIComponent(p.id) + '/items'));
  }));
  const groups = [];
  itemResults.forEach(function (result, index) {
    if (result.status !== 'fulfilled' || !result.value) return;
    result.value.forEach(function (item) {
      groups.push({ project: projects[index], item: item });
    });
  });
  return { groups: groups, states: states, assigneeMap: assigneeMap };
}

function workItemSectionLabel(item, states) {
  const state = states.find(function (s) { return s.name === item.status || s.id === item.status; });
  const name = item.status || (state && state.name) || 'Unstated';
  return state && state.group ? name + ' / ' + cap(state.group) : name;
}

function renderWorkItemGroups(data) {
  if (!data || !data.groups.length) return '';
  const byState = {};
  data.groups.forEach(function (entry) {
    const label = workItemSectionLabel(entry.item, data.states);
    if (!byState[label]) byState[label] = [];
    byState[label].push(entry);
  });
  const sections = Object.keys(byState).sort().map(function (label) {
    const entries = byState[label];
    const rows = entries.map(function (entry) {
      const item = entry.item;
      const assignee = data.assigneeMap[item.assignee_id];
      const assigneeLabel = assignee
        ? (assignee.display_name
          ? assignee.display_name + (assignee.email ? ' (' + assignee.email + ')' : '')
          : assignee.email || assignee.id)
        : (item.assignee_id ? 'Unlinked assignee' : 'Unassigned');
      const start = item.start_at ? fmtDate(item.start_at) : '-';
      const due = item.due_at ? fmtDate(item.due_at) : '-';
      return '<tr><td><div class="cell-title">' + esc(item.title) + '</div>' +
        '<div class="cell-sub">' + esc(entry.project ? entry.project.name : '') + '</div></td>' +
        '<td class="small">' + esc(item.status || '-') + '</td>' +
        '<td class="small">' + esc(cap(item.priority)) + '</td>' +
        '<td class="small work-item-assignee-cell">' + esc(assigneeLabel) + '</td>' +
        '<td class="muted small work-item-dates-cell">' + esc(start) + ' / ' + esc(due) + '</td></tr>';
    }).join('');
    return '<div class="work-item-group" data-work-item-group="' + attr(label) + '">' +
      '<div class="list-row-title">' + esc(label) +
      ' <span class="badge badge--plain">' + esc(String(entries.length)) + '</span></div>' +
      '<div class="table-wrap"><table class="data"><thead><tr>' +
      '<th>Title</th><th>State</th><th>Priority</th><th>Assignee</th><th>Start / due</th>' +
      '</tr></thead><tbody>' + rows + '</tbody></table></div></div>';
  }).join('');
  return '<section class="card" data-work-item-list><div class="card-head"><div class="card-head-main">' +
    '<div class="card-title">Work items by state</div>' +
    '<div class="card-sub">This is the work-item list, not the legacy task list below.</div>' +
    '</div></div><div class="card-body">' + sections + '</div></section>';
}

async function loadTasks(token) {
  if (!can(P.taskRead)) {
    renderViewHtml(pageHead('Operations', 'Tasks', '') + errorBlock('Your role does not include task access.'));
    return;
  }
  loadingView('Tasks', 'Follow-up work across the workspace');
  const results = await Promise.allSettled([
    api(apiW('/tasks')),
    can(P.contactRead) ? fetchAll(apiW('/contacts'), 100) : Promise.resolve([]),
    loadWorkItemGroups(),
  ]);
  if (token !== state.viewToken) return;
  if (results[0].status === 'rejected') {
    renderViewHtml(pageHead('Operations', 'Tasks', '') + errorBlock(errMessage(results[0].reason)));
    return;
  }
  const all = results[0].value || [];
  const contacts = results[1].status === 'fulfilled' ? results[1].value : [];
  state.caches.tasks = all;
  const map = {};
  contacts.forEach(function (c) { map[c.id] = c; });
  const workItemHtml = results[2] && results[2].status === 'fulfilled'
    ? renderWorkItemGroups(results[2].value) : '';
  const rows = all.filter(function (t) { return state.taskStatus === 'all' || t.status === state.taskStatus; });
  const open = all.filter(function (t) { return t.status !== 'done'; }).length;

  const actions = can(P.taskWrite) ? '<button class="btn btn--primary" data-action="create-task">' + icon('plus', 16) + ' New task</button>' : '';
  let html = pageHead('Operations', 'Tasks', open + ' open of ' + all.length + ' total.', actions);
  html += workItemHtml;
  html += '<section class="card"><div class="toolbar"><select class="select" data-change="task-status" aria-label="Filter by status">' +
    selectOptions([['all', 'All tasks'], ['open', 'Open'], ['done', 'Done']], state.taskStatus) + '</select>' +
    '<span class="muted tiny">' + rows.length + ' shown</span></div>';
  if (!rows.length) {
    html += emptyState('checkSquare', 'No tasks here', 'Create a follow-up task, or choose another status filter.',
      can(P.taskWrite) ? '<button class="btn btn--primary btn--sm" data-action="create-task">New task</button>' : '');
  } else {
    html += '<div class="table-wrap"><table class="data"><thead><tr><th>Task</th><th>Contact</th><th>Priority</th><th>Due</th><th>Status</th><th></th></tr></thead><tbody>' +
      rows.map(function (t) {
        const buttons = [];
        if (can(P.taskWrite) && t.status !== 'done') buttons.push('<button class="btn btn--sm btn--accent" data-action="complete-task" data-id="' + attr(t.id) + '">' + icon('check', 14) + ' Complete</button>');
        if (can(P.taskWrite) && t.status === 'done') buttons.push('<button class="btn btn--sm btn--ghost" data-action="reopen-task" data-id="' + attr(t.id) + '">' + icon('restore', 14) + ' Reopen</button>');
        return '<tr><td><div class="cell-primary"><span class="stat-icon">' + icon('checkSquare', 15) + '</span><div>' +
          '<div class="cell-title">' + esc(t.title) + '</div><div class="cell-sub">' + esc(t.description || '') + '</div></div></div></td>' +
          '<td class="small">' + (t.contact_id ? esc(contactLabel(map, t.contact_id)) : '<span class="faint">ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â</span>') + '</td>' +
          '<td class="small">' + esc(cap(t.priority)) + '</td><td class="muted small">' + esc(t.due_at ? fmtDate(t.due_at) : 'ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â') + '</td>' +
          '<td>' + statusBadge(t.status) + '</td><td><div class="cell-actions">' + buttons.join('') + '</div></td></tr>';
      }).join('') + '</tbody></table></div>';
  }
  html += '</section>';
  renderViewHtml(html);
}

/* ------------------------------------------------------------------ *
 * Projects
 * ------------------------------------------------------------------ */

async function loadProjects(token) {
  if (!can(P.taskRead)) {
    renderViewHtml(pageHead('Operations', 'Projects', '') + errorBlock('Your role does not include project access.'));
    return;
  }
  loadingView('Projects', 'Workspace projects and their items');
  const results = await Promise.allSettled([
    api(apiW('/projects')),
  ]);
  if (token !== state.viewToken) return;
  if (results[0].status === 'rejected') {
    renderViewHtml(pageHead('Operations', 'Projects', '') + errorBlock(errMessage(results[0].reason)));
    return;
  }
  const all = results[0].value || [];
  const actions = can(P.taskWrite) ? '<button class="btn btn--primary" data-action="create-project">' + icon('plus', 16) + ' New project</button>' : '';
  let html = pageHead('Operations', 'Projects', all.length + ' projects.', actions);
  html += '<section class="card">';
  if (!all.length) {
    html += emptyState('folder', 'No projects yet', 'Create a project to start tracking work.',
      can(P.taskWrite) ? '<button class="btn btn--primary btn--sm" data-action="create-project">New project</button>' : '');
  } else {
    html += '<div class="table-wrap"><table class="data"><thead><tr><th>Project</th><th>Status</th><th>Owner</th><th>Due</th><th></th></tr></thead><tbody>' +
      all.map(function (p) {
        return '<tr><td><div class="cell-title">' + esc(p.name) + '</div><div class="cell-sub">' + esc(p.description || '') + '</div></td>' +
          '<td>' + statusBadge(p.status) + '</td>' +
          '<td class="small">' + esc(p.owner_id || 'ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â') + '</td>' +
          '<td class="muted small">' + esc(p.due_at ? fmtDate(p.due_at) : 'ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â') + '</td>' +
          '<td><button class="btn btn--sm btn--ghost" data-action="view-project" data-id="' + attr(p.id) + '">' + icon('eye', 14) + ' View</button></td></tr>';
      }).join('') + '</tbody></table></div>';
  }
  html += '</section>';
  renderViewHtml(html);
}

function builtinItemStates() {
  return [['todo', 'To do'], ['in_progress', 'In progress'], ['done', 'Done']];
}

function isOverdueItem(item) {
  if (!item || !item.due_at || item.state_group === 'done') return false;
  const due = new Date(item.due_at).getTime();
  return !isNaN(due) && due < Date.now();
}

async function loadProjectDetail(projectId, token) {
  if (!can(P.taskRead)) {
    renderViewHtml(pageHead('Operations', 'Projects', '') + errorBlock('Your role does not include project access.'));
    return;
  }
  loadingView('Projects', 'Work items and delivery state');
  const base = apiW('/projects/' + encodeURIComponent(projectId));
  const itemUrl = base + '/items' + (state.itemFilter === 'overdue' ? '?overdue=true' : '');
  const results = await Promise.allSettled([
    api(base), api(itemUrl), api(apiW('/projects/states')),
    api(apiW('/projects/assignees')), api(base + '/progress'),
    api(base + '/members'), api(base + '/board'), api(base + '/views'),
    api(base + '/labels'), api(base + '/modules'),
  ]);
  if (token !== state.viewToken) return;
  const failed = results.slice(0, 5).find(function (r) { return r.status === 'rejected'; });
  if (failed) {
    renderViewHtml(pageHead('Operations', 'Projects', '') + errorBlock(errMessage(failed.reason)));
    return;
  }
  const project = results[0].value;
  const items = results[1].value || [];
  const states = results[2].value || [];
  const assignees = results[3].value || [];
  const progress = results[4].value || {};
  // Project membership is visible only to project admins; a 403 simply hides
  // the card rather than blocking the whole project view.
  const members = results[5].status === 'fulfilled' ? (results[5].value || []) : null;
  const board = results[6].status === 'fulfilled' ? results[6].value : null;
  const savedViews = results[7].status === 'fulfilled' ? (results[7].value || []) : [];
  const labels = results[8].status === 'fulfilled' ? (results[8].value || []) : [];
  const modules = results[9].status === 'fulfilled' ? (results[9].value || []) : [];
  const activeStates = states.filter(function (s) { return s.is_active; });
  const statusOptions = activeStates.length
    ? activeStates.map(function (s) { return [s.name, cap(s.name) + ' Ãƒâ€šÃ‚Â· ' + cap(s.group)]; })
    : builtinItemStates();
  const assigneeOptions = [['', 'Unassigned']].concat(assignees.map(function (a) {
    return [a.id, a.display_name || a.email];
  }));

  const actions = '<a class="btn" href="#/projects">' + icon('chevronLeft', 15) + ' All projects</a>' +
    (can(P.taskWrite) ? '<button class="btn btn--primary" data-action="create-work-item" data-id="' +
      attr(project.id) + '">' + icon('plus', 15) + ' New work item</button>' : '');
  let html = pageHead('Operations', project.name,
    cap(project.status) + (project.restricted ? ' Ãƒâ€šÃ‚Â· Private project' : '') +
    ' Ãƒâ€šÃ‚Â· Due ' + fmtDate(project.due_at) +
    ' Ãƒâ€šÃ‚Â· ' + String(progress.total_items || 0) + ' work items', actions);

  // PL-042: compact cards/bar chart from the real /projects/{id}/progress fields.
  const progressBuckets = [['total_items', 'Total items'], ['todo_items', 'To do'], ['in_progress_items', 'In progress'], ['done_items', 'Done']];
  const maxBucket = Math.max(1, progressBuckets.reduce(function (m, b) {
    return Math.max(m, Number(progress[b[0]] || 0));
  }, 0));
  html += '<section class="card"><div class="card-head"><div class="card-head-main">' +
    '<div class="card-title">Delivery progress</div>' +
    '<div class="card-sub">Counts come from real work items; no velocity or burndown data is invented.</div>' +
    '</div></div><div class="card-body"><div class="row" style="gap:12px;flex-wrap:wrap">' +
    progressBuckets.map(function (bucket) {
      const value = Number(progress[bucket[0]] || 0);
      const width = Math.min(100, (100 * value) / maxBucket);
      return '<div class="progress-bucket-card" data-progress-bucket="' + attr(bucket[0]) + '">' +
        '<div class="card-sub">' + esc(bucket[1]) + '</div>' +
        '<div class="stat-value">' + esc(String(value)) + '</div>' +
        '<div style="height:6px;border-radius:999px;background:var(--line-soft);overflow:hidden;margin-top:8px">' +
        '<div style="height:100%;width:' + width + '%;background:var(--blue);border-radius:999px"></div>' +
        '</div></div>';
    }).join('') + '</div>' +
    '<div class="list-row" data-progress-percent><div class="list-row-main">' +
    '<div class="list-row-title">Completion</div>' +
    '<div class="list-row-sub">' + esc(String(progress.done_items || 0) + ' of ' +
      String(progress.total_items || 0) + ' complete / ' +
      String(progress.completion_percent || 0) + '%') + '</div>' +
    '<div style="height:6px;border-radius:999px;background:var(--line-soft);overflow:hidden;margin-top:8px">' +
    '<div style="height:100%;width:' + Number(progress.completion_percent || 0) +
    '%;background:var(--blue);border-radius:999px"></div></div></div></div></div></section>';

  if (members !== null) {
    const memberOptions = assignees.filter(function (a) {
      return !members.some(function (m) { return m.user_id === a.id; });
    }).map(function (a) { return [a.id, a.display_name || a.email]; });
    const roleOptions = [['lead', 'Lead'], ['member', 'Member'], ['viewer', 'Viewer']];
    html += '<section class="card"><div class="card-head"><div class="card-head-main">' +
      '<div class="card-title">Project access</div><div class="card-sub">' +
      'Roles and the default assignee are managed on this project, not on the workspace.</div></div></div>' +
      '<div class="card-body"><div class="table-wrap"><table class="data"><thead><tr>' +
      '<th>Member</th><th>Role</th><th>Default assignee</th><th>Subscribed</th><th></th></tr></thead><tbody>' +
      (members.length ? members.map(function (m) {
        return '<tr><td><div class="cell-title">' + esc(m.display_name || m.email || m.user_id) + '</div>' +
          (m.email && m.display_name ? '<div class="cell-sub">' + esc(m.email) + '</div>' : '') + '</td>' +
          '<td><select class="select" data-change="project-member-role" data-uid="' + attr(m.user_id) +
          '" aria-label="Role for ' + attr(m.display_name || m.email || m.user_id) + '">' +
          selectOptions(roleOptions, m.role) + '</select></td>' +
          '<td><button class="btn btn--sm btn--ghost" data-action="toggle-project-default-assignee" ' +
          'data-uid="' + attr(m.user_id) + '" data-on="' + (m.is_default_assignee ? 'false' : 'true') + '">' +
          (m.is_default_assignee ? 'Default' : 'Set default') + '</button></td>' +
          '<td><button class="btn btn--sm btn--ghost" data-action="toggle-project-subscribed" ' +
          'data-uid="' + attr(m.user_id) + '" data-on="' + (m.subscribed ? 'false' : 'true') + '">' +
          (m.subscribed ? 'Subscribed' : 'Not subscribed') + '</button></td>' +
          '<td>' + (m.user_id === project.owner_id ? '<span class="muted tiny">Owner</span>' :
            '<button class="btn btn--sm btn--ghost" data-action="remove-project-member" data-uid="' +
            attr(m.user_id) + '">Remove</button>') + '</td></tr>';
      }).join('') : '<tr><td colspan="5" class="muted small">No project members listed.</td></tr>') +
      '</tbody></table></div>';
    if (memberOptions.length) {
      html += '<form data-form="project-member-add" data-project-id="' + attr(project.id) + '">' +
        '<div class="form-grid">' +
        field('user_id', 'Workspace member', {
          type: 'select', options: selectOptions([['', 'Choose a member']].concat(memberOptions), ''), required: true,
        }) +
        field('role', 'Project role', { type: 'select', options: selectOptions(roleOptions, 'member') }) +
        '</div><div class="form-actions"><button type="submit" class="btn">' +
        icon('plus', 15) + ' Add to project</button></div></form>';
    }
    html += '</div></section>';
  }

  html += '<section class="card"><div class="toolbar">' +
    '<select class="select" data-change="item-filter" aria-label="Filter work items">' +
    selectOptions([['all', 'All work items'], ['overdue', 'Overdue only']], state.itemFilter) +
    '</select>' +
    '<select class="select" data-change="item-priority" aria-label="Filter by priority">' +
    selectOptions([['', 'Any priority'], ['urgent', 'Urgent'], ['high', 'High'], ['medium', 'Medium'], ['low', 'Low']], state.itemPriority || '') +
    '</select>' +
    (savedViews.length ? '<select class="select" data-change="saved-view" aria-label="Saved views">' +
      selectOptions([['', 'All views']].concat(savedViews.map(function (v) { return [v.id, v.name]; })), '') +
      '</select>' : '') +
    '<span class="muted tiny">' + items.length + ' shown</span>' +
    (can(P.taskWrite) ? '<span class="row" style="margin-left:auto;gap:6px">' +
      '<button class="btn btn--sm btn--ghost" data-action="work-item-board">' + icon('grid', 13) + ' Board</button>' +
      '<button class="btn btn--sm btn--ghost" data-action="work-item-labels">' + icon('tag', 13) + ' Labels</button>' +
      '<button class="btn btn--sm btn--ghost" data-action="work-item-modules">' + icon('layers', 13) + ' Modules</button>' +
      '<button class="btn btn--sm btn--ghost" data-action="work-item-activity">' + icon('activity', 13) + ' Activity</button>' +
      '</span>' : '') +
    '</div>';
  if (!items.length) {
    html += emptyState('checkSquare', 'No work items', state.itemFilter === 'overdue'
      ? 'Nothing is overdue in this project.'
      : 'Create a work item to start tracking delivery.');
  } else {
    html += '<div class="table-wrap"><table class="data"><thead><tr><th>Work item</th><th>State</th>' +
      '<th>Assignee</th><th>Due</th><th>Updated</th></tr></thead><tbody>' +
      items.map(function (item) {
        const overdue = isOverdueItem(item);
        return '<tr><td><div class="cell-title">' + esc(item.title) + '</div>' +
          '<div class="cell-sub">' + (item.completed_at ? 'Completed ' + esc(fmtDate(item.completed_at)) :
            esc(cap(item.state_group || 'todo') + ' bucket')) + '</div></td>' +
          '<td>' + (can(P.taskWrite)
            ? '<select class="select" data-change="item-status" data-id="' + attr(item.id) +
              '" aria-label="State for ' + attr(item.title) + '">' +
              selectOptions(statusOptions, item.status) + '</select>'
            : '<span class="badge badge--plain">' + esc(cap(item.status)) + '</span>') + '</td>' +
          '<td>' + (can(P.taskWrite)
            ? '<select class="select" data-change="item-assignee" data-id="' + attr(item.id) +
              '" aria-label="Assignee for ' + attr(item.title) + '">' +
              selectOptions(assigneeOptions, item.assignee_id || '') + '</select>'
            : '<span class="small">' + esc(String(item.assignee_id || '').slice(0, 8) || 'ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â') + '</span>') + '</td>' +
          '<td class="small">' + esc(fmtDate(item.due_at)) +
          (overdue ? ' <span class="badge badge--red">Overdue</span>' : '') + '</td>' +
          '<td class="muted small">' + esc(relTime(item.updated_at)) + '</td></tr>';
      }).join('') + '</tbody></table></div>';
  }
  html += '</section>';

  html += '<section class="card"><div class="toolbar"><strong>State set</strong>' +
    '<span class="muted tiny">Grouped states roll up into progress.</span></div>' +
    '<div class="table-wrap"><table class="data"><thead><tr><th>State</th><th>Progress group</th>' +
    '<th>Order</th><th>Status</th><th></th></tr></thead><tbody>' +
    (states.length ? states.map(function (s) {
      return '<tr><td class="cell-title">' + esc(s.name) + '</td>' +
        '<td><span class="badge badge--plain">' + esc(cap(s.group)) + '</span></td>' +
        '<td class="small">' + Number(s.position || 0) + '</td>' +
        '<td>' + (s.is_active ? '<span class="badge badge--green">Active</span>' :
          '<span class="badge badge--amber">Inactive</span>') + '</td>' +
        '<td>' + (can(P.taskWrite) ? '<button class="btn btn--sm btn--ghost" data-action="toggle-project-state" data-id="' +
          attr(s.id) + '" data-active="' + (s.is_active ? 'true' : 'false') + '">' +
          (s.is_active ? 'Deactivate' : 'Activate') + '</button>' : '') + '</td></tr>';
    }).join('') : '<tr><td colspan="5" class="muted small">Using the built-in states: ' +
      esc(builtinItemStates().map(function (s) { return s[1]; }).join(', ')) + '.</td></tr>') +
    '</tbody></table></div>';
  if (can(P.taskWrite)) {
    html += '<form data-form="project-state-create" data-project-id="' + attr(project.id) + '">' +
      '<div class="form-grid">' +
      field('name', 'New state', { placeholder: 'e.g. Code review', required: true }) +
      field('group', 'Progress group', {
        type: 'select', options: selectOptions(
          [['todo', 'To do'], ['in_progress', 'In progress'], ['done', 'Done']], 'todo'),
      }) +
      field('position', 'Order', { type: 'number', value: '0' }) +
      '</div><div class="form-actions"><button type="submit" class="btn">' +
      icon('plus', 15) + ' Add state</button></div></form>';
  }
  html += '</section>';
  renderViewHtml(html);
}

/* ------------------------------------------------------------------ *
 * Documents ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â metadata, enforced share controls and tracked engagement
 * ------------------------------------------------------------------ */

function docRoomName(rooms, roomId) {
  if (!roomId) return 'Unfiled';
  const found = rooms.find(function (r) { return r.id === roomId; });
  return found ? found.name : 'Unknown room';
}

function docSize(value) {
  const bytes = Number(value || 0);
  if (!bytes) return 'ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â';
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

async function loadDocuments(token) {
  if (!can(P.documentRead)) {
    renderViewHtml(pageHead('Revenue', 'Documents', '') +
      errorBlock('Your role does not include document access.'));
    return;
  }
  loadingView('Documents', 'Data rooms, document metadata and share controls');
  const results = await Promise.allSettled([
    api(apiW('/documents/rooms')), api(apiW('/documents')),
  ]);
  if (token !== state.viewToken) return;
  const failed = results.find(function (r) { return r.status === 'rejected'; });
  if (failed) {
    renderViewHtml(pageHead('Revenue', 'Documents', '') + errorBlock(errMessage(failed.reason)));
    return;
  }
  const rooms = results[0].value || [];
  const docs = results[1].value || [];
  const actions = can(P.documentWrite)
    ? '<button class="btn" data-action="create-room">' + icon('plus', 15) + ' New room</button>' +
      '<button class="btn btn--primary" data-action="create-document">' + icon('plus', 15) + ' Add document</button>'
    : '';

  let html = pageHead('Revenue', 'Documents',
    docs.length + ' document record' + (docs.length === 1 ? '' : 's') + ' Ãƒâ€šÃ‚Â· ' +
    rooms.length + ' data room' + (rooms.length === 1 ? '' : 's'), actions);
  html += governanceNote('Document records carry metadata and share policy. Encrypted file blobs uploaded through the document security API are protected at rest with a versioned local key. No external message is sent.');

  html += '<section class="card"><div class="toolbar"><strong>Data rooms</strong>' +
    '<span class="muted tiny">Group related collateral before sharing.</span></div>';
  if (!rooms.length) {
    html += emptyState('archive', 'No data rooms yet', 'Create a room to organise document records.');
  } else {
    html += '<div class="table-wrap"><table class="data"><thead><tr><th>Room</th>' +
      '<th>Description</th><th>Created</th></tr></thead><tbody>' +
      rooms.map(function (r) {
        return '<tr><td class="cell-title">' + esc(r.name) + '</td>' +
          '<td class="small">' + esc(r.description || 'ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â') + '</td>' +
          '<td class="muted small">' + esc(fmtDate(r.created_at)) + '</td></tr>';
      }).join('') + '</tbody></table></div>';
  }
  html += '</section>';

  html += '<section class="card"><div class="toolbar"><strong>Document records</strong>' +
    '<span class="muted tiny">' + docs.length + ' shown</span></div>';
  if (!docs.length) {
    html += emptyState('note', 'No documents yet', 'Add a document record with an opaque storage reference.',
      can(P.documentWrite) ? '<button class="btn btn--primary btn--sm" data-action="create-document">Add document</button>' : '');
  } else {
    html += '<div class="table-wrap"><table class="data"><thead><tr><th>Document</th><th>Type</th>' +
      '<th>Room</th><th>Size</th><th></th></tr></thead><tbody>' +
      docs.map(function (d) {
        return '<tr><td><div class="cell-title">' + esc(d.title) + '</div>' +
          '<div class="cell-sub mono">' + esc(d.storage_path) + '</div></td>' +
          '<td><span class="badge badge--plain">' + esc(cap(d.doc_type)) + '</span></td>' +
          '<td class="small">' + esc(docRoomName(rooms, d.room_id)) + '</td>' +
          '<td class="muted small">' + esc(docSize(d.size_bytes)) + '</td>' +
          '<td><button class="btn btn--sm btn--ghost" data-action="view-document" data-id="' +
          attr(d.id) + '">' + icon('eye', 14) + ' Manage</button></td></tr>';
      }).join('') + '</tbody></table></div>';
  }
  html += '</section>';
  renderViewHtml(html);
}

async function loadDocumentDetail(documentId, token) {
  if (!can(P.documentRead)) {
    renderViewHtml(pageHead('Revenue', 'Documents', '') +
      errorBlock('Your role does not include document access.'));
    return;
  }
  loadingView('Documents', 'Share controls and engagement history');
  const base = apiW('/documents/' + encodeURIComponent(documentId));
  const results = await Promise.allSettled([
    api(base), api(base + '/links'), api(base + '/analytics'),
  ]);
  if (token !== state.viewToken) return;
  const failed = results.find(function (r) { return r.status === 'rejected'; });
  if (failed) {
    renderViewHtml(pageHead('Revenue', 'Documents', '') + errorBlock(errMessage(failed.reason)));
    return;
  }
  const doc = results[0].value;
  const links = results[1].value || [];
  const analytics = results[2].value || [];
  const actions = '<a class="btn" href="#/documents">' + icon('chevronLeft', 15) + ' All documents</a>' +
    (can(P.documentWrite)
      ? '<button class="btn" data-action="create-watermark-preview" data-id="' + attr(doc.id) + '">' +
        icon('eye', 15) + ' Preview watermark</button>' +
        '<button class="btn btn--primary" data-action="create-document-link" data-id="' +
        attr(doc.id) + '">' + icon('plus', 15) + ' New share link</button>'
      : '');

  let html = pageHead('Revenue', doc.title,
    cap(doc.doc_type) + ' Ãƒâ€šÃ‚Â· ' + docSize(doc.size_bytes) + ' Ãƒâ€šÃ‚Â· ' + links.length + ' share links', actions);
  html += '<section class="card"><div class="list-row"><span class="stat-icon">' + icon('archive', 15) +
    '</span><div class="list-row-main"><div class="list-row-title">' + esc(doc.title) + '</div>' +
    '<div class="list-row-sub mono">' + esc(doc.storage_path) + '</div>' +
    '<div class="cell-sub">Recorded by ' + esc(String(doc.uploaded_by || '').slice(0, 8)) +
    ' on ' + esc(fmtDate(doc.created_at)) + '. Encrypted blobs, when uploaded through the security API, are stored separately from this metadata record.</div>' +
    '</div></div></section>';

  html += '<section class="card"><div class="toolbar"><strong>Share links</strong>' +
    '<span class="muted tiny">Controls are enforced on every recorded view.</span></div>';
  if (!links.length) {
    html += emptyState('link', 'No share links', 'Create a link to share this metadata with enforced controls.');
  } else {
    html += '<div class="table-wrap"><table class="data"><thead><tr><th>Link</th><th>Controls</th>' +
      '<th>Views</th><th>Expires</th><th></th></tr></thead><tbody>' +
      links.map(function (l) {
        const controls = [
          l.has_password ? 'Password' : 'Open',
          l.view_only ? 'View only' : 'Editable',
          l.download_allowed ? 'Download on' : 'No download',
        ].join(' Ãƒâ€šÃ‚Â· ');
        return '<tr><td><div class="cell-title mono">' + esc(String(l.id).slice(0, 8)) + '</div>' +
          '<div class="cell-sub">' + esc(fmtDate(l.created_at)) + '</div></td>' +
          '<td class="small">' + esc(controls) + '</td>' +
          '<td class="small">' + Number(l.view_count || 0) +
          (l.max_views != null ? ' / ' + Number(l.max_views) : '') + '</td>' +
          '<td class="muted small">' + esc(l.expires_at ? fmtDate(l.expires_at) : 'Never') +
          (l.revoked ? ' <span class="badge badge--red">Revoked</span>' : '') + '</td>' +
          '<td>' + (can(P.documentAdmin) && !l.revoked
            ? '<button class="btn btn--sm btn--ghost" data-action="revoke-document-link" data-id="' +
              attr(l.id) + '">' + icon('lock', 14) + ' Revoke</button>' : '') + '</td></tr>';
      }).join('') + '</tbody></table></div>';
  }
  html += '</section>';

  html += '<section class="card"><div class="toolbar"><strong>Page engagement</strong>' +
    '<span class="muted tiny">Aggregated from recorded visits.</span></div>';
  if (!analytics.length) {
    html += emptyState('activity', 'No engagement yet', 'Views and downloads appear here once a link is used.');
  } else {
    html += '<div class="table-wrap"><table class="data"><thead><tr><th>Page</th><th>Views</th>' +
      '<th>Total time</th></tr></thead><tbody>' +
      analytics.map(function (a) {
        return '<tr><td class="cell-title">Page ' + Number(a.page_number) + '</td>' +
          '<td class="small">' + Number(a.views) + '</td>' +
          '<td class="muted small">' + Number(a.total_duration_seconds || 0) + 's</td></tr>';
      }).join('') + '</tbody></table></div>';
  }
  html += '</section>';
  renderViewHtml(html);
}

async function copyDocumentToken(token) {
  try {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(token);
      toast('Share token copied. It is shown only once.', 'success');
    } else {
      const input = document.getElementById('document-token');
      if (input) input.select();
      toast('Select and copy the share token manually.', 'error');
    }
  } catch (e) {
    toast('Copy is unavailable here ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â select the share token manually.', 'error');
  }
}

/* ------------------------------------------------------------------ *
 * Notifications
 * ------------------------------------------------------------------ */

async function loadNotifications(token) {
  if (!can(P.notificationRead)) {
    renderViewHtml(pageHead('Operations', 'Notifications', '') + errorBlock('Your role does not include notification access.'));
    return;
  }
  loadingView('Notifications', 'Messages addressed to you');
  try {
    // Opening the feed marks rows seen. Reading remains a separate, explicit act.
    try { await api(apiW('/notifications/seen-all'), { method: 'POST' }); } catch (e) { /* non-fatal */ }
    const rows = await api(apiW('/notifications'));
    if (token !== state.viewToken) return;
    state.caches.notifications = rows || [];
    updateUnreadBadge();
    const counts = await api(apiW('/notifications/counts'));
    if (token !== state.viewToken) return;
    state.notifCounts = counts;
    const unread = counts ? counts.unread : state.caches.notifications.filter(function (n) { return !n.read; }).length;
    const actions = (unread ? '<button class="btn" data-action="read-all-notifications">' + icon('check', 15) + ' Mark all read</button>' : '') +
      '<button class="btn" data-action="open-notification-preferences">' + icon('settings', 15) + ' Notification preferences</button>';
    let html = pageHead('Operations', 'Notifications', unread + ' unread of ' + (counts ? counts.total : state.caches.notifications.length) + '.', actions);
    if (!state.caches.notifications.length) {
      html += '<section class="card">' + emptyState('bell', 'You are all caught up', 'Notifications created by workflows will appear here.') + '</section>';
    } else {
      html += '<section class="card">' + state.caches.notifications.map(function (n) {
        const label = esc(n.title || n.message);
        const heading = n.link ? '<a href="' + attr(n.link) + '">' + label + '</a>' : label;
        return '<div class="list-row' + (n.read ? '' : ' unread-row') + '">' +
          '<span class="stat-icon">' + icon(n.read ? 'mail' : 'bell', 15) + '</span>' +
          '<div class="list-row-main"><div class="list-row-title">' + heading + '</div>' +
          '<div class="list-row-sub">' + esc(relTime(n.created_at)) +
          ' <span class="badge badge--plain">' + esc(n.category || 'general') + '</span>' +
          (!n.seen ? ' Ãƒâ€šÃ‚Â· New' : '') +
          (n.contact_id ? ' Ãƒâ€šÃ‚Â· Contact ' + esc(String(n.contact_id).slice(0, 8)) : '') +
          '</div>' +
          (n.title ? '<div class="list-row-sub">' + esc(n.message) + '</div>' : '') +
          '</div>' +
          '<div class="list-row-side">' +
          '<span class="badge ' + (n.read ? 'badge--green' : 'badge--amber') + '">' + (n.read ? 'Read' : 'Unread') + '</span>' +
          (!n.read ? '<button class="btn btn--sm" data-action="read-notification" data-id="' + attr(n.id) + '">Mark read</button>' : '') +
          '</div></div>';
      }).join('') + '</section>';
    }
    renderViewHtml(html);
  } catch (err) {
    if (token !== state.viewToken) return;
    renderViewHtml(pageHead('Operations', 'Notifications', '') + errorBlock(errMessage(err)));
  }
}

/* ------------------------------------------------------------------ *
 * Agent activity ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â the real append-only audit feed
 * ------------------------------------------------------------------ */

async function loadActivity(token) {
  if (!can(P.eventRead)) {
    renderViewHtml(pageHead('Workspace', 'Agent activity', '') + errorBlock('Your role does not include audit event access.'));
    return;
  }
  loadingView('Agent activity', 'Append-only audit log for this workspace');
  try {
    const rows = await fetchAll(apiW('/events'), 500);
    if (token !== state.viewToken) return;
    state.caches.events = rows;
    const types = Array.from(new Set(rows.map(function (e) { return e.event_type; }))).sort();
    const visible = state.eventFilter ? rows.filter(function (e) { return e.event_type === state.eventFilter; }) : rows;
    const reversed = visible.slice().reverse();
    let html = pageHead('Workspace', 'Agent activity',
      rows.length + ' recorded ' + (rows.length === 1 ? 'event' : 'events') + ' in sequence order.',
      '<button class="btn" data-action="refresh-view">' + icon('refresh', 15) + ' Refresh</button>');
    html += '<div class="info-banner">' + icon('info', 16) +
      '<div>Events are append-only. They are written by workflows such as intake, approvals, task changes and membership.</div></div>';
    html += '<section class="card"><div class="toolbar"><select class="select" data-change="event-filter" aria-label="Filter by event type">' +
      selectOptions([['', 'All event types']].concat(types), state.eventFilter) + '</select>' +
      '<span class="muted tiny">Showing ' + reversed.length + '</span></div>' +
      (reversed.length ? '<div class="timeline">' + reversed.map(function (e) { return eventItem(e, false); }).join('') + '</div>'
        : emptyState('activity', 'No events found', 'Nothing has been recorded yet, or no events match this filter.')) + '</section>';
    renderViewHtml(html);
  } catch (err) {
    if (token !== state.viewToken) return;
    renderViewHtml(pageHead('Workspace', 'Agent activity', '') + errorBlock(errMessage(err)));
  }
}

/* ------------------------------------------------------------------ *
 * Outreach drafts
 * ------------------------------------------------------------------ */

async function loadDrafts(token) {
  if (!can(P.outreachRead)) {
    renderViewHtml(pageHead('Operations', 'Outreach drafts', '') + errorBlock('Your role does not include outreach access.'));
    return;
  }
  loadingView('Outreach drafts', 'Prepared messages awaiting approval');
  const results = await Promise.allSettled([
    api(apiW('/outreach-drafts')),
    can(P.contactRead) ? fetchAll(apiW('/contacts'), 100) : Promise.resolve([]),
  ]);
  if (token !== state.viewToken) return;
  if (results[0].status === 'rejected') {
    renderViewHtml(pageHead('Operations', 'Outreach drafts', '') + errorBlock(errMessage(results[0].reason)));
    return;
  }
  const drafts = results[0].value || [];
  const contacts = results[1].status === 'fulfilled' ? results[1].value : [];
  const map = {};
  contacts.forEach(function (c) { map[c.id] = c; });
  state.caches.drafts = drafts;
  const pending = drafts.filter(function (d) { return d.status === 'draft'; }).length;
  let html = pageHead('Operations', 'Outreach drafts', pending + ' pending approval of ' + drafts.length + ' total.');
  if (!drafts.length) {
    html += '<section class="card">' + emptyState('mail', 'No drafts yet',
      'Recording a website form submission creates a contact, task, notification and outreach draft together.') + '</section>';
  } else {
    html += '<div class="stack">' + drafts.map(function (d) {
      return '<section class="card"><div class="card-head"><div class="card-head-main">' +
        '<div class="card-title">' + esc(d.subject) + '</div><div class="card-sub">' +
        esc(contactLabel(map, d.contact_id)) + (d.approved_at ? ' Ãƒâ€šÃ‚Â· Approved ' + esc(fmtDateTime(d.approved_at)) : '') +
        '</div></div>' + statusBadge(d.status) +
        (can(P.outreachApprove) && d.status === 'draft' ? '<button class="btn btn--sm btn--primary" data-action="approve-draft" data-id="' + attr(d.id) + '">' + icon('check', 14) + ' Approve</button>' : '') +
        '</div><div class="card-body"><p class="small" style="white-space:pre-wrap">' + esc(d.body) + '</p>' +
        '<div class="divider"></div><div class="row tiny muted"><span class="mono">' + esc(d.id) + '</span>' +
        (d.approved_by ? '<span>Ãƒâ€šÃ‚Â· Approved by ' + esc(String(d.approved_by).slice(0, 8)) + '</span>' : '') + '</div></div></section>';
    }).join('') + '</div>';
  }
  renderViewHtml(html);
}

/* ------------------------------------------------------------------ *
 * Workspaces ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â onboarding, switcher, membership
 * ------------------------------------------------------------------ */

async function loadWorkspacesPage(token) {
  loadingView('Workspaces', 'Your tenant memberships');
  await loadMyWorkspaces();
  let members = null, memberError = '';
  if (can(P.memberManage)) {
    try { members = await api(apiW('/members')) || []; }
    catch (err) { memberError = errMessage(err); }
  }
  let settings = null, summary = null, flags = [], adminError = '';
  if (can(P.contactRead)) {
    const results = await Promise.allSettled([
      api(apiW('/admin/settings')),
      api(apiW('/admin/summary')),
      api(apiW('/flags')),
    ]);
    if (results[0].status === 'fulfilled') settings = results[0].value;
    if (results[1].status === 'fulfilled') summary = results[1].value;
    if (results[2].status === 'fulfilled') flags = results[2].value || [];
    if (results.some(function (r) { return r.status === 'rejected'; })) {
      adminError = errMessage(results.find(function (r) { return r.status === 'rejected'; }).reason);
    }
    state.caches.adminSettings = settings;
    state.caches.adminFlags = flags;
  }
  if (token !== state.viewToken) return;

  const actions = (can(P.workspaceManage) ? '<button class="btn btn--primary" data-action="create-workspace">' + icon('plus', 16) + ' New workspace</button>' : '') +
    '<button class="btn" data-action="accept-invite">' + icon('link', 16) + ' Accept invitation</button>';
  let html = pageHead('Account', 'Workspaces', 'A workspace is the boundary for every record and event.', actions);
  if (state.workspaceError) html += errorBlock('Workspaces could not be loaded ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â ' + state.workspaceError);
  if (!state.workspaces.length) {
    html += '<section class="card">' + emptyState('grid', 'No workspaces', 'Your account has no active workspace membership.') + '</section>';
  } else {
    html += '<div class="ws-grid">' + state.workspaces.map(function (w) {
      const current = w.id === ws();
      return '<div class="card ws-card' + (current ? ' current' : '') + '">' +
        '<div class="row-between"><div class="stat-icon">' + icon('grid', 17) + '</div>' +
        (current ? '<span class="badge badge--green">Current</span>' : '<span class="badge badge--plain">' + esc(cap(w.role)) + '</span>') + '</div>' +
        '<div><div class="ws-card-name">' + esc(w.name) + '</div><div class="tiny muted mono">' + esc(String(w.id).slice(0, 12)) + 'ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦</div></div>' +
        (current ? '<div class="tiny faint">You are working in this workspace.</div>'
          : '<button class="btn btn--sm" data-action="switch-workspace" data-id="' + attr(w.id) + '" data-name="' + attr(w.name) + '">' +
            icon('arrowRight', 14) + ' Switch to workspace</button>') + '</div>';
    }).join('') + '</div>';
  }

  html += '<div class="stack" style="margin-top:24px">';
  if (can(P.memberManage)) {
    html += '<section class="card"><div class="card-head"><div class="card-head-main"><div class="card-title">Members</div>' +
      '<div class="card-sub">People with access to this workspace</div></div>' +
      (can(P.memberInvite) ? '<button class="btn btn--sm" data-action="invite-member">' + icon('plus', 14) + ' Invite member</button>' : '') + '</div>' +
      (memberError ? errorBlock(memberError)
        : (!members || !members.length ? emptyState('users', 'No members', 'No membership records were returned.')
          : members.map(function (m) {
            return '<div class="list-row">' + avatar(m.display_name || m.email, 'sm') +
              '<div class="list-row-main"><div class="list-row-title">' + esc(m.display_name || m.email) + '</div>' +
              '<div class="list-row-sub">' + esc(m.email) + '</div></div>' +
              '<div class="list-row-side">' + statusBadge(m.status) + statusBadge(m.role) + '</div></div>';
          }).join(''))) + '</section>';
  }
  if (can(P.contactRead)) {
    const cfg = (settings && settings.settings) || {};
    html += '<section class="card"><div class="card-head"><div class="card-head-main">' +
      '<div class="card-title">Workspace administration</div>' +
      '<div class="card-sub">Live counts and settings from this workspace only</div></div></div>' +
      (adminError ? errorBlock('Administration data could not be loaded ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â ' + adminError) : '') +
      (summary ? '<div class="stats">' +
        statCard('users', 'Active members', String(summary.active_members), 'Persistent membership') +
        statCard('zap', 'Enabled flags', String(summary.enabled_flags), 'Workspace-scoped') +
        statCard('link', 'Integrations', String(summary.configured_integrations), 'Non-sensitive settings') +
        statCard('activity', 'Adapter calls', String(summary.recorded_adapter_calls), 'Local records') +
        '</div>' : '') +
      (can(P.workspaceManage) ? '<div class="card-body"><form data-form="workspace-settings" class="form-grid">' +
        field('name', 'Workspace name', { required: true, value: (settings && settings.name) || '', span: true }) +
        field('timezone', 'Timezone', { value: cfg.timezone || '', placeholder: 'Asia/Calcutta' }) +
        field('currency', 'Currency', { value: cfg.currency || '', placeholder: 'INR' }) +
        '<div class="field span-2"><button type="submit" class="btn btn--primary">' + icon('check', 15) + ' Save settings</button></div>' +
        '</form></div>' : '<div class="card-body small muted">You need workspace management permission to change these settings.</div>') +
      '<div class="card-body" style="border-top:1px solid var(--line-soft)"><div class="row-between"><div>' +
      '<div class="card-title">Feature flags</div>' +
      '<div class="card-sub">Deterministic, workspace-isolated evaluation across environments</div></div>' +
      '<div class="field" style="min-width:170px"><label class="field-label" for="flag-environment">Environment</label>' +
      '<select class="select" id="flag-environment" data-change="flag-environment">' +
      selectOptions([['production', 'Production'], ['dev', 'Development'], ['staging', 'Staging'], ['test', 'Test']], state.flagEnvironment) +
      '</select></div></div>' +
      (flags.length ? '<div class="table-wrap"><table class="data"><thead><tr><th>Key</th><th>Default</th><th>Status</th><th>Rollout</th><th></th></tr></thead><tbody>' +
        flags.map(function (f) {
          return '<tr><td><div class="cell-title mono">' + esc(f.key) + '</div>' +
            (f.description ? '<div class="cell-sub">' + esc(f.description) + '</div>' : '') + '</td>' +
            '<td class="small mono">' + esc(String(f.default_value || 'off')) + '</td>' +
            '<td>' + statusBadge(f.enabled ? 'enabled' : 'disabled') + '</td>' +
            '<td class="small">' + esc(String(f.rollout_percent)) + '%</td>' +
            '<td><div class="row" style="gap:6px">' +
            '<button class="btn btn--sm btn--ghost" data-action="flag-rules" data-key="' + attr(f.key) + '">' + icon('layers', 13) + ' Rules</button>' +
            '<button class="btn btn--sm btn--ghost" data-action="flag-exposures" data-key="' + attr(f.key) + '">' + icon('activity', 13) + ' Exposure</button>' +
            (can(P.workspaceManage)
              ? '<button class="btn btn--sm" data-action="toggle-flag" data-key="' + attr(f.key) + '" data-enabled="' + (f.enabled ? 'true' : 'false') + '">' +
                (f.enabled ? 'Disable' : 'Enable') + '</button>'
              : '') + '</div></td></tr>';
        }).join('') + '</tbody></table></div>'
        : emptyState('zap', 'No flags', 'Workspace feature flags will appear here.')) +
      (can(P.workspaceManage) ? '<div class="row" style="gap:10px;margin-top:16px;flex-wrap:wrap">' +
        '<form data-form="workspace-flag-create" class="form-grid" style="flex:1;min-width:260px">' +
        field('key', 'New flag key', { required: true, placeholder: 'new_checkout', span: true }) +
        field('default_value', 'Default value', { value: 'off', placeholder: 'off' }) +
        '<div class="field"><button type="submit" class="btn">' + icon('plus', 15) + ' Add flag</button></div></form>' +
        '<form data-form="sdk-connection-create" class="form-grid" style="flex:1;min-width:260px">' +
        field('name', 'SDK connection name', { required: true, placeholder: 'Web client', span: true }) +
        '<div class="field"><button type="submit" class="btn">' + icon('link', 15) + ' Create SDK key</button></div></form>' +
        '</div><button class="btn btn--sm btn--ghost" data-action="flag-sdk-payload" style="margin-top:8px">' +
        icon('copy', 14) + ' View SDK payload</button>' : '') +
      '</div></section>';
  }
  html += '<section class="card"><div class="card-head"><div class="card-head-main"><div class="card-title">Joining another workspace</div></div></div>' +
    '<div class="card-body small muted">Ask a workspace owner for an invitation token, then use <strong>Accept invitation</strong>. ' +
    'Switching workspaces requires your password because the API issues a new session for each workspace.</div></section>';
  html += '</div>';
  renderViewHtml(html);
}

/* ------------------------------------------------------------------ *
 * Profile
 * ------------------------------------------------------------------ */

async function loadProfile(token) {
  if (!state.me) return;
  const me = state.me;
  let html = pageHead('Account', 'My profile', 'Your identity and effective authority in this workspace.',
    '<button class="btn" data-action="nav" data-route="settings">' + icon('settings', 15) + ' Settings</button>');
  html += '<div class="detail-grid"><div class="stack">' +
    '<section class="card"><div class="card-body"><div class="ident-head">' + avatar(me.user.display_name || me.user.email, 'lg') +
    '<div><div class="ident-name">' + esc(me.user.display_name) + '</div><div class="ident-mail">' + esc(me.user.email) + '</div></div></div>' +
    '<div class="divider"></div><dl class="kv"><dt>Email status</dt><dd>' + statusBadge(me.user.email_verified ? 'verified' : 'new') + '</dd>' +
    '<dt>Workspace</dt><dd>' + esc(me.workspace_name) + '</dd><dt>Role</dt><dd>' + esc(cap(me.role)) + '</dd>' +
    '<dt>User ID</dt><dd class="mono">' + esc(me.user.id) + '</dd></dl></div></section>' +
    '</div><div class="stack">' +
    '<section class="card"><div class="card-head"><div class="card-head-main"><div class="card-title">Permissions</div>' +
    '<div class="card-sub">Granted by your workspace role</div></div></div><div class="card-body"><div class="perm-grid">' +
    (me.permissions || []).map(function (perm) { return '<span class="chip chip--green">' + esc(perm) + '</span>'; }).join('') +
    '</div></div></section>' +
    '<section class="card"><div class="card-head"><div class="card-head-main"><div class="card-title">Account actions</div></div></div>' +
    '<div class="card-body stack-sm"><a class="btn btn--block" href="#/workspaces">' + icon('grid', 15) + ' Manage workspaces</a>' +
    '<a class="btn btn--block" href="#/settings">' + icon('lock', 15) + ' Security settings</a>' +
    '<button class="btn btn--danger btn--block" data-action="logout">' + icon('logout', 15) + ' Sign out</button></div></section>' +
    '</div></div>';
  renderViewHtml(html);
}

/* ------------------------------------------------------------------ *
 * Settings
 * ------------------------------------------------------------------ */

function showApiKeySecret(issued, title, sub) {
  openModal({
    title: title,
    sub: sub,
    body: '<div class="info-banner">' + icon('lock', 16) + '<div>Copy this secret now. It is not stored and will not be shown again.</div></div>' +
      '<div class="field"><label class="field-label">Secret</label>' +
      '<textarea class="input mono" rows="3" readonly data-api-key-secret>' + esc(issued.secret) + '</textarea></div>' +
      '<div class="form-actions"><button type="button" class="btn btn--primary" data-action="close-modal">Done</button></div>',
  });
}

async function loadSettings(token) {
  if (!state.me) return;
  let members = null, memberError = '';
  if (can(P.memberManage)) {
    try { members = await api(apiW('/members')) || []; }
    catch (err) { memberError = errMessage(err); }
  }
  let apiKeys = null, apiKeyError = '';
  if (can(P.workspaceManage)) {
    try { apiKeys = await api(apiW('/api-keys')) || []; }
    catch (err) { apiKeyError = errMessage(err); }
  }
  if (token !== state.viewToken) return;
  const me = state.me;
  let html = pageHead('Account', 'Settings', 'Workspace information, security and membership.');

  html += '<div class="detail-grid"><div class="stack">';
  html += '<section class="card"><div class="card-head"><div class="card-head-main"><div class="card-title">Workspace information</div></div></div>' +
    '<div class="card-body"><dl class="kv"><dt>Workspace</dt><dd>' + esc(me.workspace_name) + '</dd>' +
    '<dt>Workspace ID</dt><dd class="mono">' + esc(me.workspace_id) + '</dd>' +
    '<dt>Your role</dt><dd>' + esc(cap(me.role)) + '</dd>' +
    '<dt>API endpoint</dt><dd class="mono">' + esc(API_BASE) + '</dd></dl>' +
    '<div class="divider"></div><a class="btn btn--sm" href="#/workspaces">' + icon('grid', 15) + ' Workspaces</a></div></section>';

  html += '<section class="card"><div class="card-head"><div class="card-head-main"><div class="card-title">Change password</div>' +
    '<div class="card-sub">Other sessions are revoked when your password changes.</div></div></div>' +
    '<div class="card-body"><form data-form="change-password">' +
    field('current_password', 'Current password', { type: 'password', required: true, autocomplete: 'current-password' }) +
    '<div style="height:16px"></div>' +
    field('new_password', 'New password', { type: 'password', required: true, min: '8', autocomplete: 'new-password', hint: 'At least 8 characters.' }) +
    '<div class="form-actions"><button class="btn btn--primary" type="submit">' + icon('lock', 15) + ' Update password</button></div>' +
    '</form></div></section>';

  html += '<section class="card"><div class="card-head"><div class="card-head-main"><div class="card-title">Email verification</div>' +
    '<div class="card-sub">Current status: ' + (me.user.email_verified ? 'verified' : 'not verified') + '</div></div></div>' +
    '<div class="card-body"><div class="row" style="margin-bottom:16px">' +
    '<button class="btn" data-action="verify-request">' + icon('mail', 15) + ' Request verification token</button></div>' +
    '<form data-form="verify-confirm"><div class="form-grid">' +
    field('verify_token', 'Verification token', { required: true, placeholder: 'Paste your single-use token' }) +
    '<div style="display:flex;align-items:flex-end"><button class="btn" type="submit">' + icon('check', 15) + ' Verify</button></div>' +
    '</div></form>' + (me.user.email_verified ? '' :
      '<p class="tiny faint" style="margin-top:12px">The API does not send mail. A token is returned on screen only when the API runs in development mode.</p>') +
    '</div></section>';

  html += '<section class="card"><div class="card-head"><div class="card-head-main"><div class="card-title">Sign out</div>' +
    '<div class="card-sub">Revoke the current server-side session and clear local tokens.</div></div></div>' +
    '<div class="card-body"><button class="btn btn--danger" data-action="logout">' + icon('logout', 15) + ' Sign out</button></div></section>';
  html += '</div><div class="stack">';

  if (can(P.memberInvite) || can(P.memberManage)) {
    html += '<section class="card"><div class="card-head"><div class="card-head-main"><div class="card-title">Team access</div></div></div><div class="card-body">' +
      (can(P.memberInvite) ? '<button class="btn btn--primary" data-action="invite-member">' + icon('plus', 15) + ' Invite member</button>' : '') +
      (can(P.memberManage) ? '<div class="divider"></div>' +
        (memberError ? errorBlock(memberError)
          : (!members || !members.length ? '<p class="small muted">No members returned.</p>'
            : members.map(function (m) {
              const isMe = m.user_id === me.user.id;
              const active = m.status === 'active';
              const roleControl = m.role === 'owner' || isMe
                ? statusBadge(m.role)
                : '<select class="select" style="min-width:150px" data-change="member-role" data-user-id="' + attr(m.user_id) + '">' +
                  selectOptions([['admin', 'Admin'], ['sales_manager', 'Sales manager'],
                    ['sales_rep', 'Sales rep'], ['marketing', 'Marketing'],
                    ['support', 'Support'], ['read_only', 'Read only']], m.role) + '</select>';
              const lifecycle = m.role === 'owner' || isMe
                ? statusBadge(active ? 'active' : m.status)
                : '<button class="btn btn--sm btn--ghost" data-action="' +
                  (active ? 'suspend-member' : 'reactivate-member') + '" data-user-id="' +
                  attr(m.user_id) + '">' + (active ? 'Suspend' : 'Reactivate') + '</button>';
              return '<div class="list-row" style="margin:0 -24px;padding-left:24px;padding-right:24px">' + avatar(m.display_name || m.email, 'sm') +
                '<div class="list-row-main"><div class="list-row-title">' + esc(m.display_name || m.email) +
                (isMe ? ' <span class="muted tiny">(you)</span>' : '') + '</div>' +
                '<div class="list-row-sub">' + esc(m.email) + '</div></div>' +
                '<div class="list-row-side row">' + roleControl + lifecycle + '</div></div>';
            }).join(''))) +
          '<p class="tiny faint" style="margin-top:12px">Suspending a member revokes workspace access on the next request, including existing sessions. The last active owner cannot be suspended.</p>' : '') + '</div></section>';
  }

  if (can(P.workspaceManage)) {
    html += '<section class="card"><div class="card-head"><div class="card-head-main">' +
      '<div class="card-title">API keys</div>' +
      '<div class="card-sub">Scoped credentials for API clients. The secret is shown only once.</div></div></div>' +
      '<div class="card-body">' + (apiKeyError ? errorBlock(apiKeyError) : '') +
      (apiKeys && apiKeys.length ? '<div class="table-wrap"><table class="data"><thead><tr>' +
        '<th>Name</th><th>Prefix</th><th>Scopes</th><th>Status</th><th></th></tr></thead><tbody>' +
        apiKeys.map(function (k) {
          return '<tr><td class="cell-title">' + esc(k.name) + '</td>' +
            '<td class="mono small">' + esc(k.prefix) + '</td>' +
            '<td class="small">' + (k.scopes || []).map(function (s) { return '<span class="chip">' + esc(s) + '</span>'; }).join(' ') + '</td>' +
            '<td class="small">' + statusBadge(k.revoked_at ? 'revoked' : 'active') +
            (k.expires_at ? ' <span class="muted">expires ' + esc(fmtDate(k.expires_at)) + '</span>' : '') + '</td>' +
            '<td><div class="row" style="gap:6px">' +
            (k.revoked_at ? '' :
              '<button class="btn btn--sm btn--ghost" data-action="api-key-rotate" data-id="' + attr(k.id) + '">' + icon('refresh', 13) + ' Rotate</button>' +
              '<button class="btn btn--sm btn--ghost" data-action="api-key-revoke" data-id="' + attr(k.id) + '">' + icon('close', 13) + ' Revoke</button>') +
            '</div></td></tr>';
        }).join('') + '</tbody></table></div>' : '<p class="small muted">No API keys issued in this workspace.</p>') +
      '<div class="divider"></div>' +
      '<form data-form="api-key-create" class="form-grid">' +
      field('name', 'Key name', { required: true, placeholder: 'Reporting client', span: true }) +
      field('scopes', 'Scopes (comma-separated)', { required: true, placeholder: 'contact:read,task:read' }) +
      '<div class="field"><button type="submit" class="btn btn--primary">' + icon('plus', 15) + ' Issue key</button></div>' +
      '</form>' +
      '<p class="tiny faint" style="margin-top:12px">Allowed scopes are your own permissions. A key cannot manage other keys, and the secret is never stored or shown again.</p>' +
      '</div></section>';
  }

  html += '<section class="card"><div class="card-head"><div class="card-head-main"><div class="card-title">Your permissions</div></div></div>' +
    '<div class="card-body"><div class="perm-grid">' +
    (me.permissions || []).map(function (perm) { return '<span class="chip">' + esc(perm) + '</span>'; }).join('') +
    '</div></div></section>';
  html += '</div></div>';
  renderViewHtml(html);
}

/* ------------------------------------------------------------------ *
 * Form submissions
 * ------------------------------------------------------------------ */

function showFormResult(form, html) { if (form) form.innerHTML = html; }

async function processForm(name, fd, form) {
  const text = function (key) { return String(fd.get(key) || '').trim(); };

  if (name === 'login' || name === 'register' || name === 'bootstrap') {
    let endpoint, body;
    if (name === 'login') {
      endpoint = '/api/v1/auth/login';
      body = { email: text('email'), password: String(fd.get('password') || '') };
    } else if (name === 'register') {
      const check = await api('/api/v1/auth/email/check', {
        method: 'POST', body: { email: text('email') }, skipRefresh: true,
      });
      if (!check.available) {
        toast('That email is already registered. Sign in instead.', 'error');
        return;
      }
      endpoint = '/api/v1/auth/register';
      body = { email: text('email'), password: String(fd.get('password') || ''), display_name: text('display_name') };
    } else {
      endpoint = '/api/v1/setup/bootstrap';
      body = {
        workspace_name: text('workspace_name'), email: text('email'),
        password: String(fd.get('password') || ''), display_name: text('display_name'),
      };
    }
    const tokens = await api(endpoint, { method: 'POST', body: body, skipRefresh: true });
    storeTokens(tokens);
    state.me = await api('/api/v1/auth/me', { skipRefresh: true });
    await loadMyWorkspaces();
    navigate('dashboard');
    toast(name === 'login' ? 'Signed in.' : 'Workspace ready.', 'success');
    return;
  }

  if (name === 'reset-request') {
    const data = await api('/api/v1/auth/password-reset/request', { method: 'POST', body: { email: text('email') }, skipRefresh: true });
    const dev = data && data.development_token ? '<p class="small">Development token: <span class="mono">' +
      esc(data.development_token) + '</span></p>' : '';
    showFormResult(form, '<div class="info-banner">' + icon('info', 16) + '<div>' +
      esc((data && data.message) || 'If the account exists, a reset token was created.') + '</div></div>' + dev +
      '<a class="btn btn--primary btn--block" href="#/reset-confirm">Continue to password reset ' + icon('arrowRight', 15) + '</a>');
    return;
  }

  if (name === 'reset-confirm') {
    await api('/api/v1/auth/password-reset/confirm', {
      method: 'POST', body: { token: text('token'), new_password: String(fd.get('new_password') || '') }, skipRefresh: true,
    });
    toast('Password reset. Sign in with your new password.', 'success');
    navigate('login');
    return;
  }

  if (name === 'confirm') {
    const fn = state.pendingConfirm;
    state.pendingConfirm = null;
    closeModal();
    if (fn) await fn();
    return;
  }

  if (name === 'create-contact' || name === 'edit-contact') {
    const tags = text('tags').split(',').map(function (t) { return t.trim(); }).filter(Boolean);
    if (name === 'create-contact') {
      const created = await api(apiW('/contacts'), {
        method: 'POST',
        body: {
          email: text('email'), full_name: text('full_name') || null,
          company_name: text('company_name') || null, phone: text('phone') || null,
          source: text('source') || 'manual', tags: tags,
        },
      });
      closeModal();
      navigate('contacts/' + encodeURIComponent(created.id));
      toast('Contact created.', 'success');
    } else {
      await api(apiW('/contacts/' + encodeURIComponent(text('id'))), {
        method: 'PATCH',
        body: {
          full_name: text('full_name') || null, company_name: text('company_name') || null,
          phone: text('phone') || null, lifecycle_stage: text('lifecycle_stage') || null, tags: tags,
        },
      });
      closeModal();
      await loadView();
      toast('Contact updated.', 'success');
    }
    return;
  }

  if (name === 'add-note') {
    const cid = form.dataset.contactId;
    await api(apiW('/contacts/' + encodeURIComponent(cid) + '/notes'), {
      method: 'POST', body: { contact_id: cid, body: text('note_body') },
    });
    await loadView();
    toast('Note added.', 'success');
    return;
  }

  if (name === 'create-company') {
    await api(apiW('/companies'), {
      method: 'POST',
      body: {
        name: text('name'), industry: text('industry') || null,
        website: text('website') || null, location: text('location') || null,
      },
    });
    closeModal();
    await loadView();
    toast('Company created.', 'success');
    return;
  }

  if (name === 'create-lead') {
    await api(apiW('/leads'), {
      method: 'POST',
      body: {
        contact_id: text('contact_id'), source: text('source') || 'manual',
        status: 'new', priority: text('priority') || 'normal', score: Number(text('score') || 0),
      },
    });
    closeModal();
    await loadView();
    toast('Lead created.', 'success');
    return;
  }

  if (name === 'edit-lead') {
    await api(apiW('/leads/' + encodeURIComponent(text('id'))), {
      method: 'PATCH',
      body: { priority: text('priority'), score: Number(text('score') || 0) },
    });
    closeModal();
    await loadView();
    toast('Lead updated.', 'success');
    return;
  }

  if (name === 'create-task') {
    await api(apiW('/tasks'), {
      method: 'POST',
      body: {
        title: text('title'), contact_id: text('contact_id') || null,
        description: text('description') || null, priority: text('priority') || 'normal',
        due_at: text('due_at') ? new Date(text('due_at')).toISOString() : null,
      },
    });
    closeModal();
    await loadView();
    toast('Task created.', 'success');
    return;
  }

  if (name === 'record-intake') {
    const body = {
      email: text('email'), full_name: text('full_name') || null, company: text('company') || null,
      message: text('message') || null, source: text('source') || 'website_form',
    };
    if (text('submission_id')) body.submission_id = text('submission_id');
    const result = await api(apiW('/intake/website-form'), { method: 'POST', body: body });
    closeModal();
    await loadView();
    openModal({
      title: 'Intake recorded',
      sub: result.created_contact ? 'A new contact was identified.' : 'An existing contact was updated.',
      body: '<p class="small muted">One workflow run created linked records and a shared correlation id.</p>' +
        '<dl class="kv"><dt>Contact</dt><dd class="mono">' + esc(result.contact_id) + '</dd>' +
        '<dt>Lead</dt><dd class="mono">' + esc(result.lead_id) + '</dd>' +
        '<dt>Task</dt><dd class="mono">' + esc(result.task_id) + '</dd>' +
        '<dt>Draft</dt><dd class="mono">' + esc(result.draft_id) + '</dd>' +
        '<dt>Correlation</dt><dd class="mono">' + esc(result.correlation_id) + '</dd></dl>' +
        '<div class="form-actions"><a class="btn btn--primary" href="#/contacts/' + encodeURIComponent(result.contact_id) + '">' +
        icon('arrowRight', 15) + ' Open contact</a></div>',
    });
    toast('Intake workflow completed.', 'success');
    return;
  }

  if (name === 'experiment-create' || name === 'experiment-edit') {
    const isEdit = name.endsWith('-edit');
    const body = {
      name: text('name'), metric_name: text('metric_name'),
      hypothesis: text('hypothesis') || null,
      baseline: text('baseline') === '' ? null : Number(text('baseline')),
      target: text('target') === '' ? null : Number(text('target')),
    };
    const url = apiW('/analytics') + (isEdit ? '/' + encodeURIComponent(text('id')) : '');
    await api(url, { method: isEdit ? 'PATCH' : 'POST', body: body });
    closeModal();
    toast(isEdit ? 'Experiment updated.' : 'Experiment created.', 'success');
    await loadView();
    return;
  }

  if (name === 'experiment-status') {
    await api(apiW('/analytics/' + encodeURIComponent(text('id')) + '/status'), {
      method: 'POST', body: { status: text('status') },
    });
    closeModal();
    toast('Experiment status changed.', 'success');
    await loadView();
    return;
  }

  if (name === 'experiment-result') {
    await api(apiW('/analytics/' + encodeURIComponent(text('id')) + '/results'), {
      method: 'POST',
      body: {
        variant: text('variant'),
        impressions: Number(text('impressions')),
        conversions: Number(text('conversions')),
      },
    });
    closeModal();
    toast('Result recorded.', 'success');
    await loadView();
    return;
  }

  if (name === 'create-workspace') {
    const tokens = await api('/api/v1/workspaces', { method: 'POST', body: { name: text('name') } });
    storeTokens(tokens);
    state.me = await api('/api/v1/auth/me');
    await loadMyWorkspaces();
    closeModal();
    navigate('dashboard');
    toast('Workspace created.', 'success');
    return;
  }

  if (name === 'workspace-settings') {
    const cfg = (state.caches.adminSettings && state.caches.adminSettings.settings) || {};
    cfg.timezone = text('timezone');
    cfg.currency = text('currency');
    await api(apiW('/admin/settings'), {
      method: 'PATCH',
      body: { name: text('name'), settings: cfg },
    });
    state.me = await api('/api/v1/auth/me');
    await loadMyWorkspaces();
    toast('Workspace settings saved.', 'success');
    await loadView();
    return;
  }

  if (name === 'api-key-create') {
    const scopes = text('scopes').split(',').map(function (s) { return s.trim(); }).filter(Boolean);
    const issued = await api(apiW('/api-keys'), {
      method: 'POST', body: { name: text('name'), scopes: scopes },
    });
    showApiKeySecret(issued, 'API key issued', 'Copy the secret before closing this dialog.');
    toast('API key issued.', 'success');
    return;
  }

  if (name === 'workspace-flag-create') {
    await api(apiW('/flags'), {
      method: 'POST',
      body: { key: text('key'), enabled: false, default_value: text('default_value') || 'off' },
    });
    toast('Flag created.', 'success');
    await loadView();
    return;
  }

  if (name === 'project-label-create') {
    await api(apiW('/projects/' + encodeURIComponent(currentProjectId()) + '/labels'), {
      method: 'POST', body: { name: text('name') },
    });
    await openWorkItemLabels();
    toast('Label created.', 'success');
    return;
  }

  if (name === 'sdk-connection-create') {
    const created = await api(apiW('/flags/sdk/connections'), {
      method: 'POST',
      body: { name: text('name'), environment: state.flagEnvironment },
    });
    closeModal();
    openModal({
      title: 'SDK key created',
      sub: 'Copy it now ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â the secret is shown once and is not stored in plain text.',
      body: '<div class="card-body"><div class="field"><label class="field-label">SDK key</label>' +
        '<textarea class="input mono" readonly rows="3">' + esc(created.sdk_key || '') + '</textarea></div>' +
        '<div class="tiny muted">Scope: ' + esc(state.flagEnvironment) + '. Revoke it any time from this workspace.</div></div>',
    });
    toast('SDK connection created.', 'success');
    return;
  }

  if (name === 'flag-rule-create') {
    const attribute = text('attribute');
    const op = text('op') || 'eq';
    const value = text('value');
    let parsed;
    try { parsed = JSON.parse(value); } catch (err) { parsed = value; }
    await api(apiW('/flags/' + encodeURIComponent(state.selectedFlag) + '/rules'), {
      method: 'POST',
      body: { conditions: [{ attribute: attribute, op: op, value: parsed }], value: text('result') || 'on', rollout_percent: 100 },
    });
    await openFlagRules(state.selectedFlag);
    toast('Rule added.', 'success');
    return;
  }

  if (name === 'switch-workspace') {
    const tokens = await api('/api/v1/auth/login', {
      method: 'POST',
      body: { email: state.me.user.email, password: String(fd.get('password') || ''), workspace_id: text('workspace_id') },
      skipRefresh: true,
    });
    storeTokens(tokens);
    state.me = await api('/api/v1/auth/me');
    await loadMyWorkspaces();
    closeModal();
    navigate('dashboard');
    toast('Workspace switched.', 'success');
    return;
  }

  if (name === 'accept-invite') {
    const tokens = await api('/api/v1/invitations/accept', { method: 'POST', body: { token: text('token') }, skipRefresh: true });
    storeTokens(tokens);
    state.me = await api('/api/v1/auth/me');
    await loadMyWorkspaces();
    closeModal();
    navigate('dashboard');
    toast('Invitation accepted.', 'success');
    return;
  }

  if (name === 'invite-member') {
    const result = await api(apiW('/invitations'), { method: 'POST', body: { email: text('email'), role: text('role') } });
    closeModal();
    openModal({
      title: 'Invitation created',
      sub: result.email + ' Ãƒâ€šÃ‚Â· ' + cap(result.role),
      body: '<p class="small muted">The API does not send email. Copy this single-use token and give it to the invitee; ' +
        'they accept it while signed in.</p><div class="field"><label>Invitation token</label>' +
        '<input class="input mono" id="invite-token" readonly value="' + attr(result.invite_token) + '"></div>' +
        '<div class="form-actions"><button class="btn btn--primary" data-action="copy-invite" data-token="' +
        attr(result.invite_token) + '">' + icon('copy', 15) + ' Copy token</button></div>',
    });
    await loadView();
    toast('Invitation created.', 'success');
    return;
  }

  if (name === 'change-password') {
    await api('/api/v1/auth/change-password', {
      method: 'POST',
      body: { current_password: String(fd.get('current_password') || ''), new_password: String(fd.get('new_password') || '') },
    });
    form.reset();
    toast('Password updated. Other sessions were revoked.', 'success');
    return;
  }

  if (name === 'verify-confirm') {
    await api('/api/v1/auth/email/verify/confirm', { method: 'POST', body: { token: text('verify_token') }, skipRefresh: true });
    state.me = await api('/api/v1/auth/me');
    form.reset();
    await loadView();
    toast('Email verified.', 'success');
    return;
  }

  if (name === 'create-agent' || name === 'edit-agent') {
    const body = {
      name: text('name'), purpose: text('purpose'),
      model_provider: text('model_provider'), model_name: text('model_name'),
      boundary: text('boundary'), max_steps: Number(text('max_steps') || 0),
      status: text('status'), requires_approval: fd.get('requires_approval') !== null,
    };
    if (name === 'create-agent') {
      await api(apiW('/agents'), { method: 'POST', body: body });
      toast('Agent created. No external provider was called.', 'success');
    } else {
      await api(apiW('/agents/' + encodeURIComponent(text('id'))), { method: 'PATCH', body: body });
      toast('Agent updated.', 'success');
    }
    closeModal();
    await loadView();
    return;
  }

  if (name === 'request-agent-run') {
    await api(apiW('/agents/' + encodeURIComponent(text('agent_id')) + '/runs'), {
      method: 'POST',
      body: { task: text('task'), steps_taken: Number(text('steps_taken') || 0) },
    });
    closeModal();
    await loadView();
    toast('Run queued. No external AI provider was called.', 'success');
    return;
  }

  if (name === 'record-agent-progress') {
    await api(apiW('/agents/' + encodeURIComponent(text('agent_id')) +
      '/runs/' + encodeURIComponent(text('run_id')) + '/progress'), {
      method: 'POST',
      body: {
        steps_taken: Number(text('steps_taken') || 0),
        status: text('status'),
        error: text('error') || null,
      },
    });
    closeModal();
    await loadView();
    toast('Run progress recorded.', 'success');
    return;
  }

  if (name === 'save-integration') {
    let config;
    try { config = JSON.parse(text('config') || '{}'); }
    catch (e) { throw new Error('Settings must be valid JSON, for example {"folder":"INBOX"}.'); }
    if (!config || typeof config !== 'object' || Array.isArray(config)) {
      throw new Error('Settings must be a JSON object.');
    }
    await api(apiW('/integrations'), {
      method: 'PUT',
      body: {
        provider: text('provider'), display_name: text('display_name'),
        status: text('status'), config: config,
      },
    });
    closeModal();
    await loadView();
    toast('Integration configuration recorded. No outbound adapter is active.', 'success');
    return;
  }

  if (name === 'search-query') {
    state.searchQuery = text('q');
    await loadView();
    return;
  }

  if (name === 'create-room') {
    await api(apiW('/documents/rooms'), {
      method: 'POST',
      body: { name: text('name'), description: text('description') || null },
    });
    closeModal();
    await loadView();
    toast('Data room created.', 'success');
    return;
  }

  if (name === 'create-document') {
    await api(apiW('/documents'), {
      method: 'POST',
      body: {
        title: text('title'), storage_path: text('storage_path'),
        doc_type: text('doc_type') || 'other',
        size_bytes: Number(text('size_bytes') || 0),
        room_id: text('room_id') || null,
      },
    });
    closeModal();
    await loadView();
    toast('Document record added. No file was uploaded.', 'success');
    return;
  }

  if (name === 'create-watermark-preview') {
    const documentId = form.dataset.documentId || currentRoute().split('/')[1];
    const view = await api(apiW('/documents/' + encodeURIComponent(documentId) + '/watermark-views'), {
      method: 'POST',
      body: {
        viewer_email: text('viewer_email'),
        viewer_name: text('viewer_name') || null,
      },
    });
    const overlayResponse = await fetch(
      API_BASE + apiW('/documents/security/watermark-views/' + encodeURIComponent(view.view_token) + '/overlay'),
      { headers: { Authorization: 'Bearer ' + state.access } }
    );
    if (!overlayResponse.ok) throw new Error('The watermark overlay could not be rendered.');
    const overlayUrl = URL.createObjectURL(await overlayResponse.blob());
    const pages = [1, 2, 3].map(function (pageNumber) {
      return '<div style="position:relative;height:180px;margin:10px 0;overflow:hidden;' +
        'border:1px solid var(--line-soft);background:#fff">' +
        '<div style="padding:24px;color:var(--muted)">Page ' + pageNumber + ' of 3 Ã‚Â· preview</div>' +
        '<img src="' + attr(overlayUrl) + '" alt="Attributed watermark for ' + attr(view.viewer_email) +
        '" style="position:absolute;inset:0;width:100%;height:100%;opacity:.62;pointer-events:none"></div>';
    }).join('');
    showFormResult(form,
      '<div class="info-banner">' + icon('info', 16) + '<div>Watermark generated for ' +
      esc(view.viewer_email) + ' Ã‚Â· view ' + esc(view.id) + '. This attribution identifies a leak to this view.</div></div>' +
      pages +
      '<div class="field span-2"><label>Attribution text</label>' +
      '<input class="input mono" readonly value="' + attr(view.watermark_text) + '"></div>');
    return;
  }

  if (name === 'create-document-link') {
    const documentId = form.dataset.documentId || currentRoute().split('/')[1];
    const created = await api(apiW('/documents/' + encodeURIComponent(documentId) + '/links'), {
      method: 'POST',
      body: {
        password: text('password') || null,
        expires_in_hours: text('expires_in_hours') ? Number(text('expires_in_hours')) : null,
        max_views: text('max_views') ? Number(text('max_views')) : null,
        view_only: fd.get('view_only') !== null,
        download_allowed: fd.get('download_allowed') !== null,
      },
    });
    await loadView();
    showFormResult(form,
      '<div class="info-banner">' + icon('info', 16) + '<div>Share link created. Copy the token now ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â it is shown once and is not stored in the browser.</div></div>' +
      '<div class="field span-2"><label for="document-token">Share token</label>' +
      '<input class="input mono" id="document-token" readonly value="' + attr(created.token) + '"></div>' +
      '<div class="form-actions"><button class="btn btn--primary" data-action="copy-document-token" data-token="' +
      attr(created.token) + '">' + icon('check', 15) + ' Copy token</button>' +
      '<button type="button" class="btn" data-action="close-modal">Done</button></div>');
    return;
  }

  if (name === 'create-project') {
    const created = await api(apiW('/projects'), {
      method: 'POST',
      body: {
        name: text('name'), description: text('description') || null,
        status: text('status') || 'planning', due_at: dateValue(text('due_at')),
        restricted: fd.get('restricted') !== null,
      },
    });
    closeModal();
    navigate('projects/' + encodeURIComponent(created.id));
    toast('Project created.', 'success');
    return;
  }

  if (name === 'project-member-add') {
    const projectId = form.dataset.projectId || currentRoute().split('/')[1];
    await api(apiW('/projects/' + encodeURIComponent(projectId) + '/members'), {
      method: 'POST',
      body: {
        user_id: text('user_id'), role: text('role') || 'member',
      },
    });
    await loadView();
    toast('Member added to this project.', 'success');
    return;
  }

  if (name === 'create-work-item') {
    const projectId = form.dataset.projectId || currentRoute().split('/')[1];
    await api(apiW('/projects/' + encodeURIComponent(projectId) + '/items'), {
      method: 'POST',
      body: {
        title: text('title'), status: text('status') || 'todo',
        assignee_id: text('assignee_id') || null, due_at: dateValue(text('due_at')),
      },
    });
    closeModal();
    await loadView();
    toast('Work item added to this project.', 'success');
    return;
  }

  if (name === 'project-state-create') {
    const projectId = form.dataset.projectId || currentRoute().split('/')[1];
    await api(apiW('/projects/states'), {
      method: 'POST',
      body: {
        name: text('name'), group: text('group') || 'todo',
        position: Number(text('position') || 0),
      },
    });
    await loadView();
    toast('State added to this workspace.', 'success');
    return;
  }

  if (name === 'create-ticket') {
    const created = await api(apiW('/tickets'), {
      method: 'POST',
      body: {
        subject: text('subject'), body: text('body'),
        contact_id: text('contact_id') || null,
        priority: text('priority') || 'normal',
        origin_channel: text('origin_channel') || 'local',
        conversation_type: text('conversation_type') || 'question',
      },
    });
    closeModal();
    navigate('inbox/' + encodeURIComponent(created.id));
    toast('Ticket created. No message was sent.', 'success');
    return;
  }

  if (name === 'ticket-message') {
    const ticketId = form.dataset.ticketId || text('ticket_id');
    await api(apiW('/tickets/' + encodeURIComponent(ticketId) + '/messages'), {
      method: 'POST', body: {
        body: text('body'),
        direction: text('direction') || 'outbound',
        channel: text('channel') || 'local',
      },
    });
    await loadView();
    toast('Reply recorded. Nothing was sent externally.', 'success');
    return;
  }

  if (name === 'identify-customer') {
    const result = await api(apiW('/tickets/identify'), {
      method: 'POST',
      body: {
        email: text('email'),
        full_name: text('full_name') || null,
        company_name: text('company_name') || null,
      },
    });
    closeModal();
    await loadView();
    toast(result.created ? 'Visitor identified as a CRM contact.' :
      'Existing CRM contact reused for this visitor.', 'success');
    return;
  }

  if (name === 'create-campaign') {
    const created = await api(apiW('/campaigns'), {
      method: 'POST',
      body: { name: text('name'), channel: text('channel'), goal: text('goal') || null },
    });
    closeModal();
    navigate('campaigns/' + encodeURIComponent(created.id));
    toast('Campaign created. Nothing was sent.', 'success');
    return;
  }

  if (name === 'record-campaign-metric') {
    const campaignId = form.dataset.campaignId;
    await api(apiW('/campaigns/' + encodeURIComponent(campaignId) + '/metrics'), {
      method: 'POST',
      body: {
        date: text('date'), impressions: Number(text('impressions') || 0),
        clicks: Number(text('clicks') || 0), leads: Number(text('leads') || 0),
        spend: Number(text('spend') || 0),
      },
    });
    await loadView();
    toast('Metric recorded locally.', 'success');
    return;
  }

  if (name === 'notification-preference-save') {
    await api(apiW('/notification-preferences'), {
      method: 'POST',
      body: {
        level: text('level') || 'global', target: text('target') || '*',
        channel: text('channel') || 'email', enabled: text('enabled') !== 'false',
      },
    });
    closeModal();
    await loadView();
    toast('Notification preference saved locally. No message was sent.', 'success');
    return;
  }

  if (name === 'campaign-journey-step-add') {
    const campaignId = form.dataset.campaignId;
    const stepKind = text('step_kind') || 'action';
    let stepAction = text('action');
    let config = {};
    const rawConfig = text('config');
    if (rawConfig && rawConfig.trim()) {
      try { config = JSON.parse(rawConfig); }
      catch (e) { toast('Rule must be valid JSON.', 'error'); return; }
    }
    if (stepKind === 'condition') {
      stepAction = 'journey.condition_evaluated';
      if (!Object.keys(config).length) config = { field: 'source', op: 'eq', value: 'website' };
    } else if (stepKind === 'decision') {
      stepAction = 'journey.decision_evaluated';
      if (!Object.keys(config).length) {
        config = { field: 'source', branches: [
          { value: 'website', label: 'Website' }, { value: 'other', label: 'Other' },
        ] };
      }
    }
    await api(apiW('/campaigns/' + encodeURIComponent(campaignId) + '/journey-steps'), {
      method: 'POST',
      body: {
        position: Number(text('position') || 1), channel: text('channel') || 'email',
        action: stepAction, label: text('label'), step_kind: stepKind, config: config,
      },
    });
    await loadView();
    toast('Journey step added. It records a local event only.', 'success');
    return;
  }

  if (name === 'campaign-schedule') {
    const campaignId = form.dataset.campaignId;
    const toUtc = function (raw) {
      if (!raw) return null;
      const parsed = new Date(raw);
      return isNaN(parsed.getTime()) ? null : parsed.toISOString();
    };
    await api(apiW('/campaigns/' + encodeURIComponent(campaignId) + '/schedule'), {
      method: 'POST',
      body: { start_at: toUtc(text('start_at')), end_at: toUtc(text('end_at')) },
    });
    await loadView();
    toast('Schedule saved.', 'success');
    return;
  }

  if (name === 'campaign-enroll-contact') {
    const campaignId = form.dataset.campaignId;
    await api(apiW('/campaigns/' + encodeURIComponent(campaignId) + '/enrollments'), {
      method: 'POST',
      body: { contact_id: text('contact_id') },
    });
    await loadView();
    toast('Contact enrolled in the local journey.', 'success');
    return;
  }

  if (name === 'create-deal') {
    const created = await api(apiW('/deals'), {
      method: 'POST',
      body: {
        title: text('title'), company: text('company') || null,
        contact_id: text('contact_id') || null, value: Number(text('value') || 0),
        stage: text('stage') || 'new', probability: Number(text('probability') || 0),
      },
    });
    closeModal();
    navigate('deals/' + encodeURIComponent(created.id));
    toast('Deal created.', 'success');
    return;
  }

  if (name === 'add-deal-activity') {
    const dealId = form.dataset.dealId;
    await api(apiW('/deals/' + encodeURIComponent(dealId) + '/activities'), {
      method: 'POST', body: { activity_type: text('activity_type'), note: text('note') || null },
    });
    await loadView();
    toast('Activity recorded.', 'success');
    return;
  }

  if (name === 'create-survey') {
    const created = await api(apiW('/surveys'), {
      method: 'POST',
      body: { name: text('name'), description: text('description') || null },
    });
    closeModal();
    navigate('surveys/' + encodeURIComponent(created.id));
    toast('Survey created. No invitations were sent.', 'success');
    return;
  }

  if (name === 'add-survey-response') {
    const surveyId = form.dataset.surveyId;
    const score = text('score') ? Number(text('score')) : null;
    await api(apiW('/surveys/' + encodeURIComponent(surveyId) + '/responses'), {
      method: 'POST',
      body: { contact_id: text('contact_id') || null, score: score, comment: text('comment') || null },
    });
    await loadView();
    toast('Response recorded locally.', 'success');
    return;
  }

  if (name === 'save-survey-config') {
    const surveyId = form.dataset.surveyId;
    const languages = text('languages').split(',').map(function (x) { return x.trim(); }).filter(Boolean);
    await api(apiW('/feedback/surveys/' + encodeURIComponent(surveyId) + '/config'), {
      method: 'POST',
      body: {
        display_option: text('display_option'), visibility: text('visibility'),
        theme: text('theme'), languages: languages, custom_css: text('custom_css') || null,
      },
    });
    await loadView();
    toast('Survey configuration saved locally.', 'success');
    return;
  }

  if (name === 'add-survey-question') {
    const surveyId = form.dataset.surveyId;
    await api(apiW('/feedback/surveys/' + encodeURIComponent(surveyId) + '/questions'), {
      method: 'POST',
      body: { type: text('type'), code: text('code'), label: text('label') },
    });
    await loadView();
    toast('Question added.', 'success');
    return;
  }

  if (name === 'set-survey-embedded') {
    const surveyId = form.dataset.surveyId;
    let embedded;
    try { embedded = JSON.parse(text('data')); }
    catch (err) { throw new Error('Embedded data must be valid JSON.'); }
    await api(apiW('/feedback/surveys/' + encodeURIComponent(surveyId) + '/embedded/set'), {
      method: 'POST', body: { subject: text('subject'), data: embedded },
    });
    await loadView();
    toast('Embedded data set for this subject.', 'success');
    return;
  }

  if (name === 'create-survey-from-template') {
    const created = await api(apiW('/feedback/surveys/from-template'), {
      method: 'POST', body: { name: text('name'), template: text('template') },
    });
    closeModal();
    navigate('surveys/' + encodeURIComponent(created.survey_id));
    toast('Survey created from template. No invitations were sent.', 'success');
    return;
  }

  if (name === 'create-survey-link') {
    const surveyId = form.dataset.surveyId;
    const link = await api(apiW('/feedback/surveys/' + encodeURIComponent(surveyId) + '/links'), {
      method: 'POST',
      body: {
        kind: text('kind'), slug: text('slug') || null, source: text('source') || null,
      },
    });
    await loadView();
    toast('Link created: ' + String(link.token).slice(0, 10) + '...', 'success');
    return;
  }

  if (name === 'create-survey-tag') {
    const surveyId = form.dataset.surveyId;
    await api(apiW('/feedback/surveys/' + encodeURIComponent(surveyId) + '/tags'), {
      method: 'POST', body: { name: text('name') },
    });
    await loadView();
    toast('Tag added.', 'success');
    return;
  }

  if (name === 'create-action-class') {
    await api(apiW('/feedback/targeting/action-classes'), {
      method: 'POST',
      body: { name: text('name'), description: text('description') || null },
    });
    await loadView();
    toast('Action added.', 'success');
    return;
  }

  if (name === 'create-trigger') {
    const surveyId = form.dataset.surveyId;
    await api(apiW('/feedback/targeting/triggers'), {
      method: 'POST',
      body: {
        survey_id: surveyId, action_class_id: text('action_class_id'),
        name: text('name'), percentage: Number(text('percentage')),
        cooldown_seconds: Number(text('cooldown_seconds')),
      },
    });
    await loadView();
    toast('Trigger added.', 'success');
    return;
  }

  if (name === 'save-survey-controls') {
    const surveyId = form.dataset.surveyId;
    const max = text('max_responses');
    await api(apiW('/feedback/targeting/surveys/' + encodeURIComponent(surveyId) + '/controls'), {
      method: 'POST',
      body: {
        max_responses: max === '' ? null : Number(max),
        schedule_start: text('schedule_start') || null,
        schedule_end: text('schedule_end') || null,
      },
    });
    await loadView();
    toast('Submission controls saved locally.', 'success');
    return;
  }

  if (name === 'create-notification-workflow') {
    await api(apiW('/notification-workflows/workflows'), {
      method: 'POST',
      body: {
        key: text('key'), name: text('name'), channel: text('channel'),
        severity: text('severity'),
        tags: text('tags').split(',').map(function (t) { return t.trim(); }).filter(Boolean),
      },
    });
    closeModal();
    navigate('notification-workflows');
    toast('Notification workflow created locally.', 'success');
    return;
  }

  if (name === 'instantiate-notification-template') {
    await api(apiW('/notification-workflows/templates/' + encodeURIComponent(text('key')) +
      '/instantiate'), { method: 'POST', body: { name: text('name') || undefined } });
    closeModal();
    navigate('notification-workflows');
    toast('Template instantiated as a real workflow.', 'success');
    return;
  }

  if (name === 'trigger-notification-workflow') {
    const result = await api(apiW('/notification-workflows/workflows/' +
      encodeURIComponent(form.dataset.workflowId) + '/trigger'), {
      method: 'POST',
      body: { title: text('title'), html: text('html'), action_url: text('action_url') },
    });
    closeModal();
    toast('Trigger recorded locally: ' + result.status + '.', 'success');
    await loadView();
    return;
  }

  if (name === 'evaluate-notification-digest') {
    const result = await api(apiW('/notification-workflows/digest/evaluate'), {
      method: 'POST',
      body: { workflow_id: form.dataset.workflowId, window_key: text('window_key'),
        title: text('title') },
    });
    closeModal();
    openModal({ title: 'Digest evaluated',
      sub: result.event_count + ' events folded into one digest for ' + result.window_key + '.',
      body: '<p class="small">' + esc(result.title) + '</p>' });
    await loadView();
    return;
  }

  if (name === 'create-notification-feed' || name === 'create-notification-context') {
    const path = name === 'create-notification-feed' ? '/feeds' : '/contexts';
    await api(apiW('/notification-workflows' + path), {
      method: 'POST', body: { key: text('key'), name: text('name') },
    });
    closeModal();
    navigate('notification-workflows');
    toast(path === '/feeds' ? 'Feed created locally.' : 'Context created locally.', 'success');
    return;
  }

  if (name === 'create-notification-layout') {
    await api(apiW('/notification-workflows/layouts'), {
      method: 'POST', body: { key: text('key'), name: text('name'), body: text('body') },
    });
    closeModal();
    navigate('notification-workflows');
    toast('Layout created with sanitised markup.', 'success');
    return;
  }

  if (name === 'create-notification-webhook') {
    await api(apiW('/notification-workflows/webhooks/endpoints'), {
      method: 'POST',
      body: { name: text('name'), url: text('url'),
        event_types: text('event_types').split(',').map(function (t) { return t.trim(); }).filter(Boolean) },
    });
    closeModal();
    navigate('notification-workflows');
    toast('Local-only webhook endpoint registered.', 'success');
    return;
  }

  if (name === 'filter-notification-messages') {
    state.lastNotificationFeed = text('feed');
    state.lastNotificationContext = text('context');
    await loadView();
    return;
  }

  if (name === 'create-feedback-dataset') {
    await api(apiW('/feedback-intelligence/datasets'), {
      method: 'POST', body: { key: text('key'), name: text('name'), description: text('description') || undefined },
    });
    closeModal();
    navigate('feedback-intelligence');
    toast('Feedback dataset created locally.', 'success');
    return;
  }

  if (name === 'create-feedback-field') {
    await api(apiW('/feedback-intelligence/fields'), {
      method: 'POST', body: { key: text('key'), label: text('label'), type: text('type') },
    });
    closeModal();
    navigate('feedback-intelligence');
    toast('Reusable field created locally.', 'success');
    return;
  }

  if (name === 'create-feedback-segment') {
    let rules;
    try { rules = JSON.parse(text('rules_json') || '[]'); }
    catch (err) { throw new Error('Rules must be valid JSON.'); }
    await api(apiW('/feedback-intelligence/segments'), {
      method: 'POST', body: { key: text('key'), name: text('name'), rules: rules },
    });
    closeModal();
    navigate('feedback-intelligence');
    toast('Audience segment created locally.', 'success');
    return;
  }

  if (name === 'create-feedback-dashboard') {
    const created = await api(apiW('/feedback-intelligence/dashboards'), {
      method: 'POST', body: { key: text('key'), name: text('name'), widgets: [
        { id: 'sentiment', type: 'sentiment', title: 'Sentiment' },
        { id: 'sources', type: 'count_by_source', title: 'By source' },
        { id: 'volume', type: 'volume', title: 'Volume' },
      ] },
    });
    closeModal();
    openModal({ title: 'Dashboard created',
      sub: 'Computed live from stored feedback records.',
      body: '<p class="small">' + esc(created.name) + ' Ã‚Â· 3 widgets</p>' });
    await loadView();
    return;
  }

  if (name === 'create-feedback-source') {
    await api(apiW('/feedback-intelligence/datasets/' + encodeURIComponent(form.dataset.datasetId) + '/sources'), {
      method: 'POST', body: { key: text('key'), name: text('name'), source_type: text('source_type') },
    });
    closeModal();
    navigate('feedback-intelligence');
    toast('Feedback source created locally.', 'success');
    return;
  }

  if (name === 'ingest-feedback') {
    const result = await api(apiW('/feedback-intelligence/datasets/' +
      encodeURIComponent(form.dataset.datasetId) + '/records'), {
      method: 'POST', body: {
        payload: { text: text('text') },
        reserved: { page: text('page') || undefined },
        metadata: { respondent_id: text('respondent') || undefined },
      },
    });
    closeModal();
    toast('Feedback record stored locally: ' + result.sentiment + '.', 'success');
    await loadView();
    return;
  }

  if (name === 'create-experiment-metric') {
    await api(apiW('/experiment-stats/metrics'), {
      method: 'POST', body: { key: text('key'), name: text('name'), type: text('type') },
    });
    closeModal();
    navigate('experiment-stats');
    toast('Experiment metric created locally.', 'success');
    return;
  }

  if (name === 'create-experiment-definition') {
    let variants;
    try { variants = JSON.parse(text('variants_json') || '[]'); }
    catch (err) { throw new Error('Variants must be valid JSON.'); }
    await api(apiW('/experiment-stats/experiments'), {
      method: 'POST', body: { key: text('key'), name: text('name'), variants: variants },
    });
    closeModal();
    navigate('experiment-stats');
    toast('Experiment created locally.', 'success');
    return;
  }

  if (name === 'record-experiment-observation') {
    const num = function (n) { return Number(text(n) || 0); };
    const result = await api(apiW('/experiment-stats/experiments/' +
      encodeURIComponent(form.dataset.experimentId) + '/observations'), {
      method: 'POST', body: {
        metric_id: text('metric_id'), variant: text('variant'),
        sessions: num('sessions'), conversions: num('conversions'),
        value_sum: num('value_sum'), value_sq_sum: num('value_sq_sum'),
      },
    });
    closeModal();
    toast('Observation stored: ' + result.variant + ' Ã‚Â· ' + result.sessions + ' sessions.', 'success');
    await loadView();
    return;
  }

  if (name === 'analyze-experiment') {
    const result = await api(apiW('/experiment-stats/experiments/' +
      encodeURIComponent(form.dataset.experimentId) + '/analyze'), {
      method: 'POST', body: { metric_id: text('metric_id'), engine: text('engine') },
    });
    closeModal();
    openModal({ title: 'Analysis result', sub: result.engine + ' engine over stored observations',
      body: '<pre class="small">' + esc(JSON.stringify(result, null, 2)) + '</pre>' });
    await loadView();
    return;
  }

  if (name === 'run-power-analysis') {
    const body = {
      baseline_rate: Number(text('baseline_rate') || 0),
      alpha: Number(text('alpha') || 0.05), power: Number(text('power') || 0.8),
    };
    if (text('mde')) body.mde = Number(text('mde'));
    if (text('sample_size')) body.sample_size = Number(text('sample_size'));
    const result = await api(apiW('/experiment-stats/analysis/power'), { method: 'POST', body: body });
    closeModal();
    openModal({ title: 'Power analysis', sub: result.method,
      body: '<pre class="small">' + esc(JSON.stringify(result, null, 2)) + '</pre>' });
    return;
  }

  if (name === 'run-correction') {
    const values = (text('p_values') || '').split(',').map(function (v) { return Number(v.trim()); })
      .filter(function (v) { return Number.isFinite(v); });
    const result = await api(apiW('/experiment-stats/analysis/correct'), {
      method: 'POST', body: { p_values: values, alpha: Number(text('alpha') || 0.05) },
    });
    closeModal();
    openModal({ title: 'Correction result', sub: result.count + ' p-values adjusted',
      body: '<pre class="small">' + esc(JSON.stringify(result, null, 2)) + '</pre>' });
    return;
  }

  if (name === 'create-experiment-project') {
    await api(apiW('/experiment-ops/projects'), {
      method: 'POST', body: {
        key: text('key'), name: text('name'), description: text('description') || undefined,
      },
    });
    closeModal();
    navigate('experiment-ops');
    toast('Experiment project created locally.', 'success');
    return;
  }

  if (name === 'create-saved-group') {
    let conditions;
    try { conditions = JSON.parse(text('conditions_json') || '[]'); }
    catch (err) { throw new Error('Conditions must be valid JSON.'); }
    await api(apiW('/experiment-ops/projects/' + encodeURIComponent(text('project_id')) + '/saved-groups'), {
      method: 'POST', body: { key: text('key'), name: text('name'), conditions: conditions },
    });
    closeModal();
    navigate('experiment-ops');
    toast('Saved group created locally.', 'success');
    return;
  }

  if (name === 'create-experiment-dimension') {
    let values;
    try { values = JSON.parse(text('values_json') || '[]'); }
    catch (err) { throw new Error('Values must be valid JSON.'); }
    await api(apiW('/experiment-ops/dimensions'), {
      method: 'POST', body: {
        key: text('key'), name: text('name'), attribute: text('attribute'), values: values,
      },
    });
    closeModal();
    navigate('experiment-ops');
    toast('Dimension created locally.', 'success');
    return;
  }

  if (name === 'create-experiment-segment') {
    let rules;
    try { rules = JSON.parse(text('rules_json') || '[]'); }
    catch (err) { throw new Error('Rules must be valid JSON.'); }
    await api(apiW('/experiment-ops/segments'), {
      method: 'POST', body: { key: text('key'), name: text('name'), rules: rules },
    });
    closeModal();
    navigate('experiment-ops');
    toast('Segment created locally.', 'success');
    return;
  }

  if (name === 'create-flag-revision') {
    let definition;
    try { definition = JSON.parse(text('definition_json') || '{}'); }
    catch (err) { throw new Error('Definition must be valid JSON.'); }
    const revision = await api(apiW('/experiment-ops/flags/' +
      encodeURIComponent(form.dataset.flagId) + '/revisions'), {
      method: 'POST', body: { definition: definition },
    });
    closeModal();
    openModal({ title: 'Draft revision created',
      sub: 'Version ' + revision.version + ' is stored as a draft.',
      body: '<p class="small">The live flag is unchanged until you publish this revision.</p>' +
        '<div class="form-actions"><button type="button" class="btn" ' +
        'data-action="close-modal">Close</button><button class="btn btn--primary" ' +
        'data-action="publish-flag-revision" data-id="' + attr(revision.id) +
        '">Publish revision</button></div>' });
    await loadView();
    return;
  }

  if (name === 'archive-flag') {
    await api(apiW('/experiment-ops/flags/' + encodeURIComponent(form.dataset.flagId) + '/archive'), {
      method: 'POST', body: { reason: text('reason') || undefined },
    });
    closeModal();
    toast('Flag archived locally.', 'success');
    navigate('experiment-ops');
    return;
  }

  if (name === 'diagnose-flag') {
    let attributes;
    try { attributes = JSON.parse(text('attributes_json') || '{}'); }
    catch (err) { throw new Error('Attributes must be valid JSON.'); }
    const result = await api(apiW('/experiment-ops/flags/' +
      encodeURIComponent(form.dataset.flagId) + '/diagnose'), {
      method: 'POST', body: {
        user_key: text('user_key'), attributes: attributes, environment: text('environment'),
      },
    });
    closeModal();
    openModal({ title: 'Evaluation diagnosis',
      sub: result.enabled ? 'Enabled: ' + result.variant : 'Not enabled: ' + result.reason,
      body: '<pre class="small">' + esc(JSON.stringify(result, null, 2)) + '</pre>' });
    return;
  }

  if (name === 'create-aa-test') {
    await api(apiW('/experiment-ops/aa-tests'), {
      method: 'POST', body: {
        project_id: text('project_id'), key: text('key'), name: text('name'),
      },
    });
    closeModal();
    navigate('experiment-ops');
    toast('A/A test created locally.', 'success');
    return;
  }

  if (name === 'create-timeseries-point') {
    await api(apiW('/experiment-ops/timeseries'), {
      method: 'POST', body: {
        experiment_key: text('experiment_key'), metric_key: text('metric_key'),
        day: text('day'), sessions: Number(text('sessions') || 0),
        conversions: Number(text('conversions') || 0),
      },
    });
    closeModal();
    toast('Time series point stored locally.', 'success');
    await loadView();
    return;
  }

  if (name === 'view-timeseries') {
    const result = await api(apiW('/experiment-ops/timeseries/summary') +
      '?experiment_key=' + encodeURIComponent(text('experiment_key')));
    closeModal();
    openModal({ title: 'Time series', sub: 'Cumulative impact over ' + result.series.length + ' days',
      body: '<pre class="small">' + esc(JSON.stringify(result.series, null, 2)) + '</pre>' });
    return;
  }

  if (name === 'bind-experiment-role') {
    await api(apiW('/experiment-platform/roles/bindings'), {
      method: 'POST', body: { user_id: text('user_id'), role: text('role') },
    });
    closeModal();
    navigate('experiment-platform');
    toast('Experiment role bound locally.', 'success');
    return;
  }

  if (name === 'check-experiment-role') {
    const result = await api(apiW('/experiment-platform/roles/can') +
      '?role=' + encodeURIComponent(text('role')) +
      '&permission=' + encodeURIComponent(text('permission')));
    openModal({ title: result.allowed ? 'Permission allowed' : 'Permission denied',
      sub: result.role + ' Ã‚Â· ' + result.permission,
      body: '<pre class="small">' + esc(JSON.stringify(result, null, 2)) + '</pre>' });
    return;
  }

  if (name === 'create-delivery-webhook') {
    const eventTypes = text('event_types').split(',').map(function (v) { return v.trim(); }).filter(Boolean);
    await api(apiW('/experiment-delivery/webhooks'), {
      method: 'POST', body: {
        key: text('key'), name: text('name'), scope: text('scope'),
        event_types: eventTypes, target_label: text('target_label'),
      },
    });
    closeModal();
    navigate('experiment-delivery');
    toast('Local webhook created.', 'success');
    return;
  }

  if (name === 'emit-delivery-webhook') {
    let payload = {};
    try { payload = JSON.parse(text('payload') || '{}'); } catch (err) { payload = {}; }
    await api(apiW('/experiment-delivery/webhooks/' + encodeURIComponent(form.dataset.id) + '/emit'), {
      method: 'POST', body: { event_type: text('event_type'), payload: payload },
    });
    closeModal();
    navigate('experiment-delivery');
    toast('Delivery recorded locally.', 'success');
    return;
  }

  if (name === 'purge-delivery-cache') {
    const result = await api(apiW('/experiment-delivery/cache/purge'), {
      method: 'POST', body: { prefix: text('prefix'), reason: text('reason') },
    });
    closeModal();
    navigate('experiment-delivery');
    toast(result.purged_count + ' local cache entries purged.', 'success');
    return;
  }

  if (name === 'schedule-refresh-job') {
    await api(apiW('/experiment-delivery/refresh-jobs'), {
      method: 'POST', body: {
        key: text('key'), job_type: text('job_type'), target_key: text('target_key'),
      },
    });
    closeModal();
    navigate('experiment-delivery');
    toast('Local refresh job scheduled.', 'success');
    return;
  }

  if (name === 'create-survey-config') {
    const channels = text('channels').split(',').map(function (v) { return v.trim(); }).filter(Boolean);
    await api(apiW('/survey-delivery/configs'), {
      method: 'POST', body: {
        survey_id: text('survey_id'), channels: channels,
        embed_mode: text('embed_mode'), host_css_mode: text('host_css_mode'),
      },
    });
    closeModal();
    navigate('survey-delivery');
    toast('Survey delivery config created locally.', 'success');
    return;
  }

  if (name === 'evaluate-survey-creative') {
    const result = await api(apiW('/survey-delivery/creatives/' + encodeURIComponent(form.dataset.id) + '/evaluate'), {
      method: 'POST', body: {
        page: text('page'), device: text('device'),
        views: Number(text('views') || 1), share: Number(text('share') || 100),
      },
    });
    openModal({ title: result.show ? 'Creative would show' : 'Creative hidden',
      sub: 'Local evaluation Ã‚Â· ' + (result.reasons || []).join(', '),
      body: '<pre class="small">' + esc(JSON.stringify(result, null, 2)) + '</pre>' });
    return;
  }

  if (name === 'automation-quota-override') {
    await api(apiW('/notification-automation/quotas'), {
      method: 'PUT', body: { key: text('key'), value: Number(text('value')) },
    });
    navigate('notification-automation');
    toast('Quota override saved locally.', 'success');
    return;
  }

  if (name === 'automation-subscriber-search') {
    const result = await api(apiW('/notification-automation/subscribers?q=' + encodeURIComponent(text('q'))));
    openModal({ title: 'Subscriber search',
      sub: (result || []).length + ' match(es)',
      body: '<pre class="small">' + esc(JSON.stringify(result, null, 2)) + '</pre>' });
    return;
  }

  if (name === 'automation-subscriber-create') {
    await api(apiW('/notification-automation/subscribers'), {
      method: 'POST', body: { subscriber_key: text('subscriber_key'), email: text('email'), name: text('name') },
    });
    navigate('notification-automation');
    toast('Subscriber created locally.', 'success');
    return;
  }

  if (name === 'automation-subscriber-bulk') {
    const keys = text('keys').split(',').map(function (k) { return k.trim(); }).filter(Boolean);
    const result = await api(apiW('/notification-automation/subscribers/bulk'), {
      method: 'POST', body: { subscribers: keys.map(function (k) { return { subscriber_key: k }; }) },
    });
    navigate('notification-automation');
    toast(result.created + ' subscribers created locally.', 'success');
    return;
  }

  if (name === 'automation-endpoint-add') {
    const body = { channel: text('channel'), endpoint: text('endpoint') };
    if (text('secret')) body.secret = text('secret');
    await api(apiW('/notification-automation/subscribers/' + encodeURIComponent(text('subscriber_id')) + '/endpoints'), {
      method: 'POST', body: body,
    });
    navigate('notification-automation');
    toast('Channel endpoint stored locally (secret hashed).', 'success');
    return;
  }

  if (name === 'automation-code-step-create') {
    await api(apiW('/notification-automation/code-steps'), {
      method: 'POST', body: {
        workflow_key: text('workflow_key'), step_key: text('step_key'),
        code: text('code'), publish: text('publish') === 'on',
      },
    });
    navigate('notification-automation');
    toast('Code step saved locally.', 'success');
    return;
  }

  if (name === 'automation-code-step-evaluate') {
    let payload = {};
    try { payload = JSON.parse(text('payload') || '{}'); } catch (err) { toast('Payload must be valid JSON.', 'error'); return; }
    const result = await api(apiW('/notification-automation/code-steps/' + encodeURIComponent(text('step_id')) + '/evaluate'), {
      method: 'POST', body: { payload: payload },
    });
    openModal({ title: 'Sandboxed code step result',
      sub: 'sandboxed: ' + !!result.sandboxed + ' Ã‚Â· external_calls: ' + !!result.external_calls,
      body: '<pre class="small">' + esc(JSON.stringify(result, null, 2)) + '</pre>' });
    return;
  }

  if (name === 'automation-http-stub-create') {
    let response = {};
    try { response = JSON.parse(text('response') || '{}'); } catch (err) { toast('Response must be valid JSON.', 'error'); return; }
    await api(apiW('/notification-automation/http-stubs'), {
      method: 'POST', body: { path: text('path'), method: text('method'), response: response },
    });
    navigate('notification-automation');
    toast('Local HTTP stub registered.', 'success');
    return;
  }

  if (name === 'automation-http-step-create') {
    await api(apiW('/notification-automation/http-steps'), {
      method: 'POST', body: {
        workflow_key: text('workflow_key'), step_key: text('step_key'),
        method: text('method'), path: text('path'), authorized: text('authorized') === 'on',
      },
    });
    navigate('notification-automation');
    toast('HTTP step saved locally.', 'success');
    return;
  }

  if (name === 'automation-routing-rule-create') {
    let conditions = [];
    try { conditions = JSON.parse(text('conditions') || '[]'); } catch (err) { toast('Conditions must be valid JSON.', 'error'); return; }
    await api(apiW('/notification-automation/routing-rules'), {
      method: 'POST', body: {
        workflow_key: text('workflow_key'), provider: text('provider'),
        priority: Number(text('priority') || 100), conditions: conditions,
      },
    });
    navigate('notification-automation');
    toast('Routing rule added locally.', 'success');
    return;
  }

  if (name === 'automation-routing-evaluate') {
    let context = {};
    try { context = JSON.parse(text('context') || '{}'); } catch (err) { toast('Context must be valid JSON.', 'error'); return; }
    const body = { workflow_key: text('workflow_key'), context: context };
    if (text('subscriber_key')) body.subscriber_key = text('subscriber_key');
    const result = await api(apiW('/notification-automation/routing/evaluate'), { method: 'POST', body: body });
    openModal({ title: 'Provider routing result',
      sub: 'primary: ' + result.primary + ' Ã‚Â· fallbacks: ' + (result.fallbacks || []).join(', '),
      body: '<pre class="small">' + esc(JSON.stringify(result, null, 2)) + '</pre>' });
    return;
  }

  if (name === 'automation-demo-send') {
    let payload = {};
    try { payload = JSON.parse(text('payload') || '{}'); } catch (err) { toast('Payload must be valid JSON.', 'error'); return; }
    const result = await api(apiW('/notification-automation/demo-send'), {
      method: 'POST', body: { provider: text('provider'), subscriber_key: text('subscriber_key'), payload: payload },
    });
    navigate('notification-automation');
    toast('Simulated ' + result.provider + ' send recorded locally (' + result.used_today + '/' + result.daily_limit + ').', 'success');
    return;
  }

  if (name === 'automation-broadcast') {
    let payload = {};
    try { payload = JSON.parse(text('payload') || '{}'); } catch (err) { toast('Payload must be valid JSON.', 'error'); return; }
    const result = await api(apiW('/notification-automation/broadcast'), {
      method: 'POST', body: {
        workflow_key: text('workflow_key'), payload: payload, authorized: text('authorized') === 'on',
      },
    });
    navigate('notification-automation');
    toast('Broadcast delivered locally to ' + result.recipients + ' subscribers.', 'success');
    return;
  }

  if (name === 'email-template-create') {
    const result = await api(apiW('/email-engagement/templates'), {
      method: 'POST', body: { name: text('name'), subject: text('subject'),
        html_body: text('html_body'), text_body: text('text_body') },
    });
    state.emailTemplateId = result.id;
    navigate('email-engagement');
    toast('Template created locally.', 'success');
    return;
  }

  if (name === 'email-translation-create') {
    await api(apiW('/email-engagement/templates/' + encodeURIComponent(state.emailTemplateId || '') + '/translations'), {
      method: 'POST', body: { locale: text('locale'), subject: text('subject'),
        html_body: text('html_body'), text_body: text('text_body') },
    });
    navigate('email-engagement');
    toast('Translation stored locally.', 'success');
    return;
  }

  if (name === 'email-variant-create') {
    await api(apiW('/email-engagement/templates/' + encodeURIComponent(state.emailTemplateId || '') + '/variants'), {
      method: 'POST', body: { name: text('name'), subject: text('subject'),
        weight: parseInt(text('weight') || '1', 10) || 1 },
    });
    navigate('email-engagement');
    toast('A/B variant stored locally.', 'success');
    return;
  }

  if (name === 'email-token-create') {
    const body = { recipient_id: text('recipient_id') };
    if (text('target_url')) body.target_url = text('target_url');
    const result = await api(apiW('/email-engagement/templates/' +
      encodeURIComponent(state.emailTemplateId || '') + '/tokens'), { method: 'POST', body: body });
    navigate('email-engagement');
    openModal({ title: 'Local ' + esc(result.kind) + ' token',
      sub: 'no outbound request is made by NOVARA',
      body: '<pre class="small">' + esc(JSON.stringify(result, null, 2)) + '</pre>' });
    return;
  }

  if (name === 'email-bounce-create') {
    await api(apiW('/email-engagement/engagement/bounces'), {
      method: 'POST', body: { recipient_id: text('recipient_id'),
        template_id: state.emailTemplateId || '', metadata: { reason: text('reason') } },
    });
    navigate('email-engagement');
    toast('Bounce recorded locally.', 'success');
    return;
  }

  if (name === 'email-reply-create') {
    await api(apiW('/email-engagement/engagement/replies'), {
      method: 'POST', body: { recipient_id: text('recipient_id'),
        metadata: { subject: text('subject') } },
    });
    navigate('email-engagement');
    toast('Reply recorded locally.', 'success');
    return;
  }

  if (name === 'email-signature-save') {
    await api(apiW('/email-engagement/signatures'), {
      method: 'POST', body: { display_name: text('display_name'),
        body_html: text('body_html'), is_default: text('is_default') === 'true' },
    });
    navigate('email-engagement');
    toast('Signature saved locally.', 'success');
    return;
  }

  if (name === 'email-image-add') {
    await api(apiW('/email-engagement/templates/' + encodeURIComponent(state.emailTemplateId || '') + '/images'), {
      method: 'POST', body: { cid: text('cid'), content_type: text('content_type'),
        content_base64: text('content_base64') },
    });
    navigate('email-engagement');
    toast('Inline image stored locally.', 'success');
    return;
  }

  if (name === 'planning-item-select') {
    state.planningItemId = text('item_id');
    navigate('work-item-planning');
    toast('Work item opened.', 'success');
    return;
  }

  if (name === 'planning-relation') {
    await api(apiW('/work-item-planning/items/' + encodeURIComponent(state.planningItemId || '') + '/relations'), {
      method: 'POST', body: { target_item_id: text('target_item_id'),
        relation_type: text('relation_type'), note: text('note') },
    });
    navigate('work-item-planning');
    toast('Relation and inverse created locally.', 'success');
    return;
  }

  if (name === 'planning-dependency') {
    await api(apiW('/work-item-planning/items/' + encodeURIComponent(state.planningItemId || '') + '/dependencies'), {
      method: 'POST', body: { depends_on_id: text('depends_on_id'), kind: text('kind'),
        target_date: text('target_date') || null },
    });
    navigate('work-item-planning');
    toast('Dependency stored with violation check.', 'success');
    return;
  }

  if (name === 'planning-scheme') {
    await api(apiW('/work-item-planning/estimate-schemes'), {
      method: 'POST', body: { name: text('name'), kind: text('kind'),
        values: JSON.parse(text('values') || '{}') },
    });
    navigate('work-item-planning');
    toast('Estimate scheme created.', 'success');
    return;
  }

  if (name === 'planning-estimate') {
    await api(apiW('/work-item-planning/items/' + encodeURIComponent(state.planningItemId || '') + '/estimates'), {
      method: 'POST', body: { scheme_id: text('scheme_id'), value: Number(text('value') || 0),
        category: text('category') || null },
    });
    navigate('work-item-planning');
    toast('Estimate saved locally.', 'success');
    return;
  }

  if (name === 'planning-schedule') {
    await api(apiW('/work-item-planning/items/' + encodeURIComponent(state.planningItemId || '') + '/schedule'), {
      method: 'PATCH', body: { start_at: text('start_at') || null, due_at: text('due_at') || null },
    });
    navigate('work-item-planning');
    toast('Schedule persisted.', 'success');
    return;
  }

  if (name === 'planning-cell') {
    await api(apiW('/work-item-planning/items/' + encodeURIComponent(state.planningItemId || '') + '/table-cell'), {
      method: 'PATCH', body: { field: text('field'), value: text('value') },
    });
    navigate('work-item-planning');
    toast('Inline edit persisted.', 'success');
    return;
  }

  if (name === 'planning-update') {
    await api(apiW('/work-item-planning/items/' + encodeURIComponent(state.planningItemId || '') + '/updates'), {
      method: 'POST', body: { body: text('body') },
    });
    navigate('work-item-planning');
    toast('Status update posted.', 'success');
    return;
  }

  if (name === 'planning-recurrence') {
    await api(apiW('/work-item-planning/items/' + encodeURIComponent(state.planningItemId || '') + '/recurrences'), {
      method: 'POST', body: { frequency: text('frequency'), interval: Number(text('interval') || 1),
        next_at: text('next_at') },
    });
    navigate('work-item-planning');
    toast('Recurrence saved; materialisation is explicit.', 'success');
    return;
  }

  if (name === 'planning-time-log') {
    await api(apiW('/work-item-planning/items/' + encodeURIComponent(state.planningItemId || '') + '/time-logs'), {
      method: 'POST', body: { minutes: Number(text('minutes') || 0), note: text('note') },
    });
    navigate('work-item-planning');
    toast('Worklog recorded.', 'success');
    return;
  }

  if (name === 'planning-subscribe') {
    await api(apiW('/work-item-planning/items/' + encodeURIComponent(state.planningItemId || '') + '/subscribers'), {
      method: 'POST', body: { user_id: text('user_id') },
    });
    navigate('work-item-planning');
    toast('Subscriber added to exact recipient set.', 'success');
    return;
  }

  if (name === 'planning-template') {
    await api(apiW('/work-item-planning/templates'), {
      method: 'POST', body: { name: text('name'), target_kind: text('target_kind'),
        payload: JSON.parse(text('payload') || '{}') },
    });
    navigate('work-item-planning');
    toast('Template stored locally.', 'success');
    return;
  }

  if (name === 'planning-instantiate') {
    await api(apiW('/work-item-planning/templates/' + encodeURIComponent(text('template_id')) + '/instantiate'), {
      method: 'POST', body: { project_id: text('project_id') || null, title: text('title') || null },
    });
    navigate('work-item-planning');
    toast('Template instantiated locally.', 'success');
    return;
  }

  if (name === 'collab-project-select') {
    state.collabProjectId = text('project_id');
    state.collabItemId = '';
    state.collabCursor = '';
    await loadView();
    toast('Project scope opened.', 'success');
    return;
  }

  if (name === 'collab-item-select') {
    state.collabItemId = text('item_id');
    const selected = (state.caches.collabItems || []).find(function (i) { return i.id === state.collabItemId; });
    if (selected) state.collabProjectId = selected.project_id;
    await loadView();
    toast('Work item opened.', 'success');
    return;
  }

  if (name === 'collab-cursor-page') {
    state.collabPerPage = Number(text('per_page') || 5);
    state.collabCursor = text('cursor');
    await loadView();
    toast('Cursor page applied.', 'success');
    return;
  }

  if (name === 'collab-csv-import') {
    const result = await api(apiW('/work-collab/projects/' +
      encodeURIComponent(state.collabProjectId || '') + '/csv-import'), {
      method: 'POST', body: { csv_text: text('csv_text') },
    });
    state.collabCursor = '';
    await loadView();
    toast(result.count + ' work items imported from provider-neutral CSV.', 'success');
    return;
  }

  if (name === 'collab-attachment-add') {
    await api(apiW('/work-collab/items/' + encodeURIComponent(state.collabItemId || '') + '/attachments'), {
      method: 'POST', body: { file_id: text('file_id'), label: text('label') || null },
    });
    await loadView();
    toast('Stored file attached to this work item.', 'success');
    return;
  }

  if (name === 'collab-mention-create') {
    const result = await api(apiW('/work-collab/items/' + encodeURIComponent(state.collabItemId || '') + '/mentions'), {
      method: 'POST', body: {
        user_ids: text('user_ids').split(',').map(function (u) { return u.trim(); }).filter(Boolean),
        body: text('body'), source: text('source') || 'comment',
        comment_id: text('comment_id') || null,
      },
    });
    await loadView();
    toast('Mention recorded; ' + result.subscribed.length + ' local subscription(s) added.', 'success');
    return;
  }

  if (name === 'collab-team-note') {
    await api(apiW('/work-collab/projects/' + encodeURIComponent(state.collabProjectId || '') + '/team-notes'), {
      method: 'POST', body: { body: text('body'), item_id: state.collabItemId || null },
    });
    await loadView();
    toast('Team note added to local activity.', 'success');
    return;
  }

  if (name === 'collab-restriction-set') {
    await api(apiW('/work-collab/items/' + encodeURIComponent(state.collabItemId || '') + '/restriction'), {
      method: 'PUT', body: {
        allowed_user_ids: text('allowed_user_ids').split(',').map(function (u) { return u.trim(); }).filter(Boolean),
        reason: text('reason'),
      },
    });
    await loadView();
    toast('Item restriction applied locally.', 'success');
    return;
  }

  if (name === 'collab-shape') {
    const fields = text('fields');
    const expand = text('expand');
    const query = '?fields=' + encodeURIComponent(fields) + '&expand=' + encodeURIComponent(expand);
    const result = await api(apiW('/work-collab/items/' +
      encodeURIComponent(state.collabItemId || '') + '/shaped') + query);
    openModal({ title: 'Shaped work item', sub: 'allow-listed local projection',
      body: '<pre class="small">' + esc(JSON.stringify(result, null, 2)) + '</pre>' });
    return;
  }

  if (name === 'ag-custom-role-create') {
    const perms = text('permissions').split(',').map(s=>s.trim()).filter(Boolean);
    await api(apiW('/access-governance/custom-roles'), { method: 'POST',
      body: { slug: text('slug'), name: text('name'), permissions: perms } });
    await loadView(); toast('Custom role created.', 'success'); return;
  }
  if (name === 'ag-custom-role-assign') {
    await api(apiW('/access-governance/custom-roles/' + encodeURIComponent(text('role_id')) + '/assign'), { method: 'POST',
      body: { user_id: text('user_id'), role: text('role_id') } });
    await loadView(); toast('Custom role assigned.', 'success'); return;
  }
  if (name === 'ag-custom-role-revoke') {
    await api(apiW('/access-governance/custom-roles/' + encodeURIComponent(text('role_id')) + '/revoke'), { method: 'POST',
      body: { user_id: text('user_id'), role: text('role_id') } });
    await loadView(); toast('Custom role revoked.', 'success'); return;
  }
  if (name === 'ag-scheme-create') {
    let grants = {};
    try { grants = JSON.parse(text('grants') || '{}'); } catch(e){ toast('Grants must be JSON.', 'error'); return; }
    await api(apiW('/access-governance/schemes'), { method: 'POST',
      body: { name: text('name'), grants } });
    await loadView(); toast('Permission scheme created.', 'success'); return;
  }
  if (name === 'ag-scheme-assign') {
    await api(apiW('/access-governance/schemes/' + encodeURIComponent(text('scheme_id')) + '/assign'), { method: 'POST',
      body: { project_id: text('project_id') } });
    await loadView(); toast('Scheme assigned.', 'success'); return;
  }
  if (name === 'ag-permission-check') {
    const result = await api(apiW('/access-governance/permissions/check'), { method: 'POST',
      body: { permission: text('permission') } });
    openModal({ title: 'Permission check', sub: text('permission'),
      body: '<pre class="small">' + esc(JSON.stringify(result, null, 2)) + '</pre>' });
    return;
  }

  if (name === 'fg-schedule-create') {
    let stateValue;
    try { stateValue = JSON.parse(text('state_json')); }
    catch (e) { toast('State must be a valid JSON object.', 'error'); return; }
    await api(apiW('/flag-governance/schedules'), { method: 'POST',
      body: { flag_key: text('flag_key'), starts_at: text('starts_at'), state: stateValue } });
    await loadView();
    toast('Local flag schedule saved.', 'success');
    return;
  }

  if (name === 'fg-schedule-resolve') {
    const result = await api(apiW('/flag-governance/schedules/resolve'), { method: 'POST',
      body: { flag_values: { [text('flag_key')]: 'off' }, attrs: { at: text('at') } } });
    const entry = result.states[text('flag_key')];
    openModal({ title: 'Scheduled state', sub: text('flag_key') + ' at ' + text('at'),
      body: '<pre class="small">' + esc(JSON.stringify(entry, null, 2)) + '</pre>' });
    return;
  }

  if (name === 'fg-secure-attr') {
    const result = await api(apiW('/flag-governance/secure-attributes'), { method: 'POST',
      body: { flag_key: text('flag_key'), attribute: text('attribute'),
        salt: text('salt'), value: text('value') } });
    openModal({ title: 'Attribute hashed locally', sub: result.attribute,
      body: '<p class="small">Salted digest: <code>' + esc(result.digest) +
        '</code>. The raw value is not stored in the digest.</p>' });
    await loadView();
    return;
  }

  if (name === 'fg-sticky') {
    const result = await api(apiW('/flag-governance/sticky'), { method: 'POST',
      body: { flag_key: text('flag_key'), user_key: text('user_key'),
        percent: Number(text('percent') || 0) } });
    openModal({ title: 'Sticky assignment', sub: result.flag_key + ' Â· ' + result.user_key,
      body: '<p class="small">Variant <strong>' + esc(result.variant) +
        '</strong> is stored locally and will not change when the rollout changes.</p>' });
    return;
  }

  if (name === 'fg-prereq-create') {
    let condition;
    try { condition = JSON.parse(text('condition_json') || '{}'); }
    catch (e) { toast('Target condition must be a valid JSON object.', 'error'); return; }
    await api(apiW('/flag-governance/prerequisites'), { method: 'POST',
      body: { flag_key: text('flag_key'), prerequisite_key: text('prerequisite_key'),
        required_value: text('required_value'), target_condition: condition } });
    await loadView();
    toast('Local prerequisite saved.', 'success');
    return;
  }

  if (name === 'fg-prereq-check') {
    let values, attrs;
    try { values = JSON.parse(text('flag_values_json') || '{}'); attrs = JSON.parse(text('attrs_json') || '{}'); }
    catch (e) { toast('Flag values and attributes must be valid JSON objects.', 'error'); return; }
    attrs.flag_key = text('flag_key');
    const result = await api(apiW('/flag-governance/prerequisites/check'), { method: 'POST',
      body: { flag_values: values, attrs: attrs } });
    openModal({ title: 'Prerequisite check', sub: result.reason,
      body: '<p class="small">' + esc(text('flag_key')) + ' prerequisites are ' +
        (result.met ? 'met' : 'not met') + ' (' + result.count + ' checked).</p>' });
    return;
  }

  if (name === 'fg-redirect-create') {
    await api(apiW('/flag-governance/redirects'), { method: 'POST',
      body: { flag_key: text('flag_key'), rule_id: text('rule_id'), target_url: text('target_url') } });
    await loadView();
    toast('Local redirect rule saved.', 'success');
    return;
  }

  if (name === 'fg-redirect-resolve') {
    const result = await api(apiW('/flag-governance/redirects/resolve'), { method: 'POST',
      body: { attrs: { flag_key: text('flag_key'), rule_id: text('rule_id') } } });
    openModal({ title: 'Rule result', sub: text('rule_id'),
      body: result.redirect ? '<p class="small">Redirects locally to <code>' +
        esc(result.redirect.target_url) + '</code>.</p>' :
        '<p class="small">No active redirect for this rule.</p>' });
    return;
  }

  if (name === 'fg-env-create') {
    let overrides;
    try { overrides = JSON.parse(text('overrides_json') || '{}'); }
    catch (e) { toast('Overrides must be a valid JSON object.', 'error'); return; }
    await api(apiW('/flag-governance/environments'), { method: 'POST',
      body: { environment: text('environment'), parent_environment: text('parent_environment') || null,
        overrides: overrides } });
    await loadView();
    toast('Environment inheritance saved.', 'success');
    return;
  }

  if (name === 'fg-env-resolve') {
    const result = await api(apiW('/flag-governance/environments/resolve'), { method: 'POST',
      body: { attrs: { environment: text('environment') } } });
    openModal({ title: 'Effective environment', sub: result.chain.join(' â†’ '),
      body: '<pre class="small">' + esc(JSON.stringify(result.effective, null, 2)) + '</pre>' });
    return;
  }

  if (name === 'fg-template-create') {
    let definition;
    try { definition = JSON.parse(text('definition_json')); }
    catch (e) { toast('Definition must be a valid JSON object.', 'error'); return; }
    await api(apiW('/flag-governance/templates'), { method: 'POST',
      body: { key: text('key'), definition: definition } });
    await loadView();
    toast('Reusable template saved.', 'success');
    return;
  }

  if (name === 'fg-template-instantiate') {
    const result = await api(apiW('/flag-governance/templates/instantiate'), { method: 'POST',
      body: { template_key: text('template_key'), flag_key: text('flag_key') } });
    openModal({ title: 'Flag instantiated', sub: result.key,
      body: '<pre class="small">' + esc(JSON.stringify(result, null, 2)) + '</pre>' });
    return;
  }

  if (name === 'fg-safe-rollout-create') {
    await api(apiW('/flag-governance/safe-rollouts'), { method: 'POST',
      body: { flag_key: text('flag_key'), guardrail_metric: text('guardrail_metric'),
        threshold: Number(text('threshold') || 0), current_percent: Number(text('current_percent') || 0) } });
    await loadView();
    toast('Local safe rollout started.', 'success');
    return;
  }

  if (name === 'fg-safe-rollout-eval') {
    const result = await api(apiW('/flag-governance/safe-rollouts/evaluate'), { method: 'POST',
      body: { flag_key: text('flag_key'), observed_rate: Number(text('observed_rate') || 0),
        baseline_rate: Number(text('baseline_rate') || 0) } });
    openModal({ title: 'Guardrail decision', sub: result.guardrail_metric,
      body: '<p class="small">Decision: <strong>' + esc(result.action) +
        '</strong> Â· next traffic ' + result.next_percent + '% Â· delta ' +
        Number(result.delta).toFixed(4) + '</p>' });
    return;
  }

  if (name === 'fg-settings-save') {
    await api(apiW('/flag-governance/settings'), { method: 'PUT',
      body: { require_project_for_features: text('require_project_for_features') === 'true',
        require_project_for_sdk: text('require_project_for_sdk') === 'true' } });
    await loadView();
    toast('Flag settings saved locally.', 'success');
    return;
  }

  if (name === 'fg-ramp-create') {
    await api(apiW('/flag-governance/ramps'), { method: 'POST',
      body: { flag_key: text('flag_key'), start_percent: Number(text('start_percent') || 0),
        end_percent: Number(text('end_percent') || 0), starts_at: text('starts_at'),
        ends_at: text('ends_at') } });
    await loadView();
    toast('Local ramp schedule saved.', 'success');
    return;
  }

  if (name === 'fg-ramp-percent') {
    const result = await api(apiW('/flag-governance/ramps/percent-at'), { method: 'POST',
      body: { attrs: { flag_key: text('flag_key'), at: text('at') } } });
    openModal({ title: 'Ramp traffic', sub: result.at,
      body: '<p class="small">' + esc(result.flag_key) + ' is at <strong>' +
        result.percent + '%</strong> traffic.</p>' });
    return;
  }

  if (name === 'fg-revision-create') {
    let config;
    try { config = JSON.parse(text('config_json')); }
    catch (e) { toast('Config must be a valid JSON object.', 'error'); return; }
    await api(apiW('/flag-governance/revisions'), { method: 'POST',
      body: { flag_key: text('flag_key'), effective_at: text('effective_at'), config: config } });
    await loadView();
    toast('Scheduled revision saved as pending.', 'success');
    return;
  }

  if (name === 'fg-revision-apply') {
    const result = await api(apiW('/flag-governance/revisions/apply'), { method: 'POST',
      body: { flag_key: text('flag_key'), revision_id: text('revision_id') || null } });
    await loadView();
    toast('Revision applied locally.', 'success');
    return;
  }

  if (name === 'fg-revision-resolve') {
    const result = await api(apiW('/flag-governance/revisions/resolve'), { method: 'POST',
      body: { attrs: { flag_key: text('flag_key'), at: text('at') } } });
    openModal({ title: 'Effective revision', sub: text('flag_key') + ' at ' + text('at'),
      body: '<pre class="small">' + esc(JSON.stringify(result.revision, null, 2)) + '</pre>' });
    return;
  }

  if (name === 'fg-config-set') {
    let value;
    try { value = JSON.parse(text('value_json')); }
    catch (e) { toast('Value must be a valid JSON object.', 'error'); return; }
    await api(apiW('/flag-governance/configs'), { method: 'POST',
      body: { flag_key: text('flag_key'), environment: text('environment'),
        value_type: text('value_type'), value: value } });
    await loadView();
    toast('Typed configuration saved locally.', 'success');
    return;
  }

  if (name === 'adv-analysis-create') {
    let inputs;
    try { inputs = JSON.parse(text('inputs_json')); }
    catch (e) { toast('Inputs must be a valid JSON object.', 'error'); return; }
    const result = await api(apiW('/advanced-experiments/analyses'), {
      method: 'POST', body: { name: text('name'), kind: text('kind'),
        experiment_key: text('experiment_key'), inputs: inputs },
    });
    state.advAnalysisId = result.id;
    await loadView();
    toast('Analysis computed and saved locally.', 'success');
    return;
  }

  if (name === 'adv-bandit-arm') {
    await api(apiW('/advanced-experiments/bandits/' +
      encodeURIComponent(state.advBanditKey || 'onboarding') + '/arms'), {
      method: 'POST', body: { arm: text('arm'), alpha: Number(text('alpha') || 1),
        beta: Number(text('beta') || 1), pulls: Number(text('pulls') || 0) },
    });
    await loadView();
    toast('Bandit arm saved locally.', 'success');
    return;
  }

  if (name === 'adv-bandit-reward') {
    await api(apiW('/advanced-experiments/bandits/' +
      encodeURIComponent(state.advBanditKey || 'onboarding') + '/reward'), {
      method: 'POST', body: { arm: text('arm'), reward: Number(text('reward') || 0) },
    });
    await loadView();
    toast('Reward applied to the local bandit arm.', 'success');
    return;
  }

  if (name === 'adv-bandit-recommend') {
    const result = await api(apiW('/advanced-experiments/bandits/' +
      encodeURIComponent(state.advBanditKey || 'onboarding') + '/recommend'), {
      method: 'POST', body: { policy: text('policy'), seed: Number(text('seed') || 11) },
    });
    openModal({ title: 'Recommended arm', sub: result.policy + ' Ã‚Â· local computation',
      body: '<p class="small">Choose <strong>' + esc(result.arm) + '</strong> for this bandit.</p>' });
    return;
  }

  if (name === 'adv-holdout-create') {
    await api(apiW('/advanced-experiments/holdouts'), {
      method: 'POST', body: { name: text('name'), fraction: Number(text('fraction') || 0),
        experiment_keys: text('experiment_keys').split(',').map(function (k) { return k.trim(); }).filter(Boolean) },
    });
    await loadView();
    toast('Local holdout created.', 'success');
    return;
  }

  if (name === 'adv-holdout-check') {
    const result = await api(apiW('/advanced-experiments/holdouts/' +
      encodeURIComponent(text('holdout_id')) + '/check'), {
      method: 'POST', body: { user_key: text('user_key') },
    });
    openModal({ title: 'Holdout assignment', sub: esc(result.holdout),
      body: '<p class="small">' + esc(result.user_key) + ' is ' +
        (result.assigned ? 'in' : 'not in') + ' the local holdout.</p>' });
    return;
  }

  if (name === 'wiki-page-select') {
    state.wikiPageId = text('page_id');
    navigate('wiki-pages');
    toast('Wiki page opened.', 'success');
    return;
  }

  if (name === 'wiki-revision') {
    await api(apiW('/wiki-pages/pages/' + encodeURIComponent(state.wikiPageId || '') + '/revisions'), {
      method: 'POST', body: { title: text('title'), body: text('body'), reason: text('reason') },
    });
    navigate('wiki-pages');
    toast('Revision saved locally.', 'success');
    return;
  }

  if (name === 'wiki-view') {
    await api(apiW('/wiki-pages/pages/' + encodeURIComponent(state.wikiPageId || '') + '/views'), {
      method: 'POST', body: { visitor_id: text('visitor_id'), source: text('source') || 'local' },
    });
    navigate('wiki-pages');
    toast('Local view recorded.', 'success');
    return;
  }

  if (name === 'wiki-publication') {
    await api(apiW('/wiki-pages/pages/' + encodeURIComponent(state.wikiPageId || '') + '/publication'), {
      method: 'PUT', body: { published: text('published') === 'true', slug: text('slug') },
    });
    navigate('wiki-pages');
    toast('Publication settings saved locally.', 'success');
    return;
  }

  if (name === 'wiki-export') {
    const result = await api(apiW('/wiki-pages/pages/' + encodeURIComponent(state.wikiPageId || '') + '/exports'), {
      method: 'POST', body: { format: text('format') },
    });
    navigate('wiki-pages');
    openModal({ title: 'Local ' + esc(result.format) + ' export',
      sub: 'generated locally Ã‚Â· sha256 ' + esc(result.content_hash),
      body: '<pre class="small">' + esc(result.content) + '</pre>' });
    return;
  }

  if (name === 'wiki-label') {
    await api(apiW('/wiki-pages/labels'), { method: 'POST', body: { name: text('name') } });
    await api(apiW('/wiki-pages/pages/' + encodeURIComponent(state.wikiPageId || '') + '/labels'), {
      method: 'POST', body: { name: text('name') },
    });
    navigate('wiki-pages');
    toast('Label created and attached locally.', 'success');
    return;
  }

  if (name === 'wiki-parent') {
    await api(apiW('/wiki-pages/pages/' + encodeURIComponent(state.wikiPageId || '') + '/parent'), {
      method: 'PUT', body: { parent_id: text('parent_id') || null,
        position: parseInt(text('position') || '0', 10) || 0 },
    });
    navigate('wiki-pages');
    toast('Page parent saved locally.', 'success');
    return;
  }

  if (name === 'wiki-collection') {
    const result = await api(apiW('/wiki-pages/collections'), {
      method: 'POST', body: { name: text('name'), description: text('description') },
    });
    await api(apiW('/wiki-pages/collections/' + encodeURIComponent(result.id) + '/items'), {
      method: 'POST', body: { page_id: state.wikiPageId || '', position: 0 },
    });
    navigate('wiki-pages');
    toast('Collection created locally.', 'success');
    return;
  }

  if (name === 'wiki-blocks') {
    let blocks = [];
    try { blocks = JSON.parse(text('blocks') || '[]'); } catch (err) { toast('Blocks must be valid JSON.', 'error'); return; }
    await api(apiW('/wiki-pages/pages/' + encodeURIComponent(state.wikiPageId || '') + '/blocks'), {
      method: 'PUT', body: { blocks: blocks },
    });
    navigate('wiki-pages');
    toast('Editor blocks saved locally.', 'success');
    return;
  }

  if (name === 'wiki-editing') {
    await api(apiW('/wiki-pages/pages/' + encodeURIComponent(state.wikiPageId || '') + '/editing'), {
      method: 'POST', body: { ttl_seconds: parseInt(text('ttl_seconds') || '60', 10) || 60 },
    });
    navigate('wiki-pages');
    toast('Local edit lease started.', 'success');
    return;
  }

  if (name === 'wiki-comment-inline') {
    await api(apiW('/wiki-pages/blocks/' + encodeURIComponent(state.wikiBlockId || '') + '/comments'), {
      method: 'POST', body: { body: text('body'), block_id: state.wikiBlockId || '' },
    });
    closeModal();
    navigate('wiki-pages');
    toast('Inline comment added locally.', 'success');
    return;
  }

  if (name === 'exposure-tracker-create') {
    await api(apiW('/experiment-exposure/trackers'), {
      method: 'POST', body: { provider_key: text('provider_key'), note: text('note') },
    });
    navigate('experiment-exposure');
    toast('Local exposure tracker configured.', 'success');
    return;
  }

  if (name === 'exposure-mapping-set') {
    await api(apiW('/experiment-exposure/trackers/' + encodeURIComponent(text('tracker_id')) + '/mappings'), {
      method: 'PUT', body: { source_field: text('source_field'), target_field: text('target_field') },
    });
    navigate('experiment-exposure');
    toast('Field mapping saved locally.', 'success');
    return;
  }

  if (name === 'exposure-ingest') {
    let payload = {};
    try { payload = JSON.parse(text('payload') || '{}'); } catch (err) { toast('Payload must be valid JSON.', 'error'); return; }
    const body = { payload: payload };
    if (text('event_id')) body.event_id = text('event_id');
    const result = await api(apiW('/experiment-exposure/trackers/' +
      encodeURIComponent(text('tracker_id')) + '/exposures'), { method: 'POST', body: body });
    navigate('experiment-exposure');
    toast('Exposure ' + result.status + ' locally.', 'success');
    return;
  }

  if (name === 'exposure-batch-ingest') {
    let items = [];
    try { items = JSON.parse(text('items') || '[]'); } catch (err) { toast('Batch must be valid JSON.', 'error'); return; }
    const result = await api(apiW('/experiment-exposure/trackers/' +
      encodeURIComponent(text('tracker_id')) + '/exposures/batch'), {
      method: 'POST', body: { items: items },
    });
    navigate('experiment-exposure');
    toast('Batch: ' + result.accepted + ' accepted, ' + result.duplicates +
      ' duplicates, ' + result.rejected + ' rejected.', 'success');
    return;
  }

  if (name === 'conversation-presence') {
    await api(apiW('/conversation-ops/presence'), {
      method: 'PUT', body: { state: text('state') },
    });
    navigate('conversation-ops');
    toast('Presence recorded locally.', 'success');
    return;
  }

  if (name === 'conversation-snooze') {
    const until = new Date(Date.now() + Number(text('minutes') || 60) * 60000).toISOString();
    await api(apiW('/conversation-ops/tickets/' + encodeURIComponent(text('ticket_id')) + '/snooze'), {
      method: 'POST', body: { until: until, reason: text('reason') },
    });
    navigate('conversation-ops');
    toast('Conversation snoozed locally.', 'success');
    return;
  }

  if (name === 'conversation-mention-note') {
    const body = { body: text('body'), mentions: [text('mentioned_user_id')] };
    await api(apiW('/conversation-ops/tickets/' + encodeURIComponent(text('ticket_id')) + '/mention-note'), {
      method: 'POST', body: body,
    });
    navigate('conversation-ops');
    toast('Internal note and local mention saved.', 'success');
    return;
  }

  if (name === 'conversation-reply') {
    const body = { body: text('body'), force: text('force') === 'on' };
    if (text('client_msg_id')) body.client_msg_id = text('client_msg_id');
    const result = await api(apiW('/conversation-ops/tickets/' + encodeURIComponent(text('ticket_id')) + '/reply'), {
      method: 'POST', body: body,
    });
    navigate('conversation-ops');
    toast('Reply recorded locally (id ' + result.message_id + ').', 'success');
    return;
  }

  if (name === 'conversation-collision') {
    const result = await api(apiW('/conversation-ops/tickets/' + encodeURIComponent(text('ticket_id')) + '/collision'));
    openModal({ title: 'Collision check',
      sub: 'warning: ' + !!result.warning + ' Ã‚Â· polling-only transport',
      body: '<pre class="small">' + esc(JSON.stringify(result, null, 2)) + '</pre>' });
    return;
  }

  if (name === 'conversation-receipt') {
    await api(apiW('/conversation-ops/messages/' + encodeURIComponent(text('message_id')) + '/receipt'), {
      method: 'POST', body: { read: text('read') === 'on' },
    });
    navigate('conversation-ops');
    toast('Receipt recorded locally.', 'success');
    return;
  }

  if (name === 'conversation-bulk') {
    const ids = text('ticket_ids').split(',').map(function (s) { return s.trim(); }).filter(Boolean);
    const body = { ticket_ids: ids, status: text('status') || 'open' };
    if (text('assignee_id')) body.assignee_id = text('assignee_id');
    if (text('label')) body.label = text('label');
    const result = await api(apiW('/conversation-ops/tickets/bulk'), { method: 'POST', body: body });
    navigate('conversation-ops');
    toast(result.updated + ' conversations updated locally.', 'success');
    return;
  }

  if (name === 'conversation-folder-create') {
    let filters = {};
    try { filters = JSON.parse(text('filters') || '{}'); } catch (err) { toast('Filters must be valid JSON.', 'error'); return; }
    await api(apiW('/conversation-ops/folders'), {
      method: 'POST', body: { name: text('name'), filters: filters },
    });
    navigate('conversation-ops');
    toast('Folder saved locally with live counts.', 'success');
    return;
  }

  if (name === 'conversation-mute') {
    await api(apiW('/conversation-ops/tickets/' + encodeURIComponent(text('ticket_id')) + '/mute'), {
      method: 'POST', body: { muted: text('muted') === 'on' },
    });
    navigate('conversation-ops');
    toast('Mute state saved locally.', 'success');
    return;
  }

  if (name === 'conversation-hours-create') {
    let slots = [];
    try { slots = JSON.parse(text('slots') || '[]'); } catch (err) { toast('Slots must be valid JSON.', 'error'); return; }
    await api(apiW('/conversation-ops/inbox-hours'), {
      method: 'POST', body: {
        inbox_key: text('inbox_key'), timezone: text('timezone') || 'UTC',
        away_message: text('away_message'), slots: slots,
      },
    });
    navigate('conversation-ops');
    toast('Inbox schedule saved locally.', 'success');
    return;
  }

  if (name === 'conversation-hours-override') {
    const body = {
      date: text('date'), closed: text('closed') === 'on',
    };
    if (text('start_minute')) body.start_minute = Number(text('start_minute'));
    if (text('end_minute')) body.end_minute = Number(text('end_minute'));
    await api(apiW('/conversation-ops/inbox-hours/' + encodeURIComponent(text('hours_id')) + '/overrides'), {
      method: 'POST', body: body,
    });
    navigate('conversation-ops');
    toast('Date override saved locally.', 'success');
    return;
  }

  if (name === 'conversation-hours-holiday') {
    await api(apiW('/conversation-ops/inbox-hours/' + encodeURIComponent(text('hours_id')) + '/holidays'), {
      method: 'POST', body: {
        date: text('date'), name: text('name'), region: text('region'),
      },
    });
    navigate('conversation-ops');
    toast('Holiday saved locally.', 'success');
    return;
  }

  if (name === 'conversation-hours-close-region') {
    let dates = [];
    try { dates = JSON.parse(text('dates') || '[]'); } catch (err) { toast('Dates must be valid JSON.', 'error'); return; }
    const result = await api(apiW('/conversation-ops/inbox-hours/' + encodeURIComponent(text('hours_id')) + '/holidays/close-region'), {
      method: 'POST', body: { region: text('region'), dates: dates },
    });
    navigate('conversation-ops');
    toast(result.closed_dates + ' dates closed locally for ' + result.region + '.', 'success');
    return;
  }

  if (name === 'conversation-hours-availability') {
    const query = text('at') ? '?at=' + encodeURIComponent(text('at')) : '';
    const result = await api(apiW('/conversation-ops/inbox-hours/' + encodeURIComponent(text('hours_id')) + '/availability') + query);
    openModal({ title: 'Inbox availability',
      sub: result.open ? 'open locally' : 'unavailable: ' + result.reason,
      body: '<pre class="small">' + esc(JSON.stringify(result, null, 2)) + '</pre>' });
    return;
  }

  if (name === 'sales-cohort-create') {
    let filters = {};
    try { filters = JSON.parse(text('filters') || '{}'); } catch (err) { toast('Filters must be valid JSON.', 'error'); return; }
    await api(apiW('/sales-engagement/cohorts'), {
      method: 'POST', body: { name: text('name'), filters: filters },
    });
    navigate('sales-engagement');
    toast('Cohort saved locally.', 'success');
    return;
  }

  if (name === 'sales-offer-suggest') {
    const result = await api(apiW('/sales-engagement/offers/suggest'), {
      method: 'POST', body: { industry: text('industry'), pain: text('pain'), budget: text('budget') },
    });
    openModal({ title: 'Local offer suggestion',
      sub: 'generated_by: ' + result.generated_by,
      body: '<p>' + esc(result.offer) + '</p><p class="muted small">' + esc(result.rationale) + '</p>' });
    return;
  }

  if (name === 'sales-drafts-generate') {
    const body = { campaign_key: text('campaign_key'), steps: Number(text('steps') || 3) };
    if (text('cohort_id')) body.cohort_id = text('cohort_id');
    const result = await api(apiW('/sales-engagement/drafts/generate'), { method: 'POST', body: body });
    navigate('sales-engagement');
    toast(result.created + ' local sequence drafts generated.', 'success');
    return;
  }

  if (name === 'sales-sending-mode') {
    await api(apiW('/sales-engagement/delivery-mode'), {
      method: 'PUT', body: { mode: text('mode') },
    });
    navigate('sales-engagement');
    toast('Sending mode updated locally.', 'success');
    return;
  }

  if (name === 'sales-autopilot-optin') {
    await api(apiW('/sales-engagement/autopilot/opt-in'), {
      method: 'POST', body: { opt_in: text('opt_in') === 'on', confirm: text('confirm') === 'on' },
    });
    navigate('sales-engagement');
    toast('Autopilot choice saved locally.', 'success');
    return;
  }

  if (name === 'sales-sending-pause') {
    const body = { scope: text('scope'), paused: text('paused') === 'on' };
    if (text('inbox_key')) body.inbox_key = text('inbox_key');
    await api(apiW('/sales-engagement/delivery-pause'), { method: 'POST', body: body });
    navigate('sales-engagement');
    toast('Pause state applied locally.', 'success');
    return;
  }

  if (name === 'sales-send-rule-create') {
    let config = {};
    try { config = JSON.parse(text('config') || '{}'); } catch (err) { toast('Config must be valid JSON.', 'error'); return; }
    await api(apiW('/sales-engagement/delivery-rules'), {
      method: 'POST', body: { name: text('name'), kind: text('kind'), config: config },
    });
    navigate('sales-engagement');
    toast('Send extension registered locally.', 'success');
    return;
  }

  if (name === 'sales-outbox-enqueue') {
    await api(apiW('/sales-engagement/local-queue/enqueue'), {
      method: 'POST', body: {
        draft_id: text('draft_id'), recipient: text('recipient'), inbox_key: text('inbox_key') || 'default',
      },
    });
    navigate('sales-engagement');
    toast('Message enqueued in the local outbox (approval ladder applies).', 'success');
    return;
  }

  if (name === 'record-document-event') {
    const result = await api(apiW('/document-engagement/documents/' + encodeURIComponent(text('document_id')) + '/events'), {
      method: 'POST', body: {
        event_type: text('event_type'), visitor: text('visitor') || 'anonymous',
        scroll_depth: Number(text('scroll_depth') || 0),
        country: text('country') || 'unknown', city: text('city') || 'unknown',
        device: text('device') || 'unknown',
      },
    });
    navigate('document-engagement');
    toast('Engagement recorded locally' + (result.is_internal ? ' (internal, excluded).' : '.'), 'success');
    return;
  }

  if (name === 'record-document-click') {
    await api(apiW('/document-engagement/documents/' + encodeURIComponent(text('document_id')) + '/click'), {
      method: 'POST', body: { target: text('target'), visitor: text('visitor') || 'anonymous' },
    });
    navigate('document-engagement');
    toast('Click recorded locally.', 'success');
    return;
  }

  if (name === 'add-document-reaction') {
    await api(apiW('/document-engagement/documents/' + encodeURIComponent(text('document_id')) + '/reactions'), {
      method: 'POST', body: { key: text('key'), page_number: Number(text('page_number') || 0) },
    });
    navigate('document-engagement');
    toast('Reaction added locally.', 'success');
    return;
  }

  if (name === 'add-document-feedback') {
    await api(apiW('/document-engagement/documents/' + encodeURIComponent(text('document_id')) + '/feedback'), {
      method: 'POST', body: { body: text('body'), rating: Number(text('rating') || 5) },
    });
    navigate('document-engagement');
    toast('Feedback recorded locally.', 'success');
    return;
  }

  if (name === 'add-document-annotation') {
    await api(apiW('/document-engagement/documents/' + encodeURIComponent(text('document_id')) + '/annotations'), {
      method: 'POST', body: {
        page_number: Number(text('page_number') || 1), kind: text('kind'), content: text('content'),
      },
    });
    navigate('document-engagement');
    toast('Annotation added locally.', 'success');
    return;
  }

  if (name === 'add-internal-visitor') {
    await api(apiW('/document-engagement/internal-visitors'), {
      method: 'POST', body: { match_type: text('match_type'), value: text('value') },
    });
    navigate('document-engagement');
    toast('Internal visitor excluded from analytics.', 'success');
    return;
  }

  if (name === 'update-document-metadata') {
    const body = {};
    if (text('title')) body.title = text('title');
    if (text('folder_id')) body.folder_id = text('folder_id');
    await api(apiW('/document-engagement/documents/' + encodeURIComponent(text('document_id')) + '/metadata'), {
      method: 'PATCH', body: body,
    });
    navigate('document-engagement');
    toast('Document metadata updated locally.', 'success');
    return;
  }

  if (name === 'promote-document-version') {
    const body = {};
    if (text('external_url')) body.external_url = text('external_url');
    const result = await api(apiW('/document-engagement/documents/' + encodeURIComponent(text('document_id')) +
      '/versions/' + encodeURIComponent(text('version_id')) + '/promote'), {
      method: 'POST', body: body,
    });
    navigate('document-engagement');
    toast('Version promoted locally' + (result.external_url ? ' and repointed.' : '.'), 'success');
    return;
  }

  if (name === 'search-document-names') {
    const result = await api(apiW('/document-engagement/documents/search?q=' + encodeURIComponent(text('q'))));
    openModal({ title: 'Document name search',
      sub: (result || []).length + ' match(es)',
      body: '<pre class="small">' + esc(JSON.stringify(result, null, 2)) + '</pre>' });
    return;
  }

  if (name === 'create-advanced-embedder') {
    await api(apiW('/search-advanced/indexes/' + encodeURIComponent(text('index')) + '/embedders'), {
      method: 'POST', body: {
        name: text('name'), kind: text('kind'), dimensions: Number(text('dimensions') || 32),
      },
    });
    navigate('search-advanced');
    toast('Local embedder created.', 'success');
    return;
  }

  if (name === 'advanced-hybrid-search') {
    const result = await api(apiW('/search-advanced/indexes/' + encodeURIComponent(text('index')) + '/search/hybrid'), {
      method: 'POST', body: {
        q: text('q'), embedder_name: text('embedder_name'),
        semantic_weight: Number(text('semantic_weight') || 0.5),
      },
    });
    openModal({ title: 'Hybrid search results',
      sub: 'Local semantic + lexical blend Ã‚Â· ' + (result.results || []).length + ' hits',
      body: '<pre class="small">' + esc(JSON.stringify(result, null, 2)) + '</pre>' });
    return;
  }

  if (name === 'create-advanced-suggestion') {
    await api(apiW('/search-advanced/indexes/' + encodeURIComponent(text('index')) + '/suggestions'), {
      method: 'POST', body: { key: text('key'), attribute: text('attribute') },
    });
    navigate('search-advanced');
    toast('Suggestion connector created locally.', 'success');
    return;
  }

  if (name === 'advanced-suggest') {
    const result = await api(apiW('/search-advanced/indexes/' + encodeURIComponent(text('index')) + '/suggest'), {
      method: 'POST', body: { q: text('q') },
    });
    openModal({ title: 'Suggestions',
      sub: (result.suggestions || []).join(', ') || 'No prefix matches',
      body: '<pre class="small">' + esc(JSON.stringify(result, null, 2)) + '</pre>' });
    return;
  }

  if (name === 'create-advanced-federation') {
    let members;
    try { members = JSON.parse(text('members') || '[]'); }
    catch (err) { throw new Error('Members must be a valid JSON array of {index, weight}.'); }
    await api(apiW('/search-advanced/federations'), {
      method: 'POST', body: { key: text('key'), members: members },
    });
    navigate('search-advanced');
    toast('Federation created locally.', 'success');
    return;
  }

  if (name === 'advanced-federated-search') {
    const result = await api(apiW('/search-advanced/federations/' + encodeURIComponent(text('federation')) + '/search'), {
      method: 'POST', body: { q: text('q') },
    });
    openModal({ title: 'Federated search results',
      sub: 'Weighted merge Ã‚Â· ' + (result.results || []).length + ' hits',
      body: '<pre class="small">' + esc(JSON.stringify(result, null, 2)) + '</pre>' });
    return;
  }

  if (name === 'advanced-swap') {
    await api(apiW('/search-advanced/indexes/' + encodeURIComponent(text('left')) + '/swap'), {
      method: 'POST', body: { right_index: text('right') },
    });
    navigate('search-advanced');
    toast('Indexes swapped locally.', 'success');
    return;
  }

  if (name === 'advanced-edit-function') {
    const ids = text('document_ids').split(',').map(function (v) { return v.trim(); }).filter(Boolean);
    const result = await api(apiW('/search-advanced/indexes/' + encodeURIComponent(text('index')) + '/documents/edit-function'), {
      method: 'POST', body: {
        attribute: text('attribute'), op: text('op'),
        value: text('value') || null, document_ids: ids,
      },
    });
    navigate('search-advanced');
    toast('Edited ' + result.changed + ' document(s) locally.', 'success');
    return;
  }

  if (name === 'advanced-compact') {
    await api(apiW('/search-advanced/indexes/' + encodeURIComponent(text('index')) + '/compact'), {
      method: 'POST', body: { kind: text('kind') },
    });
    navigate('search-advanced');
    toast('Compaction recorded locally.', 'success');
    return;
  }

  if (name === 'create-advanced-template') {
    await api(apiW('/search-advanced/indexes/' + encodeURIComponent(text('index')) + '/templates'), {
      method: 'POST', body: { key: text('key'), kind: text('kind'), body: text('body') },
    });
    navigate('search-advanced');
    toast('Template created locally.', 'success');
    return;
  }

  if (name === 'advanced-template-render') {
    let doc;
    try { doc = JSON.parse(text('document') || '{}'); }
    catch (err) { throw new Error('Document must be valid JSON.'); }
    const result = await api(apiW('/search-advanced/indexes/' + encodeURIComponent(text('index')) +
      '/templates/' + encodeURIComponent(text('template_id')) + '/render'), {
      method: 'POST', body: { document: doc, query: text('query') },
    });
    openModal({ title: 'Rendered template', sub: result.template || '',
      body: '<pre class="small">' + esc(result.rendered || '') + '</pre>' });
    return;
  }

  if (name === 'create-advanced-preview') {
    const created = await api(apiW('/search-advanced/indexes/' + encodeURIComponent(text('index')) + '/previews'), {
      method: 'POST', body: { key: text('key'), query: text('query') },
    });
    const result = await api(apiW('/search-advanced/previews/' + encodeURIComponent(created.id) + '/run'), {
      method: 'POST',
    });
    openModal({ title: 'Local search preview',
      sub: 'local_only: ' + !!result.local_only + ' Ã‚Â· ' + (result.results || []).length + ' hits',
      body: '<pre class="small">' + esc(JSON.stringify(result, null, 2)) + '</pre>' });
    return;
  }

  if (name === 'create-query-fact-table') {
    let fields;
    try { fields = JSON.parse(text('fields_json') || '[]'); }
    catch (err) { throw new Error('Fields must be a valid JSON array.'); }
    await api(apiW('/experiment-queries/fact-tables'), {
      method: 'POST', body: { key: text('key'), name: text('name'),
        source: text('source'), fields: fields },
    });
    closeModal();
    navigate('experiment-queries');
    toast('Local fact table created.', 'success');
    return;
  }

  if (name === 'create-discovery-query') {
    let fields, filters;
    try {
      fields = JSON.parse(text('fields_json') || '[]');
      filters = JSON.parse(text('filters_json') || '[]');
    } catch (err) { throw new Error('Fields and filters must be valid JSON arrays.'); }
    await api(apiW('/experiment-queries/discovery-queries'), {
      method: 'POST', body: { key: text('key'), name: text('name'),
        fact_table_id: text('fact_table_id'), fields: fields, filters: filters,
        limit: Number(text('limit') || 100) },
    });
    closeModal();
    navigate('experiment-queries');
    toast('Discovery query created locally.', 'success');
    return;
  }

  if (name === 'create-assignment-query') {
    let filters;
    try { filters = JSON.parse(text('filters_json') || '[]'); }
    catch (err) { throw new Error('Filters must be a valid JSON array.'); }
    await api(apiW('/experiment-queries/assignment-queries'), {
      method: 'POST', body: { key: text('key'), name: text('name'),
        experiment_key: text('experiment_key'), source: text('source'), filters: filters },
    });
    closeModal();
    navigate('experiment-queries');
    toast('Assignment query created locally.', 'success');
    return;
  }

  if (name === 'create-identifier-type') {
    await api(apiW('/experiment-queries/identifier-types'), {
      method: 'POST', body: { key: text('key'), name: text('name'),
        attribute: text('attribute'), pattern: text('pattern') || undefined,
        normalization: text('normalization') },
    });
    closeModal();
    navigate('experiment-queries');
    toast('Identifier type created locally.', 'success');
    return;
  }

  if (name === 'create-identifier-join') {
    let mappings;
    try { mappings = JSON.parse(text('mappings_json') || '[]'); }
    catch (err) { throw new Error('Mappings must be a valid JSON array.'); }
    await api(apiW('/experiment-queries/identifier-joins'), {
      method: 'POST', body: { key: text('key'), name: text('name'),
        left_type_id: text('left_type_id'), right_type_id: text('right_type_id'),
        mappings: mappings },
    });
    closeModal();
    navigate('experiment-queries');
    toast('Identifier join created locally.', 'success');
    return;
  }

  if (name === 'resolve-identifier-join') {
    const result = await api(apiW('/experiment-queries/identifier-joins/' +
      encodeURIComponent(form.dataset.joinId) + '/resolve'), {
      method: 'POST', body: { value: text('value'), direction: text('direction') },
    });
    openModal({ title: 'Join resolution', sub: result.count + ' local match(es)',
      body: '<pre class="small">' + esc(JSON.stringify(result, null, 2)) + '</pre>' });
    return;
  }

  if (name === 'create-experiment-funnel') {
    let steps;
    try { steps = JSON.parse(text('steps_json') || '[]'); }
    catch (err) { throw new Error('Steps must be a valid JSON array.'); }
    await api(apiW('/experiment-queries/funnels'), {
      method: 'POST', body: { key: text('key'), name: text('name'),
        experiment_key: text('experiment_key'), steps: steps },
    });
    closeModal();
    navigate('experiment-queries');
    toast('Experiment funnel created locally.', 'success');
    return;
  }

  if (name === 'create-experiment-report') {
    let config;
    try { config = JSON.parse(text('config_json') || '{}'); }
    catch (err) { throw new Error('Config must be a valid JSON object.'); }
    await api(apiW('/experiment-queries/reports'), {
      method: 'POST', body: { key: text('key'), name: text('name'),
        report_type: text('report_type'), config: config },
    });
    closeModal();
    navigate('experiment-queries');
    toast('Local experiment report created.', 'success');
    return;
  }

  if (name === 'assess-carryover') {
    const result = await api(apiW('/experiment-queries/carryover'), {
      method: 'POST', body: { key: text('key'), experiment_key: text('experiment_key'),
        previous_end: text('previous_end'), restart: text('restart'),
        washout_days: Number(text('washout_days') || 7) },
    });
    closeModal();
    openModal({ title: result.warning ? 'Carryover risk detected' : 'Carryover risk low',
      sub: result.gap_days + ' day(s) elapsed',
      body: '<p>' + esc(result.guidance) + '</p>' });
    await loadView();
    return;
  }

  if (name === 'create-search-index') {
    await api(apiW('/search-engine/indexes'), {
      method: 'POST',
      body: { name: text('name'), primary_key: text('primary_key') || 'id' },
    });
    closeModal();
    navigate('search-indexes');
    toast('Search index created locally.', 'success');
    return;
  }

  if (name === 'search-index-query') {
    state.lastSearchQuery = text('q');
    state.lastSearchResult = await api(apiW('/search-engine/indexes/' +
      encodeURIComponent(text('index')) + '/search'), {
      method: 'POST', body: { q: text('q'), limit: 20 },
    });
    await loadView();
    return;
  }

  if (name === 'evaluate-trigger') {
    let attributes;
    try { attributes = JSON.parse(text('attributes') || '{}'); }
    catch (err) { throw new Error('Context attributes must be valid JSON.'); }
    const result = await api(apiW('/feedback/targeting/triggers/' +
      encodeURIComponent(form.dataset.triggerId) + '/evaluate'), {
      method: 'POST',
      body: { user_id: text('user_id'), action: text('action'), attributes: attributes },
    });
    openModal({ title: result.shown ? 'Survey would be shown' : 'Survey suppressed',
      sub: 'Reason: ' + result.reason,
      body: '<pre class="small">' + esc(JSON.stringify(result, null, 2)) + '</pre>' });
    toast('Decision recorded locally.', 'success');
    return;
  }

  if (name === 'consent-preferences') {
    const pending = state.pendingConsent;
    if (!pending) throw new Error('Preference session expired. Reopen the contact.');
    const channels = {};
    ['email', 'sms', 'push'].forEach(function (channel) {
      const box = form.querySelector('[name="channel_' + channel + '"]');
      if (box) channels[channel] = box.checked;
    });
    await api(apiW('/email/preferences'), {
      method: 'POST', body: { token: pending.token, channels: channels },
    });
    state.pendingConsent = null;
    closeModal();
    await loadView();
    toast('Preferences saved locally. No email was sent.', 'success');
    return;
  }

  if (name === 'marketing-contact-classify') {
    await api(apiW('/marketing-content/contact-types'), {
      method: 'POST', body: { contact_id: text('contact_id'), kind: text('kind') },
    });
    navigate('marketing-content');
    toast('Contact classified locally.', 'success');
    return;
  }

  if (name === 'marketing-contact-identify') {
    await api(apiW('/marketing-content/contact-types/' + encodeURIComponent(text('contact_id')) + '/identify'), {
      method: 'POST', body: { details: { email: text('email') } },
    });
    navigate('marketing-content');
    toast('Visitor identified locally.', 'success');
    return;
  }

  if (name === 'marketing-contact-get') {
    const result = await api(apiW('/marketing-content/contact-types/' +
      encodeURIComponent(text('contact_id'))));
    openModal({ title: 'Contact classification', sub: result.kind,
      body: '<pre class="small">' + esc(JSON.stringify(result, null, 2)) + '</pre>' });
    return;
  }

  if (name === 'marketing-page-create') {
    await api(apiW('/marketing-content/landing-pages'), {
      method: 'POST', body: {
        name: text('name'), slug: text('slug'), html_body: text('html_body'),
      },
    });
    navigate('marketing-content');
    toast('Landing page stored locally. Nothing was published externally.', 'success');
    return;
  }

  if (name === 'marketing-form-create') {
    await api(apiW('/marketing-content/forms'), {
      method: 'POST', body: {
        name: text('name'),
        fields: String(text('fields') || '').split(',').map(function (f) { return f.trim(); }).filter(Boolean),
      },
    });
    navigate('marketing-content');
    toast('Form stored locally.', 'success');
    return;
  }

  if (name === 'marketing-form-progressive') {
    const result = await api(apiW('/marketing-content/forms/' + encodeURIComponent(text('form_id')) +
      '/progressive-fields?contact_id=' + encodeURIComponent(text('contact_id'))));
    openModal({ title: 'Pending profile fields', sub: 'Locally derived from known contact details',
      body: '<pre class="small">' + esc(JSON.stringify(result, null, 2)) + '</pre>' });
    return;
  }

  if (name === 'marketing-form-submit') {
    const result = await api(apiW('/marketing-content/forms/' + encodeURIComponent(text('form_id')) + '/submit'), {
      method: 'POST', body: {
        contact_id: text('contact_id'), answers: { email: text('email') },
        actions: String(text('actions') || '').split(',').map(function (a) { return a.trim(); }).filter(Boolean),
      },
    });
    openModal({ title: 'Local submit effects', sub: 'No email or SMS was sent',
      body: '<pre class="small">' + esc(JSON.stringify(result, null, 2)) + '</pre>' });
    return;
  }

  if (name === 'marketing-content-create') {
    const variants = {};
    String(text('variants') || '').split('\n').forEach(function (line) {
      const pos = line.indexOf(':');
      if (pos > 0) variants[line.slice(0, pos).trim()] = line.slice(pos + 1).trim();
    });
    await api(apiW('/marketing-content/dynamic-content'), {
      method: 'POST', body: {
        name: text('name'), segment_field: text('segment_field'), variants: variants,
      },
    });
    navigate('marketing-content');
    toast('Dynamic content stored locally.', 'success');
    return;
  }

  if (name === 'marketing-dynamic-resolve') {
    const field = text('segment_field');
    const value = text('value');
    const attributes = {};
    attributes[field] = value;
    const result = await api(apiW('/marketing-content/dynamic-content/' +
      encodeURIComponent(text('content_id')) + '/resolve'), { method: 'POST', body: { attributes: attributes } });
    openModal({ title: 'Resolved variant', sub: 'Deterministic local selection',
      body: '<pre class="small">' + esc(JSON.stringify(result, null, 2)) + '</pre>' });
    return;
  }

  if (name === 'marketing-asset-add') {
    await api(apiW('/marketing-content/assets'), {
      method: 'POST', body: {
        name: text('name'), content_type: text('content_type'),
        content_base64: text('content_base64'),
      },
    });
    navigate('marketing-content');
    toast('Asset stored locally. No download was served.', 'success');
    return;
  }

  if (name === 'marketing-widget-create') {
    await api(apiW('/marketing-content/dashboard-widgets'), {
      method: 'POST', body: {
        name: text('name'), widget_type: text('widget_type'),
        config: { source: text('source') },
      },
    });
    navigate('marketing-content');
    toast('Dashboard widget stored locally.', 'success');
    return;
  }

  if (name === 'support-report-filter') {
    state.supportReportDimension = text('dimension');
    state.supportReportStatus = text('status');
    navigate('support-reporting');
    toast('Support report filters applied locally.', 'success');
    return;
  }

  if (name === 'support-csat-rule-create') {
    const splitLabels = function (value) {
      return String(value || '').split(',').map(function (part) { return part.trim(); }).filter(Boolean);
    };
    await api(apiW('/support-reporting/csat-rules'), {
      method: 'POST',
      body: {
        name: text('name'),
        include_labels: splitLabels(text('include_labels')),
        exclude_labels: splitLabels(text('exclude_labels')),
        enabled: true,
      },
    });
    navigate('support-reporting');
    toast('CSAT rule stored locally. No survey was sent.', 'success');
    return;
  }

  throw new Error('Unknown form: ' + name);
}

async function handleFormSubmit(form) {
  const button = form.querySelector('[type="submit"]');
  const original = button ? button.innerHTML : null;
  if (button) { button.disabled = true; button.innerHTML = icon('refresh', 15) + ' WorkingÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦'; }
  clearFormError(form);
  try {
    await processForm(form.dataset.form, new FormData(form), form);
  } catch (err) {
    const message = errMessage(err);
    setFormError(form, message);
    toast(message, 'error');
  } finally {
    if (button && button.isConnected) { button.disabled = false; button.innerHTML = original; }
  }
}

/* ------------------------------------------------------------------ *
 * Modal openers for create / edit flows
 * ------------------------------------------------------------------ */

function openCreateContact() {
  openModal({
    title: 'Add contact',
    sub: 'One shared customer identity for the whole workspace.',
    body: '<form data-form="create-contact"><div class="form-grid">' +
      field('email', 'Email', { type: 'email', required: true, placeholder: 'name@company.com' }) +
      field('full_name', 'Full name', { placeholder: 'Alex Morgan' }) +
      field('company_name', 'Company', { placeholder: 'Acme Inc.' }) +
      field('phone', 'Phone', { placeholder: '+1 555 0100' }) +
      field('source', 'Source', { placeholder: 'manual', value: 'manual' }) +
      field('tags', 'Tags', { placeholder: 'vip, inbound' }) +
      '</div><div class="form-actions"><button type="button" class="btn" data-action="close-modal">Cancel</button>' +
      '<button type="submit" class="btn btn--primary">' + icon('plus', 15) + ' Create contact</button></div></form>',
  });
}

async function openEditContact(id) {
  let c = state.caches.contact;
  if (!c || c.id !== id) {
    try { c = await api(apiW('/contacts/' + encodeURIComponent(id))); }
    catch (err) { toast(errMessage(err), 'error'); return; }
  }
  openModal({
    title: 'Edit contact',
    sub: c.email,
    body: '<form data-form="edit-contact"><input type="hidden" name="id" value="' + attr(c.id) + '">' +
      '<div class="form-grid">' +
      field('full_name', 'Full name', { value: c.full_name || '' }) +
      field('company_name', 'Company', { value: c.company_name || '' }) +
      field('phone', 'Phone', { value: c.phone || '' }) +
      field('lifecycle_stage', 'Lifecycle stage', {
        type: 'select',
        options: selectOptions([['lead', 'Lead'], ['qualified', 'Qualified'], ['opportunity', 'Opportunity'], ['customer', 'Customer']], c.lifecycle_stage),
      }) +
      field('tags', 'Tags', { value: (c.tags || []).join(', '), placeholder: 'comma, separated', span: true }) +
      '</div><div class="form-actions"><button type="button" class="btn" data-action="close-modal">Cancel</button>' +
      '<button type="submit" class="btn btn--primary">' + icon('check', 15) + ' Save changes</button></div></form>',
  });
}

function openCreateCompany() {
  openModal({
    title: 'Add company',
    sub: 'Organisation records can be referenced by contacts.',
    body: '<form data-form="create-company"><div class="form-grid">' +
      field('name', 'Company name', { required: true, placeholder: 'Acme Inc.', span: true }) +
      field('industry', 'Industry', { placeholder: 'Software' }) +
      field('website', 'Website', { placeholder: 'https://example.com' }) +
      field('location', 'Location', { placeholder: 'City, Country' }) +
      '</div><div class="form-actions"><button type="button" class="btn" data-action="close-modal">Cancel</button>' +
      '<button type="submit" class="btn btn--primary">' + icon('plus', 15) + ' Create company</button></div></form>',
  });
}

async function openCreateLead() {
  const contacts = await fetchAll(apiW('/contacts'), 100);
  if (!contacts.length) {
    openModal({
      title: 'Add lead',
      body: emptyState('users', 'Create a contact first', 'A lead must point at an existing contact record.') +
        '<div class="form-actions"><button class="btn btn--primary" data-action="goto-contacts">Go to contacts</button></div>',
    });
    return;
  }
  const options = selectOptions(contacts.map(function (c) {
    return [c.id, (c.full_name || c.email) + ' ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â ' + c.email];
  }), '');
  openModal({
    title: 'Add lead',
    sub: 'Qualification starts as new.',
    body: '<form data-form="create-lead"><div class="form-grid">' +
      field('contact_id', 'Contact', { type: 'select', required: true, options: options, span: true }) +
      field('source', 'Source', { placeholder: 'manual', value: 'manual' }) +
      field('priority', 'Priority', { type: 'select', options: selectOptions([['low', 'Low'], ['normal', 'Normal'], ['high', 'High']], 'normal') }) +
      field('score', 'Score', { type: 'number', value: '0', min: '0' }) +
      '</div><div class="form-actions"><button type="button" class="btn" data-action="close-modal">Cancel</button>' +
      '<button type="submit" class="btn btn--primary">' + icon('plus', 15) + ' Create lead</button></div></form>',
  });
}

function openEditLead(lead) {
  openModal({
    title: 'Edit lead',
    sub: 'Status changes use Qualify and Convert.',
    body: '<form data-form="edit-lead"><input type="hidden" name="id" value="' + attr(lead.id) + '">' +
      '<div class="form-grid">' +
      field('priority', 'Priority', { type: 'select', options: selectOptions([['low', 'Low'], ['normal', 'Normal'], ['high', 'High']], lead.priority) }) +
      field('score', 'Score', { type: 'number', value: String(lead.score || 0), min: '0' }) +
      '</div><div class="form-actions"><button type="button" class="btn" data-action="close-modal">Cancel</button>' +
      '<button type="submit" class="btn btn--primary">' + icon('check', 15) + ' Save lead</button></div></form>',
  });
}

async function openCreateTask() {
  let contacts = [];
  if (can(P.contactRead)) {
    try { contacts = await fetchAll(apiW('/contacts'), 100); } catch (e) { contacts = []; }
  }
  const options = [['', 'No contact']].concat(contacts.map(function (c) {
    return [c.id, c.full_name || c.email];
  }));
  openModal({
    title: 'New task',
    sub: 'Follow-up work is recorded as an event.',
    body: '<form data-form="create-task"><div class="form-grid">' +
      field('title', 'Title', { required: true, placeholder: 'Follow up with Acme', span: true }) +
      field('contact_id', 'Contact', { type: 'select', options: selectOptions(options, '') }) +
      field('priority', 'Priority', { type: 'select', options: selectOptions([['low', 'Low'], ['normal', 'Normal'], ['high', 'High']], 'normal') }) +
      field('due_at', 'Due date and time', { type: 'datetime-local' }) +
      field('description', 'Description', { type: 'textarea', placeholder: 'Optional context', span: true }) +
      '</div><div class="form-actions"><button type="button" class="btn" data-action="close-modal">Cancel</button>' +
      '<button type="submit" class="btn btn--primary">' + icon('plus', 15) + ' Create task</button></div></form>',
  });
}

function openIntake() {
  openModal({
    title: 'Record website form',
    sub: 'One submission creates a linked contact, lead, task, notification and draft.',
    body: '<form data-form="record-intake"><div class="form-grid">' +
      field('email', 'Submitter email', { type: 'email', required: true, placeholder: 'name@company.com', span: true }) +
      field('full_name', 'Full name', { placeholder: 'Alex Morgan' }) +
      field('company', 'Company', { placeholder: 'Acme Inc.' }) +
      field('source', 'Source', { value: 'website_form', placeholder: 'website_form' }) +
      field('submission_id', 'Submission ID', { placeholder: 'Optional ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â repeated IDs are idempotent' }) +
      field('message', 'Message', { type: 'textarea', placeholder: 'What did they ask for?', span: true }) +
      '</div><div class="form-actions"><button type="button" class="btn" data-action="close-modal">Cancel</button>' +
      '<button type="submit" class="btn btn--primary">' + icon('inbox', 15) + ' Run intake</button></div></form>',
  });
}

const AGENT_PROVIDERS = [['local', 'Local'], ['openai', 'OpenAI'], ['anthropic', 'Anthropic']];
const AGENT_STATES = [['active', 'Active'], ['paused', 'Paused']];

function agentFields(agent) {
  const editing = !!agent;
  return (editing ? '<input type="hidden" name="id" value="' + attr(agent.id) + '">' : '') +
    '<div class="form-grid">' +
    field('name', 'Name', { required: true, value: editing ? agent.name : '', placeholder: 'Research assistant' }) +
    field('model_provider', 'Model provider', {
      type: 'select', options: selectOptions(AGENT_PROVIDERS, editing ? agent.model_provider : 'local'),
    }) +
    field('model_name', 'Model name', { required: true, value: editing ? agent.model_name : '', placeholder: 'llama-3' }) +
    field('max_steps', 'Maximum steps', {
      type: 'number', min: '1', value: editing ? String(agent.max_steps) : '10',
      hint: 'Hard limit on steps a run may record.',
    }) +
    field('purpose', 'Purpose', {
      type: 'textarea', required: true, span: true, value: editing ? agent.purpose : '',
      placeholder: 'What this agent is for',
    }) +
    field('boundary', 'Boundary', {
      type: 'textarea', required: true, span: true, value: editing ? agent.boundary : '',
      placeholder: 'What this agent must never do',
    }) +
    field('status', 'Status', {
      type: 'select', options: selectOptions(AGENT_STATES, editing ? agent.status : 'active'),
    }) +
    checkboxField('requires_approval', 'Require approval before a run completes',
      editing ? !!agent.requires_approval : false,
      'Governed runs wait for an approver instead of completing themselves.') +
    '</div>';
}

function openCreateAgent() {
  openModal({
    title: 'New agent',
    sub: 'Configuration only ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â no external AI provider is called.',
    body: '<form data-form="create-agent">' + agentFields(null) +
      governanceNote('This records a governed configuration. No AI output is generated.') +
      '<div class="form-actions"><button type="button" class="btn" data-action="close-modal">Cancel</button>' +
      '<button type="submit" class="btn btn--primary">' + icon('plus', 15) + ' Create agent</button></div></form>',
  });
}

function openEditAgent(agent) {
  openModal({
    title: 'Edit agent',
    sub: agent.name + ' Ãƒâ€šÃ‚Â· changes are recorded as events.',
    body: '<form data-form="edit-agent">' + agentFields(agent) +
      '<div class="form-actions"><button type="button" class="btn" data-action="close-modal">Cancel</button>' +
      '<button type="submit" class="btn btn--primary">' + icon('check', 15) + ' Save agent</button></div></form>',
  });
}

function openAgentRun(agent) {
  openModal({
    title: 'Request agent run',
    sub: agent.name + ' Ãƒâ€šÃ‚Â· ' + cap(agent.model_provider) + ' Ãƒâ€šÃ‚Â· up to ' + agent.max_steps + ' steps',
    body: '<form data-form="request-agent-run"><input type="hidden" name="agent_id" value="' + attr(agent.id) + '">' +
      '<div class="form-grid">' +
      field('task', 'Task', { type: 'textarea', required: true, span: true, placeholder: 'Describe the work to record' }) +
      field('steps_taken', 'Starting steps', {
        type: 'number', min: '0', value: '0',
        hint: 'Cannot exceed ' + agent.max_steps + ' steps for this agent.',
      }) +
      '</div>' + governanceNote('This records a queued run. No external AI provider is called and no output is fabricated.') +
      '<div class="form-actions"><button type="button" class="btn" data-action="close-modal">Cancel</button>' +
      '<button type="submit" class="btn btn--primary">' + icon('zap', 15) + ' Request run</button></div></form>',
  });
}

function openAgentProgress(agent, run) {
  openModal({
    title: 'Record run progress',
    sub: 'Task: ' + run.task,
    body: '<form data-form="record-agent-progress">' +
      '<input type="hidden" name="agent_id" value="' + attr(agent.id) + '">' +
      '<input type="hidden" name="run_id" value="' + attr(run.id) + '">' +
      '<div class="form-grid">' +
      field('steps_taken', 'Steps taken', {
        type: 'number', min: String(run.steps_taken), value: String(run.steps_taken),
        hint: 'Steps cannot decrease or exceed ' + agent.max_steps + '.',
      }) +
      field('status', 'Status', {
        type: 'select',
        options: selectOptions([
          ['running', 'Running'], ['completed', 'Completed'],
          ['failed', 'Failed'], ['awaiting_approval', 'Awaiting approval'],
        ], run.status),
      }) +
      field('error', 'Error detail', { type: 'textarea', span: true, placeholder: 'Optional ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â only when a run fails' }) +
      '</div>' + governanceNote(agent.requires_approval
        ? 'This agent requires approval: marking work completed moves the run to awaiting approval.'
        : 'Progress is recorded locally. Steps are a governance record, not executed AI work.') +
      '<div class="form-actions"><button type="button" class="btn" data-action="close-modal">Cancel</button>' +
      '<button type="submit" class="btn btn--primary">' + icon('check', 15) + ' Save progress</button></div></form>',
  });
}

function openConfigureIntegration(entry, row) {
  const config = row && row.config ? JSON.stringify(row.config, null, 2) : '{}';
  openModal({
    title: (row ? 'Edit ' : 'Configure ') + entry.display_name,
    sub: 'Provider key: ' + entry.provider,
    body: '<form data-form="save-integration"><input type="hidden" name="provider" value="' + attr(entry.provider) + '">' +
      '<div class="form-grid">' +
      field('display_name', 'Display name', { value: row ? row.display_name : entry.display_name }) +
      field('status', 'Status', {
        type: 'select',
        options: selectOptions([['configured', 'Configured'], ['disconnected', 'Disconnected'], ['disabled', 'Disabled']],
          row ? row.status : 'configured'),
      }) +
      field('config', 'Non-sensitive settings (JSON)', {
        type: 'textarea', span: true, value: config,
        hint: 'Secrets such as API keys, tokens and passwords are rejected by the API.',
      }) +
      '</div>' + governanceNote('Recording settings does not activate a live adapter or make an outbound call.') +
      '<div class="form-actions"><button type="button" class="btn" data-action="close-modal">Cancel</button>' +
      '<button type="submit" class="btn btn--primary">' + icon('check', 15) + ' Save settings</button></div></form>',
  });
}

function openInviteMember() {
  openModal({
    title: 'Invite member',
    sub: 'The API returns a one-time token; it does not send email.',
    body: '<form data-form="invite-member"><div class="form-grid">' +
      field('email', 'Email', { type: 'email', required: true, placeholder: 'teammate@company.com', span: true }) +
      field('role', 'Role', { type: 'select', options: selectOptions([
        ['admin', 'Admin'], ['sales_manager', 'Sales manager'], ['sales_rep', 'Sales rep'],
        ['marketing', 'Marketing'], ['support', 'Support'], ['read_only', 'Read only'],
      ], 'sales_rep'), span: true }) +
      '</div><div class="form-actions"><button type="button" class="btn" data-action="close-modal">Cancel</button>' +
      '<button type="submit" class="btn btn--primary">' + icon('link', 15) + ' Create invitation</button></div></form>',
  });
}

function currentProjectId() {
  const parts = currentRoute().split('/');
  return parts[1] || '';
}

async function openWorkItemBoard() {
  const board = await api(apiW('/projects/' + encodeURIComponent(currentProjectId()) + '/board'));
  const columns = (board && board.columns) || [];
  const body = columns.length ? '<div class="row" style="gap:12px;align-items:flex-start;overflow-x:auto">' +
    columns.map(function (c) {
      return '<div style="min-width:190px;flex:1"><div class="card-title" style="margin-bottom:8px">' +
        esc(c.name) + ' <span class="muted tiny">' + (c.items || []).length + '</span></div>' +
        (c.items || []).map(function (i) {
          return '<div class="list-row"><div class="list-row-main"><div class="list-row-title small">' +
            esc(i.title) + '</div></div></div>';
        }).join('') + '</div>';
    }).join('') + '</div>' : emptyState('grid', 'Empty board', 'The board derives from real work-item states.');
  openModal({ title: 'Work item board', sub: 'Grouped by the real workflow states of this project.', body: '<div class="card-body">' + body + '</div>' });
}

async function openWorkItemLabels() {
  const labels = await api(apiW('/projects/' + encodeURIComponent(currentProjectId()) + '/labels'));
  const body = (labels || []).map(function (l) {
    return '<div class="list-row"><span class="badge" style="background:' + esc(l.color || '#dfe8e4') + '">' +
      esc(l.name) + '</span></div>';
  }).join('');
  openModal({
    title: 'Project labels',
    sub: 'Labels are workspace-scoped and filter work items.',
    body: '<div class="card-body">' + (body || emptyState('tag', 'No labels', 'Create a label to organise work.')) +
      '<form data-form="project-label-create" class="form-grid" style="margin-top:16px">' +
      field('name', 'Label name', { required: true, span: true }) +
      '<div class="field"><button type="submit" class="btn">' + icon('plus', 14) + ' Add label</button></div></form></div>',
  });
}

async function openWorkItemModules() {
  const modules = await api(apiW('/projects/' + encodeURIComponent(currentProjectId()) + '/modules'));
  const body = (modules || []).map(function (m) {
    return '<div class="list-row"><div class="list-row-main"><div class="list-row-title">' +
      esc(m.name) + '</div><div class="list-row-sub">' + esc(m.state || 'planned') +
      ' Ãƒâ€šÃ‚Â· ' + String(m.progress_percent || 0) + '% complete</div></div></div>';
  }).join('');
  openModal({ title: 'Project modules', sub: 'Modules group work with a lead, dates and progress.',
    body: '<div class="card-body">' + (body || emptyState('layers', 'No modules', 'Create a module to group delivery work.')) + '</div>' });
}

async function openWorkItemActivity(itemId) {
  const id = itemId || (state.selectedItemId || '');
  if (!id) { toast('Select a work item first.', 'error'); return; }
  const rows = await api(apiW('/projects/' + encodeURIComponent(currentProjectId()) + '/items/' + encodeURIComponent(id) + '/activity'));
  const body = (rows || []).map(function (a) {
    return '<div class="list-row"><div class="list-row-main"><div class="list-row-title small">' +
      esc(a.field || a.event_type) + '</div><div class="list-row-sub">' +
      esc(String(a.old_value || '')) + ' ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ ' + esc(String(a.new_value || '')) + '</div></div></div>';
  }).join('');
  openModal({ title: 'Item activity', sub: 'Immutable field-change history from the shared event spine.',
    body: '<div class="card-body">' + (body || emptyState('activity', 'No activity', 'Changes to this item appear here.')) + '</div>' });
}

async function applySavedView(viewId) {
  if (!viewId) { loadView(); return; }
  const view = await api(apiW('/projects/' + encodeURIComponent(currentProjectId()) + '/views/' + encodeURIComponent(viewId)));
  if (view && view.filters) {
    state.itemPriority = view.filters.priority || '';
    state.itemFilter = view.filters.overdue ? 'overdue' : 'all';
  }
  loadView();
  toast('Saved view applied.', 'success');
}

async function openFlagRules(key) {
  state.selectedFlag = key;
  const rules = await api(apiW('/flags/' + encodeURIComponent(key) + '/rules'));
  const rows = (rules || []).map(function (r) {
    return '<div class="list-row"><div class="list-row-main">' +
      '<div class="list-row-title mono">#' + String(r.position) + ' ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ ' + esc(String(r.value || 'on')) + '</div>' +
      '<div class="list-row-sub">' + esc(JSON.stringify(r.conditions || [])) + '</div></div>' +
      '<div class="list-row-side">' + statusBadge(r.enabled ? 'enabled' : 'disabled') + '</div></div>';
  }).join('');
  openModal({
    title: 'Flag rules ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â ' + key,
    sub: 'Ordered first-match-wins targeting rules from the real API.',
    body: '<div class="card-body">' + (rows || emptyState('layers', 'No rules', 'This flag always uses its default value.')) +
      '<form data-form="flag-rule-create" class="form-grid" style="margin-top:16px">' +
      field('attribute', 'Attribute', { required: true, placeholder: 'plan', value: 'plan' }) +
      field('op', 'Operator', { type: 'select', options: selectOptions(
        [['eq', 'equals'], ['ne', 'not equals'], ['in', 'in list'], ['gt', 'greater than'], ['contains', 'contains'], ['exists', 'exists']], 'eq') }) +
      field('value', 'Match value', { placeholder: '"pro" or ["pro","team"]', span: true }) +
      field('result', 'Return value', { value: 'on', placeholder: 'on' }) +
      '<div class="field"><button type="submit" class="btn">' + icon('plus', 14) + ' Add rule</button></div></form></div>',
  });
}

async function openFlagExposures(key) {
  const rows = await api(apiW('/flags/' + encodeURIComponent(key) + '/exposures'));
  const body = (rows || []).map(function (e) {
    return '<div class="list-row"><div class="list-row-main"><div class="list-row-title mono">' +
      esc(e.user_key) + '</div><div class="list-row-sub">' + esc(e.variant || 'default') + '</div></div>' +
      '<div class="list-row-side tiny muted">' + esc(fmtDate(e.created_at)) + '</div></div>';
  }).join('');
  openModal({
    title: 'Exposures ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â ' + key,
    sub: 'First assignment recorded per user, workspace-scoped and append-only.',
    body: '<div class="card-body">' + (body || emptyState('activity', 'No exposures', 'No evaluations have been recorded yet.')) + '</div>',
  });
}

async function openSdkPayload() {
  const payload = await api(apiW('/flags/sdk/payload?environment=' + encodeURIComponent(state.flagEnvironment)));
  openModal({
    title: 'SDK payload ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â ' + state.flagEnvironment,
    sub: 'The same configuration an embedded local SDK evaluates without an HTTP round trip.',
    body: '<div class="card-body"><textarea class="input mono" readonly rows="12">' +
      esc(JSON.stringify(payload, null, 2)) + '</textarea></div>',
  });
}

const EXPERIMENT_STATUSES = ['draft', 'running', 'stopped', 'completed'];

function experimentStatusOptions(current) {
  return EXPERIMENT_STATUSES.map(function (s) {
    return '<option value="' + s + '"' + (s === current ? ' selected' : '') + '>' + cap(s) + '</option>';
  }).join('');
}

function openCreateExperiment() {
  openModal({
    title: 'New experiment',
    sub: 'One workspace-scoped hypothesis with a measurable metric.',
    body: '<form data-form="experiment-create"><div class="form-grid">' +
      field('name', 'Name', { required: true, placeholder: 'Onboarding subject line', span: true }) +
      field('metric_name', 'Metric', { required: true, placeholder: 'activation_rate' }) +
      field('baseline', 'Baseline', { type: 'number', step: 'any', placeholder: '0.28' }) +
      field('target', 'Target', { type: 'number', step: 'any', placeholder: '0.35' }) +
      field('hypothesis', 'Hypothesis', { type: 'textarea', span: true,
        placeholder: 'A shorter subject line raises activation.' }) +
      '</div><div class="form-actions"><button type="button" class="btn" data-action="close-modal">Cancel</button>' +
      '<button type="submit" class="btn btn--primary">' + icon('plus', 15) + ' Create experiment</button></div></form>',
  });
}

function openEditExperiment(id) {
  const e = (state.caches.experiments || []).find(function (row) { return row.id === id; });
  if (!e) { toast('Experiment is no longer available. Refresh the page.', 'error'); return; }
  openModal({
    title: 'Edit experiment',
    sub: e.name,
    body: '<form data-form="experiment-edit"><input type="hidden" name="id" value="' + attr(e.id) + '">' +
      '<div class="form-grid">' +
      field('name', 'Name', { required: true, value: e.name, span: true }) +
      field('metric_name', 'Metric', { required: true, value: e.metric_name }) +
      field('baseline', 'Baseline', { type: 'number', step: 'any', value: e.baseline == null ? '' : e.baseline }) +
      field('target', 'Target', { type: 'number', step: 'any', value: e.target == null ? '' : e.target }) +
      field('hypothesis', 'Hypothesis', { type: 'textarea', value: e.hypothesis || '', span: true }) +
      '</div><div class="form-actions"><button type="button" class="btn" data-action="close-modal">Cancel</button>' +
      '<button type="submit" class="btn btn--primary">' + icon('check', 15) + ' Save changes</button></div></form>',
  });
}

function openExperimentStatus(id, status) {
  openModal({
    title: 'Change experiment status',
    sub: 'Every transition is recorded with its previous value.',
    body: '<form data-form="experiment-status"><input type="hidden" name="id" value="' + attr(id) + '">' +
      field('status', 'Status', { type: 'select', required: true,
        options: experimentStatusOptions(status), span: true }) +
      '<div class="form-actions"><button type="button" class="btn" data-action="close-modal">Cancel</button>' +
      '<button type="submit" class="btn btn--primary">' + icon('check', 15) + ' Change status</button></div></form>',
  });
}

async function openExperimentResults(id) {
  const known = (state.caches.experiments || []).find(function (e) { return e.id === id; });
  let rows = [];
  try { rows = await api(apiW('/analytics/' + encodeURIComponent(id) + '/results')) || []; }
  catch (err) { toast(errMessage(err), 'error'); return; }
  const listing = rows.length
    ? '<div class="table-wrap"><table class="data"><thead><tr><th>Variant</th><th>Impressions</th>' +
      '<th>Conversions</th><th>Rate</th></tr></thead><tbody>' +
      rows.map(function (r) {
        const rate = Number(r.impressions)
          ? (Number(r.conversions) / Number(r.impressions) * 100).toFixed(1) + '%' : 'ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â';
        return '<tr><td class="mono">' + esc(r.variant) + '</td><td>' + Number(r.impressions) + '</td>' +
          '<td>' + Number(r.conversions) + '</td><td>' + rate + '</td></tr>';
      }).join('') + '</tbody></table></div>'
    : emptyState('activity', 'No results yet', 'Record a variant result to see it here.');
  openModal({
    title: 'Experiment results',
    sub: (known && known.name) || 'Experiment',
    body: '<div class="stack">' + listing +
      (can(P.workspaceManage)
        ? '<form data-form="experiment-result"><input type="hidden" name="id" value="' + attr(id) + '">' +
          '<div class="form-grid">' +
          field('variant', 'Variant', { required: true, value: 'control' }) +
          field('impressions', 'Impressions', { required: true, type: 'number', min: '0', value: '0' }) +
          field('conversions', 'Conversions', { required: true, type: 'number', min: '0', value: '0' }) +
          '</div><div class="form-actions"><button type="submit" class="btn btn--primary">' +
          icon('plus', 14) + ' Record result</button></div></form>'
        : '') + '</div>',
  });
}

function openCreateWorkspace() {
  openModal({
    title: 'Create workspace',
    sub: 'You will own the new workspace and a new session is issued.',
    body: '<form data-form="create-workspace">' +
      field('name', 'Workspace name', { required: true, placeholder: 'Acme Inc.', span: true }) +
      '<div class="form-actions"><button type="button" class="btn" data-action="close-modal">Cancel</button>' +
      '<button type="submit" class="btn btn--primary">' + icon('plus', 15) + ' Create workspace</button></div></form>',
  });
}

function openAcceptInvite() {
  openModal({
    title: 'Accept invitation',
    sub: 'Use the single-use token shared by a workspace owner.',
    body: '<form data-form="accept-invite">' +
      field('token', 'Invitation token', { required: true, placeholder: 'Paste invitation token', span: true }) +
      '<div class="form-actions"><button type="button" class="btn" data-action="close-modal">Cancel</button>' +
      '<button type="submit" class="btn btn--primary">' + icon('check', 15) + ' Accept invitation</button></div></form>',
  });
}

function openSwitchWorkspace(id, name) {
  openModal({
    title: 'Switch workspace',
    sub: name + ' Ãƒâ€šÃ‚Â· confirm with your password',
    body: '<form data-form="switch-workspace"><input type="hidden" name="workspace_id" value="' + attr(id) + '">' +
      field('password', 'Password', { type: 'password', required: true, autocomplete: 'current-password', span: true }) +
      '<div class="form-actions"><button type="button" class="btn" data-action="close-modal">Cancel</button>' +
      '<button type="submit" class="btn btn--primary">' + icon('arrowRight', 15) + ' Switch</button></div></form>',
  });
}

async function openVerifyRequest() {
  try {
    const data = await api('/api/v1/auth/email/verify/request', { method: 'POST' });
    const dev = data && data.development_token ? '<div class="field"><label>Development token</label>' +
      '<input class="input mono" id="verify-dev-token" readonly value="' + attr(data.development_token) + '"></div>' : '';
    openModal({
      title: 'Verification token created',
      sub: 'No email is sent by the API.',
      body: '<p class="small muted">Paste the single-use token below to verify your email address.</p>' + dev +
        '<div class="form-actions"><button class="btn btn--primary" data-action="close-modal">Done</button></div>',
    });
  } catch (err) { toast(errMessage(err), 'error'); }
}

/* ------------------------------------------------------------------ *
 * Button actions
 * ------------------------------------------------------------------ */

async function logout() {
  try { await api('/api/v1/auth/logout', { method: 'POST', skipRefresh: true }); }
  catch (e) { /* local sign-out still completes */ }
  clearTokens();
  state.me = null;
  state.workspaces = [];
  state.workspaceError = '';
  state.caches = {
    contacts: [], leads: [], tasks: [], notifications: [], drafts: [], events: [], companies: [],
    agents: [], agentRuns: [], integrations: [], integrationCatalog: null,
  };
  closeModal();
  navigate('login');
  renderAuth('login');
  toast('Signed out. Local tokens were cleared.', 'success');
}

async function copyInvite(token) {
  try {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(token);
      toast('Invitation token copied.', 'success');
    } else {
      const input = document.getElementById('invite-token');
      if (input) input.select();
      toast('Select and copy the token manually.', 'error');
    }
  } catch (e) {
    toast('Copy is unavailable here ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â select the token manually.', 'error');
  }
}

async function processAction(action, el) {
  const id = el.dataset.id || '';
  switch (action) {
    case 'nav':
      document.body.classList.remove('sidebar-open');
      navigate(el.dataset.route);
      return;
    case 'toggle-sidebar': document.body.classList.toggle('sidebar-open'); return;
    case 'close-sidebar': document.body.classList.remove('sidebar-open'); return;
    case 'close-modal': closeModal(); return;
    case 'refresh-view': await loadView(); return;
    case 'logout': await logout(); return;
    case 'goto-contacts': closeModal(); navigate('contacts'); return;
    case 'create-contact': openCreateContact(); return;
    case 'edit-contact': await openEditContact(id); return;
    case 'create-company': openCreateCompany(); return;
    case 'create-lead': await openCreateLead(); return;
    case 'edit-lead': {
      const lead = (state.caches.leads || []).find(function (l) { return l.id === id; });
      if (!lead) { toast('Lead is no longer loaded. Refresh the list.', 'error'); return; }
      openEditLead(lead); return;
    }
    case 'create-task': await openCreateTask(); return;
    case 'record-intake': openIntake(); return;
    case 'invite-member': openInviteMember(); return;
    case 'suspend-member':
    case 'reactivate-member': {
      const nextStatus = action === 'suspend-member' ? 'suspended' : 'active';
      await api(apiW('/members/' + encodeURIComponent(el.dataset.userId || '')), {
        method: 'PATCH', body: { status: nextStatus },
      });
      await loadView();
      toast(nextStatus === 'suspended' ? 'Member suspended. Access is revoked on the next request.' :
        'Member reactivated.', 'success');
      return;
    }
    case 'consent-unsubscribe':
    case 'consent-resubscribe':
    case 'consent-dnc': {
      const links = await consentTokens(id);
      const route = action === 'consent-unsubscribe' ? 'unsubscribe'
        : (action === 'consent-resubscribe' ? 'resubscribe' : 'dnc');
      await api(apiW('/email/' + route), { method: 'POST', body: { token: links[route].token } });
      await loadView();
      toast('Consent updated locally. No email was sent.', 'success');
      return;
    }
    case 'consent-preferences': {
      const links = await consentTokens(id);
      const prefs = await api(apiW('/email/preferences') + '?token=' + encodeURIComponent(links.preferences.token));
      state.pendingConsent = { contactId: id, token: links.preferences.token };
      const box = function (channel, label, checked) {
        return '<label class="check"><input type="checkbox" name="channel_' + channel + '"' +
          (checked ? ' checked' : '') + '> ' + esc(label) + '</label>';
      };
      openModal({
        title: 'Email preferences',
        sub: prefs.email + (prefs.do_not_contact ? ' Ãƒâ€šÃ‚Â· global do-not-contact active' : ''),
        body: (prefs.do_not_contact
          ? governanceNote('Global do-not-contact is active. Resubscribe before changing channels.')
          : '<form data-form="consent-preferences"><div class="form-grid">' +
            box('email', 'Email updates', prefs.channels.email) +
            box('sms', 'SMS updates', prefs.channels.sms) +
            box('push', 'Push updates', prefs.channels.push) +
            '</div><div class="form-actions"><button type="button" class="btn" data-action="close-modal">Cancel</button>' +
            '<button type="submit" class="btn btn--primary">Save preferences</button></div></form>'),
      });
      return;
    }
    case 'create-workspace': openCreateWorkspace(); return;
    case 'toggle-flag': {
      const fkey = String(el.dataset.key || '');
      const enabled = el.dataset.enabled !== 'true';
      await api(apiW('/flags/' + encodeURIComponent(fkey)), { method: 'PATCH', body: { enabled: enabled } });
      toast(enabled ? 'Flag enabled.' : 'Flag disabled.', 'success');
      await loadView();
      return;
    }
    case 'api-key-rotate': {
      const keyId = String(el.dataset.id || '');
      const rotated = await api(apiW('/api-keys/' + encodeURIComponent(keyId) + '/rotate'), {
        method: 'POST', body: {},
      });
      showApiKeySecret(rotated, 'API key rotated', 'The previous secret is invalid immediately.');
      toast('API key rotated. The old secret is invalid.', 'success');
      return;
    }
    case 'api-key-revoke': {
      const keyId = String(el.dataset.id || '');
      openConfirm('Revoke this API key?',
        'Requests using it will fail immediately. This cannot be undone.',
        'Revoke key', async function () {
          await api(apiW('/api-keys/' + encodeURIComponent(keyId)), { method: 'DELETE' });
          await loadView();
          toast('API key revoked.', 'success');
        }, true);
      return;
    }
    case 'work-item-board': await openWorkItemBoard(); return;
    case 'work-item-labels': await openWorkItemLabels(); return;
    case 'work-item-modules': await openWorkItemModules(); return;
    case 'work-item-activity': await openWorkItemActivity(String(el.dataset.id || '')); return;
    case 'flag-rules': await openFlagRules(String(el.dataset.key || '')); return;
    case 'flag-exposures': await openFlagExposures(String(el.dataset.key || '')); return;
    case 'flag-sdk-payload': await openSdkPayload(); return;
    case 'experiment-create': openCreateExperiment(); return;
    case 'experiment-edit': openEditExperiment(id); return;
    case 'experiment-status': openExperimentStatus(id, el.dataset.status || 'draft'); return;
    case 'experiment-results': await openExperimentResults(id); return;
    case 'experiment-delete':
      openConfirm('Delete this experiment?',
        'The experiment and its recorded results are removed from this workspace. The audit event is kept.',
        'Delete experiment', async function () {
          await api(apiW('/analytics/' + encodeURIComponent(id)), { method: 'DELETE' });
          await loadView();
          toast('Experiment deleted.', 'success');
        }, true);
      return;
    case 'accept-invite': openAcceptInvite(); return;
    case 'switch-workspace': openSwitchWorkspace(id, el.dataset.name || 'workspace'); return;
    case 'verify-request': await openVerifyRequest(); return;
    case 'copy-invite': await copyInvite(el.dataset.token || ''); return;
    case 'open-contact': navigate('contacts/' + encodeURIComponent(id)); return;
    case 'contacts-prev':
      state.contactFilters.skip = Math.max(0, state.contactFilters.skip - state.contactFilters.limit);
      await refreshContactsTable(state.viewToken); return;
    case 'contacts-next':
      state.contactFilters.skip += state.contactFilters.limit;
      await refreshContactsTable(state.viewToken); return;

    case 'archive-contact':
      await api(apiW('/contacts/' + encodeURIComponent(id) + '/archive'), { method: 'POST' });
      await loadView(); toast('Contact archived.', 'success'); return;
    case 'restore-contact':
      await api(apiW('/contacts/' + encodeURIComponent(id) + '/restore'), { method: 'POST' });
      await loadView(); toast('Contact restored.', 'success'); return;
    case 'delete-contact':
      openConfirm('Delete contact permanently?',
        'The contact must be archived and have no dependent records. This cannot be undone.',
        'Delete contact', async function () {
          await api(apiW('/contacts/' + encodeURIComponent(id)), { method: 'DELETE' });
          navigate('contacts'); toast('Contact deleted.', 'success');
        }, true);
      return;

    case 'qualify-lead':
      await api(apiW('/leads/' + encodeURIComponent(id) + '/qualify'), { method: 'POST' });
      await loadView(); toast('Lead qualified.', 'success'); return;
    case 'convert-lead':
      await api(apiW('/leads/' + encodeURIComponent(id) + '/convert'), { method: 'POST' });
      await loadView(); toast('Lead converted; contact is now a customer.', 'success'); return;

    case 'complete-task':
      await api(apiW('/tasks/' + encodeURIComponent(id)), { method: 'PATCH', body: { status: 'done' } });
      await loadView(); toast('Task completed.', 'success'); return;
    case 'reopen-task':
      await api(apiW('/tasks/' + encodeURIComponent(id)), { method: 'PATCH', body: { status: 'open' } });
      await loadView(); toast('Task reopened.', 'success'); return;

    case 'open-notification-preferences': {
      const prefs = await api(apiW('/notification-preferences'));
      const prefRows = (prefs || []).map(function (p) {
        return '<tr><td>' + esc(cap(p.level)) + '</td><td>' + esc(p.target) + '</td>' +
          '<td>' + esc(cap(p.channel)) + '</td><td>' +
          '<span class="badge ' + (p.enabled ? 'badge--green' : 'badge--amber') + '">' +
          (p.enabled ? 'On' : 'Off') + '</span></td></tr>';
      }).join('');
      openModal({
        title: 'Notification preferences',
        sub: 'Per-channel and per-workflow settings. Saving never sends a message.',
        body: '<div class="table-wrap"><table class="data"><thead><tr>' +
          '<th>Level</th><th>Target</th><th>Channel</th><th>State</th></tr></thead><tbody>' +
          (prefRows || '<tr><td colspan="4" class="muted small">No preferences yet.</td></tr>') +
          '</tbody></table></div>' +
          '<form data-form="notification-preference-save"><div class="form-grid">' +
          field('level', 'Level', { type: 'select', options: selectOptions(
            [['global', 'Global'], ['workflow', 'Workflow'], ['channel', 'Channel']], 'global') }) +
          field('target', 'Target (workflow key)', { placeholder: '*' }) +
          field('channel', 'Channel', { type: 'select', options: selectOptions(
            [['in_app', 'In app'], ['email', 'Email'], ['sms', 'SMS'],
             ['push', 'Push'], ['chat', 'Chat']], 'email') }) +
          field('enabled', 'Enabled', { type: 'select', options: selectOptions(
            [['true', 'On'], ['false', 'Off']], 'true') }) +
          '</div><div class="form-actions"><button type="button" class="btn" data-action="close-modal">Cancel</button>' +
          '<button type="submit" class="btn btn--primary">Save preference</button></div></form>',
      });
      return;
    }
    case 'read-notification':
      await api(apiW('/notifications/' + encodeURIComponent(id) + '/read'), { method: 'POST' });
      await loadNotificationsSilently(); await loadView(); return;
    case 'read-all-notifications': {
      await api(apiW('/notifications/read-all'), { method: 'POST' });
      await loadNotificationsSilently(); await loadView();
      toast('All notifications marked read.', 'success');
      return;
    }
    case 'approve-draft':
      await api(apiW('/outreach-drafts/' + encodeURIComponent(id) + '/approve'), { method: 'POST' });
      await loadView(); toast('Draft approved. Nothing was sent externally.', 'success'); return;

    case 'create-agent': openCreateAgent(); return;
    case 'edit-agent': {
      const agent = (state.caches.agents || []).find(function (a) { return a.id === id; });
      if (!agent) { toast('Agent is no longer loaded. Refresh the list.', 'error'); return; }
      openEditAgent(agent);
      return;
    }
    case 'agent-status':
      await api(apiW('/agents/' + encodeURIComponent(id) + '/status'), {
        method: 'POST', body: { status: el.dataset.status },
      });
      await loadView();
      toast(el.dataset.status === 'paused' ? 'Agent paused.' : 'Agent resumed.', 'success');
      return;
    case 'delete-agent':
      openConfirm('Delete this agent?',
        'Runs are kept for audit. An agent with runs cannot be deleted.',
        'Delete agent', async function () {
          await api(apiW('/agents/' + encodeURIComponent(id)), { method: 'DELETE' });
          await loadView();
          toast('Agent deleted.', 'success');
        }, true);
      return;
    case 'request-agent-run': {
      const agent = (state.caches.agents || []).find(function (a) { return a.id === id; });
      if (!agent) { toast('Agent is no longer loaded. Refresh the list.', 'error'); return; }
      openAgentRun(agent);
      return;
    }
    case 'agent-progress': {
      const agent = (state.caches.agents || []).find(function (a) { return a.id === el.dataset.agent; });
      const run = (state.caches.agentRuns || []).find(function (r) { return r.id === id; });
      if (!agent || !run) { toast('Run is no longer loaded. Refresh the list.', 'error'); return; }
      openAgentProgress(agent, run);
      return;
    }
    case 'approve-agent-run':
      await api(apiW('/agents/' + encodeURIComponent(el.dataset.agent || '') +
        '/runs/' + encodeURIComponent(id) + '/approve'), { method: 'POST' });
      await loadView();
      toast('Run approved. Nothing was sent externally.', 'success');
      return;
    case 'configure-integration': {
      const provider = el.dataset.provider || '';
      const catalog = (state.caches.integrationCatalog && state.caches.integrationCatalog.providers) || [];
      const entry = catalog.find(function (p) { return p.provider === provider; });
      if (!entry) { toast('Provider is no longer loaded. Refresh the list.', 'error'); return; }
      const row = (state.caches.integrations || []).find(function (r) { return r.provider === provider; });
      openConfigureIntegration(entry, row);
      return;
    }
    case 'disable-integration':
      await api(apiW('/integrations/' + encodeURIComponent(el.dataset.provider || '') + '/disable'), {
        method: 'POST',
      });
      await loadView();
      toast('Integration disabled. No outbound network call was made.', 'success');
      return;

    case 'job-run': {
      const result = await api(apiW('/jobs/run'), { method: 'POST', body: { limit: 10 } });
      await loadView();
      toast('Worker claimed ' + result.claimed + ' job(s): ' + result.succeeded +
        ' succeeded, ' + result.retried + ' retried, ' + result.dead_lettered + ' dead-lettered.', 'success');
      return;
    }
    case 'job-recover': {
      const result = await api(apiW('/jobs/recover'), { method: 'POST' });
      await loadView();
      toast(result.recovered + ' stale job(s) returned to the queue.', 'success');
      return;
    }
    case 'job-cancel':
      await api(apiW('/jobs/' + encodeURIComponent(id) + '/cancel'), { method: 'POST' });
      await loadView();
      toast('Job cancelled.', 'success');
      return;
    case 'job-retry':
      await api(apiW('/jobs/' + encodeURIComponent(id) + '/retry'), { method: 'POST' });
      await loadView();
      toast('Job re-queued for another attempt.', 'success');
      return;
    case 'adapter-test': {
      const provider = el.dataset.provider || '';
      const result = await api(apiW('/adapters/' + encodeURIComponent(provider) + '/invoke'), {
        method: 'POST', body: { operation: 'test', request: {} },
      });
      await loadView();
      if (result.status === 'recorded') {
        toast('Local mock recorded for ' + provider + '. Nothing was sent externally.', 'success');
      } else {
        toast('Call rejected (' + result.status + '). ' + (result.response && result.response.note ? result.response.note : 'No outbound call was made.'), 'error');
      }
      return;
    }

    case 'search-open': {
      const host = document.getElementById('search-results-host');
      if (host) host.innerHTML = '';
      const kind = el.dataset.kind;
      const hint = el.dataset.hint || '';
      if (kind === 'contact') navigate('contacts/' + encodeURIComponent(id));
      else if (kind === 'note') {
        const match = hint.match(/^\/contacts\/([^/]+)/);
        navigate(match ? 'contacts/' + encodeURIComponent(match[1]) : 'contacts');
      }
      else if (kind === 'lead') navigate('leads');
      else if (kind === 'company') navigate('companies');
      else if (kind === 'task') navigate('tasks');
      else if (kind === 'outreach_draft') navigate('drafts');
      else if (kind === 'ticket') navigate('inbox/' + encodeURIComponent(id));
      else if (kind === 'project' || kind === 'project_item') {
        const match = hint.match(/^\/projects\/([^/]+)/);
        navigate(match ? 'projects/' + encodeURIComponent(match[1]) : 'projects');
      }
      else navigate('dashboard');
      return;
    }
    case 'search-all': {
      const input = document.getElementById('global-search');
      state.searchQuery = input ? input.value.trim() : '';
      const host = document.getElementById('search-results-host');
      if (host) host.innerHTML = '';
      navigate('search');
      return;
    }
    case 'open-ticket': navigate('inbox/' + encodeURIComponent(id)); return;
    case 'view-project': navigate('projects/' + encodeURIComponent(id)); return;
    case 'toggle-project-default-assignee':
    case 'toggle-project-subscribed': {
      const parts = currentRoute().split('/');
      const key = action === 'toggle-project-default-assignee' ? 'is_default_assignee' : 'subscribed';
      const body = {}; body[key] = el.dataset.on === 'true';
      await api(apiW('/projects/' + encodeURIComponent(parts[1] || '') +
        '/members/' + encodeURIComponent(el.dataset.uid)), { method: 'PATCH', body: body });
      await loadView();
      toast(key === 'is_default_assignee' ? 'Default assignee updated.' : 'Subscription updated.', 'success');
      return;
    }
    case 'remove-project-member': {
      const parts = currentRoute().split('/');
      await api(apiW('/projects/' + encodeURIComponent(parts[1] || '') +
        '/members/' + encodeURIComponent(el.dataset.uid)), { method: 'DELETE' });
      await loadView();
      toast('Project member removed.', 'success');
      return;
    }
    case 'view-document': navigate('documents/' + encodeURIComponent(id)); return;
    case 'create-room':
      openModal({
        title: 'New data room',
        sub: 'A workspace-scoped container for document metadata. No file is uploaded.',
        body: '<form data-form="create-room"><div class="form-grid">' +
          field('name', 'Room name', { required: true, span: true, placeholder: 'Board pack' }) +
          field('description', 'Description', { type: 'textarea', span: true, placeholder: 'Optional' }) +
          '</div><div class="form-actions"><button type="button" class="btn" data-action="close-modal">Cancel</button>' +
          '<button type="submit" class="btn btn--primary">' + icon('plus', 15) + ' Create room</button></div></form>',
      });
      return;
    case 'create-document': {
      let rooms = [];
      try { rooms = await api(apiW('/documents/rooms')); } catch (e) { /* empty options */ }
      const roomOptions = [['', 'Unfiled']].concat(rooms.map(function (r) { return [r.id, r.name]; }));
      openModal({
        title: 'Add document record',
        sub: 'Register metadata and an opaque storage reference. NOVARA never opens the file.',
        body: '<form data-form="create-document"><div class="form-grid">' +
          field('title', 'Title', { required: true, span: true, placeholder: 'Proposal.pdf' }) +
          field('storage_path', 'Storage reference', {
            required: true, span: true, placeholder: 'metadata://local/proposal.pdf',
            hint: 'An opaque reference chosen by you; it is never fetched by NOVARA.',
          }) +
          field('doc_type', 'Type', {
            type: 'select', options: selectOptions(
              [['pdf', 'PDF'], ['doc', 'Document'], ['sheet', 'Spreadsheet'], ['deck', 'Deck'], ['other', 'Other']], 'pdf'),
          }) +
          field('size_bytes', 'Size (bytes)', { type: 'number', value: '0', min: '0' }) +
          field('room_id', 'Data room', { type: 'select', options: selectOptions(roomOptions, '') }) +
          '</div><div class="form-actions"><button type="button" class="btn" data-action="close-modal">Cancel</button>' +
          '<button type="submit" class="btn btn--primary">' + icon('plus', 15) + ' Add document</button></div></form>',
      });
      return;
    }
    case 'create-watermark-preview':
      openModal({
        title: 'Per-view watermark preview',
        sub: 'A unique, attributed overlay is generated for this viewer at preview time. The stored document is not changed.',
        body: '<form data-form="create-watermark-preview" data-document-id="' + attr(id) + '"><div class="form-grid">' +
          field('viewer_email', 'Viewer email', { required: true, span: true, type: 'email', placeholder: 'reviewer@example.com' }) +
          field('viewer_name', 'Viewer name', { span: true, placeholder: 'Optional' }) +
          '</div><div class="form-actions"><button type="button" class="btn" data-action="close-modal">Cancel</button>' +
          '<button type="submit" class="btn btn--primary">' + icon('eye', 15) + ' Generate preview</button></div></form>',
      });
      return;
    case 'create-document-link':
      openModal({
        title: 'New share link',
        sub: 'Policy is enforced when a view or download is recorded. Nothing is sent externally.',
        body: '<form data-form="create-document-link" data-document-id="' + attr(id) + '"><div class="form-grid">' +
          field('password', 'Password (optional)', { type: 'password', placeholder: 'Leave blank for no password' }) +
          field('expires_in_hours', 'Expires in hours', { type: 'number', min: '1', placeholder: 'Optional' }) +
          field('max_views', 'Maximum views', { type: 'number', min: '1', placeholder: 'Optional' }) +
          checkboxField('view_only', 'View only', true, 'Visitors can view metadata but not edit it.') +
          checkboxField('download_allowed', 'Allow recorded downloads', false,
            'Records a download event; encrypted blobs use their own security API.') +
          '</div><div class="form-actions"><button type="button" class="btn" data-action="close-modal">Cancel</button>' +
          '<button type="submit" class="btn btn--primary">' + icon('plus', 15) + ' Create link</button></div></form>',
      });
      return;
    case 'revoke-document-link':
      await api(apiW('/documents/links/' + encodeURIComponent(id) + '/revoke'), { method: 'POST' });
      await loadView();
      toast('Share link revoked.', 'success');
      return;
    case 'copy-document-token': await copyDocumentToken(el.dataset.token || ''); return;
    case 'create-project': {
      openModal({
        title: 'New project',
        sub: 'A workspace-scoped container for delivery work. No external service is contacted.',
        body: '<form data-form="create-project"><div class="form-grid">' +
          field('name', 'Project name', { required: true, span: true, placeholder: 'Q4 rollout' }) +
          field('description', 'Description', { type: 'textarea', span: true, placeholder: 'Optional' }) +
          field('status', 'Status', {
            type: 'select', options: selectOptions(
              [['planning', 'Planning'], ['active', 'Active'], ['on_hold', 'On hold'], ['completed', 'Completed']], 'planning'),
          }) +
          field('due_at', 'Due date', { type: 'date' }) +
          checkboxField('restricted', 'Private project', false,
            'Only listed project members can see or change this project. You become its lead.') +
          '</div><div class="form-actions"><button type="button" class="btn" data-action="close-modal">Cancel</button>' +
          '<button type="submit" class="btn btn--primary">' + icon('plus', 15) + ' Create project</button></div></form>',
      });
      return;
    }
    case 'create-work-item': {
      let states = [];
      let assignees = [];
      try {
        const [stateResult, assigneeResult] = await Promise.all([
          api(apiW('/projects/states')), api(apiW('/projects/assignees')),
        ]);
        states = stateResult || [];
        assignees = assigneeResult || [];
      } catch (e) { /* forms fall back to built-in states */ }
      const active = states.filter(function (s) { return s.is_active; });
      const statusOptions = active.length
        ? active.map(function (s) { return [s.name, cap(s.name) + ' Ãƒâ€šÃ‚Â· ' + cap(s.group)]; })
        : builtinItemStates();
      openModal({
        title: 'New work item',
        sub: 'State, assignee and due date are stored in this workspace only.',
        body: '<form data-form="create-work-item" data-project-id="' + attr(id) + '"><div class="form-grid">' +
          field('title', 'Title', { required: true, span: true, placeholder: 'What needs doing?' }) +
          field('status', 'State', { type: 'select', options: selectOptions(statusOptions, statusOptions[0][0]) }) +
          field('assignee_id', 'Assignee', {
            type: 'select', options: selectOptions(
              [['', 'Unassigned']].concat(assignees.map(function (a) {
                return [a.id, a.display_name || a.email];
              })), ''),
          }) +
          field('due_at', 'Due date', { type: 'date' }) +
          '</div><div class="form-actions"><button type="button" class="btn" data-action="close-modal">Cancel</button>' +
          '<button type="submit" class="btn btn--primary">' + icon('plus', 15) + ' Add work item</button></div></form>',
      });
      return;
    }
    case 'toggle-project-state': {
      await api(apiW('/projects/states/' + encodeURIComponent(id)), {
        method: 'PATCH', body: { is_active: el.dataset.active !== 'true' },
      });
      await loadView();
      toast('State updated.', 'success');
      return;
    }
    case 'support-teams': await openSupportTeams(); return;
    case 'support-inboxes': await openSupportInboxes(); return;
    case 'support-labels': await openSupportLabels(); return;
    case 'support-routing': await openSupportRouting(); return;
    case 'support-segments': await openSupportSegments(); return;
    case 'support-replies': await openSupportReplies(); return;
    case 'support-help': await openSupportHelp(); return;
    case 'support-reports': await openSupportReports(); return;
    case 'insert-saved-reply': {
      const replies = await api(apiW('/tickets/saved-replies'));
      const rows = (replies || []).map(function (reply) {
        return '<button type="button" class="list-row" data-action="expand-saved-reply" ' +
          'data-reply-id="' + attr(reply.id) + '" data-ticket-id="' +
          attr(el.dataset.ticketId || '') + '"' +
          (el.dataset.contactId ? ' data-contact-id="' + attr(el.dataset.contactId) + '"' : '') +
          '><div class="list-row-main"><div class="list-row-title">' + esc(reply.name) + '</div>' +
          '<div class="list-row-sub">' + esc(String(reply.body || '').slice(0, 120)) + '</div>' +
          '</div></button>';
      }).join('');
      openModal({
        title: 'Insert saved reply',
        sub: 'Expansion is local. The text is placed in the draft only; press Add reply to record it.',
        body: '<div class="card-body">' + (rows || emptyState('note', 'No saved replies',
          'Create a saved reply in Support operations first.')) + '</div>',
      });
      return;
    }
    case 'expand-saved-reply': {
      const payload = { ticket_id: el.dataset.ticketId || '' };
      if (el.dataset.contactId) payload.contact_id = el.dataset.contactId;
      const expanded = await api(apiW('/tickets/saved-replies/' +
        encodeURIComponent(el.dataset.replyId) + '/expand'), {
        method: 'POST', body: payload,
      });
      const unresolved = expanded.unresolved || [];
      applyExpandedReply(expanded.body || '', unresolved);
      state.pendingExpandedReply.ticketId = payload.ticket_id;
      closeModal();
      toast((unresolved.length
        ? 'Saved reply inserted; unresolved variables: ' + unresolved.join(', ')
        : 'Saved reply inserted into the draft.') + ' Nothing was sent.', 'success');
      return;
    }
    case 'back-to-inbox': navigate('inbox'); return;
    case 'ticket-set-status': {
      await api(apiW('/tickets/' + encodeURIComponent(id)), {
        method: 'PATCH', body: { status: el.dataset.status },
      });
      await loadView();
      toast('Ticket status updated.', 'success');
      return;
    }
    case 'identify-customer': {
      openModal({
        title: 'Identify visitor',
        sub: 'Capture the email before the conversation. An existing CRM contact is reused, never duplicated.',
        body: '<form data-form="identify-customer"><div class="form-grid">' +
          field('email', 'Email', { type: 'email', required: true, span: true, placeholder: 'visitor@example.com' }) +
          field('full_name', 'Full name', { placeholder: 'Optional' }) +
          field('company_name', 'Company', { placeholder: 'Optional' }) +
          '</div><div class="form-actions"><button type="button" class="btn" data-action="close-modal">Cancel</button>' +
          '<button type="submit" class="btn btn--primary">' + icon('user', 15) + ' Identify</button></div></form>',
      });
      return;
    }
    case 'create-ticket': {
      const contacts = state.caches.contacts || [];
      openModal({
        title: 'New ticket',
        sub: 'Start a shared support conversation. Nothing is sent externally.',
        body: '<form data-form="create-ticket"><div class="form-grid">' +
          field('subject', 'Subject', { required: true, placeholder: 'Issue summary', span: true }) +
          field('body', 'Details', { type: 'textarea', required: true, span: true, placeholder: 'What happened?' }) +
          field('contact_id', 'Linked contact', {
            type: 'select', span: true,
            options: selectOptions([['', 'No contact linked']].concat(contacts.map(function (c) {
              return [c.id, c.full_name || c.email];
            })), ''),
          }) +
          field('priority', 'Priority', {
            type: 'select', options: selectOptions(
              [['low', 'Low'], ['normal', 'Normal'], ['high', 'High'], ['urgent', 'Urgent']], 'normal'),
          }) +
          field('origin_channel', 'Origin', {
            type: 'select', options: selectOptions(
              [['local', 'Local'], ['web_form', 'Web form'], ['email', 'Email'], ['import', 'Import']], 'local'),
          }) +
          field('conversation_type', 'Type', {
            type: 'select', options: selectOptions(
              [['question', 'Question'], ['incident', 'Incident'], ['billing', 'Billing'], ['feedback', 'Feedback']], 'question'),
          }) +
          '</div><div class="form-actions"><button type="button" class="btn" data-action="close-modal">Cancel</button>' +
          '<button type="submit" class="btn btn--primary">' + icon('plus', 15) + ' Create ticket</button></div></form>',
      });
      return;
    }
    case 'open-campaign': navigate('campaigns/' + encodeURIComponent(id)); return;
    case 'back-to-campaigns': navigate('campaigns'); return;
    case 'campaign-set-status': {
      await api(apiW('/campaigns/' + encodeURIComponent(id)), {
        method: 'PATCH', body: { status: el.dataset.status },
      });
      await loadView();
      toast('Campaign status updated.', 'success');
      return;
    }
    case 'campaign-run-journey': {
      await api(apiW('/campaigns/' + encodeURIComponent(id) + '/run'), { method: 'POST' });
      await loadView();
      toast('Journey advanced one local step. Nothing was sent.', 'success');
      return;
    }
    case 'campaign-record-engagement': {
      await api(apiW('/campaigns/' + encodeURIComponent(id) + '/engagement'), {
        method: 'POST', body: { contact_id: el.dataset.contact, kind: el.dataset.kind },
      });
      await loadView();
      toast('Local engagement recorded.', 'success');
      return;
    }
    case 'campaign-exit-enrollment': {
      await api(apiW('/campaigns/' + encodeURIComponent(id) + '/enrollments/' +
        encodeURIComponent(el.dataset.contact)), { method: 'DELETE' });
      await loadView();
      toast('Contact exited the journey.', 'success');
      return;
    }
    case 'create-campaign': {
      openModal({
        title: 'New campaign',
        sub: 'Record a campaign and its goal. No emails or ads are sent by this build.',
        body: '<form data-form="create-campaign"><div class="form-grid">' +
          field('name', 'Campaign name', { required: true, placeholder: 'Spring product launch', span: true }) +
          field('channel', 'Channel', {
            type: 'select', options: selectOptions(optionList(CAMPAIGN_CHANNELS), 'email'),
          }) +
          field('goal', 'Goal', { placeholder: 'e.g. 200 qualified leads', span: true }) +
          '</div><div class="form-actions"><button type="button" class="btn" data-action="close-modal">Cancel</button>' +
          '<button type="submit" class="btn btn--primary">' + icon('plus', 15) + ' Create campaign</button></div></form>',
      });
      return;
    }
    case 'open-deal': navigate('deals/' + encodeURIComponent(id)); return;
    case 'back-to-deals': navigate('deals'); return;
    case 'deal-set-stage': {
      await api(apiW('/deals/' + encodeURIComponent(id)), {
        method: 'PATCH', body: { stage: el.dataset.stage },
      });
      await loadView();
      toast('Deal stage updated.', 'success');
      return;
    }
    case 'create-deal': {
      let contacts = [];
      try { contacts = await api(apiW('/contacts') + '?limit=100') || []; } catch (e) { contacts = []; }
      openModal({
        title: 'New deal',
        sub: 'Track an opportunity in this workspace. No outreach is sent.',
        body: '<form data-form="create-deal"><div class="form-grid">' +
          field('title', 'Deal title', { required: true, placeholder: 'Annual licence', span: true }) +
          field('company', 'Company', { placeholder: 'Optional company name' }) +
          field('value', 'Value', { type: 'number', min: 0, value: '0' }) +
          field('contact_id', 'Linked contact', {
            type: 'select', span: true,
            options: selectOptions([['', 'No contact linked']].concat(contacts.map(function (c) {
              return [c.id, c.full_name || c.email];
            })), ''),
          }) +
          field('stage', 'Stage', { type: 'select', options: selectOptions(optionList(DEAL_STAGES), 'new') }) +
          field('probability', 'Probability %', { type: 'number', min: 0, value: '0' }) +
          '</div><div class="form-actions"><button type="button" class="btn" data-action="close-modal">Cancel</button>' +
          '<button type="submit" class="btn btn--primary">' + icon('plus', 15) + ' Create deal</button></div></form>',
      });
      return;
    }
    case 'open-survey': navigate('surveys/' + encodeURIComponent(id)); return;
    case 'back-to-surveys': navigate('surveys'); return;
    case 'survey-from-template': {
      openModal({
        title: 'New survey from template',
        sub: 'Creates a local survey with typed questions. Nothing is distributed.',
        body: '<form data-form="create-survey-from-template"><div class="form-grid">' +
          field('name', 'Survey name', { required: true, placeholder: 'Quarterly feedback', span: true }) +
          field('template', 'Template', {
            type: 'select',
            options: selectOptions([
              ['nps', 'Net Promoter Score'], ['csat', 'Customer Satisfaction'],
              ['ces', 'Customer Effort Score'], ['best_practice', 'Best-practice feedback'],
              ['contact_form', 'Contact Form'], ['docs_feedback', 'Docs Feedback'],
              ['feature_chaser', 'Feature Chaser'], ['feedback_box', 'Feedback Box'],
              ['improve_email_content', 'Improve Email Content'], ['app_interview_prompt', 'App Interview Prompt'],
              ['churn_survey', 'Churn Survey'], ['product_market_fit', 'Product-Market Fit Survey'],
              ['quiz_time', 'Quiz Time'], ['improve_trial_conversion', 'Improve Trial Conversion'],
              ['panel_management', 'Panel Management'], ['collect_google_reviews', 'Collect Google Reviews'],
            ], 'nps'),
          }) +
          '</div><div class="form-actions"><button type="button" class="btn" data-action="close-modal">Cancel</button>' +
          '<button type="submit" class="btn btn--primary">' + icon('plus', 15) + ' Create from template</button></div></form>',
      });
      return;
    }
    case 'survey-status':
      await api(apiW('/surveys/' + encodeURIComponent(id)), {
        method: 'PATCH', body: { status: el.dataset.status },
      });
      await loadView();
      toast('Survey status updated.', 'success');
      return;
    case 'answer-finish':
      await api(apiW('/feedback/answers/' + encodeURIComponent(id)), {
        method: 'PATCH', body: { partial: false },
      });
      await loadView();
      toast('Answer marked finished.', 'success');
      return;
    case 'answer-delete':
      await api(apiW('/feedback/answers/' + encodeURIComponent(id)), { method: 'DELETE' });
      await loadView();
      toast('Answer deleted.', 'success');
      return;
    case 'answers-export': {
      const result = await api(apiW('/feedback/surveys/' + encodeURIComponent(id) + '/answers/export'));
      openModal({ title: 'Exported answers', sub: result.rows + ' rows, CSV',
        body: '<pre class="small">' + esc(result.csv) + '</pre>' });
      return;
    }
    case 'create-notification-workflow':
      openModal({
        title: 'New notification workflow',
        sub: 'One stable, workspace-scoped workflow definition. No channel delivery is claimed.',
        body: '<form data-form="create-notification-workflow"><div class="form-grid">' +
          field('key', 'Key', { required: true, placeholder: 'order-updates', span: true }) +
          field('name', 'Name', { required: true, placeholder: 'Order updates' }) +
          field('channel', 'Channel', { type: 'select', options: selectOptions(
            [['in_app', 'In-app'], ['email', 'Email'], ['sms', 'SMS'], ['push', 'Push'], ['chat', 'Chat']]) }) +
          field('severity', 'Severity', { type: 'select', options: selectOptions(
            [['info', 'Info'], ['warning', 'Warning'], ['critical', 'Critical']]) }) +
          field('tags', 'Tags (comma separated)', { placeholder: 'billing, lifecycle', span: true }) +
          '</div><div class="form-actions"><button type="button" class="btn" data-action="close-modal">Cancel</button>' +
          '<button type="submit" class="btn btn--primary">' + icon('plus', 15) + ' Create workflow</button></div></form>',
      });
      return;
    case 'instantiate-notification-template':
      openModal({
        title: 'Instantiate a workflow template',
        sub: 'Clean-room templates create real workflow definitions from stored presets.',
        body: '<form data-form="instantiate-notification-template"><div class="form-grid">' +
          field('key', 'Template', { type: 'select', options: selectOptions(
            [['welcome', 'Welcome sequence'], ['security-alert', 'Security alert'],
             ['invoice-ready', 'Invoice ready'], ['weekly-digest', 'Weekly digest']]) }) +
          field('name', 'Workflow name', { placeholder: 'Optional override', span: true }) +
          '</div><div class="form-actions"><button type="submit" class="btn btn--primary">' +
          icon('check', 15) + ' Instantiate locally</button></div></form>',
      });
      return;
    case 'trigger-notification-workflow':
      openModal({
        title: 'Trigger workflow locally',
        sub: 'Records a message in this workspace. Rich HTML is sanitised; routes must be in-app.',
        body: '<form data-form="trigger-notification-workflow" data-workflow-id="' + attr(id) + '">' +
          '<div class="form-grid">' +
          field('title', 'Title', { required: true, value: 'Notification', span: true }) +
          field('html', 'Rich content', { type: 'textarea', value: '<b>Hello</b>' }) +
          field('action_url', 'Action route', { value: '#/notifications' }) +
          '</div><div class="form-actions"><button type="submit" class="btn btn--primary">' +
          icon('bell', 15) + ' Record trigger</button></div></form>',
      });
      return;
    case 'evaluate-notification-digest':
      openModal({
        title: 'Evaluate digest window',
        sub: 'Fires one digest per workflow and window, even with zero or many events.',
        body: '<form data-form="evaluate-notification-digest" data-workflow-id="' + attr(id) + '">' +
          '<div class="form-grid">' +
          field('window_key', 'Window key', { required: true, placeholder: '2026-11-23', span: true }) +
          field('title', 'Digest title', { value: 'Your digest' }) +
          '</div><div class="form-actions"><button type="submit" class="btn btn--primary">' +
          icon('check', 15) + ' Evaluate digest</button></div></form>',
      });
      return;
    case 'create-notification-feed':
      openModal({
        title: 'New notification feed',
        sub: 'Messages can be assigned to a feed and filtered by it.',
        body: '<form data-form="create-notification-feed"><div class="form-grid">' +
          field('key', 'Key', { required: true, placeholder: 'alerts' }) +
          field('name', 'Name', { required: true, placeholder: 'Alerts' }) +
          '</div><div class="form-actions"><button type="submit" class="btn btn--primary">' +
          icon('plus', 15) + ' Create feed</button></div></form>',
      });
      return;
    case 'create-notification-context':
      openModal({
        title: 'New notification context',
        sub: 'Exact-match context key that isolates Inbox and preference state.',
        body: '<form data-form="create-notification-context"><div class="form-grid">' +
          field('key', 'Key', { required: true, placeholder: 'tenant-a' }) +
          field('name', 'Name', { required: true, placeholder: 'Tenant A' }) +
          '</div><div class="form-actions"><button type="submit" class="btn btn--primary">' +
          icon('plus', 15) + ' Create context</button></div></form>',
      });
      return;
    case 'create-notification-layout':
      openModal({
        title: 'New notification layout',
        sub: 'Use {{content}} as the content slot. All markup is sanitised and attributes are removed.',
        body: '<form data-form="create-notification-layout"><div class="form-grid">' +
          field('key', 'Key', { required: true, placeholder: 'brand' }) +
          field('name', 'Name', { required: true, placeholder: 'Brand layout' }) +
          field('body', 'Layout HTML', { type: 'textarea', required: true,
            value: '<section class="brand">{{content}}</section>', span: true }) +
          '</div><div class="form-actions"><button type="submit" class="btn btn--primary">' +
          icon('plus', 15) + ' Create layout</button></div></form>',
      });
      return;
    case 'create-notification-webhook':
      openModal({
        title: 'New webhook endpoint',
        sub: 'Only loopback hosts and relative /api/ paths are accepted. Deliveries are signed records.',
        body: '<form data-form="create-notification-webhook"><div class="form-grid">' +
          field('name', 'Name', { required: true, placeholder: 'local-sink' }) +
          field('url', 'URL', { required: true, placeholder: '/api/hooks/local', span: true }) +
          field('event_types', 'Event types (comma separated)', { placeholder: 'workflow.created' }) +
          '</div><div class="form-actions"><button type="submit" class="btn btn--primary">' +
          icon('plus', 15) + ' Create endpoint</button></div></form>',
      });
      return;
    case 'create-feedback-dataset':
      openModal({
        title: 'New feedback dataset',
        sub: 'A local container for related feedback records and sources.',
        body: '<form data-form="create-feedback-dataset"><div class="form-grid">' +
          field('key', 'Key', { required: true, placeholder: 'customer-feedback' }) +
          field('name', 'Name', { required: true, placeholder: 'Customer feedback' }) +
          field('description', 'Description', { type: 'textarea', span: true }) +
          '</div><div class="form-actions"><button type="button" class="btn" data-action="close-modal">Cancel</button>' +
          '<button type="submit" class="btn btn--primary">' + icon('plus', 15) + ' Create dataset</button></div></form>',
      });
      return;
    case 'create-feedback-field':
      openModal({
        title: 'New reusable field',
        sub: 'Declare a field once; bind it to surveys and change it in one place.',
        body: '<form data-form="create-feedback-field"><div class="form-grid">' +
          field('key', 'Key', { required: true, placeholder: 'nps_score' }) +
          field('label', 'Label', { required: true, placeholder: 'How likely are you to recommend us?' }) +
          field('type', 'Type', { type: 'select', options: selectOptions([
            ['short_text', 'Short text'], ['long_text', 'Long text'], ['single_choice', 'Single choice'],
            ['multi_choice', 'Multi choice'], ['rating', 'Rating'], ['nps', 'NPS'],
            ['csat', 'CSAT'], ['number', 'Number'], ['date', 'Date'], ['email', 'Email'],
          ]) }) + '</div><div class="form-actions"><button type="submit" class="btn btn--primary">' +
          icon('plus', 15) + ' Create field</button></div></form>',
      });
      return;
    case 'create-feedback-segment':
      openModal({
        title: 'New audience segment',
        sub: 'Rules evaluate real workspace contact attributes and custom fields.',
        body: '<form data-form="create-feedback-segment"><div class="form-grid">' +
          field('key', 'Key', { required: true, placeholder: 'power-users' }) +
          field('name', 'Name', { required: true, placeholder: 'Power users' }) +
          field('rules_json', 'Rules JSON', { type: 'textarea', span: true,
            value: '[{"field":"plan","op":"eq","value":"pro"}]' }) +
          '</div><div class="form-actions"><button type="submit" class="btn btn--primary">' +
          icon('plus', 15) + ' Create segment</button></div></form>',
      });
      return;
    case 'create-feedback-dashboard':
      openModal({
        title: 'New feedback dashboard',
        sub: 'Widgets are computed from persisted records, not static values.',
        body: '<form data-form="create-feedback-dashboard"><div class="form-grid">' +
          field('key', 'Key', { required: true, placeholder: 'overview' }) +
          field('name', 'Name', { required: true, placeholder: 'Feedback overview' }) +
          '</div><div class="form-actions"><button type="submit" class="btn btn--primary">' +
          icon('plus', 15) + ' Create dashboard</button></div></form>',
      });
      return;
    case 'create-feedback-source':
      openModal({
        title: 'New feedback source',
        sub: 'Sources route incoming feedback into this dataset.',
        body: '<form data-form="create-feedback-source" data-dataset-id="' + attr(id) + '">' +
          '<div class="form-grid">' +
          field('key', 'Key', { required: true, placeholder: 'web-form' }) +
          field('name', 'Name', { required: true, placeholder: 'Website form' }) +
          field('source_type', 'Source type', { type: 'select', options: selectOptions([
            ['web', 'Web'], ['email', 'Email'], ['survey', 'Survey'], ['chat', 'Chat'],
            ['api', 'API'], ['import', 'Import'], ['support', 'Support'], ['interview', 'Interview'],
          ]) }) + '</div><div class="form-actions"><button type="submit" class="btn btn--primary">' +
          icon('plus', 15) + ' Create source</button></div></form>',
      });
      return;
    case 'ingest-feedback':
      openModal({
        title: 'Ingest one feedback record',
        sub: 'Stores the record locally with reserved fields and respondent metadata.',
        body: '<form data-form="ingest-feedback" data-dataset-id="' + attr(id) + '">' +
          '<div class="form-grid">' +
          field('text', 'Feedback text', { type: 'textarea', required: true, span: true,
            value: 'I love the new experience' }) +
          field('page', 'Page', { placeholder: '/pricing' }) +
          field('respondent', 'Respondent id', { placeholder: 'alice' }) +
          '</div><div class="form-actions"><button type="submit" class="btn btn--primary">' +
          icon('plus', 15) + ' Ingest locally</button></div></form>',
      });
      return;
    case 'view-feedback-records': {
      const rows = await api(apiW('/feedback-intelligence/datasets/' + encodeURIComponent(id) + '/records'));
      openModal({ title: 'Feedback records', sub: rows.length + ' stored records',
        body: rows.length
          ? '<div class="table-wrap"><table class="data"><thead><tr><th>Text</th><th>Sentiment</th>' +
            '<th>Respondent</th></tr></thead><tbody>' + rows.map(function (r) {
              return '<tr><td>' + esc(String((r.payload || {}).text || '')) + '</td><td>' +
                esc(r.sentiment) + '</td><td class="small">' + esc(r.respondent_hash.slice(0, 12)) +
                '</td></tr>';
            }).join('') + '</tbody></table></div>'
          : '<p class="muted small">No records yet.</p>' });
      return;
    }
    case 'view-feedback-dashboard': {
      const result = await api(apiW('/feedback-intelligence/dashboards/' + encodeURIComponent(id) + '/data'));
      openModal({ title: 'Dashboard data', sub: 'Computed live from ' + result.source_record_count + ' records',
        body: '<pre class="small">' + esc(JSON.stringify(result.widgets, null, 2)) + '</pre>' });
      return;
    }
    case 'create-experiment-metric':
      openModal({
        title: 'New experiment metric',
        sub: 'A typed definition used by the local statistics engines.',
        body: '<form data-form="create-experiment-metric"><div class="form-grid">' +
          field('key', 'Key', { required: true, placeholder: 'signup_rate' }) +
          field('name', 'Name', { required: true, placeholder: 'Signup rate' }) +
          field('type', 'Type', { type: 'select', options: selectOptions([
            ['proportion', 'Proportion'], ['mean', 'Mean'], ['ratio', 'Ratio'],
          ]) }) + '</div><div class="form-actions"><button type="button" class="btn" ' +
          'data-action="close-modal">Cancel</button><button type="submit" class="btn btn--primary">' +
          icon('plus', 15) + ' Create metric</button></div></form>',
      });
      return;
    case 'create-experiment-definition':
      openModal({
        title: 'New experiment',
        sub: 'Variants and traffic shares are validated before anything is stored.',
        body: '<form data-form="create-experiment-definition"><div class="form-grid">' +
          field('key', 'Key', { required: true, placeholder: 'checkout_redesign' }) +
          field('name', 'Name', { required: true, placeholder: 'Checkout redesign' }) +
          field('variants_json', 'Variants JSON', { type: 'textarea', span: true,
            value: '[{"key":"control","traffic_share":0.5},{"key":"variant","traffic_share":0.5}]' }) +
          '</div><div class="form-actions"><button type="button" class="btn" ' +
          'data-action="close-modal">Cancel</button><button type="submit" class="btn btn--primary">' +
          icon('plus', 15) + ' Create experiment</button></div></form>',
      });
      return;
    case 'record-experiment-observation': {
      const metrics = await api(apiW('/experiment-stats/metrics'));
      const experiments = await api(apiW('/experiment-stats/experiments'));
      const experiment = experiments.find(function (e) { return e.id === id; }) || experiments[0];
      const variants = experiment ? experiment.variants.map(function (v) { return [v.key, v.key]; }) : [];
      openModal({
        title: 'Record observation',
        sub: experiment ? 'For ' + esc(experiment.name) : 'Create an experiment first',
        body: '<form data-form="record-experiment-observation" data-experiment-id="' + attr(id) + '">' +
          '<div class="form-grid">' +
          field('metric_id', 'Metric', { type: 'select', options: selectOptions(
            metrics.map(function (m) { return [m.id, m.name + ' (' + m.type + ')']; })) }) +
          field('variant', 'Variant', { type: 'select', options: selectOptions(variants) }) +
          field('sessions', 'Sessions', { type: 'number', min: 0, value: '1000' }) +
          field('conversions', 'Conversions', { type: 'number', min: 0, value: '100' }) +
          field('value_sum', 'Value sum (mean metrics)', { type: 'number', step: 'any', value: '0' }) +
          field('value_sq_sum', 'Value square sum', { type: 'number', step: 'any', value: '0' }) +
          '</div><div class="form-actions"><button type="button" class="btn" ' +
          'data-action="close-modal">Cancel</button><button type="submit" class="btn btn--primary">' +
          icon('plus', 15) + ' Store observation</button></div></form>',
      });
      return;
    }
    case 'analyze-experiment': {
      const metrics = await api(apiW('/experiment-stats/metrics'));
      openModal({
        title: 'Analyze experiment',
        sub: 'Runs a local statistics engine over stored observations.',
        body: '<form data-form="analyze-experiment" data-experiment-id="' + attr(id) + '">' +
          '<div class="form-grid">' +
          field('metric_id', 'Metric', { type: 'select', options: selectOptions(
            metrics.map(function (m) { return [m.id, m.name + ' (' + m.type + ')']; })) }) +
          field('engine', 'Engine', { type: 'select', options: selectOptions([
            ['frequentist', 'Frequentist (p-value, CI)'], ['bayesian', 'Bayesian (P(B>A), loss)'],
          ]) }) + '</div><div class="form-actions"><button type="button" class="btn" ' +
          'data-action="close-modal">Cancel</button><button type="submit" class="btn btn--primary">' +
          icon('activity', 15) + ' Run analysis</button></div></form>',
      });
      return;
    }
    case 'check-experiment-srm': {
      const result = await api(apiW('/experiment-stats/experiments/' + encodeURIComponent(id) + '/srm'),
        { method: 'POST' });
      openModal({ title: 'Sample ratio mismatch',
        sub: result.srm_detected ? 'SRM DETECTED (p < 0.001)' : 'No SRM detected',
        body: '<pre class="small">' + esc(JSON.stringify(result, null, 2)) + '</pre>' });
      return;
    }
    case 'check-experiment-health': {
      const result = await api(apiW('/experiment-stats/experiments/' + encodeURIComponent(id) + '/health'),
        { method: 'POST' });
      openModal({ title: 'Result health check',
        sub: result.healthy ? 'No health issues' : 'Issues detected',
        body: '<pre class="small">' + esc(JSON.stringify(result.diagnostics, null, 2)) + '</pre>' });
      return;
    }
    case 'run-power-analysis':
      openModal({
        title: 'Power analysis',
        sub: 'Estimates sample size or minimum detectable effect locally.',
        body: '<form data-form="run-power-analysis"><div class="form-grid">' +
          field('baseline_rate', 'Baseline rate', { type: 'number', step: 'any', min: 0.001, value: '0.1' }) +
          field('mde', 'Minimum detectable effect', { type: 'number', step: 'any', value: '0.02' }) +
          field('sample_size', 'Sample size (optional)', { type: 'number', min: 2, value: '' }) +
          field('alpha', 'Alpha', { type: 'number', step: 'any', value: '0.05' }) +
          field('power', 'Power', { type: 'number', step: 'any', value: '0.8' }) +
          '</div><div class="form-actions"><button type="button" class="btn" ' +
          'data-action="close-modal">Cancel</button><button type="submit" class="btn btn--primary">' +
          icon('activity', 15) + ' Calculate</button></div></form>',
      });
      return;
    case 'run-correction':
      openModal({
        title: 'Multiple-testing correction',
        sub: 'Bonferroni and Benjamini-Hochberg adjustments over a list of p-values.',
        body: '<form data-form="run-correction"><div class="form-grid">' +
          field('p_values', 'P-values (comma separated)', { span: true, value: '0.01, 0.04, 0.03, 0.2' }) +
          field('alpha', 'Alpha', { type: 'number', step: 'any', value: '0.05' }) +
          '</div><div class="form-actions"><button type="button" class="btn" ' +
          'data-action="close-modal">Cancel</button><button type="submit" class="btn btn--primary">' +
          icon('filter', 15) + ' Correct</button></div></form>',
      });
      return;
    case 'create-experiment-project':
      openModal({
        title: 'New experiment project',
        sub: 'Namespaces flags, experiments and settings inside this workspace.',
        body: '<form data-form="create-experiment-project"><div class="form-grid">' +
          field('key', 'Key', { required: true, placeholder: 'web-app' }) +
          field('name', 'Name', { required: true, placeholder: 'Web app' }) +
          field('description', 'Description', { type: 'textarea', span: true }) +
          '</div><div class="form-actions"><button type="button" class="btn" ' +
          'data-action="close-modal">Cancel</button><button type="submit" class="btn btn--primary">' +
          icon('plus', 15) + ' Create project</button></div></form>',
      });
      return;
    case 'archive-experiment-project':
      await api(apiW('/experiment-ops/projects/' + encodeURIComponent(id) + '/archive'),
        { method: 'POST' });
      toast('Project archived.', 'success');
      navigate('experiment-ops');
      return;
    case 'create-saved-group': {
      const projects = await api(apiW('/experiment-ops/projects'));
      openModal({
        title: 'New saved group',
        sub: 'A reusable, locally evaluated targeting list.',
        body: '<form data-form="create-saved-group" data-project-id="' + attr(id) + '">' +
          '<div class="form-grid">' +
          field('project_id', 'Project', { type: 'select', required: true, options: selectOptions(
            projects.map(function (p) { return [p.id, p.name]; }), id) }) +
          field('key', 'Key', { required: true, placeholder: 'pro-users' }) +
          field('name', 'Name', { required: true, placeholder: 'Pro users' }) +
          field('conditions_json', 'Conditions JSON', { type: 'textarea', span: true,
            value: '[{"attribute":"plan","op":"eq","value":"pro"}]' }) +
          '</div><div class="form-actions"><button type="button" class="btn" ' +
          'data-action="close-modal">Cancel</button><button type="submit" class="btn btn--primary">' +
          icon('plus', 15) + ' Create group</button></div></form>',
      });
      return;
    }
    case 'create-experiment-dimension':
      openModal({
        title: 'New dimension',
        sub: 'Break experiment results down by a user attribute.',
        body: '<form data-form="create-experiment-dimension"><div class="form-grid">' +
          field('key', 'Key', { required: true, placeholder: 'browser' }) +
          field('name', 'Name', { required: true, placeholder: 'Browser' }) +
          field('attribute', 'Attribute', { required: true, placeholder: 'browser' }) +
          field('values_json', 'Values JSON', { type: 'textarea', span: true,
            value: '["chrome","firefox"]' }) +
          '</div><div class="form-actions"><button type="button" class="btn" ' +
          'data-action="close-modal">Cancel</button><button type="submit" class="btn btn--primary">' +
          icon('plus', 15) + ' Create dimension</button></div></form>',
      });
      return;
    case 'create-experiment-segment':
      openModal({
        title: 'New segment',
        sub: 'A reusable audience slice defined by attribute rules.',
        body: '<form data-form="create-experiment-segment"><div class="form-grid">' +
          field('key', 'Key', { required: true, placeholder: 'power-users' }) +
          field('name', 'Name', { required: true, placeholder: 'Power users' }) +
          field('rules_json', 'Rules JSON', { type: 'textarea', span: true,
            value: '[{"attribute":"plan","op":"eq","value":"pro"}]' }) +
          '</div><div class="form-actions"><button type="button" class="btn" ' +
          'data-action="close-modal">Cancel</button><button type="submit" class="btn btn--primary">' +
          icon('plus', 15) + ' Create segment</button></div></form>',
      });
      return;
    case 'view-flag-history': {
      const result = await api(apiW('/experiment-ops/flags/' + encodeURIComponent(id) + '/history'));
      openModal({ title: 'Flag history', sub: result.revisions.length + ' revisions',
        body: '<pre class="small">' + esc(JSON.stringify(result, null, 2)) + '</pre>' });
      return;
    }
    case 'create-flag-revision':
      openModal({
        title: 'New draft revision',
        sub: 'The flag is unchanged until this revision is published.',
        body: '<form data-form="create-flag-revision" data-flag-id="' + attr(id) + '">' +
          '<div class="form-grid">' +
          field('definition_json', 'Definition JSON', { type: 'textarea', span: true,
            value: '{"enabled":true,"rollout_percent":50,"description":"local rollout"}' }) +
          '</div><div class="form-actions"><button type="button" class="btn" ' +
          'data-action="close-modal">Cancel</button><button type="submit" class="btn btn--primary">' +
          icon('plus', 15) + ' Create draft</button></div></form>',
      });
      return;
    case 'publish-flag-revision':
      await api(apiW('/experiment-ops/revisions/' + encodeURIComponent(id) + '/activate'),
        { method: 'POST' });
      toast('Revision published; flag definition applied.', 'success');
      navigate('experiment-ops');
      return;
    case 'archive-flag':
      openModal({
        title: 'Archive flag',
        sub: 'Archived flags are disabled immediately and surfaced as stale candidates.',
        body: '<form data-form="archive-flag" data-flag-id="' + attr(id) + '"><div class="form-grid">' +
          field('reason', 'Reason', { type: 'textarea', span: true, placeholder: 'superseded' }) +
          '</div><div class="form-actions"><button type="button" class="btn" ' +
          'data-action="close-modal">Cancel</button><button type="submit" class="btn btn--primary">' +
          'Archive</button></div></form>',
      });
      return;
    case 'diagnose-flag':
      openModal({
        title: 'Diagnose evaluation',
        sub: 'See which local rule produced a value for a user.',
        body: '<form data-form="diagnose-flag" data-flag-id="' + attr(id) + '">' +
          '<div class="form-grid">' +
          field('user_key', 'User key', { required: true, value: 'alice' }) +
          field('attributes_json', 'Attributes JSON', { type: 'textarea', span: true,
            value: '{"plan":"pro"}' }) +
          field('environment', 'Environment', { value: 'production' }) +
          '</div><div class="form-actions"><button type="button" class="btn" ' +
          'data-action="close-modal">Cancel</button><button type="submit" class="btn btn--primary">' +
          icon('activity', 15) + ' Diagnose</button></div></form>',
      });
      return;
    case 'create-aa-test': {
      const projects = await api(apiW('/experiment-ops/projects'));
      openModal({
        title: 'New A/A test',
        sub: 'Identical variants validate assignment and metric plumbing.',
        body: '<form data-form="create-aa-test"><div class="form-grid">' +
          field('project_id', 'Project', { type: 'select', options: selectOptions(
            projects.map(function (p) { return [p.id, p.name]; })) }) +
          field('key', 'Key', { required: true, placeholder: 'aa-checkout' }) +
          field('name', 'Name', { required: true, placeholder: 'A/A checkout' }) +
          '</div><div class="form-actions"><button type="button" class="btn" ' +
          'data-action="close-modal">Cancel</button><button type="submit" class="btn btn--primary">' +
          icon('plus', 15) + ' Create A/A test</button></div></form>',
      });
      return;
    }
    case 'view-aa-result': {
      const result = await api(apiW('/experiment-ops/aa-tests/' + encodeURIComponent(id) + '/result'));
      openModal({ title: 'A/A result', sub: result.passed ? 'Plumbing validated' : 'Imbalance detected',
        body: '<pre class="small">' + esc(JSON.stringify(result, null, 2)) + '</pre>' });
      return;
    }
    case 'create-timeseries-point':
      openModal({
        title: 'Record time series point',
        sub: 'Points aggregate into a cumulative impact series.',
        body: '<form data-form="create-timeseries-point"><div class="form-grid">' +
          field('experiment_key', 'Experiment key', { required: true, value: 'checkout' }) +
          field('metric_key', 'Metric key', { required: true, value: 'conversion' }) +
          field('day', 'Day', { required: true, placeholder: '2026-11-23' }) +
          field('sessions', 'Sessions', { type: 'number', min: 0, value: '100' }) +
          field('conversions', 'Conversions', { type: 'number', min: 0, value: '10' }) +
          '</div><div class="form-actions"><button type="button" class="btn" ' +
          'data-action="close-modal">Cancel</button><button type="submit" class="btn btn--primary">' +
          icon('plus', 15) + ' Store point</button></div></form>',
      });
      return;
    case 'view-timeseries':
      openModal({
        title: 'View time series',
        sub: 'Cumulative impact by day.',
        body: '<form data-form="view-timeseries"><div class="form-grid">' +
          field('experiment_key', 'Experiment key', { required: true, value: 'checkout' }) +
          '</div><div class="form-actions"><button type="button" class="btn" ' +
          'data-action="close-modal">Cancel</button><button type="submit" class="btn btn--primary">' +
          icon('activity', 15) + ' Load series</button></div></form>',
      });
      return;
    case 'view-stale-flags': {
      const result = await api(apiW('/experiment-ops/stale-flags'));
      openModal({ title: 'Stale flag candidates', sub: result.count + ' flags flagged',
        body: result.count
          ? '<div class="table-wrap"><table class="data"><thead><tr><th>Flag</th><th>Reasons</th>' +
            '</tr></thead><tbody>' + result.flags.map(function (f) {
              return '<tr><td class="mono">' + esc(f.key) + '</td><td class="small">' +
                esc(f.reasons.join(', ')) + '</td></tr>';
            }).join('') + '</tbody></table></div>'
          : '<p class="muted small">No stale flags detected.</p>' });
      return;
    }
    case 'create-query-fact-table': {
      const contract = await api(apiW('/experiment-queries/api-contract'));
      openModal({
        title: 'New local fact table',
        sub: 'Describes one workspace-scoped row set for discovery queries. No warehouse access.',
        body: '<form data-form="create-query-fact-table"><div class="form-grid">' +
          field('key', 'Key', { required: true, placeholder: 'observations-facts' }) +
          field('name', 'Name', { required: true, placeholder: 'Observations' }) +
          field('source', 'Source', { type: 'select', options: selectOptions(
            (contract.fact_sources || []).map(function (s) { return [s, s]; })) }) +
          field('fields_json', 'Fields (JSON array)', { type: 'textarea', span: true,
            value: '["variant", "sessions", "conversions"]' }) +
          '</div><div class="form-actions"><button type="button" class="btn" ' +
          'data-action="close-modal">Cancel</button><button type="submit" class="btn btn--primary">' +
          icon('plus', 15) + ' Create fact table</button></div></form>',
      });
      return;
    }
    case 'preview-query-fact-table': {
      const result = await api(apiW('/experiment-queries/fact-tables/' + encodeURIComponent(id) + '/preview'));
      openModal({ title: 'Fact table preview', sub: result.source + ' Ã‚Â· ' + result.rows.length + ' rows',
        body: '<pre class="small">' + esc(JSON.stringify(result, null, 2)) + '</pre>' });
      return;
    }
    case 'create-discovery-query': {
      const facts = await api(apiW('/experiment-queries/fact-tables'));
      openModal({
        title: 'New discovery query',
        sub: 'Filters and projects the local fact table you select.',
        body: '<form data-form="create-discovery-query"><div class="form-grid">' +
          field('key', 'Key', { required: true, placeholder: 'control-facts' }) +
          field('name', 'Name', { required: true, placeholder: 'Control facts' }) +
          field('fact_table_id', 'Fact table', { type: 'select', options: selectOptions(
            (facts || []).map(function (f) { return [f.id, f.name]; })) }) +
          field('fields_json', 'Fields (JSON array)', { type: 'textarea', span: true,
            value: '["variant", "sessions", "conversions"]' }) +
          field('filters_json', 'Filters (JSON array)', { type: 'textarea', span: true,
            value: '[{"field":"variant","op":"eq","value":"control"}]' }) +
          field('limit', 'Limit', { type: 'number', min: 1, value: '100' }) +
          '</div><div class="form-actions"><button type="button" class="btn" ' +
          'data-action="close-modal">Cancel</button><button type="submit" class="btn btn--primary">' +
          icon('plus', 15) + ' Create query</button></div></form>',
      });
      return;
    }
    case 'run-discovery-query': {
      const result = await api(apiW('/experiment-queries/discovery-queries/' + encodeURIComponent(id) + '/run'),
        { method: 'POST', body: {} });
      openModal({ title: 'Discovery result', sub: result.count + ' matching local rows',
        body: '<pre class="small">' + esc(JSON.stringify(result, null, 2)) + '</pre>' });
      return;
    }
    case 'create-assignment-query':
      openModal({
        title: 'New assignment query',
        sub: 'Identifies exposed units from local assignment and exposure rows.',
        body: '<form data-form="create-assignment-query"><div class="form-grid">' +
          field('key', 'Key', { required: true, placeholder: 'exposed-units' }) +
          field('name', 'Name', { required: true, placeholder: 'Exposed units' }) +
          field('experiment_key', 'Experiment key', { required: true, value: 'checkout' }) +
          field('source', 'Source', { type: 'select', options: selectOptions([
            ['both', 'Assignments and exposures'], ['assignments', 'Assignments only'],
            ['exposures', 'Exposures only'],
          ]) }) +
          field('filters_json', 'Filters (JSON array)', { type: 'textarea', span: true,
            value: '[]' }) +
          '</div><div class="form-actions"><button type="button" class="btn" ' +
          'data-action="close-modal">Cancel</button><button type="submit" class="btn btn--primary">' +
          icon('plus', 15) + ' Create query</button></div></form>',
      });
      return;
    case 'run-assignment-query': {
      const result = await api(apiW('/experiment-queries/assignment-queries/' + encodeURIComponent(id) + '/run'),
        { method: 'POST', body: {} });
      openModal({ title: 'Assignment result', sub: result.count + ' local units',
        body: '<pre class="small">' + esc(JSON.stringify(result, null, 2)) + '</pre>' });
      return;
    }
    case 'create-identifier-type':
      openModal({
        title: 'New identifier type',
        sub: 'Configures how one local unit identifier is normalised and validated.',
        body: '<form data-form="create-identifier-type"><div class="form-grid">' +
          field('key', 'Key', { required: true, placeholder: 'user-id' }) +
          field('name', 'Name', { required: true, placeholder: 'User id' }) +
          field('attribute', 'Attribute', { required: true, placeholder: 'user_id' }) +
          field('pattern', 'Pattern (regex, optional)', { placeholder: '[a-z0-9]+' }) +
          field('normalization', 'Normalisation', { type: 'select', options: selectOptions([
            ['lower', 'Lower case'], ['strip', 'Trim'], ['strip_lower', 'Trim and lower case'],
            ['none', 'None'],
          ]) }) +
          '</div><div class="form-actions"><button type="button" class="btn" ' +
          'data-action="close-modal">Cancel</button><button type="submit" class="btn btn--primary">' +
          icon('plus', 15) + ' Create identifier type</button></div></form>',
      });
      return;
    case 'normalize-identifier': {
      const result = await api(apiW('/experiment-queries/identifier-types/' + encodeURIComponent(id) + '/normalize'),
        { method: 'POST', body: { value: String(el.dataset.value || '') } });
      openModal({ title: 'Identifier normalised', sub: result.valid ? 'Valid local identifier' : 'Invalid identifier',
        body: '<pre class="small">' + esc(JSON.stringify(result, null, 2)) + '</pre>' });
      return;
    }
    case 'create-identifier-join': {
      const types = await api(apiW('/experiment-queries/identifier-types'));
      const opts = selectOptions((types || []).map(function (t) { return [t.id, t.name]; }));
      openModal({
        title: 'New identifier join',
        sub: 'Maps one local identifier type to another inside this workspace.',
        body: '<form data-form="create-identifier-join"><div class="form-grid">' +
          field('key', 'Key', { required: true, placeholder: 'user-email' }) +
          field('name', 'Name', { required: true, placeholder: 'User to email' }) +
          field('left_type_id', 'Left type', { type: 'select', options: opts }) +
          field('right_type_id', 'Right type', { type: 'select', options: opts }) +
          field('mappings_json', 'Mappings (JSON array)', { type: 'textarea', span: true,
            value: '[{"left":"u1","right":"u1@example.com"}]' }) +
          '</div><div class="form-actions"><button type="button" class="btn" ' +
          'data-action="close-modal">Cancel</button><button type="submit" class="btn btn--primary">' +
          icon('plus', 15) + ' Create join</button></div></form>',
      });
      return;
    }
    case 'resolve-identifier-join': {
      openModal({
        title: 'Resolve identifier join',
        sub: 'Look up a mapped identifier in local data.',
        body: '<form data-form="resolve-identifier-join" data-join-id="' + attr(id) + '"><div class="form-grid">' +
          field('value', 'Value', { required: true, placeholder: 'u1' }) +
          field('direction', 'Direction', { type: 'select', options: selectOptions([
            ['left_to_right', 'Left to right'], ['right_to_left', 'Right to left'],
          ]) }) +
          '</div><div class="form-actions"><button type="button" class="btn" ' +
          'data-action="close-modal">Cancel</button><button type="submit" class="btn btn--primary">' +
          icon('search', 15) + ' Resolve</button></div></form>',
      });
      return;
    }
    case 'create-experiment-funnel':
      openModal({
        title: 'New experiment funnel',
        sub: 'Steps must be an ordered prefix of assigned, exposed and converted.',
        body: '<form data-form="create-experiment-funnel"><div class="form-grid">' +
          field('key', 'Key', { required: true, placeholder: 'checkout-funnel' }) +
          field('name', 'Name', { required: true, placeholder: 'Checkout funnel' }) +
          field('experiment_key', 'Experiment key', { required: true, value: 'checkout' }) +
          field('steps_json', 'Steps (JSON array)', { type: 'textarea', span: true,
            value: '["assigned", "exposed", "converted"]' }) +
          '</div><div class="form-actions"><button type="button" class="btn" ' +
          'data-action="close-modal">Cancel</button><button type="submit" class="btn btn--primary">' +
          icon('plus', 15) + ' Create funnel</button></div></form>',
      });
      return;
    case 'view-experiment-funnel': {
      const result = await api(apiW('/experiment-queries/funnels/' + encodeURIComponent(id) + '/result'));
      openModal({ title: 'Funnel result', sub: result.overall_conversion + '% overall conversion',
        body: '<pre class="small">' + esc(JSON.stringify(result, null, 2)) + '</pre>' });
      return;
    }
    case 'create-experiment-report':
      openModal({
        title: 'New local experiment report',
        sub: 'Summarises this workspace\'s own experiment rows. No external platform is contacted.',
        body: '<form data-form="create-experiment-report"><div class="form-grid">' +
          field('key', 'Key', { required: true, placeholder: 'experiment-summary' }) +
          field('name', 'Name', { required: true, placeholder: 'Experiment summary' }) +
          field('report_type', 'Report type', { type: 'select', options: selectOptions([
            ['experiment_summary', 'Experiment summary'],
            ['timeseries_summary', 'Time series summary'],
            ['funnel_summary', 'Funnel summary'],
          ]) }) +
          field('config_json', 'Config (JSON object)', { type: 'textarea', span: true,
            value: '{"experiment_key":"checkout"}' }) +
          '</div><div class="form-actions"><button type="button" class="btn" ' +
          'data-action="close-modal">Cancel</button><button type="submit" class="btn btn--primary">' +
          icon('plus', 15) + ' Create report</button></div></form>',
      });
      return;
    case 'run-experiment-report': {
      const result = await api(apiW('/experiment-queries/reports/' + encodeURIComponent(id) + '/run'),
        { method: 'POST', body: {} });
      openModal({ title: result.name || 'Report result', sub: 'Computed from local rows',
        body: '<pre class="small">' + esc(JSON.stringify(result, null, 2)) + '</pre>' });
      return;
    }
    case 'assess-carryover':
      openModal({
        title: 'Assess carryover risk',
        sub: 'Warns when a restart may carry learning between variants.',
        body: '<form data-form="assess-carryover"><div class="form-grid">' +
          field('key', 'Key', { required: true, placeholder: 'checkout-restart' }) +
          field('experiment_key', 'Experiment key', { required: true, value: 'checkout' }) +
          field('previous_end', 'Previous end', { required: true, placeholder: '2026-11-01' }) +
          field('restart', 'Restart date', { required: true, placeholder: '2026-11-23' }) +
          field('washout_days', 'Washout days', { type: 'number', min: 0, value: '7' }) +
          '</div><div class="form-actions"><button type="button" class="btn" ' +
          'data-action="close-modal">Cancel</button><button type="submit" class="btn btn--primary">' +
          icon('activity', 15) + ' Assess</button></div></form>',
      });
      return;
    case 'acknowledge-carryover':
      await api(apiW('/experiment-queries/carryover/' + encodeURIComponent(id) + '/acknowledge'),
        { method: 'POST', body: {} });
      await loadView();
      toast('Carryover guidance acknowledged.', 'success');
      return;
    case 'view-experiment-openapi': {
      const result = await api(apiW('/experiment-platform/openapi-status'));
      openModal({ title: 'Generated API contract', sub: result.operation_count + ' live operations',
        body: '<pre class="small">' + esc(JSON.stringify(result, null, 2)) + '</pre>' });
      return;
    }
    case 'bind-experiment-role': {
      const [members, roles] = await Promise.all([
        api(apiW('/members')), api(apiW('/experiment-platform/roles')),
      ]);
      openModal({
        title: 'Bind experimentation role',
        sub: 'Workspace-scoped overlay; it never grants external access.',
        body: '<form data-form="bind-experiment-role"><div class="form-grid">' +
          field('user_id', 'Workspace member', { type: 'select', options: selectOptions(
            (members || []).map(function (m) {
              return [m.user_id || m.id, m.display_name || m.email || m.user_id || m.id];
            })) }) +
          field('role', 'Role', { type: 'select', options: selectOptions(
            (roles || []).map(function (r) { return [r.role, r.role]; })) }) +
          '</div><div class="form-actions"><button type="button" class="btn" ' +
          'data-action="close-modal">Cancel</button><button type="submit" class="btn btn--primary">' +
          icon('check', 15) + ' Bind role</button></div></form>',
      });
      return;
    }
    case 'check-experiment-role': {
      const roles = await api(apiW('/experiment-platform/roles'));
      openModal({
        title: 'Check role permission',
        sub: 'Evaluates a permission against a default experimentation role.',
        body: '<form data-form="check-experiment-role"><div class="form-grid">' +
          field('role', 'Role', { type: 'select', options: selectOptions(
            (roles || []).map(function (r) { return [r.role, r.role]; })) }) +
          field('permission', 'Permission', { required: true, placeholder: 'contact:read', value: 'contact:read' }) +
          '</div><div class="form-actions"><button type="button" class="btn" ' +
          'data-action="close-modal">Cancel</button><button type="submit" class="btn btn--primary">' +
          icon('search', 15) + ' Check</button></div></form>',
      });
      return;
    }
    case 'view-delivery-contract': {
      const result = await api(apiW('/experiment-delivery/api-contract'));
      openModal({ title: 'Local delivery contract', sub: 'external_calls: ' + !!result.external_calls,
        body: '<pre class="small">' + esc(JSON.stringify(result, null, 2)) + '</pre>' });
      return;
    }
    case 'create-delivery-webhook': {
      openModal({
        title: 'New delivery webhook',
        sub: 'Recorded locally; no URL is contacted.',
        body: '<form data-form="create-delivery-webhook"><div class="form-grid">' +
          field('key', 'Key', { required: true, placeholder: 'event-hook' }) +
          field('name', 'Name', { required: true, placeholder: 'Experiment events' }) +
          field('scope', 'Scope', { type: 'select', options: selectOptions([
            ['event', 'event'], ['sdk', 'sdk'], ['global_sdk', 'global_sdk'],
          ]) }) +
          field('event_types', 'Event types (comma separated)', { placeholder: 'flag.updated' }) +
          field('target_label', 'Target label', { value: 'local', required: true }) +
          '</div><div class="form-actions"><button type="button" class="btn" ' +
          'data-action="close-modal">Cancel</button><button type="submit" class="btn btn--primary">' +
          icon('plus', 15) + ' Create webhook</button></div></form>',
      });
      return;
    }
    case 'emit-delivery-webhook': {
      const hooks = await api(apiW('/experiment-delivery/webhooks'));
      const hook = (hooks || []).find(function (w) { return w.id === id; }) || {};
      openModal({
        title: 'Emit local delivery',
        sub: 'Scope ' + (hook.scope || '') + ' Ã‚Â· recorded only, never sent.',
        body: '<form data-form="emit-delivery-webhook" data-id="' + attr(id) + '"><div class="form-grid">' +
          field('event_type', 'Event type', { required: true,
            value: (hook.event_types || [])[0] || 'payload.changed' }) +
          field('payload', 'Payload (JSON)', { span: true, value: '{}' }) +
          '</div><div class="form-actions"><button type="button" class="btn" ' +
          'data-action="close-modal">Cancel</button><button type="submit" class="btn btn--primary">' +
          icon('activity', 15) + ' Record delivery</button></div></form>',
      });
      return;
    }
    case 'purge-delivery-cache': {
      openModal({
        title: 'Purge local cache',
        sub: 'Marks local cache entries as purged; no CDN is called.',
        body: '<form data-form="purge-delivery-cache"><div class="form-grid">' +
          field('prefix', 'Key prefix', { required: true, placeholder: 'sdk:payload:' }) +
          field('reason', 'Reason', { required: true, placeholder: 'local flag change' }) +
          '</div><div class="form-actions"><button type="button" class="btn" ' +
          'data-action="close-modal">Cancel</button><button type="submit" class="btn btn--primary">' +
          icon('check', 15) + ' Purge</button></div></form>',
      });
      return;
    }
    case 'schedule-refresh-job': {
      openModal({
        title: 'Schedule local refresh',
        sub: 'A durable local job; no external scheduler is used.',
        body: '<form data-form="schedule-refresh-job"><div class="form-grid">' +
          field('key', 'Key', { required: true, placeholder: 'nightly-results' }) +
          field('job_type', 'Type', { type: 'select', options: selectOptions([
            ['experiment_results', 'experiment_results'], ['metric', 'metric'],
          ]) }) +
          field('target_key', 'Target key', { required: true, placeholder: 'checkout' }) +
          '</div><div class="form-actions"><button type="button" class="btn" ' +
          'data-action="close-modal">Cancel</button><button type="submit" class="btn btn--primary">' +
          icon('plus', 15) + ' Schedule</button></div></form>',
      });
      return;
    }
    case 'run-refresh-job': {
      const result = await api(apiW('/experiment-delivery/refresh-jobs/' + encodeURIComponent(id) + '/run'),
        { method: 'POST', body: {} });
      await loadView();
      toast('Refresh completed (' + result.status + ').', 'success');
      return;
    }
    case 'view-automation-contract': {
      const result = await api(apiW('/notification-automation/api-contract'));
      openModal({ title: 'Local notification automation contract',
        sub: 'external_calls: ' + !!result.external_calls +
          ' Ã‚Â· external_delivery: ' + !!result.external_delivery,
        body: '<pre class="small">' + esc(JSON.stringify(result, null, 2)) + '</pre>' });
      return;
    }
    case 'toggle-automation-flag': {
      const enabled = el.dataset.enabled !== '1';
      await api(apiW('/notification-automation/feature-flags/' + encodeURIComponent(id)), {
        method: 'PATCH', body: { enabled: enabled },
      });
      navigate('notification-automation');
      toast('Feature flag ' + (enabled ? 'enabled.' : 'disabled.'), 'success');
      return;
    }
    case 'remove-automation-routing-rule': {
      await api(apiW('/notification-automation/routing-rules/' + encodeURIComponent(id)), { method: 'DELETE' });
      navigate('notification-automation');
      toast('Routing rule removed.', 'success');
      return;
    }
    case 'view-email-contract': {
      const result = await api(apiW('/email-engagement/api-contract'));
      openModal({ title: 'Local email contract',
        sub: 'version ' + esc(result.version) + ' Ã‚Â· email_sent: ' + !!result.email_sent,
        body: '<pre class="small">' + esc(JSON.stringify(result, null, 2)) + '</pre>' });
      return;
    }
    case 'email-open-template': {
      state.emailTemplateId = id;
      navigate('email-engagement');
      toast('Template opened.', 'success');
      return;
    }
    case 'email-online-version': {
      const result = await api(apiW('/email-engagement/templates/' +
        encodeURIComponent(state.emailTemplateId || '') + '/online'));
      openModal({ title: 'Online version (local render)',
        sub: 'sha256 ' + esc(result.content_hash),
        body: '<pre class="small">' + esc(result.html) + '</pre>' });
      return;
    }
    case 'view-planning-contract': {
      const result = await api(apiW('/work-item-planning/api-contract'));
      openModal({ title: 'Local work-item planning contract',
        sub: 'version ' + esc(result.version) + ' Ã‚Â· ' + esc(result.scheduler || ''),
        body: '<pre class="small">' + esc(JSON.stringify(result, null, 2)) + '</pre>' });
      return;
    }
    case 'planning-open-item': {
      state.planningItemId = id;
      navigate('work-item-planning');
      toast('Work item opened.', 'success');
      return;
    }
    case 'planning-materialize': {
      const result = await api(apiW('/work-item-planning/recurrences/' +
        encodeURIComponent(id) + '/materialize'), { method: 'POST', body: {} });
      navigate('work-item-planning');
      toast(result.created ? 'Next work item created locally.' : 'Recurrence is not due yet.',
        result.created ? 'success' : 'info');
      return;
    }
    case 'planning-unsubscribe': {
      await api(apiW('/work-item-planning/items/' + encodeURIComponent(state.planningItemId || '') +
        '/subscribers/' + encodeURIComponent(id)), { method: 'DELETE' });
      navigate('work-item-planning');
      toast('Subscriber removed from recipient set.', 'success');
      return;
    }

    case 'view-flag-governance-contract': {
      const data = await api(apiW('/flag-governance/api-contract'));
      openModal({ title: 'Flag governance API contract', sub: 'GET /api/workspaces/{id}/flag-governance/api-contract',
        body: '<pre class="small">' + esc(JSON.stringify(data, null, 2)) + '</pre>' });
      break;
    }
    case 'view-access-governance-contract': {
      const data = await api(apiW('/access-governance/permissions'));
      openModal({ title: 'Access governance contract', sub: 'GET /api/workspaces/{id}/access-governance/permissions',
        body: '<pre class="small">' + esc(JSON.stringify(data, null, 2)) + '</pre>' });
      break;
    }
    case 'fg-open-flag': {
      state.fgFlagKey = target.dataset.flag || '';
      await loadView();
      break;
    }

    case 'view-adv-contract': {
      const result = await api(apiW('/advanced-experiments/api-contract'));
      openModal({ title: 'Local advanced experimentation contract',
        sub: 'external_calls ' + String(result.external_calls) + ' Ã‚Â· ' +
          (result.capabilities || []).length + ' capabilities',
        body: '<pre class="small">' + esc(JSON.stringify(result, null, 2)) + '</pre>' });
      return;
    }
    case 'adv-open-analysis': {
      state.advAnalysisId = id;
      await loadView();
      toast('Analysis opened.', 'success');
      return;
    }
    case 'view-collab-contract': {
      const result = await api(apiW('/work-collab/api-contract'));
      openModal({ title: 'Local work collaboration contract',
        sub: 'generated from ' + esc(result.generated_from) + ' Ã‚Â· ' + result.route_count + ' routes',
        body: '<pre class="small">' + esc(JSON.stringify(result, null, 2)) + '</pre>' });
      return;
    }
    case 'collab-open-item': {
      state.collabItemId = id;
      state.collabProjectId = el.dataset.project || state.collabProjectId || '';
      state.collabCursor = '';
      await loadView();
      toast('Work item opened in collaboration view.', 'success');
      return;
    }
    case 'collab-cursor-next':
    case 'collab-cursor-prev': {
      state.collabCursor = el.dataset.cursor || '';
      await loadView();
      return;
    }
    case 'collab-guarded-open': {
      const result = await api(apiW('/work-collab/items/' + encodeURIComponent(id) + '/guarded'));
      openModal({ title: 'Guarded work item', sub: result.title,
        body: '<pre class="small">' + esc(JSON.stringify(result, null, 2)) + '</pre>' });
      return;
    }
    case 'view-wiki-contract': {
      const result = await api(apiW('/wiki-pages/api-contract'));
      openModal({ title: 'Local wiki contract',
        sub: 'version ' + esc(result.version) + ' Ã‚Â· ' + esc(result.realtime_transport || ''),
        body: '<pre class="small">' + esc(JSON.stringify(result, null, 2)) + '</pre>' });
      return;
    }
    case 'wiki-restore-revision': {
      openConfirm('Restore wiki revision',
        'The page title and body will be replaced with this revision. A new version is appended; nothing is deleted.',
        'Restore revision', async function () {
          await api(apiW('/wiki-pages/revisions/' + encodeURIComponent(id) + '/restore'),
            { method: 'POST' });
          navigate('wiki-pages');
          toast('Revision restored locally.', 'success');
        });
      return;
    }
    case 'wiki-comment-block': {
      state.wikiBlockId = id;
      openModal({ title: 'Inline comment',
        sub: 'local, attached to this editor block',
        body: '<form data-form="wiki-comment-inline"><div class="form-grid">' +
          field('body', 'Comment', { type: 'textarea', span: true, required: true,
            placeholder: 'What should change?' }) +
          '</div><div class="form-actions"><button type="button" class="btn" data-action="close-modal">Cancel</button>' +
          '<button type="submit" class="btn btn--primary">' + icon('note', 15) + ' Add comment</button></div></form>' });
      return;
    }
    case 'wiki-resolve-comment': {
      await api(apiW('/wiki-pages/comments/' + encodeURIComponent(id) + '/resolve'),
        { method: 'POST' });
      navigate('wiki-pages');
      toast('Inline comment resolved.', 'success');
      return;
    }
    case 'view-exposure-contract': {
      const result = await api(apiW('/experiment-exposure/api-contract'));
      openModal({ title: 'Local exposure contract',
        sub: 'external_calls: ' + !!result.external_calls +
          ' Ã‚Â· vendor_sdk_used: ' + !!result.vendor_sdk_used,
        body: '<pre class="small">' + esc(JSON.stringify(result, null, 2)) + '</pre>' });
      return;
    }
    case 'view-exposure-sample': {
      const result = await api(apiW('/experiment-exposure/providers/' +
        encodeURIComponent(id) + '/sample'));
      openModal({ title: id + ' local sample payload',
        sub: 'offline, no outbound traffic',
        body: '<pre class="small">' + esc(JSON.stringify(result.payload, null, 2)) + '</pre>' });
      return;
    }
    case 'toggle-exposure-tracker': {
      const enabled = id && (el.dataset.state === 'true');
      const apply = async function () {
        await api(apiW('/experiment-exposure/trackers/' + encodeURIComponent(id)), {
          method: 'PUT', body: { enabled: !enabled, note: '' },
        });
        navigate('experiment-exposure');
        toast(enabled ? 'Tracker disabled locally.' : 'Tracker enabled locally.', 'success');
      };
      if (enabled) {
        openConfirm('Disable exposure tracker',
          'Exposures from this adapter will be rejected while it is disabled. No external service is contacted.',
          'Disable tracker', apply, true);
      } else {
        await apply();
      }
      return;
    }
    case 'view-conversation-contract': {
      const result = await api(apiW('/conversation-ops/api-contract'));
      openModal({ title: 'Local conversation operations contract',
        sub: 'external_calls: ' + !!result.external_calls +
          ' Ã‚Â· external_delivery: ' + !!result.external_delivery,
        body: '<pre class="small">' + esc(JSON.stringify(result, null, 2)) + '</pre>' });
      return;
    }
    case 'expire-conversation-snoozes': {
      const result = await api(apiW('/conversation-ops/snoozes/expire-due'), { method: 'POST' });
      navigate('conversation-ops');
      toast(result.expired + ' snoozes expired; conversations returned to the queue.', 'success');
      return;
    }
    case 'unsnooze-conversation': {
      await api(apiW('/conversation-ops/tickets/' + encodeURIComponent(id) + '/unsnooze'), {
        method: 'POST',
      });
      navigate('conversation-ops');
      toast('Conversation returned to the queue.', 'success');
      return;
    }
    case 'conversation-set-typing': {
      if (!id) { toast('Open a conversation first.', 'error'); return; }
      await api(apiW('/conversation-ops/tickets/' + encodeURIComponent(id) + '/typing'), {
        method: 'POST', body: { ttl_seconds: 30 },
      });
      toast('Typing indicator recorded locally for 30s.', 'success');
      return;
    }
    case 'remove-conversation-folder': {
      await api(apiW('/conversation-ops/folders/' + encodeURIComponent(id)), { method: 'DELETE' });
      navigate('conversation-ops');
      toast('Folder removed.', 'success');
      return;
    }
    case 'view-sales-contract': {
      const result = await api(apiW('/sales-engagement/api-contract'));
      openModal({ title: 'Local sales engagement contract',
        sub: 'external_calls: ' + !!result.external_calls +
          ' Ã‚Â· external_delivery: ' + !!result.external_delivery,
        body: '<pre class="small">' + esc(JSON.stringify(result, null, 2)) + '</pre>' });
      return;
    }
    case 'activate-free-signals': {
      const result = await api(apiW('/sales-engagement/signals/activate-free'), {
        method: 'POST', body: { confirm: true },
      });
      navigate('sales-engagement');
      toast(result.activated + ' free signals activated locally.', 'success');
      return;
    }
    case 'activate-sales-signal': {
      const tier = el.dataset.tier || 'free';
      const doActivate = async function () {
        await api(apiW('/sales-engagement/signals/' + encodeURIComponent(id) + '/activate'), {
          method: 'POST', body: { confirm: true },
        });
        navigate('sales-engagement');
        toast('Signal ' + id + ' activated locally.', 'success');
      };
      if (tier === 'paid') {
        openConfirm('Activate paid signal?',
          'Signal ' + id + ' is a paid tier. Activation is recorded locally and requires your explicit confirmation.',
          'Activate paid signal', doActivate, true);
      } else {
        await doActivate();
      }
      return;
    }
    case 'evaluate-sales-cohort': {
      const result = await api(apiW('/sales-engagement/cohorts/' + encodeURIComponent(id) + '/evaluate'), {
        method: 'POST',
      });
      openModal({ title: 'Cohort evaluation',
        sub: result.matched + ' lead(s) matched locally',
        body: '<pre class="small">' + esc(JSON.stringify(result, null, 2)) + '</pre>' });
      return;
    }
    case 'remove-send-rule': {
      await api(apiW('/sales-engagement/delivery-rules/' + encodeURIComponent(id)), { method: 'DELETE' });
      navigate('sales-engagement');
      toast('Send rule removed.', 'success');
      return;
    }
    case 'outbox-transition': {
      const next = el.dataset.next;
      const result = await api(apiW('/sales-engagement/local-queue/' + encodeURIComponent(id) + '/' + next), {
        method: 'POST',
      });
      navigate('sales-engagement');
      toast('Outbox message is now ' + result.status + ' (no real delivery).', 'success');
      return;
    }
    case 'view-engagement-contract': {
      const result = await api(apiW('/document-engagement/api-contract'));
      openModal({ title: 'Local document engagement contract',
        sub: 'external_calls: ' + !!result.external_calls +
          ' Ã‚Â· external_geolocation: ' + !!result.external_geolocation,
        body: '<pre class="small">' + esc(JSON.stringify(result, null, 2)) + '</pre>' });
      return;
    }
    case 'view-document-analytics': {
      const result = await api(apiW('/document-engagement/documents/' + encodeURIComponent(id) + '/analytics'));
      openModal({ title: 'Document engagement analytics',
        sub: result.views + ' views Ã‚Â· ' + result.clicks + ' clicks Ã‚Â· ' +
          result.excluded_internal + ' internal excluded',
        body: '<pre class="small">' + esc(JSON.stringify(result, null, 2)) + '</pre>' });
      return;
    }
    case 'remove-internal-visitor': {
      await api(apiW('/document-engagement/internal-visitors/' + encodeURIComponent(id)), { method: 'DELETE' });
      navigate('document-engagement');
      toast('Internal visitor removed.', 'success');
      return;
    }
    case 'view-advanced-contract': {
      const result = await api(apiW('/search-advanced/api-contract'));
      openModal({ title: 'Local advanced search contract',
        sub: 'external_model_calls: ' + !!result.external_model_calls +
          ' Ã‚Â· external_sdk: ' + !!result.external_sdk,
        body: '<pre class="small">' + esc(JSON.stringify(result, null, 2)) + '</pre>' });
      return;
    }
    case 'view-survey-contract': {
      const result = await api(apiW('/survey-delivery/api-contract'));
      openModal({ title: 'Local survey delivery contract',
        sub: 'external_calls: ' + !!result.external_calls,
        body: '<pre class="small">' + esc(JSON.stringify(result, null, 2)) + '</pre>' });
      return;
    }
    case 'create-survey-config': {
      const surveys = await api(apiW('/surveys'));
      openModal({
        title: 'New survey delivery config',
        sub: 'Configures channels and delivery options for one local survey.',
        body: '<form data-form="create-survey-config"><div class="form-grid">' +
          field('survey_id', 'Survey', { type: 'select', options: selectOptions(
            (surveys || []).map(function (s) { return [s.id, s.name || s.id]; })) }) +
          field('channels', 'Channels (comma separated)', {
            span: true, value: 'link', placeholder: 'link, website',
            hint: 'in_app, website, link, email, embed',
          }) +
          field('embed_mode', 'Embed mode', { type: 'select', options: selectOptions([
            ['iframe', 'iframe'], ['email_snippet', 'email_snippet'], ['widget', 'widget'],
          ]) }) +
          field('host_css_mode', 'Host CSS mode', { type: 'select', options: selectOptions([
            ['isolated', 'isolated'], ['scoped', 'scoped'], ['inherit', 'inherit'],
          ]) }) +
          '</div><div class="form-actions"><button type="button" class="btn" ' +
          'data-action="close-modal">Cancel</button><button type="submit" class="btn btn--primary">' +
          icon('plus', 15) + ' Create config</button></div></form>',
      });
      return;
    }
    case 'evaluate-survey-creative': {
      const creatives = await api(apiW('/survey-delivery/creatives'));
      const creative = (creatives || []).find(function (c) { return c.id === id; }) || {};
      openModal({
        title: 'Evaluate creative locally',
        sub: creative.key + ' Ã‚Â· ' + creative.type + ' Ã‚Â· no external call',
        body: '<form data-form="evaluate-survey-creative" data-id="' + attr(id) + '"><div class="form-grid">' +
          field('page', 'Page', { value: '/', required: true }) +
          field('device', 'Device', { type: 'select', options: selectOptions([
            ['desktop', 'desktop'], ['tablet', 'tablet'], ['mobile', 'mobile'],
          ]) }) +
          field('views', 'Views', { type: 'number', value: '1' }) +
          field('share', 'Share %', { type: 'number', value: '100' }) +
          '</div><div class="form-actions"><button type="button" class="btn" ' +
          'data-action="close-modal">Cancel</button><button type="submit" class="btn btn--primary">' +
          icon('activity', 15) + ' Evaluate</button></div></form>',
      });
      return;
    }
    case 'create-search-index': {
      openModal({
        title: 'New search index',
        sub: 'Creates a local workspace-scoped index. No external service is used.',
        body: '<form data-form="create-search-index"><div class="form-grid">' +
          field('name', 'Index name', { required: true, placeholder: 'products', span: true }) +
          field('primary_key', 'Primary key', { value: 'id', placeholder: 'id' }) +
          '</div><div class="form-actions"><button type="button" class="btn" data-action="close-modal">Cancel</button>' +
          '<button type="submit" class="btn btn--primary">' + icon('plus', 15) + ' Create index</button></div></form>',
      });
      return;
    }
    case 'search-index-delete':
      await api(apiW('/search-engine/indexes/' + encodeURIComponent(id)), { method: 'DELETE' });
      await loadView();
      toast('Search index deleted locally.', 'success');
      return;
    case 'trigger-evaluate': {
      openModal({
        title: 'Evaluate trigger locally',
        sub: 'Compute a show/no-show decision from stored state.',
        body: '<form data-form="evaluate-trigger" data-trigger-id="' + attr(id) + '"><div class="form-grid">' +
          field('user_id', 'User ID', { required: true, placeholder: 'visitor-1', span: true }) +
          field('action', 'Action name', { required: true, value: 'purchase' }) +
          field('attributes', 'Context attributes (JSON)', { type: 'textarea', value: '{}' }) +
          '</div><div class="form-actions"><button type="submit" class="btn btn--primary">' +
          icon('check', 15) + ' Evaluate</button></div></form>',
      });
      return;
    }
    case 'create-survey': {
      openModal({
        title: 'New survey',
        sub: 'Create a feedback record. Distribution is not performed by this build.',
        body: '<form data-form="create-survey"><div class="form-grid">' +
          field('name', 'Survey name', { required: true, placeholder: 'Post-demo feedback', span: true }) +
          field('description', 'Description', {
            type: 'textarea', span: true, placeholder: 'What should this survey learn?',
          }) +
          '</div><div class="form-actions"><button type="button" class="btn" data-action="close-modal">Cancel</button>' +
          '<button type="submit" class="btn btn--primary">' + icon('plus', 15) + ' Create survey</button></div></form>',
      });
      return;
    }
    case 'view-marketing-content-contract': {
      const result = await api(apiW('/marketing-content/api-contract'));
      openModal({ title: 'Local marketing content contract',
        sub: 'version ' + esc(String(result.version || '')) + ' Ã‚Â· ' + esc(String(result.delivery || '')),
        body: '<pre class="small">' + esc(JSON.stringify(result, null, 2)) + '</pre>' });
      return;
    }
    case 'marketing-page-preview': {
      const result = await api(apiW('/marketing-content/landing-pages/' + encodeURIComponent(id) + '/preview'));
      openModal({ title: 'Local page preview', sub: 'No external delivery',
        body: '<pre class="small">' + esc(String(result.html || '')) + '</pre>' });
      return;
    }
    case 'marketing-page-publish': {
      await api(apiW('/marketing-content/landing-pages/' + encodeURIComponent(id) + '/publication'), {
        method: 'PUT', body: { published: true },
      });
      await loadView();
      toast('Local publish flag set. No hosting or delivery occurred.', 'success');
      return;
    }
    case 'marketing-dashboard-view': {
      const result = await api(apiW('/marketing-content/dashboard'));
      openModal({ title: 'Marketing dashboard', sub: 'Local records only',
        body: '<pre class="small">' + esc(JSON.stringify(result, null, 2)) + '</pre>' });
      return;
    }
    case 'view-support-reporting-contract': {
      const result = await api(apiW('/support-reporting/api-contract'));
      openModal({ title: 'Local support reporting contract',
        sub: 'openapi ' + esc(String(result.openapi || '')) + ' Ã‚Â· ' + esc(String(result.route_count || 0)) + ' support routes',
        body: '<pre class="small">' + esc(JSON.stringify(result, null, 2)) + '</pre>' });
      return;
    }
    case 'support-report-export': {
      const dimension = state.supportReportDimension || 'agents';
      const status = state.supportReportStatus || '';
      const params = ['dimension=' + encodeURIComponent(dimension)];
      if (status) params.push('status=' + encodeURIComponent(status));
      const response = await fetch(API_BASE + apiW('/support-reporting/reports/export?' + params.join('&')), {
        headers: { Authorization: 'Bearer ' + state.access },
      });
      if (!response.ok) throw new Error('CSV export failed with status ' + response.status);
      const csv = await response.text();
      openModal({ title: 'Support report CSV', sub: 'Rows match the on-screen filtered report. Nothing was delivered.',
        body: '<pre class="small">' + esc(csv) + '</pre>' });
      return;
    }
    case 'support-csat-token-issue': {
      await api(apiW('/support-reporting/csat-surveys/' + encodeURIComponent(id) + '/response-token'),
        { method: 'POST', body: {} });
      toast('One-time response token issued locally. It is not displayed.', 'success');
      return;
    }
    default: return;
  }
}

/* ------------------------------------------------------------------ *
 * Universal search - the real workspace-scoped /search API
 * ------------------------------------------------------------------ */

const SEARCH_TYPE_OPTIONS = [
  ['all', 'All types'], ['contact', 'Contacts'], ['lead', 'Leads'],
  ['company', 'Companies'], ['task', 'Tasks'], ['note', 'Notes'],
  ['outreach_draft', 'Outreach drafts'], ['ticket', 'Tickets'],
  ['project', 'Projects'], ['project_item', 'Work items'],
];

function searchTypeLabel(type) {
  const found = SEARCH_TYPE_OPTIONS.filter(function (item) { return item[0] === type; })[0];
  return found ? found[1] : String(type || 'record');
}

function searchResultButton(result) {
  return '<button class="search-result" data-action="search-open" data-kind="' + attr(result.type) +
    '" data-id="' + attr(result.id) + '" data-hint="' + attr(result.url_hint || '') + '">' +
    '<span class="stat-icon">' + icon(SEARCH_ICONS[result.type] || 'activity', 14) + '</span>' +
    '<span class="search-result-main"><span class="search-result-title">' + esc(result.title) + '</span>' +
    '<span class="search-result-sub">' + esc(searchTypeLabel(result.type) + (result.subtitle ? ' - ' + result.subtitle : '')) +
    '</span></span>' + icon('arrowRight', 14) + '</button>';
}

const SEARCH_ICONS = {
  contact: 'users', lead: 'target', company: 'building',
  task: 'checkSquare', note: 'note', outreach_draft: 'mail',
  ticket: 'inbox', project: 'layers', project_item: 'checkSquare',
};

async function loadSearch(token) {
  if (!can(P.contactRead)) {
    renderViewHtml(pageHead('Workspace', 'Universal search', '') + errorBlock('Your role does not include search access.'));
    return;
  }
  loadingView('Universal search', 'One workspace-scoped index across the shared CRM data.');
  const query = (state.searchQuery || '').trim();
  let data = null;
  let failure = null;
  if (query) {
    try {
      data = await api(apiW('/search') + '?q=' + encodeURIComponent(query) + '&limit=50');
    } catch (err) {
      failure = err;
    }
  }
  if (token !== state.viewToken) return;

  let html = pageHead('Workspace', 'Universal search',
    'Find contacts, companies, leads, tasks, notes and outreach drafts in this workspace only.',
    '<a class="btn" href="#/dashboard">' + icon('chevronLeft', 15) + ' Back to overview</a>');
  html += '<section class="card"><form data-form="search-query"><div class="form-grid">' +
    field('q', 'Search term', {
      value: state.searchQuery || '', placeholder: 'Name, email, company, task or note text', span: true,
    }) +
    '<div class="field span-2"><label for="search-type">Result type</label>' +
    '<select class="select" id="search-type" data-change="search-type">' +
    selectOptions(SEARCH_TYPE_OPTIONS, state.searchType) + '</select></div></div>' +
    '<div class="form-actions"><button type="submit" class="btn btn--primary">' +
    icon('search', 15) + ' Search</button></div></form></section>';

  if (failure) {
    html += '<section class="card">' + errorBlock(errMessage(failure)) + '</section>';
  } else if (!query) {
    html += '<section class="card">' + emptyState('search', 'Search your workspace',
      'Enter a term above to search every shared record in this workspace.') + '</section>';
  } else if (!data || !data.results || !data.results.length) {
    html += '<section class="card">' + emptyState('search', 'No matches',
      'No workspace record matched your term. Try a broader search.') + '</section>';
  } else {
    const rows = data.results.filter(function (item) {
      return state.searchType === 'all' || item.type === state.searchType;
    });
    html += '<section class="card"><div class="toolbar"><span class="muted tiny">' +
      esc(String(data.total) + ' matches for "' + query + '"') + '</span></div>';
    if (!rows.length) {
      html += emptyState('search', 'No results of this type',
        'Choose another result type or search for a different term.');
    } else {
      html += '<div class="table-wrap"><table class="data"><thead><tr><th>Record</th><th>Type</th><th>Detail</th><th></th></tr></thead><tbody>' +
        rows.map(function (item) {
          return '<tr><td><div class="cell-primary"><span class="stat-icon">' +
            icon(SEARCH_ICONS[item.type] || 'activity', 15) + '</span><div><div class="cell-title">' +
            esc(item.title) + '</div><div class="cell-sub">' + esc(item.id.slice(0, 8)) + '</div></div></div></td>' +
            '<td>' + statusBadge(item.type) + '</td><td class="small muted">' + esc(item.subtitle || '-') + '</td>' +
            '<td><button class="btn btn--sm" data-action="search-open" data-kind="' + attr(item.type) +
            '" data-id="' + attr(item.id) + '" data-hint="' + attr(item.url_hint || '') + '">Open</button></td></tr>';
        }).join('') + '</tbody></table></div>';
    }
    html += '</section>';
  }
  renderViewHtml(html);
}

/* ------------------------------------------------------------------ *
 * Customer inbox - shared support tickets over the tested /tickets API
 * ------------------------------------------------------------------ */

/* ---- Support operations: real data, local configuration only ------------ */
function supportRows(items, fields) {
  return (items || []).map(function (item) {
    return '<div class="list-row"><div class="list-row-main">' +
      '<div class="list-row-title">' + esc(String(item[fields[0]] || '')) + '</div>' +
      '<div class="list-row-sub">' + fields.slice(1).map(function (f) {
        const v = item[f];
        return f + ': ' + esc(typeof v === 'object' ? JSON.stringify(v) : String(v === undefined || v === null ? '-' : v));
      }).join(' Ãƒâ€šÃ‚Â· ') + '</div></div></div>';
  }).join('');
}

async function openSupportCollection(title, sub, endpoint, fields, glyph) {
  const items = await api(apiW(endpoint));
  openModal({
    title: title, sub: sub,
    body: '<div class="card-body">' + (supportRows(items, fields) ||
      emptyState(glyph, 'Nothing configured', 'Create this in the local API to see it here.')) + '</div>',
  });
}

function openSupportTeams() {
  return openSupportCollection('Support teams', 'Workspace-scoped teams with members and ticket assignment.',
    '/tickets/teams', ['name', 'description', 'created_at'], 'users');
}
function openSupportInboxes() {
  return openSupportCollection('Inboxes', 'Local routing channels. No external mailbox is connected.',
    '/tickets/inboxes', ['name', 'channel', 'slug'], 'inbox');
}
function openSupportLabels() {
  return openSupportCollection('Ticket labels', 'Labels can be applied to tickets and reported per workspace.',
    '/tickets/labels', ['name', 'color'], 'tag');
}
function openSupportRouting() {
  return openSupportCollection('Routing rules', 'Stored rules route new unassigned tickets; manual assignment wins.',
    '/tickets/routing-rules', ['name', 'channel', 'strategy', 'enabled'], 'shuffle');
}
function openSupportSegments() {
  return openSupportCollection('Segments', 'Stored contact rules reusable from the customer inbox.',
    '/tickets/segments', ['name', 'definition'], 'filter');
}

/* CW-023: a saved reply only fills the local draft; nothing is delivered. */
function applyExpandedReply(body, unresolved) {
  state.pendingExpandedReply = state.pendingExpandedReply || {};
  state.pendingExpandedReply.body = body || '';
  state.pendingExpandedReply.unresolved = unresolved || [];
  const form = document.querySelector('form[data-form="ticket-message"]');
  const area = form ? form.querySelector('textarea[name="body"]') : null;
  if (area) {
    area.value = body || '';
    area.focus();
  }
  const notice = document.querySelector('[data-saved-reply-notice]');
  if (notice) {
    if ((unresolved || []).length) {
      notice.textContent = 'Unresolved variables: ' + unresolved.join(', ');
      notice.hidden = false;
    } else {
      notice.textContent = '';
      notice.hidden = true;
    }
  }
}

async function openSupportReplies() {
  const [replies, macros] = await Promise.all([
    api(apiW('/tickets/saved-replies')), api(apiW('/tickets/macros')),
  ]);
  const body = '<div class="card-title">Saved replies</div>' +
    (supportRows(replies, ['name', 'created_at']) || '<div class="muted small">No saved replies.</div>') +
    '<div class="card-title" style="margin-top:16px">Macros</div>' +
    (supportRows(macros, ['name', 'actions']) || '<div class="muted small">No macros.</div>');
  openModal({
    title: 'Replies & macros',
    sub: 'Text is inserted locally. This build offers no external send action.',
    body: '<div class="card-body">' + body + '</div>',
  });
}

async function openSupportHelp() {
  const portals = await api(apiW('/tickets/help-portals'));
  const rows = (portals || []).map(function (p) {
    return '<div class="list-row"><div class="list-row-main"><div class="list-row-title">' +
      esc(p.name) + '</div><div class="list-row-sub">/' + esc(p.slug) + '</div></div></div>';
  }).join('');
  openModal({
    title: 'Help center', sub: 'Published articles are readable; drafts stay hidden from the public endpoint.',
    body: '<div class="card-body">' + (rows || emptyState('book', 'No portals', 'Create a help portal in the local API.')) + '</div>',
  });
}

async function openSupportReports() {
  const [overview, conversations, csat] = await Promise.all([
    api(apiW('/tickets/reports/overview')),
    api(apiW('/tickets/reports/conversations')),
    api(apiW('/tickets/reports/csat')),
  ]);
  const block = function (title, value) {
    return '<div style="flex:1;min-width:140px"><div class="card-sub">' + esc(title) + '</div>' +
      '<div class="stat-value">' + esc(String(value === undefined || value === null ? '-' : value)) + '</div></div>';
  };
  const pairs = Object.entries(overview || {}).map(function (kv) { return block(kv[0], kv[1]); }).join('');
  openModal({
    title: 'Support reports',
    sub: 'Counts and rates come from workspace-scoped ticket and response rows.',
    body: '<div class="card-body"><div class="row" style="gap:16px;flex-wrap:wrap">' +
      (pairs || block('No data', '-')) + '</div>' +
      '<div class="tiny muted" style="margin-top:12px">Conversation series: ' +
      esc(String((conversations || []).length)) + ' points Ãƒâ€šÃ‚Â· CSAT series: ' +
      esc(String((csat || []).length)) + ' points</div></div>',
  });
}

async function loadInbox(token) {
  if (!can(P.contactRead)) {
    renderViewHtml(pageHead('Relationships', 'Customer inbox', '') + errorBlock('Your role does not include inbox access.'));
    return;
  }
  loadingView('Customer inbox', 'Shared support conversations in this workspace.');
  const params = [];
  if (state.ticketStatus && state.ticketStatus !== 'all') {
    params.push('status=' + encodeURIComponent(state.ticketStatus));
  }
  if (state.ticketOwner === 'mine') params.push('mine=true');
  if (state.ticketOwner === 'unassigned') params.push('unassigned=true');
  const suffix = params.length ? '?' + params.join('&') : '';
  let tickets = [];
  let contacts = [];
  try {
    const [ticketResult, contactResult, countResult, teamResult, inboxResult, labelResult, segmentResult] = await Promise.all([
      api(apiW('/tickets') + suffix),
      api(apiW('/contacts') + '?limit=100'),
      api(apiW('/tickets/counts')),
      api(apiW('/tickets/teams')).catch(function () { return []; }),
      api(apiW('/tickets/inboxes')).catch(function () { return []; }),
      api(apiW('/tickets/labels')).catch(function () { return []; }),
      api(apiW('/tickets/segments')).catch(function () { return []; }),
    ]);
    tickets = ticketResult || [];
    contacts = contactResult || [];
    state.ticketCounts = countResult;
    state.caches.supportTeams = teamResult || [];
    state.caches.supportInboxes = inboxResult || [];
    state.caches.supportLabels = labelResult || [];
    state.caches.supportSegments = segmentResult || [];
  } catch (err) {
    if (token !== state.viewToken) return;
    renderViewHtml(pageHead('Relationships', 'Customer inbox', '') + errorBlock(errMessage(err)));
    return;
  }
  if (token !== state.viewToken) return;
  state.caches.tickets = tickets;
  state.caches.contacts = contacts;
  const contactMap = {};
  contacts.forEach(function (c) { contactMap[c.id] = c; });
  // CW-075: the reusable segment filters this view by its matched contact ids.
  if (state.ticketSegmentContactIds) {
    const segmentContacts = new Set(state.ticketSegmentContactIds);
    tickets = tickets.filter(function (t) { return segmentContacts.has(t.contact_id); });
  }
  const actions = (can(P.noteWrite)
    ? '<button class="btn" data-action="identify-customer">' + icon('user', 15) + ' Identify visitor</button>' : '') +
    (can(P.noteWrite)
      ? '<button class="btn btn--primary" data-action="create-ticket">' + icon('plus', 15) + ' New ticket</button>' : '');
  let html = pageHead('Relationships', 'Customer inbox',
    ticketCountSummary(state.ticketCounts) || (tickets.length + ' tickets shown.'), actions);
  html += governanceNote('Tickets and replies stay in this workspace. No email or message is sent by this build.');
  html += '<section class="card"><div class="toolbar">' +
    '<select class="select" data-change="ticket-status" aria-label="Filter by ticket status">' +
    selectOptions([['all', 'All statuses'], ['open', 'Open'], ['pending', 'Pending'], ['resolved', 'Resolved'], ['closed', 'Closed']], state.ticketStatus) +
    '</select><select class="select" data-change="ticket-owner" aria-label="Filter by assignee">' +
    selectOptions([['all', 'Everyone'], ['mine', 'Assigned to me'], ['unassigned', 'Unassigned']], state.ticketOwner) +
    '</select>' +
    (state.caches.supportInboxes.length ? '<select class="select" data-change="ticket-inbox" aria-label="Filter by inbox">' +
      selectOptions([['', 'All inboxes']].concat(state.caches.supportInboxes.map(function (i) { return [i.id, i.name]; })), state.ticketInbox) +
      '</select>' : '') +
    (state.caches.supportLabels.length ? '<select class="select" data-change="ticket-label" aria-label="Filter by label">' +
      selectOptions([['', 'All labels']].concat(state.caches.supportLabels.map(function (l) { return [l.id, l.name]; })), state.ticketLabel) +
      '</select>' : '') +
    (state.caches.supportSegments.length ? '<select class="select" data-change="ticket-segment" aria-label="Filter by saved segment">' +
      selectOptions([['', 'All contacts']].concat(state.caches.supportSegments.map(function (s) { return [s.id, s.name]; })), state.ticketSegment) +
      '</select>' : '') +
    (state.ticketSegmentInfo ? '<span class="muted tiny" data-ticket-segment-info>' +
      esc(state.ticketSegmentInfo.name + ' / ' + state.ticketSegmentInfo.count + ' contacts') + '</span>' : '') +
    '<span class="muted tiny" data-ticket-counts>' +
    esc(ticketCountSummary(state.ticketCounts)) + '</span>' +
    '<span class="muted tiny">' + tickets.length + ' shown</span></div>';
  if (!tickets.length) {
    html += emptyState('mail', 'No tickets here',
      'Create a ticket to start a shared support conversation, or change the status filter.',
      can(P.noteWrite) ? '<button class="btn btn--primary btn--sm" data-action="create-ticket">New ticket</button>' : '');
  } else {
    html += '<div class="table-wrap"><table class="data"><thead><tr><th>Subject</th><th>Contact</th><th>Assignee</th><th>Priority</th><th>Status</th><th>Updated</th><th></th></tr></thead><tbody>' +
      tickets.map(function (t) {
        const contact = contactMap[t.contact_id];
        return '<tr><td><div class="cell-primary"><span class="stat-icon">' + icon('mail', 15) +
          '</span><div><div class="cell-title">' + esc(t.subject) + '</div><div class="cell-sub">' +
          esc((t.body || '').slice(0, 90)) + '</div><div class="cell-sub">' +
          esc(cap(t.origin_channel || 'local')) + ' Ãƒâ€šÃ‚Â· ' + esc(cap(t.conversation_type || 'question')) + '</div></div></div></td>' +
          '<td class="small">' + (contact ? esc(contact.full_name || contact.email) : '<span class="faint">-</span>') + '</td>' +
          '<td class="small">' + (t.assignee_id ? esc(String(t.assignee_id).slice(0, 8)) : '<span class="faint">Unassigned</span>') + '</td>' +
          '<td class="small">' + esc(cap(t.priority)) + '</td><td>' + statusBadge(t.status) + '</td>' +
          '<td class="muted small">' + esc(fmtDate(t.updated_at)) + '</td>' +
          '<td><button class="btn btn--sm" data-action="open-ticket" data-id="' + attr(t.id) + '">Open</button></td></tr>';
      }).join('') + '</tbody></table></div>';
  }
  html += '</section>';
  html += '<section class="card"><div class="card-body"><div class="card-title">Support operations</div>' +
    '<div class="card-sub">All configuration is local to this workspace. No message is sent externally.</div>' +
    '<div class="row" style="gap:8px;flex-wrap:wrap;margin-top:12px">' +
    supportOpButton('support-teams', 'users', 'Teams') +
    supportOpButton('support-inboxes', 'inbox', 'Inboxes') +
    supportOpButton('support-labels', 'tag', 'Labels') +
    supportOpButton('support-routing', 'refresh', 'Routing rules') +
    supportOpButton('support-segments', 'filter', 'Segments') +
    supportOpButton('support-replies', 'message', 'Replies & macros') +
    supportOpButton('support-help', 'note', 'Help center') +
    supportOpButton('support-reports', 'activity', 'Reports') +
    '</div></div></section>';
  renderViewHtml(html);
}

function supportOpButton(action, glyph, label) {
  return '<button class="btn btn--sm btn--ghost" data-action="' + action + '">' +
    icon(glyph, 14) + ' ' + label + '</button>';
}

async function loadTicketDetail(ticketId, token) {
  if (!can(P.contactRead)) {
    renderViewHtml(pageHead('Relationships', 'Ticket', '') + errorBlock('Your role does not include inbox access.'));
    return;
  }
  loadingView('Ticket', 'Conversation and status history.');
  let detail = null;
  let contacts = [];
  let assignees = [];
  try {
    const [detailResult, contactResult, assigneeResult] = await Promise.all([
      api(apiW('/tickets/' + encodeURIComponent(ticketId))),
      api(apiW('/contacts') + '?limit=100'),
      api(apiW('/tickets/assignees')),
    ]);
    detail = detailResult;
    contacts = contactResult || [];
    assignees = assigneeResult || [];
  } catch (err) {
    if (token !== state.viewToken) return;
    renderViewHtml(pageHead('Relationships', 'Ticket', '') + errorBlock(errMessage(err)));
    return;
  }
  if (token !== state.viewToken) return;
  const ticket = detail.ticket;
  const messages = detail.messages || [];
  const contactMap = {};
  contacts.forEach(function (c) { contactMap[c.id] = c; });
  const contact = contactMap[ticket.contact_id];
  let html = pageHead('Relationships', ticket.subject,
    'Opened ' + fmtDate(ticket.created_at) + ' - ' + cap(ticket.priority) + ' priority.',
    '<a class="btn" data-action="back-to-inbox">' + icon('chevronLeft', 15) + ' Back to inbox</a>');
  html += governanceNote('Replies are recorded here only. This build never sends external messages.');
  const currentAssignee = assignees.find(function (a) { return a.id === ticket.assignee_id; });
  html += '<section class="card"><div class="list-row"><span class="stat-icon">' + icon('mail', 15) + '</span>' +
    '<div class="list-row-main"><div class="list-row-title">' + statusBadge(ticket.status) + ' ' + esc(ticket.subject) +
    '</div><div class="list-row-sub">' + (contact ? 'Linked contact: ' + esc(contact.full_name || contact.email)
      : 'No contact linked') + ' - ticket ' + esc(ticket.id.slice(0, 8)) + '</div>' +
    '<div class="list-row-sub">' + esc(cap(ticket.origin_channel || 'local')) + ' Ãƒâ€šÃ‚Â· ' +
    esc(cap(ticket.conversation_type || 'question')) + ' Ãƒâ€šÃ‚Â· Assignee: ' +
    (currentAssignee ? esc(currentAssignee.display_name || currentAssignee.email) : 'Unassigned') + '</div>' +
    '</div></div>';
  if (can(P.noteWrite)) {
    const options = [['', 'Unassigned']].concat(assignees.map(function (a) {
      return [a.id, a.display_name || a.email];
    }));
    html += '<div class="toolbar"><span class="muted tiny">Assign conversation</span>' +
      '<select class="select" data-change="ticket-assignee" data-id="' + attr(ticket.id) + '" aria-label="Assign conversation">' +
      selectOptions(options, ticket.assignee_id || '') + '</select></div>';
  }
  if (can(P.noteWrite)) {
    html += '<div class="toolbar"><span class="muted tiny">Change status</span>' +
      ['open', 'pending', 'resolved', 'closed'].filter(function (s) { return s !== ticket.status; })
        .map(function (s) {
          return '<button class="btn btn--sm" data-action="ticket-set-status" data-id="' + attr(ticket.id) +
            '" data-status="' + attr(s) + '">' + esc(cap(s)) + '</button>';
        }).join('') + '</div>';
  }
  html += '</section>';
  html += '<section class="card"><div class="page-head-main"><h2 class="page-title">Conversation</h2>' +
    '<p class="page-sub">' + messages.length + ' recorded ' + (messages.length === 1 ? 'reply' : 'replies') + '.</p></div>';
  if (!messages.length) {
    html += emptyState('mail', 'No replies yet',
      'Add the first internal reply. It stays in this workspace.');
  } else {
    html += messages.map(function (m) {
      return '<div class="list-row"><span class="stat-icon">' + icon('user', 15) + '</span>' +
        '<div class="list-row-main"><div class="list-row-title">' + esc(m.body) + '</div>' +
        '<div class="list-row-sub">By ' + esc(m.author_id.slice(0, 8)) + ' - ' + esc(relTime(m.created_at)) +
        ' <span class="badge badge--plain">' + esc(cap(m.direction || 'outbound')) + '</span>' +
        ' <span class="badge badge--plain">' + esc(cap(m.channel || 'local')) + '</span>' +
        (m.is_internal ? ' <span class="badge badge--amber">Internal</span>' : '') + '</div></div></div>';
    }).join('');
  }
  html += '</section>';
  if (can(P.noteWrite)) {
    html += '<section class="card"><form data-form="ticket-message" data-ticket-id="' + attr(ticket.id) + '">' +
      '<div class="form-grid">' +
      field('body', 'Reply or internal note', {
        type: 'textarea', required: true, span: true,
        placeholder: 'Record what was done. Nothing is sent externally.',
      }) +
      field('direction', 'Direction', {
        type: 'select', options: selectOptions(
          [['inbound', 'Inbound'], ['outbound', 'Outbound']], 'outbound'),
      }) +
      field('channel', 'Channel', {
        type: 'select', options: selectOptions(
          [['local', 'Local'], ['web_form', 'Web form'], ['email', 'Email'], ['import', 'Import']], 'local'),
      }) +
      '</div><div class="info-banner" data-saved-reply-notice hidden></div>' +
      '<div class="form-actions">' +
      '<button type="button" class="btn btn--sm" data-action="insert-saved-reply" data-ticket-id="' +
      attr(ticket.id) + '"' + (ticket.contact_id ? ' data-contact-id="' + attr(ticket.contact_id) + '"' : '') +
      '>' + icon('note', 14) + ' Insert saved reply</button>' +
      '<button type="submit" class="btn btn--primary">' +
      icon('plus', 15) + ' Add reply</button></div></form></section>';
  }
  renderViewHtml(html);
  if (state.pendingExpandedReply && state.pendingExpandedReply.ticketId === ticket.id) {
    applyExpandedReply(state.pendingExpandedReply.body, state.pendingExpandedReply.unresolved);
  }
}

/* ------------------------------------------------------------------ *
 * Campaign Studio, Sales pipeline and Feedback Studio.
 * These views expose already-tested workspace APIs. They record local
 * data only; no email, ads, SMS or public post is created by this build.
 * ------------------------------------------------------------------ */

const CAMPAIGN_CHANNELS = ['email', 'ads', 'social', 'other'];
const CAMPAIGN_STATUSES = ['draft', 'active', 'paused', 'completed'];
const DEAL_STAGES = ['new', 'qualified', 'proposal', 'won', 'lost'];

function money(value) {
  const n = Number(value || 0);
  return n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function optionList(values) {
  return values.map(function (value) { return [value, cap(value)]; });
}

async function loadCampaigns(token) {
  if (!can(P.contactRead)) {
    renderViewHtml(pageHead('Operations', 'Campaign Studio', '') +
      errorBlock('Your role does not include campaign access.'));
    return;
  }
  loadingView('Campaign Studio', 'Campaign lifecycle and recorded metrics.');
  const suffix = state.campaignStatus !== 'all'
    ? '?status=' + encodeURIComponent(state.campaignStatus) : '';
  let campaigns = [];
  let performance = [];
  try {
    const [listResult, perfResult] = await Promise.all([
      api(apiW('/campaigns') + suffix),
      api(apiW('/campaigns/performance')),
    ]);
    campaigns = listResult || [];
    performance = perfResult || [];
  } catch (err) {
    if (token !== state.viewToken) return;
    renderViewHtml(pageHead('Operations', 'Campaign Studio', '') + errorBlock(errMessage(err)));
    return;
  }
  if (token !== state.viewToken) return;
  state.caches.campaigns = campaigns;
  const perfMap = {};
  performance.forEach(function (p) { perfMap[p.campaign_id] = p; });
  const leads = performance.reduce(function (sum, p) { return sum + (p.total_leads || 0); }, 0);
  const spend = performance.reduce(function (sum, p) { return sum + Number(p.total_spend || 0); }, 0);

  let html = pageHead('Operations', 'Campaign Studio',
    campaigns.length + ' campaign' + (campaigns.length === 1 ? '' : 's') + ' in this workspace.',
    can(P.contactWrite) ? '<button class="btn btn--primary" data-action="create-campaign">' +
      icon('plus', 15) + ' New campaign</button>' : '');
  html += governanceNote('Campaigns and metrics are recorded here only. This build sends no email, ads or messages.');
  html += '<div class="stats">' +
    statCard('layers', 'Campaigns', String(campaigns.length), 'In this workspace') +
    statCard('check', 'Active', String(campaigns.filter(function (c) { return c.status === 'active'; }).length), 'Currently running') +
    statCard('target', 'Leads recorded', String(leads), 'From campaign metrics') +
    statCard('tag', 'Spend recorded', money(spend), 'Local figures', 'blue') + '</div>';
  html += '<section class="card"><div class="toolbar">' +
    '<select class="select" data-change="campaign-status" aria-label="Filter by campaign status">' +
    selectOptions([['all', 'All statuses']].concat(optionList(CAMPAIGN_STATUSES)), state.campaignStatus) +
    '</select><span class="muted tiny">' + campaigns.length + ' shown</span></div>';
  if (!campaigns.length) {
    html += emptyState('layers', 'No campaigns yet',
      'Create a campaign to record its goal and daily metrics.',
      can(P.contactWrite) ? '<button class="btn btn--primary btn--sm" data-action="create-campaign">New campaign</button>' : '');
  } else {
    html += '<div class="table-wrap"><table class="data"><thead><tr><th>Campaign</th><th>Channel</th><th>Status</th>' +
      '<th>Metric days</th><th>Leads</th><th>Spend</th><th></th></tr></thead><tbody>' +
      campaigns.map(function (c) {
        const p = perfMap[c.id] || {};
        return '<tr><td><div class="cell-primary"><span class="stat-icon">' + icon('layers', 15) +
          '</span><div><div class="cell-title">' + esc(c.name) + '</div><div class="cell-sub">' +
          esc((c.goal || '').slice(0, 90) || 'No goal recorded') + '</div></div></div></td>' +
          '<td class="small">' + esc(cap(c.channel)) + '</td><td>' + statusBadge(c.status) + '</td>' +
          '<td class="small">' + esc(String(p.metric_days || 0)) + '</td>' +
          '<td class="small">' + esc(String(p.total_leads || 0)) + '</td>' +
          '<td class="small">' + money(p.total_spend || 0) + '</td>' +
          '<td><button class="btn btn--sm" data-action="open-campaign" data-id="' + attr(c.id) + '">Open</button></td></tr>';
      }).join('') + '</tbody></table></div>';
  }
  html += '</section>';
  renderViewHtml(html);
}

async function loadCampaignDetail(campaignId, token) {
  if (!can(P.contactRead)) {
    renderViewHtml(pageHead('Operations', 'Campaign', '') +
      errorBlock('Your role does not include campaign access.'));
    return;
  }
  loadingView('Campaign', 'Goal, journey, enrollments and recorded daily metrics.');
  const base = apiW('/campaigns/' + encodeURIComponent(campaignId));
  const sources = [
    api(base), api(base + '/metrics'), api(base + '/journey-steps'),
    api(base + '/enrollments'), api(apiW('/contacts') + '?limit=100'),
    api(apiW('/campaigns/analytics/lifecycle')),
  ];
  const results = await Promise.allSettled(sources);
  if (token !== state.viewToken) return;
  const failed = results.slice(0, 2).find(function (r) { return r.status === 'rejected'; });
  if (failed) {
    renderViewHtml(pageHead('Operations', 'Campaign', '') + errorBlock(errMessage(failed.reason)));
    return;
  }
  const detail = results[0].value;
  const metrics = results[1].value || [];
  const fulfilled = function (index) {
    return results[index].status === 'fulfilled' ? (results[index].value || []) : [];
  };
  const steps = fulfilled(2);
  const enrollments = fulfilled(3);
  const contacts = fulfilled(4);
  const lifecycle = fulfilled(5).slice(0, 12);
  const c = detail.campaign;
  let html = pageHead('Operations', c.name,
    cap(c.channel) + ' channel - created ' + fmtDate(c.created_at) + '.',
    '<a class="btn" data-action="back-to-campaigns">' + icon('chevronLeft', 15) + ' Back to campaigns</a>');
  html += governanceNote('Metrics below are entered by a user. No external campaign delivery occurs.');
  html += '<section class="card"><div class="list-row"><span class="stat-icon">' + icon('layers', 15) +
    '</span><div class="list-row-main"><div class="list-row-title">' + statusBadge(c.status) + ' ' +
    esc(c.name) + '</div><div class="list-row-sub">' + esc(c.goal || 'No goal recorded') +
    ' - campaign ' + esc(c.id.slice(0, 8)) + '</div></div></div>';
  if (can(P.contactWrite)) {
    html += '<div class="toolbar"><span class="muted tiny">Change status</span>' +
      CAMPAIGN_STATUSES.filter(function (s) { return s !== c.status; }).map(function (s) {
        return '<button class="btn btn--sm" data-action="campaign-set-status" data-id="' + attr(c.id) +
          '" data-status="' + attr(s) + '">' + esc(cap(s)) + '</button>';
      }).join('') + '</div>';
  }
  html += '</section>';

  const journeyActions = [['email.sent', 'Record email send'], ['email.opened', 'Record open'],
    ['email.clicked', 'Record click']];
  const enrolledIds = enrollments.map(function (e) { return e.contact_id; });
  const contactOptions = contacts.filter(function (p) { return enrolledIds.indexOf(p.id) === -1; })
    .map(function (p) { return [p.id, p.full_name || p.email]; });
  const contactName = function (id) {
    const found = contacts.filter(function (p) { return p.id === id; })[0];
    return found ? (found.full_name || found.email) : String(id).slice(0, 8);
  };

  html += '<section class="card"><div class="card-head"><div class="card-head-main">' +
    '<div class="card-title">Journey and schedule</div><div class="card-sub">' +
    'Steps record local analytics events only ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â no email or message is delivered.</div></div></div>' +
    '<div class="card-body"><div class="table-wrap"><table class="data"><thead><tr>' +
    '<th>#</th><th>Step</th><th>Kind</th><th>Channel</th><th>Action</th></tr></thead><tbody>' +
    (steps.length ? steps.map(function (s) {
      return '<tr><td class="small">' + Number(s.position) + '</td>' +
        '<td class="cell-title">' + esc(s.label) + '</td>' +
        '<td>' + esc(cap(s.step_kind || 'action')) + '</td>' +
        '<td>' + esc(cap(s.channel)) + '</td>' +
        '<td class="mono small">' + esc(s.action) + '</td></tr>';
    }).join('') : '<tr><td colspan="5" class="muted small">No journey steps yet.</td></tr>') +
    '</tbody></table></div>';
  if (can(P.contactWrite)) {
    html += '<form data-form="campaign-journey-step-add" data-campaign-id="' + attr(c.id) + '">' +
      '<div class="form-grid">' +
      field('position', 'Order', { type: 'number', min: 1, value: String(steps.length + 1) }) +
      field('step_kind', 'Kind', {
        type: 'select', options: selectOptions(
          [['action', 'Action'], ['condition', 'Condition'], ['decision', 'Decision']], 'action'),
      }) +
      field('channel', 'Channel', {
        type: 'select', options: selectOptions(
          [['email', 'Email'], ['ads', 'Ads'], ['social', 'Social'], ['other', 'Other']], 'email'),
      }) +
      field('action', 'Local action', {
        type: 'select', options: selectOptions(
          journeyActions.concat([
            ['journey.condition_evaluated', 'Evaluate condition'],
            ['journey.decision_evaluated', 'Evaluate decision'],
          ]), 'email.sent'),
      }) +
      field('label', 'Label', { placeholder: 'What this step records', required: true }) +
      field('config', 'Rule (JSON, optional)', {
        placeholder: '{"field":"source","op":"eq","value":"website"}',
      }) +
      '</div><div class="form-actions"><button type="submit" class="btn">' +
      icon('plus', 15) + ' Add step</button></div></form>';
    html += '<form data-form="campaign-schedule" data-campaign-id="' + attr(c.id) + '">' +
      '<div class="form-grid">' +
      field('start_at', 'Starts at', { type: 'datetime-local' }) +
      field('end_at', 'Ends at', { type: 'datetime-local' }) +
      '</div><div class="form-actions"><button type="submit" class="btn">' +
      icon('calendar', 15) + ' Save schedule</button>' +
      '<button type="button" class="btn btn--primary" data-action="campaign-run-journey" data-id="' +
      attr(c.id) + '">' + icon('zap', 15) + ' Run one step</button></div></form>';
  }
  html += '</div></section>';

  html += '<section class="card"><div class="card-head"><div class="card-head-main">' +
    '<div class="card-title">Campaign enrollments</div><div class="card-sub">' +
    'Contacts progress through the journey locally. Suppressed contacts cannot be enrolled.</div></div></div>' +
    '<div class="card-body"><div class="table-wrap"><table class="data"><thead><tr>' +
    '<th>Contact</th><th>Status</th><th>Step</th><th></th></tr></thead><tbody>' +
    (enrollments.length ? enrollments.map(function (e) {
      return '<tr><td class="cell-title">' + esc(contactName(e.contact_id)) + '</td>' +
        '<td>' + (e.status === 'active' ? '<span class="badge badge--green">Active</span>' :
          '<span class="badge badge--plain">Exited</span>') + '</td>' +
        '<td class="small">' + Number(e.current_step || 0) + '</td>' +
        '<td>' + (can(P.contactWrite) && e.status === 'active' ?
          '<button class="btn btn--sm btn--ghost" data-action="campaign-record-engagement" ' +
          'data-contact="' + attr(e.contact_id) + '" data-kind="opened">Opened</button> ' +
          '<button class="btn btn--sm btn--ghost" data-action="campaign-record-engagement" ' +
          'data-contact="' + attr(e.contact_id) + '" data-kind="clicked">Clicked</button> ' +
          '<button class="btn btn--sm btn--ghost" data-action="campaign-exit-enrollment" ' +
          'data-contact="' + attr(e.contact_id) + '">Exit</button>' : '') + '</td></tr>';
    }).join('') : '<tr><td colspan="4" class="muted small">No contacts enrolled yet.</td></tr>') +
    '</tbody></table></div>';
  if (can(P.contactWrite) && contactOptions.length) {
    html += '<form data-form="campaign-enroll-contact" data-campaign-id="' + attr(c.id) + '">' +
      '<div class="form-grid">' +
      field('contact_id', 'Contact', {
        type: 'select', options: selectOptions([['', 'Choose a contact']].concat(contactOptions), ''), required: true,
      }) +
      '</div><div class="form-actions"><button type="submit" class="btn">' +
      icon('plus', 15) + ' Enroll contact</button></div></form>';
  }
  html += '</div></section>';

  html += '<section class="card"><h2 class="page-title">Lifecycle analytics</h2>' +
    '<p class="muted small">Recorded on the shared event spine. Nothing here represents a delivered message.</p>';
  if (!lifecycle.length) {
    html += emptyState('activity', 'No lifecycle events', 'Journey steps and enrollments appear here.');
  } else {
    html += '<div class="table-wrap"><table class="data"><thead><tr>' +
      '<th>Event</th><th>Recorded</th><th>Contact</th></tr></thead><tbody>' +
      lifecycle.map(function (e) {
        return '<tr><td class="mono small">' + esc(e.event_type) + '</td>' +
          '<td class="muted small">' + esc(relTime(e.occurred_at)) + '</td>' +
          '<td class="small">' + esc(e.entity_id ? String(e.entity_id).slice(0, 8) : 'ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â') + '</td></tr>';
      }).join('') + '</tbody></table></div>';
  }
  html += '</section>';

  html += '<div class="stats">' +
    statCard('calendar', 'Metric days', String(detail.metric_days || 0), 'Days recorded') +
    statCard('eye', 'Impressions', String(detail.total_impressions || 0), 'Recorded total') +
    statCard('target', 'Leads', String(detail.total_leads || 0), 'Attributed locally') +
    statCard('tag', 'Spend', money(detail.total_spend), 'Recorded total', 'blue') + '</div>';
  html += '<section class="card"><h2 class="page-title">Daily metrics</h2>';
  if (!metrics.length) {
    html += emptyState('layers', 'No metrics recorded', 'Add a day of metrics below to build the campaign history.');
  } else {
    html += '<div class="table-wrap"><table class="data"><thead><tr><th>Date</th><th>Impressions</th>' +
      '<th>Clicks</th><th>Leads</th><th>Spend</th></tr></thead><tbody>' +
      metrics.map(function (m) {
        return '<tr><td>' + esc(m.date) + '</td><td>' + esc(String(m.impressions)) + '</td><td>' +
          esc(String(m.clicks)) + '</td><td>' + esc(String(m.leads)) + '</td><td>' + money(m.spend) + '</td></tr>';
      }).join('') + '</tbody></table></div>';
  }
  html += '</section>';
  if (can(P.contactWrite)) {
    html += '<section class="card"><form data-form="record-campaign-metric" data-campaign-id="' + attr(c.id) +
      '"><div class="form-grid">' +
      field('date', 'Date', { type: 'date', required: true, value: new Date().toISOString().slice(0, 10) }) +
      field('impressions', 'Impressions', { type: 'number', min: 0, value: '0' }) +
      field('clicks', 'Clicks', { type: 'number', min: 0, value: '0' }) +
      field('leads', 'Leads', { type: 'number', min: 0, value: '0' }) +
      field('spend', 'Spend', { type: 'number', min: 0, value: '0' }) +
      '</div><div class="form-actions"><button type="submit" class="btn btn--primary">' +
      icon('plus', 15) + ' Record metric</button></div></form></section>';
  }
  renderViewHtml(html);
}

async function loadDeals(token) {
  if (!can(P.contactRead)) {
    renderViewHtml(pageHead('Relationships', 'Sales pipeline', '') +
      errorBlock('Your role does not include pipeline access.'));
    return;
  }
  loadingView('Sales pipeline', 'Deals and stage totals for this workspace.');
  const suffix = state.dealStage !== 'all' ? '?stage=' + encodeURIComponent(state.dealStage) : '';
  let deals = [];
  let summary = null;
  try {
    const [dealResult, summaryResult] = await Promise.all([
      api(apiW('/deals') + suffix),
      api(apiW('/deals/summary')),
    ]);
    deals = dealResult || [];
    summary = summaryResult;
  } catch (err) {
    if (token !== state.viewToken) return;
    renderViewHtml(pageHead('Relationships', 'Sales pipeline', '') + errorBlock(errMessage(err)));
    return;
  }
  if (token !== state.viewToken) return;
  state.caches.deals = deals;
  const stageSummary = (summary && summary.by_stage) || [];
  const won = stageSummary.filter(function (s) { return s.stage === 'won'; })[0];

  let html = pageHead('Relationships', 'Sales pipeline',
    (summary ? summary.total_deals : deals.length) + ' deals in this workspace.',
    can(P.contactWrite) ? '<button class="btn btn--primary" data-action="create-deal">' +
      icon('plus', 15) + ' New deal</button>' : '');
  html += governanceNote('Deal stages and values are recorded here. No outreach message is sent automatically.');
  html += '<div class="stats">' +
    statCard('tag', 'Total deals', String(summary ? summary.total_deals : deals.length), 'All stages') +
    statCard('target', 'Pipeline value', money(summary ? summary.total_value : 0), 'Recorded total') +
    statCard('check', 'Won value', money(won ? won.total_value : 0), 'Closed successfully', 'blue') +
    statCard('clock', 'In progress', String(deals.filter(function (d) {
      return ['new', 'qualified', 'proposal'].indexOf(d.stage) !== -1;
    }).length), 'Shown in current filter') + '</div>';
  html += '<section class="card"><div class="toolbar">' +
    '<select class="select" data-change="deal-stage" aria-label="Filter by deal stage">' +
    selectOptions([['all', 'All stages']].concat(optionList(DEAL_STAGES)), state.dealStage) +
    '</select><span class="muted tiny">' + deals.length + ' shown</span></div>';
  if (!deals.length) {
    html += emptyState('tag', 'No deals yet', 'Create a deal to begin tracking this pipeline.',
      can(P.contactWrite) ? '<button class="btn btn--primary btn--sm" data-action="create-deal">New deal</button>' : '');
  } else {
    html += '<div class="table-wrap"><table class="data"><thead><tr><th>Deal</th><th>Company</th><th>Value</th>' +
      '<th>Stage</th><th>Probability</th><th>Expected close</th><th></th></tr></thead><tbody>' +
      deals.map(function (d) {
        return '<tr><td><div class="cell-primary"><span class="stat-icon">' + icon('tag', 15) +
          '</span><div><div class="cell-title">' + esc(d.title) + '</div><div class="cell-sub">' +
          esc(d.id.slice(0, 8)) + '</div></div></div></td>' +
          '<td class="small">' + esc(d.company || (d.contact_id ? 'Linked contact' : '-')) + '</td>' +
          '<td class="small">' + money(d.value) + '</td><td>' + statusBadge(d.stage) + '</td>' +
          '<td class="small">' + esc(String(d.probability)) + '%</td>' +
          '<td class="small muted">' + esc(fmtDate(d.expected_close_at)) + '</td>' +
          '<td><button class="btn btn--sm" data-action="open-deal" data-id="' + attr(d.id) + '">Open</button></td></tr>';
      }).join('') + '</tbody></table></div>';
  }
  html += '</section>';
  renderViewHtml(html);
}

async function loadDealDetail(dealId, token) {
  if (!can(P.contactRead)) {
    renderViewHtml(pageHead('Relationships', 'Deal', '') +
      errorBlock('Your role does not include pipeline access.'));
    return;
  }
  loadingView('Deal', 'Stage history and recorded activities.');
  let deal = null;
  let activities = [];
  const base = apiW('/deals/' + encodeURIComponent(dealId));
  try {
    const [dealResult, activityResult] = await Promise.all([api(base), api(base + '/activities')]);
    deal = dealResult;
    activities = activityResult || [];
  } catch (err) {
    if (token !== state.viewToken) return;
    renderViewHtml(pageHead('Relationships', 'Deal', '') + errorBlock(errMessage(err)));
    return;
  }
  if (token !== state.viewToken) return;
  let html = pageHead('Relationships', deal.title,
    money(deal.value) + ' - ' + cap(deal.stage) + ' - ' + deal.probability + '% probability.',
    '<a class="btn" data-action="back-to-deals">' + icon('chevronLeft', 15) + ' Back to pipeline</a>');
  html += '<section class="card"><div class="list-row"><span class="stat-icon">' + icon('tag', 15) +
    '</span><div class="list-row-main"><div class="list-row-title">' + statusBadge(deal.stage) + ' ' +
    esc(deal.title) + '</div><div class="list-row-sub">' +
    esc(deal.company || (deal.contact_id ? 'Linked contact ' + deal.contact_id.slice(0, 8) : 'No company')) +
    ' - deal ' + esc(deal.id.slice(0, 8)) + '</div></div></div>';
  if (can(P.contactWrite)) {
    html += '<div class="toolbar"><span class="muted tiny">Move to stage</span>' +
      DEAL_STAGES.filter(function (s) { return s !== deal.stage; }).map(function (s) {
        return '<button class="btn btn--sm" data-action="deal-set-stage" data-id="' + attr(deal.id) +
          '" data-stage="' + attr(s) + '">' + esc(cap(s)) + '</button>';
      }).join('') + '</div>';
  }
  html += '</section>';
  html += '<section class="card"><h2 class="page-title">Activity</h2>';
  if (!activities.length) {
    html += emptyState('activity', 'No activity recorded', 'Add a call, meeting or note to this deal.');
  } else {
    html += activities.map(function (a) {
      return '<div class="list-row"><span class="stat-icon">' + icon('activity', 15) +
        '</span><div class="list-row-main"><div class="list-row-title">' + esc(a.activity_type) +
        '</div><div class="list-row-sub">' + esc(a.note || 'No note') + ' - ' + esc(relTime(a.created_at)) +
        '</div></div></div>';
    }).join('');
  }
  html += '</section>';
  if (can(P.contactWrite)) {
    html += '<section class="card"><form data-form="add-deal-activity" data-deal-id="' + attr(deal.id) +
      '"><div class="form-grid">' +
      field('activity_type', 'Activity type', { required: true, placeholder: 'Call, meeting, note', span: true }) +
      field('note', 'Note', { type: 'textarea', span: true, placeholder: 'What happened?' }) +
      '</div><div class="form-actions"><button type="submit" class="btn btn--primary">' +
      icon('plus', 15) + ' Add activity</button></div></form></section>';
  }
  renderViewHtml(html);
}

async function loadSurveys(token) {
  if (!can(P.contactRead)) {
    renderViewHtml(pageHead('Operations', 'Feedback Studio', '') +
      errorBlock('Your role does not include feedback access.'));
    return;
  }
  loadingView('Feedback Studio', 'Surveys and recorded responses.');
  let surveys = [];
  try {
    surveys = await api(apiW('/surveys')) || [];
  } catch (err) {
    if (token !== state.viewToken) return;
    renderViewHtml(pageHead('Operations', 'Feedback Studio', '') + errorBlock(errMessage(err)));
    return;
  }
  if (token !== state.viewToken) return;
  state.caches.surveys = surveys;
  let html = pageHead('Operations', 'Feedback Studio',
    surveys.length + ' survey' + (surveys.length === 1 ? '' : 's') + ' in this workspace.',
    can(P.noteWrite) ? '<button class="btn btn--primary" data-action="create-survey">' +
      icon('plus', 15) + ' New survey</button>' +
      '<button class="btn" data-action="survey-from-template">' + icon('note', 15) + ' From template</button>' : '');
  html += governanceNote('Responses are recorded here only. This build does not distribute surveys or send invitations.');
  html += '<div class="stats">' +
    statCard('note', 'Surveys', String(surveys.length), 'In this workspace') +
    statCard('clock', 'Drafts', String(surveys.filter(function (s) { return s.status === 'draft'; }).length), 'Not yet published') +
    statCard('check', 'Active', String(surveys.filter(function (s) { return s.status === 'active'; }).length), 'Ready for responses') +
    statCard('activity', 'Scored responses', String(surveys.length ? 'see detail' : '0'), 'Per survey average') + '</div>';
  html += '<section class="card">';
  if (!surveys.length) {
    html += emptyState('note', 'No surveys yet', 'Create a survey to start collecting local feedback.',
      can(P.noteWrite) ? '<button class="btn btn--primary btn--sm" data-action="create-survey">New survey</button>' : '');
  } else {
    html += '<div class="table-wrap"><table class="data"><thead><tr><th>Survey</th><th>Status</th>' +
      '<th>Created by</th><th>Created</th><th></th></tr></thead><tbody>' +
      surveys.map(function (s) {
        return '<tr><td><div class="cell-primary"><span class="stat-icon">' + icon('note', 15) +
          '</span><div><div class="cell-title">' + esc(s.name) + '</div><div class="cell-sub">' +
          esc((s.description || '').slice(0, 90) || 'No description') + '</div></div></div></td>' +
          '<td>' + statusBadge(s.status) + '</td><td class="small">' + esc(s.created_by.slice(0, 8)) + '</td>' +
          '<td class="muted small">' + esc(fmtDate(s.created_at)) + '</td>' +
          '<td><button class="btn btn--sm" data-action="open-survey" data-id="' + attr(s.id) + '">Open</button></td></tr>';
      }).join('') + '</tbody></table></div>';
  }
  html += '</section>';
  renderViewHtml(html);
}

async function loadSurveyDetail(surveyId, token) {
  if (!can(P.contactRead)) {
    renderViewHtml(pageHead('Operations', 'Survey', '') +
      errorBlock('Your role does not include feedback access.'));
    return;
  }
  loadingView('Survey', 'Responses and satisfaction summary.');
  let detail = null;
  let responses = [];
  let contacts = [];
  let config = null;
  let questions = [];
  let links = [];
  let tags = [];
  let answers = [];
  let triggers = [];
  let actionClasses = [];
  let control = null;
  const base = apiW('/surveys/' + encodeURIComponent(surveyId));
  const ext = apiW('/feedback/surveys/' + encodeURIComponent(surveyId));
  const tgt = apiW('/feedback/targeting');
  try {
    const [detailResult, responseResult, contactResult, configResult, questionResult,
      linkResult, tagResult, answerResult, triggerResult, actionResult, controlResult] = await Promise.all([
      api(base), api(base + '/responses'), api(apiW('/contacts') + '?limit=100'),
      api(ext + '/config').catch(function () { return null; }),
      api(ext + '/questions').catch(function () { return []; }),
      api(ext + '/links').catch(function () { return []; }),
      api(ext + '/tags').catch(function () { return []; }),
      api(ext + '/answers').catch(function () { return []; }),
      api(tgt + '/triggers').catch(function () { return []; }),
      api(tgt + '/action-classes').catch(function () { return []; }),
      api(tgt + '/surveys/' + encodeURIComponent(surveyId) + '/controls').catch(function () { return null; }),
    ]);
    detail = detailResult;
    responses = responseResult || [];
    contacts = contactResult || [];
    config = configResult;
    questions = questionResult || [];
    links = linkResult || [];
    tags = tagResult || [];
    answers = answerResult || [];
    triggers = (triggerResult || []).filter(function (t) { return t.survey_id === surveyId; });
    actionClasses = actionResult || [];
    control = controlResult;
  } catch (err) {
    if (token !== state.viewToken) return;
    renderViewHtml(pageHead('Operations', 'Survey', '') + errorBlock(errMessage(err)));
    return;
  }
  if (token !== state.viewToken) return;
  const s = detail.survey;
  const contactMap = {};
  contacts.forEach(function (c) { contactMap[c.id] = c; });
  const lifecycle = can(P.noteWrite)
    ? (s.status === 'closed'
      ? '<button class="btn" data-action="survey-status" data-id="' + attr(s.id) + '" data-status="active">' + icon('refresh', 15) + ' Reopen</button>'
      : (s.status === 'draft'
        ? '<button class="btn btn--primary" data-action="survey-status" data-id="' + attr(s.id) + '" data-status="active">' + icon('check', 15) + ' Publish</button>'
        : '<button class="btn" data-action="survey-status" data-id="' + attr(s.id) + '" data-status="closed">' + icon('lock', 15) + ' Close</button>'))
    : '';
  let html = pageHead('Operations', s.name,
    'Created ' + fmtDate(s.created_at) + '. Scores use the 1-10 scale.',
    '<a class="btn" data-action="back-to-surveys">' + icon('chevronLeft', 15) + ' Back to surveys</a>' + lifecycle);
  html += governanceNote('Feedback stays in this workspace. Nothing is emailed to the respondent.');
  html += '<section class="card"><div class="list-row"><span class="stat-icon">' + icon('note', 15) +
    '</span><div class="list-row-main"><div class="list-row-title">' + statusBadge(s.status) + ' ' + esc(s.name) +
    '</div><div class="list-row-sub">' + esc(s.description || 'No description') + ' - survey ' + esc(s.id.slice(0, 8)) +
    '</div></div></div></section>';
  html += '<div class="stats">' +
    statCard('check', 'Responses', String(detail.response_count || 0), 'Recorded locally') +
    statCard('target', 'Average score', detail.average_score === null || detail.average_score === undefined
      ? '-' : String(detail.average_score), 'Out of 10', 'blue') +
    statCard('activity', 'With comment', String(responses.filter(function (r) { return !!r.comment; }).length), 'Written feedback') +
    statCard('users', 'Identified', String(responses.filter(function (r) { return !!r.contact_id; }).length), 'Linked to a contact') + '</div>';
  html += '<section class="card"><h2 class="page-title">Responses</h2>';
  if (!responses.length) {
    html += emptyState('note', 'No responses yet', 'Record the first response below.');
  } else {
    html += '<div class="table-wrap"><table class="data"><thead><tr><th>Contact</th><th>Score</th>' +
      '<th>Comment</th><th>Recorded</th></tr></thead><tbody>' +
      responses.map(function (r) {
        const c = contactMap[r.contact_id];
        return '<tr><td class="small">' + (c ? esc(c.full_name || c.email) : '<span class="faint">-</span>') + '</td>' +
          '<td>' + (r.score === null || r.score === undefined ? '<span class="faint">-</span>' : esc(String(r.score) + '/10')) + '</td>' +
          '<td class="small">' + esc((r.comment || '').slice(0, 140) || '-') + '</td>' +
          '<td class="muted small">' + esc(fmtDate(r.created_at)) + '</td></tr>';
      }).join('') + '</tbody></table></div>';
  }
  html += '</section>';
  if (s.status === 'closed') {
    html += governanceNote('This survey is closed. Reopen it to record further responses; existing feedback is kept.');
  } else if (can(P.noteWrite)) {
    html += '<section class="card"><form data-form="add-survey-response" data-survey-id="' + attr(s.id) +
      '"><div class="form-grid">' +
      field('contact_id', 'Respondent', {
        type: 'select', span: true,
        options: selectOptions([['', 'Not identified']].concat(contacts.map(function (c) {
          return [c.id, c.full_name || c.email];
        })), ''),
      }) +
      field('score', 'Score (1-10)', { type: 'number', min: 1, placeholder: '1 to 10' }) +
      field('comment', 'Comment', { type: 'textarea', span: true, placeholder: 'Optional written feedback' }) +
      '</div><div class="form-actions"><button type="submit" class="btn btn--primary">' +
      icon('plus', 15) + ' Record response</button></div></form></section>';
  }
  // Survey configuration (FB-008..FB-044) Ã¢â‚¬â€ persisted through the local API only.
  const cfg = config || {};
  const displayOpts = ['displayOnce', 'displayMultiple', 'displaySome', 'respondMultiple'];
  const themes = ['default', 'forest', 'gold', 'minimal'];
  html += '<section class="card"><h2 class="page-title">Survey configuration</h2>' +
    '<p class="muted small">Display, visibility, language and styling are stored in this workspace. Nothing is published externally.</p>';
  if (can(P.noteWrite)) {
    html += '<form data-form="save-survey-config" data-survey-id="' + attr(s.id) + '"><div class="form-grid">' +
      field('display_option', 'Display option', {
        type: 'select', options: selectOptions(displayOpts.map(function (o) { return [o, o]; }), cfg.display_option || 'displayOnce'),
      }) +
      field('visibility', 'Visibility', {
        type: 'select', options: selectOptions([['workspace', 'Workspace'], ['restricted', 'Restricted']], cfg.visibility || 'workspace'),
      }) +
      field('theme', 'Theme', {
        type: 'select', options: selectOptions(themes.map(function (o) { return [o, o]; }), cfg.theme || 'default'),
      }) +
      field('languages', 'Languages (comma separated)', {
        value: (cfg.languages || []).join(', '), placeholder: 'en, te',
      }) +
      field('custom_css', 'Custom CSS', {
        type: 'textarea', span: true, value: cfg.custom_css || '', placeholder: '.survey { color: #176B55; }',
      }) +
      '</div><div class="form-actions"><button type="submit" class="btn btn--primary">' +
      icon('check', 15) + ' Save configuration</button></div></form>';
  } else {
    html += '<p class="small">Current: ' + esc(cfg.display_option || 'displayOnce') + ' / ' +
      esc(cfg.visibility || 'workspace') + ' / ' + esc(cfg.theme || 'default') + '.</p>';
  }
  html += '<h3 class="page-title">Questions</h3>';
  if (!questions.length) {
    html += emptyState('note', 'No questions yet', 'Add a typed question to this survey.');
  } else {
    html += '<div class="table-wrap"><table class="data"><thead><tr><th>Code</th><th>Type</th>' +
      '<th>Label</th><th>Required</th><th>Logic</th></tr></thead><tbody>' +
      questions.map(function (q) {
        const logic = Object.keys(q.logic || {}).join(', ') || '-';
        return '<tr><td class="small">' + esc(q.code) + '</td><td>' + esc(q.type) + '</td>' +
          '<td class="small">' + esc(q.label) + '</td><td>' + (q.required ? 'Yes' : '-') + '</td>' +
          '<td class="muted small">' + esc(logic) + '</td></tr>';
      }).join('') + '</tbody></table></div>';
  }
  if (can(P.noteWrite)) {
    html += '<form data-form="add-survey-question" data-survey-id="' + attr(s.id) + '"><div class="form-grid">' +
      field('type', 'Type', {
        type: 'select', options: selectOptions(['nps', 'csat', 'ces', 'consent', 'contact_info', 'date',
          'free_text', 'single_choice', 'multi_choice', 'rating', 'image', 'video', 'address']
          .map(function (o) { return [o, o]; }), 'free_text'),
      }) +
      field('code', 'Question code', { required: true, placeholder: 'q1' }) +
      field('label', 'Label', { required: true, span: true, placeholder: 'What should we ask?' }) +
      '</div><div class="form-actions"><button type="submit" class="btn btn--primary">' +
      icon('plus', 15) + ' Add question</button></div></form>';
    html += '<form data-form="set-survey-embedded" data-survey-id="' + attr(s.id) + '"><div class="form-grid">' +
      field('subject', 'Respondent subject', { required: true, placeholder: 'visitor-1' }) +
      field('data', 'Embedded data (JSON)', { type: 'textarea', span: true, value: '{"plan": "gold"}' }) +
      '</div><div class="form-actions"><button type="submit" class="btn">' +
      icon('check', 15) + ' Set embedded data</button></div></form>';
  }
  html += '</section>';

  // Structured answers, shareable links, displays and tags (FB-066..FB-095).
  html += '<section class="card"><h2 class="page-title">Share links</h2>';
  if (!links.length) {
    html += emptyState('note', 'No share links yet', 'Create a link to open this survey for responses.');
  } else {
    html += '<div class="table-wrap"><table class="data"><thead><tr><th>Kind</th><th>Slug</th>' +
      '<th>Source</th><th>Used</th><th>Token</th></tr></thead><tbody>' +
      links.map(function (l) {
        return '<tr><td>' + esc(l.kind) + '</td><td class="small">' + esc(l.slug || '-') + '</td>' +
          '<td class="small">' + esc(l.source || '-') + '</td><td>' + (l.used ? 'Yes' : '-') + '</td>' +
          '<td class="small">' + esc(String(l.token).slice(0, 10)) + '</td></tr>';
      }).join('') + '</tbody></table></div>';
  }
  if (can(P.noteWrite)) {
    html += '<form data-form="create-survey-link" data-survey-id="' + attr(s.id) + '"><div class="form-grid">' +
      field('kind', 'Link kind', {
        type: 'select', options: selectOptions([['personal', 'Personal'], ['single_use', 'Single use']], 'personal'),
      }) +
      field('slug', 'Pretty URL slug', { placeholder: 'quarterly-review' }) +
      field('source', 'Source', { placeholder: 'website' }) +
      '</div><div class="form-actions"><button type="submit" class="btn">' +
      icon('plus', 15) + ' Create link</button></div></form>';
  }
  html += '<h3 class="page-title">Tags</h3>';
  html += tags.length
    ? '<p class="small">' + tags.map(function (t) { return esc(t.name); }).join(' &middot; ') + '</p>'
    : '<p class="muted small">No tags yet.</p>';
  if (can(P.noteWrite)) {
    html += '<form data-form="create-survey-tag" data-survey-id="' + attr(s.id) + '"><div class="form-grid">' +
      field('name', 'New tag', { required: true, placeholder: 'follow-up' }) +
      '</div><div class="form-actions"><button type="submit" class="btn">' +
      icon('plus', 15) + ' Add tag</button></div></form>';
  }
  html += '<h3 class="page-title">Structured answers</h3>';
  if (!answers.length) {
    html += emptyState('note', 'No structured answers yet', 'Answers submitted through a share link appear here.');
  } else {
    html += '<div class="table-wrap"><table class="data"><thead><tr><th>Code</th><th>Value</th>' +
      '<th>State</th><th>Tags</th><th>Actions</th></tr></thead><tbody>' +
      answers.map(function (a) {
        const state = a.partial ? 'Partial' : 'Finished';
        return '<tr><td class="small">' + esc(a.code || '-') + '</td><td class="small">' +
          esc(String(a.value)) + '</td><td>' + esc(state) + '</td><td class="small">' +
          '&mdash;</td><td>' + (can(P.noteWrite)
            ? '<button class="btn btn--sm" data-action="answer-finish" data-id="' + attr(a.id) + '">Finish</button> ' +
              '<button class="btn btn--sm" data-action="answer-delete" data-id="' + attr(a.id) + '">Delete</button>'
            : '-') + '</td></tr>';
      }).join('') + '</tbody></table></div>';
  }
  if (can(P.noteWrite)) {
    html += '<button class="btn" data-action="answers-export" data-id="' + attr(s.id) + '">' +
      icon('check', 15) + ' Export answers (CSV)</button>';
  }
  html += '</section>';

  // Targeting, triggers and survey controls (FB-055..FB-084).
  html += '<section class="card"><h2 class="page-title">Targeting and controls</h2>' +
    '<p class="muted small">Rules are evaluated locally against identified users and stored answers. ' +
    'No survey is injected into any host page.</p>';
  if (can(P.noteWrite)) {
    html += '<form data-form="create-action-class"><div class="form-grid">' +
      field('name', 'Action name', { required: true, placeholder: 'purchase' }) +
      field('description', 'Description', { placeholder: 'Optional' }) +
      '</div><div class="form-actions"><button type="submit" class="btn">' +
      icon('plus', 15) + ' Add action</button></div></form>';
  }
  html += '<h3 class="page-title">Triggers</h3>';
  if (!triggers.length) {
    html += '<p class="muted small">No triggers for this survey yet.</p>';
  } else {
    html += '<div class="table-wrap"><table class="data"><thead><tr><th>Name</th><th>Enabled</th>' +
      '<th>Rollout</th><th>Cooldown</th><th>Evaluate</th></tr></thead><tbody>' +
      triggers.map(function (t) {
        return '<tr><td class="small">' + esc(t.name) + '</td><td>' + (t.enabled ? 'Yes' : 'No') + '</td>' +
          '<td>' + esc(String(t.percentage)) + '%</td><td>' + esc(String(t.cooldown_seconds)) + 's</td>' +
          '<td><button class="btn btn--sm" data-action="trigger-evaluate" data-id="' + attr(t.id) +
          '" data-survey="' + attr(s.id) + '">Evaluate</button></td></tr>';
      }).join('') + '</tbody></table></div>';
  }
  if (can(P.noteWrite) && actionClasses.length) {
    html += '<form data-form="create-trigger" data-survey-id="' + attr(s.id) + '"><div class="form-grid">' +
      field('name', 'Trigger name', { required: true, placeholder: 'On purchase' }) +
      field('action_class_id', 'Action', {
        type: 'select',
        options: selectOptions(actionClasses.map(function (a) { return [a.id, a.name]; }), actionClasses[0].id),
      }) +
      field('percentage', 'Rollout %', { type: 'number', value: '100' }) +
      field('cooldown_seconds', 'Cooldown (seconds)', { type: 'number', value: '0' }) +
      '</div><div class="form-actions"><button type="submit" class="btn">' +
      icon('plus', 15) + ' Add trigger</button></div></form>';
  }
  html += '<h3 class="page-title">Submission controls</h3>';
  const ctrl = control || {};
  if (can(P.noteWrite)) {
    html += '<form data-form="save-survey-controls" data-survey-id="' + attr(s.id) + '"><div class="form-grid">' +
      field('max_responses', 'Maximum responses', { type: 'number', value: ctrl.max_responses == null ? '' : String(ctrl.max_responses) }) +
      field('schedule_start', 'Starts at (ISO)', { value: ctrl.schedule_start || '', placeholder: '2099-01-01T00:00:00+00:00' }) +
      field('schedule_end', 'Ends at (ISO)', { value: ctrl.schedule_end || '', placeholder: '2099-12-31T00:00:00+00:00' }) +
      '</div><div class="form-actions"><button type="submit" class="btn">' +
      icon('check', 15) + ' Save controls</button></div></form>';
  }
  html += '</section>';
  renderViewHtml(html);
}

async function loadSearchIndexes(token) {
  if (!can(P.contactRead)) {
    renderViewHtml(pageHead('Operations', 'Search indexes', '') +
      errorBlock('Your role does not include search access.'));
    return;
  }
  loadingView('Search indexes', 'Local, workspace-scoped search indexes.');
  let indexes = [];
  let version = null;
  try {
    const base = apiW('/search-engine');
    [indexes, version] = await Promise.all([
      api(base + '/indexes'), api(base + '/version'),
    ]);
    indexes = indexes || [];
  } catch (err) {
    if (token !== state.viewToken) return;
    renderViewHtml(pageHead('Operations', 'Search indexes', '') + errorBlock(errMessage(err)));
    return;
  }
  if (token !== state.viewToken) return;
  let html = pageHead('Operations', 'Search indexes',
    indexes.length + ' local index' + (indexes.length === 1 ? '' : 'es') +
    ' Ã‚Â· ' + esc(version.version || ''),
    can(P.noteWrite) ? '<button class="btn btn--primary" data-action="create-search-index">' +
      icon('plus', 15) + ' New index</button>' : '');
  html += governanceNote('Search runs entirely in this workspace. No external search service is contacted.');
  html += '<section class="card"><h2 class="page-title">Indexes</h2>';
  if (!indexes.length) {
    html += emptyState('search', 'No indexes yet', 'Create an index, then add documents through the local API.');
  } else {
    html += '<div class="table-wrap"><table class="data"><thead><tr><th>Name</th>' +
      '<th>Primary key</th><th>Created</th><th>Actions</th></tr></thead><tbody>' +
      indexes.map(function (i) {
        return '<tr><td>' + esc(i.name) + '</td><td class="small">' + esc(i.primaryKey) + '</td>' +
          '<td class="small">' + esc(String(i.createdAt).slice(0, 10)) + '</td><td>' +
          (can(P.noteWrite)
            ? '<button class="btn btn--sm" data-action="search-index-delete" data-id="' +
              attr(i.name) + '">Delete</button>'
            : '-') + '</td></tr>';
      }).join('') + '</tbody></table></div>';
  }
  html += '</section>';
  if (indexes.length) {
    html += '<section class="card"><h2 class="page-title">Search locally</h2>' +
      '<form data-form="search-index-query"><div class="form-grid">' +
      field('index', 'Index', {
        type: 'select',
        options: selectOptions(indexes.map(function (i) { return [i.name, i.name]; }), indexes[0].name),
      }) +
      field('q', 'Query', { required: true, placeholder: 'e.g. phone', value: state.lastSearchQuery || '' }) +
      '</div><div class="form-actions"><button type="submit" class="btn btn--primary">' +
      icon('search', 15) + ' Search</button></div></form>';
    if (state.lastSearchResult) {
      const result = state.lastSearchResult;
      html += '<p class="muted small">' + esc(String(result.totalHits)) + ' hits in ' +
        esc(String(result.processingTimeMs)) + ' ms</p>';
      if (!result.hits.length) {
        html += emptyState('search', 'No matches', 'Try a different query or add documents.');
      } else {
        html += '<div class="table-wrap"><table class="data"><thead><tr><th>ID</th>' +
          '<th>Document</th><th>Score</th></tr></thead><tbody>' +
          result.hits.map(function (h) {
            const first = Object.keys(h.formatted || {})[0];
            return '<tr><td class="small">' + esc(h.documentId) + '</td><td class="small">' +
              (first ? esc(String(h.formatted[first])) : esc(JSON.stringify(h.data))) + '</td>' +
              '<td>' + esc(String(h.rankingScore)) + '</td></tr>';
          }).join('') + '</tbody></table></div>';
      }
    }
    html += '</section>';
  }
  renderViewHtml(html);
}

async function loadDocumentEngagement(token) {
  if (!can(P.documentRead)) {
    renderViewHtml(pageHead('Operations', 'Document engagement', '') +
      errorBlock('Your role does not include document access.'));
    return;
  }
  loadingView('Document engagement', 'Local reactions, feedback, annotations and analytics.');
  let data;
  try {
    const base = apiW('/document-engagement');
    const [contract, documents, internal] = await Promise.all([
      api(base + '/api-contract'), api(apiW('/documents')), api(base + '/internal-visitors'),
    ]);
    data = { contract: contract || {}, documents: documents || [], internal: internal || [] };
  } catch (err) {
    if (token !== state.viewToken) return;
    renderViewHtml(pageHead('Operations', 'Document engagement', '') + errorBlock(errMessage(err)));
    return;
  }
  if (token !== state.viewToken) return;

  const write = can(P.documentWrite);
  const docOptions = selectOptions(data.documents.map(function (d) { return [d.id, d.title]; }));
  let html = pageHead('Operations', 'Document engagement',
    data.documents.length + ' documents Ã‚Â· ' + data.internal.length + ' internal visitors',
    '<button class="btn" data-action="view-engagement-contract">' + icon('info', 15) +
      ' Local contract</button>');
  html += governanceNote('Collaboration and analytics are local records. No Papermark server, hosted viewer, outbound email, geolocation service or external analytics provider is contacted; location and client fields are caller-supplied.');

  html += '<section class="card"><h2 class="page-title">Documents</h2>' +
    (data.documents.length ? '<div class="table-wrap"><table class="data"><thead><tr><th>Title</th>' +
      '<th>Type</th><th></th></tr></thead><tbody>' +
      data.documents.map(function (d) {
        return '<tr><td>' + esc(d.title) + '</td><td>' + statusBadge(d.doc_type) + '</td><td>' +
          '<button class="btn btn--sm" data-action="view-document-analytics" data-id="' + attr(d.id) +
          '">Analytics</button></td></tr>';
      }).join('') + '</tbody></table></div>'
      : '<p class="muted small">No documents yet. Add one in Documents first.</p>') + '</section>';

  html += '<section class="card"><h2 class="page-title">Internal visitors</h2>' +
    (data.internal.length ? '<div class="table-wrap"><table class="data"><thead><tr><th>Match</th>' +
      '<th>Value</th><th></th></tr></thead><tbody>' +
      data.internal.map(function (v) {
        return '<tr><td>' + statusBadge(v.match_type) + '</td><td class="mono">' + esc(v.value) + '</td>' +
          '<td>' + (write ? '<button class="btn btn--sm" data-action="remove-internal-visitor" data-id="' +
            attr(v.id) + '">Remove</button>' : '-') + '</td></tr>';
      }).join('') + '</tbody></table></div>'
      : '<p class="muted small">No internal visitors registered.</p>') +
    (write ? '<form data-form="add-internal-visitor"><div class="form-grid">' +
      field('match_type', 'Match type', { type: 'select', options: selectOptions([
        ['visitor', 'visitor'], ['email_domain', 'email_domain'],
      ]) }) +
      field('value', 'Value', { required: true, placeholder: 'novara.local' }) +
      '</div><div class="form-actions"><button type="submit" class="btn">' +
      icon('plus', 15) + ' Exclude visitor</button></div></form>' : '') + '</section>';

  if (write && data.documents.length) {
    html += '<section class="card"><h2 class="page-title">Record engagement</h2>' +
      '<form data-form="record-document-event"><div class="form-grid">' +
      field('document_id', 'Document', { type: 'select', options: docOptions }) +
      field('event_type', 'Event', { type: 'select', options: selectOptions([
        ['view', 'view'], ['scroll', 'scroll'], ['video', 'video'], ['click', 'click'],
      ]) }) +
      field('visitor', 'Visitor', { value: 'anonymous' }) +
      field('scroll_depth', 'Scroll depth %', { type: 'number', value: '0' }) +
      field('country', 'Country', { placeholder: 'IN' }) +
      field('city', 'City', { placeholder: 'Bengaluru' }) +
      field('device', 'Device', { placeholder: 'desktop' }) +
      '</div><div class="form-actions"><button type="submit" class="btn btn--primary">' +
      icon('activity', 15) + ' Record event</button></div></form>' +
      '<form data-form="record-document-click"><div class="form-grid">' +
      field('document_id', 'Document', { type: 'select', options: docOptions }) +
      field('target', 'Click target', { required: true, placeholder: 'https://cta.local/signup' }) +
      field('visitor', 'Visitor', { value: 'anonymous' }) +
      '</div><div class="form-actions"><button type="submit" class="btn">' +
      icon('activity', 15) + ' Record click</button></div></form>' +
      '</section>';

    html += '<section class="card"><h2 class="page-title">Collaboration</h2>' +
      '<form data-form="add-document-reaction"><div class="form-grid">' +
      field('document_id', 'Document', { type: 'select', options: docOptions }) +
      field('key', 'Reaction', { type: 'select', options: selectOptions([
        ['like', 'like'], ['love', 'love'], ['insightful', 'insightful'],
        ['question', 'question'], ['celebrate', 'celebrate'],
      ]) }) +
      field('page_number', 'Page (0 = whole doc)', { type: 'number', value: '0' }) +
      '</div><div class="form-actions"><button type="submit" class="btn">' +
      icon('plus', 15) + ' React</button></div></form>' +
      '<form data-form="add-document-feedback"><div class="form-grid">' +
      field('document_id', 'Document', { type: 'select', options: docOptions }) +
      field('rating', 'Rating (1-5)', { type: 'number', value: '5' }) +
      field('body', 'Feedback', { type: 'textarea', required: true, span: true }) +
      '</div><div class="form-actions"><button type="submit" class="btn">' +
      icon('plus', 15) + ' Add feedback</button></div></form>' +
      '<form data-form="add-document-annotation"><div class="form-grid">' +
      field('document_id', 'Document', { type: 'select', options: docOptions }) +
      field('page_number', 'Page', { type: 'number', value: '1' }) +
      field('kind', 'Kind', { type: 'select', options: selectOptions([
        ['highlight', 'highlight'], ['comment', 'comment'], ['note', 'note'],
      ]) }) +
      field('content', 'Content', { type: 'textarea', required: true, span: true }) +
      '</div><div class="form-actions"><button type="submit" class="btn">' +
      icon('edit', 15) + ' Annotate</button></div></form>' +
      '</section>';

    html += '<section class="card"><h2 class="page-title">Metadata, versions and search</h2>' +
      '<form data-form="update-document-metadata"><div class="form-grid">' +
      field('document_id', 'Document', { type: 'select', options: docOptions }) +
      field('title', 'New title', { placeholder: 'leave blank to keep' }) +
      field('folder_id', 'Folder ID', { placeholder: 'leave blank to keep' }) +
      '</div><div class="form-actions"><button type="submit" class="btn">' +
      icon('edit', 15) + ' Update metadata</button></div></form>' +
      '<form data-form="promote-document-version"><div class="form-grid">' +
      field('document_id', 'Document', { type: 'select', options: docOptions }) +
      field('version_id', 'Version ID', { required: true }) +
      field('external_url', 'Repoint URL', { placeholder: 'optional' }) +
      '</div><div class="form-actions"><button type="submit" class="btn">' +
      icon('activity', 15) + ' Promote version</button></div></form>' +
      '<form data-form="search-document-names"><div class="form-grid">' +
      field('q', 'Name contains', { required: true, placeholder: 'proposal' }) +
      '</div><div class="form-actions"><button type="submit" class="btn">' +
      icon('search', 15) + ' Search names</button></div></form>' +
      '</section>';
  }
  renderViewHtml(html);
}

async function loadSearchAdvanced(token) {
  if (!can(P.contactRead)) {
    renderViewHtml(pageHead('Operations', 'Advanced search', '') +
      errorBlock('Your role does not include search access.'));
    return;
  }
  loadingView('Advanced search', 'Local hybrid, federated and vector search.');
  let data;
  try {
    const base = apiW('/search-advanced');
    const [contract, indexes, federations] = await Promise.all([
      api(base + '/api-contract'), api(apiW('/search-engine') + '/indexes'),
      api(base + '/federations'),
    ]);
    data = { contract: contract || {}, indexes: indexes || [], federations: federations || [] };
  } catch (err) {
    if (token !== state.viewToken) return;
    renderViewHtml(pageHead('Operations', 'Advanced search', '') + errorBlock(errMessage(err)));
    return;
  }
  if (token !== state.viewToken) return;

  const write = can(P.noteWrite);
  const indexOptions = selectOptions(data.indexes.map(function (i) { return [i.name, i.name]; }));
  const federationOptions = selectOptions(data.federations.map(function (f) { return [f.id, f.key]; }));
  let html = pageHead('Operations', 'Advanced search',
    data.indexes.length + ' indexes Ã‚Â· ' + data.federations.length + ' federations',
    '<button class="btn" data-action="view-advanced-contract">' + icon('info', 15) +
      ' Local contract</button>');
  html += governanceNote('Hybrid, vector and federated search run locally with deterministic embeddings. No Meilisearch server, embedding model, external SDK or hosted demo is contacted.');

  html += '<section class="card"><h2 class="page-title">Federations</h2>' +
    (data.federations.length ? '<div class="table-wrap"><table class="data"><thead><tr><th>Key</th>' +
      '<th>Members</th></tr></thead><tbody>' +
      data.federations.map(function (f) {
        return '<tr><td class="mono">' + esc(f.key) + '</td><td class="small">' +
          esc((f.members || []).map(function (m) { return m.index + 'Ãƒâ€”' + m.weight; }).join(', ')) +
          '</td></tr>';
      }).join('') + '</tbody></table></div>'
      : '<p class="muted small">No federations yet. Create one below to merge indexes.</p>') + '</section>';

  if (data.indexes.length) {
    html += '<section class="card"><h2 class="page-title">Hybrid search</h2>' +
      '<form data-form="advanced-hybrid-search"><div class="form-grid">' +
      field('index', 'Index', { type: 'select', options: indexOptions }) +
      field('embedder_name', 'Embedder', { value: 'text', required: true }) +
      field('q', 'Query', { required: true, placeholder: 'e.g. running shoes' }) +
      field('semantic_weight', 'Semantic weight', { type: 'number', value: '0.5' }) +
      '</div><div class="form-actions"><button type="submit" class="btn btn--primary">' +
      icon('search', 15) + ' Hybrid search</button></div></form></section>';

    html += '<section class="card"><h2 class="page-title">Suggestions</h2>' +
      '<form data-form="advanced-suggest"><div class="form-grid">' +
      field('index', 'Index', { type: 'select', options: indexOptions }) +
      field('q', 'Prefix', { required: true, placeholder: 'e.g. run' }) +
      '</div><div class="form-actions"><button type="submit" class="btn btn--primary">' +
      icon('search', 15) + ' Suggest</button></div></form></section>';
  }

  if (data.federations.length) {
    html += '<section class="card"><h2 class="page-title">Federated search</h2>' +
      '<form data-form="advanced-federated-search"><div class="form-grid">' +
      field('federation', 'Federation', { type: 'select', options: federationOptions }) +
      field('q', 'Query', { required: true }) +
      '</div><div class="form-actions"><button type="submit" class="btn btn--primary">' +
      icon('layers', 15) + ' Federated search</button></div></form></section>';
  }

  if (write && data.indexes.length) {
    html += '<section class="card"><h2 class="page-title">Configure local search</h2>' +
      '<form data-form="create-advanced-embedder"><div class="form-grid">' +
      field('index', 'Index', { type: 'select', options: indexOptions }) +
      field('name', 'Embedder name', { value: 'text', required: true }) +
      field('kind', 'Kind', { type: 'select', options: selectOptions([
        ['local_text', 'local_text'], ['local_image', 'local_image'],
        ['user_provided', 'user_provided'], ['composite', 'composite'],
      ]) }) +
      field('dimensions', 'Dimensions', { type: 'number', value: '32' }) +
      '</div><div class="form-actions"><button type="submit" class="btn">' +
      icon('plus', 15) + ' Create embedder</button></div></form>' +
      '<form data-form="create-advanced-suggestion"><div class="form-grid">' +
      field('index', 'Index', { type: 'select', options: indexOptions }) +
      field('key', 'Suggestion key', { required: true, placeholder: 'titles' }) +
      field('attribute', 'Attribute', { required: true, placeholder: 'title' }) +
      '</div><div class="form-actions"><button type="submit" class="btn">' +
      icon('plus', 15) + ' Create suggestion</button></div></form>' +
      '<form data-form="advanced-swap"><div class="form-grid">' +
      field('left', 'Left index', { type: 'select', options: indexOptions }) +
      field('right', 'Right index', { type: 'select', options: indexOptions }) +
      '</div><div class="form-actions"><button type="submit" class="btn">' +
      icon('activity', 15) + ' Swap indexes</button></div></form>' +
      '<form data-form="advanced-edit-function"><div class="form-grid">' +
      field('index', 'Index', { type: 'select', options: indexOptions }) +
      field('attribute', 'Attribute', { required: true, placeholder: 'title' }) +
      field('op', 'Operation', { type: 'select', options: selectOptions([
        ['set', 'set'], ['upper', 'upper'], ['lower', 'lower'],
        ['suffix', 'suffix'], ['prefix', 'prefix'], ['increment', 'increment'],
      ]) }) +
      field('value', 'Value', { placeholder: 'optional' }) +
      field('document_ids', 'Document IDs (comma)', { placeholder: 'blank = all' }) +
      '</div><div class="form-actions"><button type="submit" class="btn">' +
      icon('edit', 15) + ' Edit documents</button></div></form>' +
      '<form data-form="advanced-compact"><div class="form-grid">' +
      field('index', 'Index', { type: 'select', options: indexOptions }) +
      field('kind', 'Kind', { type: 'select', options: selectOptions([
        ['index', 'index'], ['task_queue', 'task_queue'],
      ]) }) +
      '</div><div class="form-actions"><button type="submit" class="btn">' +
      icon('activity', 15) + ' Compact</button></div></form>' +
      '<form data-form="create-advanced-template"><div class="form-grid">' +
      field('index', 'Index', { type: 'select', options: indexOptions }) +
      field('key', 'Template key', { required: true }) +
      field('kind', 'Kind', { type: 'select', options: selectOptions([
        ['embedder', 'embedder'], ['chat', 'chat'], ['fragment', 'fragment'],
      ]) }) +
      field('body', 'Body', { type: 'textarea', required: true, span: true,
        placeholder: 'Searching {{query}} at {{brand}}' }) +
      '</div><div class="form-actions"><button type="submit" class="btn">' +
      icon('plus', 15) + ' Create template</button></div></form>' +
      '<form data-form="advanced-template-render"><div class="form-grid">' +
      field('index', 'Index', { type: 'select', options: indexOptions }) +
      field('template_id', 'Template ID', { required: true }) +
      field('query', 'Query', { placeholder: 'shoes' }) +
      field('document', 'Document JSON', { type: 'textarea', span: true, value: '{}' }) +
      '</div><div class="form-actions"><button type="submit" class="btn">' +
      icon('activity', 15) + ' Render template</button></div></form>' +
      '<form data-form="create-advanced-preview"><div class="form-grid">' +
      field('index', 'Index', { type: 'select', options: indexOptions }) +
      field('key', 'Preview key', { required: true }) +
      field('query', 'Query', { required: true, placeholder: 'shoes' }) +
      '</div><div class="form-actions"><button type="submit" class="btn">' +
      icon('search', 15) + ' Create & run preview</button></div></form>' +
      '</section>';
  }

  if (write) {
    html += '<section class="card"><h2 class="page-title">Create federation</h2>' +
      '<form data-form="create-advanced-federation"><div class="form-grid">' +
      field('key', 'Federation key', { required: true, placeholder: 'shop-and-learn' }) +
      field('members', 'Members JSON', { type: 'textarea', required: true, span: true,
        value: '[{"index": "products", "weight": 2}]',
        hint: 'Array of {index, weight}; indexes must exist in this workspace.' }) +
      '</div><div class="form-actions"><button type="submit" class="btn btn--primary">' +
      icon('plus', 15) + ' Create federation</button></div></form></section>';
  }
  renderViewHtml(html);
}

async function loadEmailEngagement(token) {
  if (!can(P.contactRead)) {
    renderViewHtml(pageHead('Operations', 'Email engagement', '') +
      errorBlock('Your role does not include email access.'));
    return;
  }
  loadingView('Email engagement', 'Local email content, tracking tokens and engagement governance.');
  let data;
  try {
    const base = apiW('/email-engagement');
    const templates = await api(base + '/templates') || [];
    const selected = state.emailTemplateId || (templates[0] && templates[0].id);
    let detail = null;
    if (selected) {
      const pbase = base + '/templates/' + encodeURIComponent(selected);
      const [contract, formats, translations, variants, images, engagement, online, signatures] =
        await Promise.all([
          api(base + '/api-contract'), api(pbase + '/formats'), api(pbase + '/translations'),
          api(pbase + '/variants/select'), api(pbase + '/images'), api(pbase + '/engagement'),
          api(pbase + '/online'), api(base + '/signatures'),
        ]);
      detail = {
        contract: contract || {}, formats: formats || {}, translations: translations || [],
        variant: variants || {}, images: images || [], engagement: engagement || {},
        online: online || {}, signatures: signatures || [],
      };
    }
    data = { templates: templates, selected: selected, detail: detail };
  } catch (err) {
    if (token !== state.viewToken) return;
    renderViewHtml(pageHead('Operations', 'Email engagement', '') + errorBlock(errMessage(err)));
    return;
  }
  if (token !== state.viewToken) return;

  const write = can(P.contactWrite);
  let html = pageHead('Operations', 'Email engagement',
    data.templates.length + ' templates' + (data.selected ? ' Ã‚Â· 9 local features' : ''),
    '<button class="btn" data-action="view-email-contract">' + icon('info', 15) +
      ' Local contract</button>');
  html += governanceNote('Nine email features are backed by additive local tables: HTML/text formats, translations and A/B variants, open pixels, click tokens, bounce and reply monitoring, mailer signatures, base64 inline images and an online render. Tracking tokens are opaque local identifiers; no email is sent, no request leaves the workspace, and no mail provider or hosted service is contacted.');

  html += '<section class="card"><h2 class="page-title">Templates</h2>' +
    (data.templates.length ? '<div class="table-wrap"><table class="data"><thead><tr><th>Name</th>' +
      '<th>Subject</th><th>Formats</th><th></th></tr></thead><tbody>' +
      data.templates.map(function (t) {
        return '<tr><td>' + esc(t.name) + '</td><td>' + esc(t.subject) + '</td><td>' +
          esc((t.has_html ? 'HTML ' : '') + (t.has_text ? 'text' : '').trim()) + '</td><td>' +
          '<button class="btn btn--sm" data-action="email-open-template" data-id="' + attr(t.id) +
          '">Open</button></td></tr>';
      }).join('') + '</tbody></table></div>' : '<p class="muted small">No templates yet.</p>') +
    (write ? '<form data-form="email-template-create"><div class="form-grid">' +
      field('name', 'Name', { required: true }) + field('subject', 'Subject', { required: true }) +
      field('html_body', 'HTML body', { type: 'textarea', span: true, value: '<p>Hello</p>' }) +
      field('text_body', 'Text body', { type: 'textarea', span: true, value: 'Hello' }) +
      '</div><div class="form-actions"><button type="submit" class="btn">' +
      icon('plus', 15) + ' Create template</button></div></form>' : '') + '</section>';

  if (data.detail) {
    const d = data.detail;
    html += '<section class="card"><h2 class="page-title">Content, translations &amp; variants</h2>' +
      '<p class="muted small">Selected variant: ' + esc(d.variant.selected || 'none') +
      ' Ã‚Â· translations: ' + d.translations.length + ' Ã‚Â· images: ' + d.images.length + '</p>' +
      '<pre class="small">' + esc(d.formats.html || d.formats.text || '') + '</pre>' +
      (write ? '<form data-form="email-translation-create"><div class="form-grid">' +
        field('locale', 'Locale', { required: true, placeholder: 'fr-FR' }) +
        field('subject', 'Translated subject', { required: true }) +
        field('html_body', 'HTML body', { type: 'textarea', span: true, value: '' }) +
        field('text_body', 'Text body', { type: 'textarea', span: true, value: '' }) +
        '</div><div class="form-actions"><button type="submit" class="btn">' +
        icon('plus', 15) + ' Add translation</button></div></form>' +
        '<form data-form="email-variant-create"><div class="form-grid">' +
        field('name', 'Variant name', { required: true, placeholder: 'A' }) +
        field('subject', 'Variant subject', { required: true }) +
        field('weight', 'Weight', { type: 'number', value: '1' }) +
        '</div><div class="form-actions"><button type="submit" class="btn">' +
        icon('layers', 15) + ' Add A/B variant</button></div></form>' : '') + '</section>';

    html += '<section class="card"><h2 class="page-title">Local tracking tokens</h2>' +
      '<p class="muted small">Recorded events: ' + (d.engagement.events || 0) + ' Ã‚Â· ' +
      esc(JSON.stringify(d.engagement.by_kind || {})) + '</p>' +
      (write ? '<form data-form="email-token-create"><div class="form-grid">' +
        field('recipient_id', 'Recipient id', { required: true, placeholder: 'contact-1' }) +
        field('target_url', 'Target URL (blank = open pixel)', { placeholder: 'optional' }) +
        '</div><div class="form-actions"><button type="submit" class="btn">' +
        icon('eye', 15) + ' Mint local token</button></div></form>' +
        '<form data-form="email-bounce-create"><div class="form-grid">' +
        field('recipient_id', 'Bounced recipient', { required: true }) +
        field('reason', 'Reason', { placeholder: 'hard' }) +
        '</div><div class="form-actions"><button type="submit" class="btn">' +
        icon('alert', 15) + ' Record bounce</button></div></form>' +
        '<form data-form="email-reply-create"><div class="form-grid">' +
        field('recipient_id', 'Replying recipient', { required: true }) +
        field('subject', 'Reply subject', { placeholder: 'Re: Hello' }) +
        '</div><div class="form-actions"><button type="submit" class="btn">' +
        icon('mail', 15) + ' Record reply</button></div></form>' : '') + '</section>';

    html += '<section class="card"><h2 class="page-title">Mailer signatures &amp; inline images</h2>' +
      '<div class="form-grid">' +
      (write ? '<form data-form="email-signature-save"><div class="form-grid">' +
        field('display_name', 'Display name', { required: true }) +
        field('body_html', 'Signature HTML', { type: 'textarea', span: true, value: '' }) +
        field('is_default', 'Default', { type: 'select', options: selectOptions([['false', 'no'], ['true', 'yes']]) }) +
        '</div><div class="form-actions"><button type="submit" class="btn">' +
        icon('check', 15) + ' Save signature</button></div></form>' +
        '<form data-form="email-image-add"><div class="form-grid">' +
        field('cid', 'Content-ID', { required: true, placeholder: 'logo' }) +
        field('content_type', 'MIME type', { value: 'image/png' }) +
        field('content_base64', 'Base64 content', { type: 'textarea', span: true, required: true }) +
        '</div><div class="form-actions"><button type="submit" class="btn">' +
        icon('plus', 15) + ' Add inline image</button></div></form>' : '') + '</div>' +
      (d.online.html ? '<h3 class="page-title">Online version</h3><pre class="small">' +
        esc(d.online.html) + '</pre><button class="btn btn--sm" data-action="email-online-version">' +
        icon('eye', 15) + ' Refresh online render</button>' : '') + '</section>';
  }
  renderViewHtml(html);
}

async function loadWikiPages(token) {
  if (!can(P.taskRead)) {
    renderViewHtml(pageHead('Operations', 'Wiki pages', '') +
      errorBlock('Your role does not include project access.'));
    return;
  }
  loadingView('Wiki pages', 'Versioned, labelled and locally published project documentation.');
  let data;
  try {
    const base = apiW('/wiki-pages');
    const projects = await api(apiW('/projects')) || [];
    const pageGroups = await Promise.all(projects.map(function (p) {
      return api(apiW('/projects/' + encodeURIComponent(p.id) + '/pages')).catch(function () { return []; });
    }));
    const pages = [];
    projects.forEach(function (project, idx) {
      (pageGroups[idx] || []).forEach(function (page) {
        pages.push({ id: page.id, title: page.title, scope: page.scope,
          project_id: project.id, project_name: project.name });
      });
    });
    const selected = state.wikiPageId || (pages[0] && pages[0].id);
    let detail = null;
    if (selected) {
      const pbase = base + '/pages/' + encodeURIComponent(selected);
      const [contract, revisions, analytics, publication, exports, labels, blocks, comments, editing, tree] =
        await Promise.all([
          api(base + '/api-contract'), api(pbase + '/revisions'), api(pbase + '/analytics'),
          api(pbase + '/publication'), api(pbase + '/exports'), api(pbase + '/labels'),
          api(pbase + '/blocks'), api(pbase + '/comments'), api(pbase + '/editing'),
          api(base + '/trees'),
        ]);
      detail = {
        contract: contract || {}, revisions: revisions || [], analytics: analytics || {},
        publication: publication || {}, exports: exports || [], labels: labels || [],
        blocks: blocks || [], comments: comments || [], editing: editing || [], tree: tree || [],
      };
    }
    data = { pages: pages, selected: selected, detail: detail };
  } catch (err) {
    if (token !== state.viewToken) return;
    renderViewHtml(pageHead('Operations', 'Wiki pages', '') + errorBlock(errMessage(err)));
    return;
  }
  if (token !== state.viewToken) return;

  const write = can(P.taskWrite);
  const pageOptions = selectOptions(data.pages.map(function (p) {
    return [p.id, p.project_name + ' / ' + p.title];
  }));
  const labelOptions = selectOptions(data.detail ?
    data.detail.labels.map(function (l) { return [l.name, l.name]; }) : []);
  let html = pageHead('Operations', 'Wiki pages',
    data.pages.length + ' pages' + (data.selected ? ' Ã‚Â· 8 collaboration features' : ''),
    '<button class="btn" data-action="view-wiki-contract">' + icon('info', 15) +
      ' Local contract</button>');
  html += governanceNote('Eight wiki features are backed by additive, workspace-scoped tables: version history, local view analytics, publish/export, labels, nested pages, collections, typed editor blocks and polling-based co-editing with inline comments. No Django, Channels/WebSocket, React editor package, hosted service or outbound traffic is used. Exports are deterministic local renders.');

  html += '<section class="card"><h2 class="page-title">Project pages</h2>' +
    '<form data-form="wiki-page-select"><div class="form-grid">' +
    field('page_id', 'Page', { type: 'select', options: pageOptions }) +
    '</div><div class="form-actions"><button type="submit" class="btn">' +
    icon('eye', 15) + ' Open page</button></div></form>' +
    (data.pages.length ? '<div class="table-wrap"><table class="data"><thead><tr><th>Project</th>' +
      '<th>Title</th><th>Scope</th></tr></thead><tbody>' +
      data.pages.map(function (p) {
        return '<tr><td>' + esc(p.project_name) + '</td><td>' + esc(p.title) + '</td><td>' +
          esc(p.scope) + '</td></tr>';
      }).join('') + '</tbody></table></div>' : '<p class="muted small">No project pages yet.</p>') +
    '</section>';

  if (data.detail) {
    const d = data.detail;
    html += '<section class="card"><h2 class="page-title">Version history &amp; analytics</h2>' +
      '<p class="muted small">Views: ' + (d.analytics.views || 0) + ' Ã‚Â· Unique visitors: ' +
      (d.analytics.unique_visitors || 0) + ' Ã‚Â· external_calls: ' +
      (!!d.analytics.external_calls) + '</p>' +
      (d.revisions.length ? '<div class="table-wrap"><table class="data"><thead><tr><th>Version</th>' +
        '<th>Title</th><th>Reason</th><th>Author</th><th></th></tr></thead><tbody>' +
        d.revisions.map(function (r) {
          return '<tr><td>' + r.version + '</td><td>' + esc(r.title) + '</td><td>' +
            esc(r.reason || '-') + '</td><td class="mono small">' + esc(r.author_id) + '</td><td>' +
            (write ? '<button class="btn btn--sm" data-action="wiki-restore-revision" data-id="' +
              attr(r.id) + '">Restore</button>' : '-') + '</td></tr>';
        }).join('') + '</tbody></table></div>' : '<p class="muted small">No revisions recorded.</p>') +
      (write ? '<form data-form="wiki-revision"><div class="form-grid">' +
        field('title', 'Title', { required: true }) +
        field('body', 'Body', { type: 'textarea', span: true, value: '' }) +
        field('reason', 'Change reason', { placeholder: 'what changed' }) +
        '</div><div class="form-actions"><button type="submit" class="btn">' +
        icon('edit', 15) + ' Save revision</button></div></form>' +
        '<form data-form="wiki-view"><div class="form-grid">' +
        field('visitor_id', 'Visitor id', { required: true, placeholder: 'local-visitor' }) +
        field('source', 'Source', { placeholder: 'local' }) +
        '</div><div class="form-actions"><button type="submit" class="btn">' +
        icon('eye', 15) + ' Record local view</button></div></form>' : '') + '</section>';

    html += '<section class="card"><h2 class="page-title">Publication &amp; export</h2>' +
      '<p class="muted small">State: ' + (d.publication.published ? 'published' : 'draft') +
      ' Ã‚Â· ' + esc(d.publication.public_url || 'no local URL') + '</p>' +
      (write ? '<form data-form="wiki-publication"><div class="form-grid">' +
        field('published', 'Published', { type: 'select', options: selectOptions([['true', 'yes'], ['false', 'no']]) }) +
        field('slug', 'Local slug', { required: true, placeholder: 'runbook-2026' }) +
        '</div><div class="form-actions"><button type="submit" class="btn">' +
        icon('check', 15) + ' Save publication</button></div></form>' +
        '<form data-form="wiki-export"><div class="form-grid">' +
        field('format', 'Format', { type: 'select', options: selectOptions([['md', 'Markdown'], ['html', 'HTML'], ['txt', 'Plain text']]) }) +
        '</div><div class="form-actions"><button type="submit" class="btn">' +
        icon('archive', 15) + ' Export locally</button></div></form>' : '') +
      (d.exports.length ? '<div class="table-wrap"><table class="data"><thead><tr><th>Format</th>' +
        '<th>Content hash</th><th>When</th></tr></thead><tbody>' +
        d.exports.map(function (e) {
          return '<tr><td>' + esc(e.format) + '</td><td class="mono small">' + esc(e.content_hash) +
            '</td><td class="small">' + esc(e.created_at) + '</td></tr>';
        }).join('') + '</tbody></table></div>' : '') + '</section>';

    html += '<section class="card"><h2 class="page-title">Labels, hierarchy &amp; collections</h2>' +
      '<p class="muted small">Labels: ' + esc(d.labels.map(function (l) { return l.name; }).join(', ') || '-') +
      ' Ã‚Â· Tree nodes: ' + d.tree.length + '</p>' +
      (write ? '<form data-form="wiki-label"><div class="form-grid">' +
        field('name', 'Label name', { required: true, placeholder: 'runbook' }) +
        '</div><div class="form-actions"><button type="submit" class="btn">' +
        icon('tag', 15) + ' Create &amp; attach label</button></div></form>' +
        '<form data-form="wiki-parent"><div class="form-grid">' +
        field('parent_id', 'Parent page id (blank = root)', { placeholder: 'optional' }) +
        field('position', 'Position', { type: 'number', value: '0' }) +
        '</div><div class="form-actions"><button type="submit" class="btn">' +
        icon('layers', 15) + ' Set parent</button></div></form>' +
        '<form data-form="wiki-collection"><div class="form-grid">' +
        field('name', 'Collection name', { required: true, placeholder: 'Launch docs' }) +
        field('description', 'Description', { placeholder: 'optional' }) +
        '</div><div class="form-actions"><button type="submit" class="btn">' +
        icon('plus', 15) + ' Create collection</button></div></form>' : '') + '</section>';

    html += '<section class="card"><h2 class="page-title">Editor blocks &amp; inline comments</h2>' +
      '<p class="muted small">Blocks: ' + d.blocks.length + ' Ã‚Â· Comments: ' + d.comments.length +
      ' Ã‚Â· Active external editors: ' + d.editing.length + '</p>' +
      (d.blocks.length ? '<div class="table-wrap"><table class="data"><thead><tr><th>Position</th>' +
        '<th>Type</th><th>Content</th><th></th></tr></thead><tbody>' +
        d.blocks.map(function (b) {
          return '<tr><td>' + b.position + '</td><td class="mono">' + esc(b.block_type) +
            '</td><td class="small">' + esc(JSON.stringify(b.content)) + '</td><td>' +
            (write ? '<button class="btn btn--sm" data-action="wiki-comment-block" data-id="' +
              attr(b.id) + '">Comment</button>' : '-') + '</td></tr>';
        }).join('') + '</tbody></table></div>' : '<p class="muted small">No editor blocks.</p>') +
      (d.comments.length ? '<div class="table-wrap"><table class="data"><thead><tr><th>Block</th>' +
        '<th>Comment</th><th>Resolved</th><th></th></tr></thead><tbody>' +
        d.comments.map(function (c) {
          return '<tr><td class="mono small">' + esc(c.block_id || '-') + '</td><td>' + esc(c.body) +
            '</td><td>' + statusBadge(c.resolved ? 'resolved' : 'open') + '</td><td>' +
            (write && !c.resolved ? '<button class="btn btn--sm" data-action="wiki-resolve-comment" data-id="' +
              attr(c.id) + '">Resolve</button>' : '-') + '</td></tr>';
        }).join('') + '</tbody></table></div>' : '') +
      (write ? '<form data-form="wiki-blocks"><div class="form-grid">' +
        field('blocks', 'Blocks JSON', { type: 'textarea', span: true, required: true,
          value: '[{"block_type":"paragraph","content":{"text":"Hello"},"position":0}]',
          placeholder: 'typed block array' }) +
        '</div><div class="form-actions"><button type="submit" class="btn">' +
        icon('edit', 15) + ' Save blocks</button></div></form>' +
        '<form data-form="wiki-editing"><div class="form-grid">' +
        field('ttl_seconds', 'Lease seconds (5-300)', { type: 'number', value: '60' }) +
        '</div><div class="form-actions"><button type="submit" class="btn">' +
        icon('clock', 15) + ' Start local edit lease</button></div></form>' : '') + '</section>';
  }
  renderViewHtml(html);
}

async function loadWorkItemPlanning(token) {
  if (!can(P.taskRead)) {
    renderViewHtml(pageHead('Operations', 'Work-item planning', '') +
      errorBlock('Your role does not include project access.'));
    return;
  }
  loadingView('Work-item planning', 'Relations, dependencies, estimates and local planning views.');
  let data;
  try {
    const base = apiW('/work-item-planning');
    const projects = await api(apiW('/projects')) || [];
    const groups = await Promise.all(projects.map(function (p) {
      const itemPath = ['/projects/', encodeURIComponent(p.id), '/items'].join('');
      return api(apiW(itemPath)).catch(function () { return []; });
    }));
    const items = [];
    projects.forEach(function (project, idx) {
      (groups[idx] || []).forEach(function (item) {
        items.push({ id: item.id, title: item.title, project_id: item.project_id,
          project_name: project.name, status: item.status });
      });
    });
    const selected = state.planningItemId || (items[0] && items[0].id);
    const contract = await api(base + '/api-contract');
    const templates = await api(base + '/templates') || [];
    const schemes = await api(base + '/estimate-schemes') || [];
    let detail = null;
    if (selected) {
      const pbase = base + '/items/' + encodeURIComponent(selected);
      const [relations, dependencies, estimates, calendar, roadmap, timeline, updates,
        recurrences, logs, subscribers, recipients, aggregate] = await Promise.all([
          api(pbase + '/relations'), api(pbase + '/dependencies'), api(pbase + '/estimates'),
          api(base + '/calendar'), api(base + '/roadmap'), api(base + '/timeline'),
          api(pbase + '/updates'), api(pbase + '/recurrences'), api(pbase + '/time-logs'),
          api(pbase + '/subscribers'), api(pbase + '/notification-recipients'),
          api(base + '/estimates/aggregate'),
        ]);
      detail = {
        relations: relations || [], dependencies: dependencies || [], estimates: estimates || [],
        calendar: calendar || {}, roadmap: roadmap || {}, timeline: timeline || {},
        updates: updates || [], recurrences: recurrences || [], logs: logs || {},
        subscribers: subscribers || {}, recipients: recipients || {}, aggregate: aggregate || {},
      };
    }
    data = { items: items, selected: selected, contract: contract || {},
      templates: templates, schemes: schemes, detail: detail };
  } catch (err) {
    if (token !== state.viewToken) return;
    renderViewHtml(pageHead('Operations', 'Work-item planning', '') + errorBlock(errMessage(err)));
    return;
  }
  if (token !== state.viewToken) return;

  const write = can(P.taskWrite);
  const d = data.detail || {};
  const itemOptions = selectOptions(data.items.map(function (i) {
    return [i.id, i.project_name + ' / ' + i.title];
  }), data.selected);
  const targetOptions = selectOptions(data.items.map(function (i) {
    return [i.id, i.title];
  }));
  const schemeOptions = selectOptions(data.schemes.map(function (s) {
    return [s.id, s.name + ' (' + s.kind + ')'];
  }));
  const templateOptions = selectOptions(data.templates.map(function (t) {
    return [t.id, t.name + ' (' + t.target_kind + ')'];
  }));
  let html = pageHead('Operations', 'Work-item planning',
    data.items.length + ' work items' + (data.selected ? ' Ã‚Â· 12 planning features' : ''),
    '<button class="btn" data-action="view-planning-contract">' + icon('info', 15) +
      ' Local contract</button>');
  html += governanceNote('Twelve Plane P2 planning features are backed by additive, workspace-scoped tables and local derived views: inverse relations, typed dependencies with conflict markers, estimate schemes with project/cycle aggregates, roadmap, calendar and timeline layouts, an editable table, status updates, templates, on-demand recurrence, worklogs and subscriber-driven recipients. There is no Plane source, Django/React dependency, scheduler daemon, websocket transport or outbound traffic.');

  html += '<section class="card"><h2 class="page-title">Work items</h2>' +
    '<form data-form="planning-item-select"><div class="form-grid">' +
    field('item_id', 'Open work item', { type: 'select', options: itemOptions }) +
    '</div><div class="form-actions"><button type="submit" class="btn">' +
    icon('eye', 15) + ' Open item</button></div></form>' +
    (data.items.length ? '<div class="table-wrap"><table class="data"><thead><tr><th>Project</th>' +
      '<th>Title</th><th>Status</th></tr></thead><tbody>' +
      data.items.slice(0, 40).map(function (i) {
        return '<tr><td>' + esc(i.project_name) + '</td><td>' +
          '<button class="btn btn--sm btn--ghost" data-action="planning-open-item" data-id="' +
          attr(i.id) + '">' + esc(i.title) + '</button></td><td>' + esc(i.status) + '</td></tr>';
      }).join('') + '</tbody></table></div>' : '<p class="muted small">No work items yet.</p>') +
    '</section>';

  if (!data.selected) {
    renderViewHtml(html);
    return;
  }

  html += '<section class="card"><h2 class="page-title">Relations &amp; dependencies</h2>' +
    '<p class="muted small">Relations: ' + d.relations.length + ' Ã‚Â· dependencies: ' +
    d.dependencies.length + ' Ã‚Â· timeline conflicts: ' + (d.timeline.dependency_markers || 0) + '</p>' +
    '<div class="table-wrap"><table class="data"><thead><tr><th>Kind</th><th>Other item</th>' +
    '<th>Violation</th></tr></thead><tbody>' +
    d.relations.map(function (r) {
      return '<tr><td>' + esc(r.relation_type) + '</td><td class="mono small">' +
        esc(r.target_item_id) + '</td><td>-</td></tr>';
    }).join('') +
    d.dependencies.map(function (r) {
      return '<tr><td>' + esc(r.kind) + '</td><td class="mono small">' +
        esc(r.depends_on_id) + '</td><td>' + (r.violation ?
          '<span class="badge badge--danger">conflict</span> ' + esc(r.reason) : 'clear') + '</td></tr>';
    }).join('') + '</tbody></table></div>' +
    (write ? '<form data-form="planning-relation"><div class="form-grid">' +
      field('target_item_id', 'Related item', { type: 'select', options: targetOptions }) +
      field('relation_type', 'Relation', { type: 'select', options: selectOptions([
        'relates_to', 'duplicate_of', 'implements', 'implemented_by']) }) +
      field('note', 'Note', { span: true, placeholder: 'optional' }) +
      '</div><div class="form-actions"><button type="submit" class="btn">' +
      icon('link', 15) + ' Create with inverse</button></div></form>' +
      '<form data-form="planning-dependency"><div class="form-grid">' +
      field('depends_on_id', 'Depends on item', { type: 'select', options: targetOptions }) +
      field('kind', 'Dependency type', { type: 'select', options: selectOptions([
        'blocked_by', 'blocking', 'start_after', 'finish_before']) }) +
      field('target_date', 'Target date (optional)', { placeholder: '2026-12-01T00:00:00+00:00' }) +
      '</div><div class="form-actions"><button type="submit" class="btn">' +
      icon('link', 15) + ' Add dependency</button></div></form>' : '') + '</section>';

  html += '<section class="card"><h2 class="page-title">Estimates</h2>' +
    '<p class="muted small">Project total points: ' + (d.aggregate.total_points || 0) +
      ' Ã‚Â· hours: ' + (d.aggregate.total_hours || 0) + ' Ã‚Â· categories: ' +
      esc(JSON.stringify(d.aggregate.by_category || {})) + '</p>' +
    '<div class="table-wrap"><table class="data"><thead><tr><th>Scheme</th><th>Value</th>' +
    '<th>Category</th></tr></thead><tbody>' +
    d.estimates.map(function (e) {
      return '<tr><td>' + esc(e.scheme) + '</td><td>' + esc(e.value) + '</td><td>' +
        esc(e.category || '-') + '</td></tr>';
    }).join('') + '</tbody></table></div>' +
    (write ? '<form data-form="planning-scheme"><div class="form-grid">' +
      field('name', 'Scheme name', { required: true }) +
      field('kind', 'Kind', { type: 'select', options: selectOptions(['points', 'category', 'hours']) }) +
      field('values', 'Allowed values JSON', { type: 'textarea', span: true,
        value: '{"low": 1, "high": 2}' }) +
      '</div><div class="form-actions"><button type="submit" class="btn">' +
      icon('plus', 15) + ' Create scheme</button></div></form>' +
      '<form data-form="planning-estimate"><div class="form-grid">' +
      field('scheme_id', 'Scheme', { type: 'select', options: schemeOptions }) +
      field('value', 'Value', { type: 'number', value: '1' }) +
      field('category', 'Category (category schemes)', {}) +
      '</div><div class="form-actions"><button type="submit" class="btn">' +
      icon('check', 15) + ' Save estimate</button></div></form>' : '') + '</section>';

  html += '<section class="card"><h2 class="page-title">Roadmap, calendar &amp; timeline</h2>' +
    '<p class="muted small">Roadmap groups: ' + (d.roadmap.groups || []).length +
      ' Ã‚Â· calendar entries: ' + (d.calendar.total || 0) + ' Ã‚Â· timeline rows: ' +
      (d.timeline.rows || []).length + '</p>' +
    '<div class="table-wrap"><table class="data"><thead><tr><th>View</th><th>Local grouping</th>' +
    '<th>Items</th></tr></thead><tbody>' +
    (d.roadmap.groups || []).map(function (g) {
      return '<tr><td>roadmap</td><td>' + esc(g.month) + ' / ' + esc(g.project_name) +
        '</td><td>' + g.items.length + '</td></tr>';
    }).join('') +
    Object.keys(d.calendar.groups || {}).map(function (day) {
      return '<tr><td>calendar</td><td>' + esc(day) + '</td><td>' +
        d.calendar.groups[day].length + '</td></tr>';
    }).join('') +
    (d.timeline.rows || []).map(function (r) {
      return '<tr><td>timeline</td><td>' + esc(r.label) + '</td><td>' + esc(r.kind) + '</td></tr>';
    }).join('') + '</tbody></table></div>' +
    (write ? '<form data-form="planning-schedule"><div class="form-grid">' +
      field('start_at', 'Start at', { placeholder: '2026-12-01T09:00:00+00:00' }) +
      field('due_at', 'Due at', { placeholder: '2026-12-05T17:00:00+00:00' }) +
      '</div><div class="form-actions"><button type="submit" class="btn">' +
      icon('clock', 15) + ' Save schedule</button></div></form>' +
      '<form data-form="planning-cell"><div class="form-grid">' +
      field('field', 'Column', { type: 'select', options: selectOptions([
        'title', 'status', 'priority', 'assignee_id', 'due_at', 'start_at']) }) +
      field('value', 'New value', { required: true }) +
      '</div><div class="form-actions"><button type="submit" class="btn">' +
      icon('edit', 15) + ' Apply inline edit</button></div></form>' : '') + '</section>';

  html += '<section class="card"><h2 class="page-title">Updates, recurrence, worklogs &amp; subscribers</h2>' +
    '<p class="muted small">Updates: ' + d.updates.length + ' Ã‚Â· worklog total: ' +
      (d.logs.total_minutes || 0) + ' minutes Ã‚Â· recipients: ' +
      (d.recipients.recipients || []).length + '</p>' +
    '<div class="table-wrap"><table class="data"><thead><tr><th>Record</th><th>Detail</th>' +
    '<th></th></tr></thead><tbody>' +
    d.updates.map(function (u) {
      return '<tr><td>update</td><td>' + esc(u.body) + ' Ã‚Â· sub-items ' + u.sub_items_done + '/' +
        u.sub_items_total + '</td><td></td></tr>';
    }).join('') +
    d.recurrences.map(function (r) {
      return '<tr><td>recurrence</td><td>' + esc(r.frequency) + ' Ã‚Â· next ' + esc(r.next_at) +
        '</td><td>' + (write ? '<button class="btn btn--sm" data-action="planning-materialize" data-id="' +
        attr(r.id) + '">Materialize</button>' : '') + '</td></tr>';
    }).join('') +
    (d.logs.entries || []).map(function (l) {
      return '<tr><td>worklog</td><td>' + l.minutes + ' min Ã‚Â· ' + esc(l.note) + '</td><td></td></tr>';
    }).join('') +
    (d.subscribers.subscribers || []).map(function (uid) {
      return '<tr><td>subscriber</td><td class="mono small">' + esc(uid) + '</td><td>' +
        (write ? '<button class="btn btn--sm btn--ghost" data-action="planning-unsubscribe" data-id="' +
        attr(uid) + '">Remove</button>' : '') + '</td></tr>';
    }).join('') + '</tbody></table></div>' +
    (write ? '<form data-form="planning-update"><div class="form-grid">' +
      field('body', 'Status update', { type: 'textarea', span: true, required: true }) +
      '</div><div class="form-actions"><button type="submit" class="btn">' +
      icon('note', 15) + ' Post update</button></div></form>' +
      '<form data-form="planning-recurrence"><div class="form-grid">' +
      field('frequency', 'Frequency', { type: 'select', options: selectOptions([
        'daily', 'weekly', 'monthly']) }) +
      field('interval', 'Interval', { type: 'number', value: '1' }) +
      field('next_at', 'Next at', { value: '2026-12-01T09:00:00+00:00' }) +
      '</div><div class="form-actions"><button type="submit" class="btn">' +
      icon('refresh', 15) + ' Save recurrence</button></div></form>' +
      '<form data-form="planning-time-log"><div class="form-grid">' +
      field('minutes', 'Minutes', { type: 'number', required: true, value: '30' }) +
      field('note', 'Note', {}) +
      '</div><div class="form-actions"><button type="submit" class="btn">' +
      icon('clock', 15) + ' Log time</button></div></form>' +
      '<form data-form="planning-subscribe"><div class="form-grid">' +
      field('user_id', 'Subscriber user id', { required: true }) +
      '</div><div class="form-actions"><button type="submit" class="btn">' +
      icon('bell', 15) + ' Subscribe</button></div></form>' : '') + '</section>';

  html += '<section class="card"><h2 class="page-title">Templates</h2>' +
    '<p class="muted small">Stored templates prefill new items, projects and pages locally.</p>' +
    '<div class="table-wrap"><table class="data"><thead><tr><th>Name</th><th>Target</th>' +
    '</tr></thead><tbody>' + data.templates.map(function (t) {
      return '<tr><td>' + esc(t.name) + '</td><td>' + esc(t.target_kind) + '</td></tr>';
    }).join('') + '</tbody></table></div>' +
    (write ? '<form data-form="planning-template"><div class="form-grid">' +
      field('name', 'Template name', { required: true }) +
      field('target_kind', 'Target', { type: 'select', options: selectOptions([
        'item', 'project', 'page']) }) +
      field('payload', 'Payload JSON', { type: 'textarea', span: true,
        value: '{"title": "Prefilled", "priority": "high"}' }) +
      '</div><div class="form-actions"><button type="submit" class="btn">' +
      icon('plus', 15) + ' Create template</button></div></form>' +
      '<form data-form="planning-instantiate"><div class="form-grid">' +
      field('template_id', 'Template', { type: 'select', options: templateOptions }) +
      field('project_id', 'Project id (optional)', {}) +
      field('title', 'Override title (optional)', {}) +
      '</div><div class="form-actions"><button type="submit" class="btn">' +
      icon('check', 15) + ' Instantiate</button></div></form>' : '') + '</section>';

  renderViewHtml(html);
}

async function loadWorkCollaboration(token) {
  if (!can(P.taskRead)) {
    renderViewHtml(pageHead('Operations', 'Work collaboration', '') +
      errorBlock('Your role does not include project access.'));
    return;
  }
  loadingView('Work collaboration', 'Attachments, mentions, team activity, cursor pages and item restrictions backed by local records.');
  const base = apiW('/work-collab');
  const perPage = Number(state.collabPerPage || 5);
  let data;
  try {
    const projects = await api(apiW('/projects')) || [];
    const groups = await Promise.all(projects.map(function (p) {
      const path = ['/projects/', encodeURIComponent(p.id), '/items'].join('');
      return api(apiW(path)).catch(function () { return []; });
    }));
    const items = [];
    projects.forEach(function (project, idx) {
      (groups[idx] || []).forEach(function (item) {
        items.push({ id: item.id, title: item.title, project_id: item.project_id,
          project_name: project.name, status: item.status });
      });
    });
    const projectId = state.collabProjectId ||
      (items.find(function (i) { return i.project_id === state.collabProjectId; }) || items[0] || {}).project_id ||
      (projects[0] && projects[0].id);
    const itemId = state.collabItemId ||
      (items.find(function (i) { return i.project_id === projectId; }) || items[0] || {}).id;
    const files = await api(apiW('/storage/files')) || [];
    const contract = await api(base + '/api-contract') || {};
    let cursor = null;
    if (projectId) {
      const cursorPath = base + '/projects/' + encodeURIComponent(projectId) +
        '/items/cursor?per_page=' + encodeURIComponent(perPage) +
        (state.collabCursor ? '&cursor=' + encodeURIComponent(state.collabCursor) : '');
      cursor = await api(cursorPath);
    }
    let collaboration = null;
    if (projectId) {
      collaboration = await api(base + '/projects/' + encodeURIComponent(projectId) + '/collaboration');
    }
    let detail = null;
    if (itemId) {
      const pbase = base + '/items/' + encodeURIComponent(itemId);
      const [attachments, mentions, shaped, restriction, guarded] = await Promise.all([
        api(pbase + '/attachments'), api(pbase + '/mentions'),
        api(pbase + '/shaped'), api(pbase + '/restriction'), api(pbase + '/guarded'),
      ]);
      detail = {
        attachments: attachments || {}, mentions: mentions || {}, shaped: shaped || {},
        restriction: restriction || {}, guarded: guarded || {},
      };
    }
    data = {
      projects: projects, items: items, files: files, contract: contract,
      projectId: projectId || '', itemId: itemId || '', cursor: cursor,
      collaboration: collaboration || {}, detail: detail, perPage: perPage,
    };
  } catch (err) {
    if (token !== state.viewToken) return;
    renderViewHtml(pageHead('Operations', 'Work collaboration', '') + errorBlock(errMessage(err)));
    return;
  }
  if (token !== state.viewToken) return;

  state.caches.collabItems = data.items;
  const write = can(P.taskWrite);
  const d = data.detail || {};
  const collaboration = data.collaboration || {};
  const projectOptions = selectOptions(data.projects.map(function (p) {
    return [p.id, p.name];
  }), data.projectId);
  const itemOptions = selectOptions(data.items.map(function (i) {
    return [i.id, i.project_name + ' / ' + i.title];
  }), data.itemId);
  const fileOptions = selectOptions(data.files.map(function (f) {
    return [f.id, f.original_name || f.name || f.id];
  }));
  let html = pageHead('Operations', 'Work collaboration',
    data.items.length + ' work items Ã‚Â· ' + data.files.length + ' stored files',
    '<button class="btn" data-action="view-collab-contract">' + icon('info', 15) +
      ' Local contract</button>');
  html += governanceNote('Eight Plane capabilities are backed by additive, workspace-scoped records: work-item attachments, mentions, team collaboration, opaque cursor pages, field projection and expansion, a generated local contract, item restrictions and provider-neutral CSV import. No Plane source, Django transport, hosted endpoint, outbound HTTP or external import provider is claimed.');

  html += '<section class="card"><h2 class="page-title">Scope</h2><div class="form-grid">' +
    '<form data-form="collab-project-select">' +
    field('project_id', 'Project', { type: 'select', options: projectOptions }) +
    '<div class="form-actions"><button type="submit" class="btn btn--sm">' +
    icon('folder', 15) + ' Open project</button></div></form>' +
    '<form data-form="collab-item-select">' +
    field('item_id', 'Work item', { type: 'select', options: itemOptions }) +
    '<div class="form-actions"><button type="submit" class="btn btn--sm">' +
    icon('eye', 15) + ' Open item</button></div></form>' +
    '</div>' + (data.items.length ? '<div class="table-wrap"><table class="data"><thead><tr>' +
    '<th>Project</th><th>Work item</th><th>Status</th></tr></thead><tbody>' +
    data.items.slice(0, 40).map(function (i) {
      return '<tr><td>' + esc(i.project_name) + '</td><td>' +
        '<button class="btn btn--sm btn--ghost" data-action="collab-open-item" data-id="' +
        attr(i.id) + '" data-project="' + attr(i.project_id) + '">' + esc(i.title) + '</button>' +
        '</td><td>' + esc(i.status) + '</td></tr>';
    }).join('') + '</tbody></table></div>' : '<p class="muted small">Create a project work item first.</p>') +
    '</section>';

  if (data.projectId && data.cursor) {
    html += '<section class="card"><h2 class="page-title">Cursor pages &amp; CSV import</h2>' +
      '<p class="muted small">Offset ' + data.cursor.offset + ' Ã‚Â· ' + data.cursor.count +
      ' rows on this page Ã‚Â· more: ' + (data.cursor.has_more ? 'yes' : 'no') +
      ' Ã‚Â· cursors are opaque local records.</p>' +
      '<div class="table-wrap"><table class="data"><thead><tr><th>Title</th><th>Status</th>' +
      '</tr></thead><tbody>' + data.cursor.rows.map(function (r) {
        return '<tr><td>' + esc(r.title) + '</td><td>' + esc(r.status) + '</td></tr>';
      }).join('') + '</tbody></table></div>' +
      '<div class="form-actions">' +
      (data.cursor.prev_cursor ? '<button class="btn btn--sm" data-action="collab-cursor-prev" data-cursor="' +
        attr(data.cursor.prev_cursor) + '">Previous</button>' : '') +
      (data.cursor.next_cursor ? '<button class="btn btn--sm" data-action="collab-cursor-next" data-cursor="' +
        attr(data.cursor.next_cursor) + '">Next</button>' : '') + '</div>' +
      '<form data-form="collab-cursor-page"><div class="form-grid">' +
      field('per_page', 'Rows per page', { type: 'number', value: String(data.perPage) }) +
      field('cursor', 'Opaque cursor (optional)', { value: state.collabCursor || '' }) +
      '</div><div class="form-actions"><button type="submit" class="btn btn--sm">' +
      icon('refresh', 15) + ' Apply page</button></div></form>' +
      (write ? '<form data-form="collab-csv-import"><div class="form-grid">' +
        field('csv_text', 'Provider-neutral CSV', { type: 'textarea', span: true, required: true,
          placeholder: 'title,priority,status,description,tags\nImported item,high,todo,Description,alpha|beta' }) +
        '</div><div class="form-actions"><button type="submit" class="btn btn--sm">' +
        icon('archive', 15) + ' Import into this project</button></div></form>' : '') +
      '</section>';
  }

  if (!data.itemId) {
    renderViewHtml(html);
    return;
  }

  html += '<section class="card"><h2 class="page-title">Attachments &amp; mentions</h2>' +
    '<p class="muted small">Attachments: ' + (d.attachments.attachments || []).length +
    ' Ã‚Â· mentions: ' + (d.mentions.mentions || []).length +
    ' Ã‚Â· item visible: ' + (d.guarded.guarded ? 'yes' : 'no') + '</p>' +
    '<div class="table-wrap"><table class="data"><thead><tr><th>Kind</th><th>Detail</th>' +
    '</tr></thead><tbody>' +
    (d.attachments.attachments || []).map(function (a) {
      return '<tr><td>attachment</td><td>' + esc(a.file_name) + ' Ã‚Â· ' + a.size_bytes +
        ' bytes Ã‚Â· ' + esc(a.label || '') + '</td></tr>';
    }).join('') +
    (d.mentions.mentions || []).map(function (m) {
      return '<tr><td>mention</td><td class="mono small">' + esc(m.user_id) + ' Ã‚Â· ' +
        esc(m.source) + '</td></tr>';
    }).join('') + '</tbody></table></div>' +
    (write ? '<form data-form="collab-attachment-add"><div class="form-grid">' +
      field('file_id', 'Stored file', { type: 'select', options: fileOptions }) +
      field('label', 'Label (optional)', {}) +
      '</div><div class="form-actions"><button type="submit" class="btn btn--sm">' +
      icon('link', 15) + ' Attach stored bytes</button></div></form>' +
      '<form data-form="collab-mention-create"><div class="form-grid">' +
      field('user_ids', 'User IDs (comma separated)', { required: true }) +
      field('source', 'Source', { type: 'select', options: selectOptions(['comment', 'description']) }) +
      field('comment_id', 'Comment ID (optional)', {}) +
      field('body', 'Mention body', { type: 'textarea', span: true, required: true }) +
      '</div><div class="form-actions"><button type="submit" class="btn btn--sm">' +
      icon('bell', 15) + ' Mention &amp; subscribe locally</button></div></form>' : '') +
    '</section>';

  html += '<section class="card"><h2 class="page-title">Team collaboration, shaping &amp; restrictions</h2>' +
    '<p class="muted small">Activity: ' + (collaboration.activity || []).length +
    ' Ã‚Â· comments: ' + (collaboration.comments || []).length +
    ' Ã‚Â· shaped fields: ' + ((d.shaped.fields || []).length) +
    ' Ã‚Â· allowed users: ' + ((d.restriction.allowed_user_ids || []).length) + '</p>' +
    '<div class="table-wrap"><table class="data"><thead><tr><th>Kind</th><th>Detail</th>' +
    '</tr></thead><tbody>' +
    (collaboration.activity || []).map(function (a) {
      return '<tr><td>activity</td><td>' + esc(a.kind) + ' Ã‚Â· ' + esc(JSON.stringify(a.detail)) +
        '</td></tr>';
    }).join('') +
    (collaboration.comments || []).map(function (c) {
      return '<tr><td>comment</td><td>' + esc(c.body) + '</td></tr>';
    }).join('') + '</tbody></table></div>' +
    (write ? '<form data-form="collab-team-note"><div class="form-grid">' +
      field('body', 'Team note', { type: 'textarea', span: true, required: true }) +
      '</div><div class="form-actions"><button type="submit" class="btn btn--sm">' +
      icon('note', 15) + ' Add to shared activity</button></div></form>' + '' : '') +
    (write ? '<form data-form="collab-restriction-set"><div class="form-grid">' +
      field('allowed_user_ids', 'Allowed user IDs (comma separated)', { required: true }) +
      field('reason', 'Reason', {}) +
      '</div><div class="form-actions"><button type="submit" class="btn btn--sm">' +
      icon('lock', 15) + ' Apply item restriction</button></div></form>' : '') +
    '<div class="form-actions">' +
    '<button class="btn btn--sm" data-action="collab-guarded-open" data-id="' + attr(data.itemId) + '">' +
    icon('eye', 15) + ' Open guarded item</button></div>' +
    '<form data-form="collab-shape"><div class="form-grid">' +
    field('fields', 'Fields (comma separated)', { value: (d.shaped.fields || []).join(',') }) +
    field('expand', 'Expansions (comma separated)', { value: (d.shaped.expansions || []).join(',') }) +
    '</div><div class="form-actions"><button type="submit" class="btn btn--sm">' +
    icon('layers', 15) + ' Preview shaped item</button></div></form>' +
    '</section>';

  renderViewHtml(html);
}

async function loadAccessGovernance(token) {
  const base = apiW("/access-governance");
  try {
    const [perms, roles, schemes, audit] = await Promise.all([
      api(base + '/permissions').catch(() => ({ allow_list: [], governance_permissions: [] })),
      api(base + '/custom-roles').catch(() => []),
      api(base + '/schemes').catch(() => []),
      api(base + '/audit?limit=20').catch(() => ({ items: [], count: 0, ip_recorded: false })),
    ]);
    const roleRows = Array.isArray(roles) ? roles : (roles.items || []);
    const schemeRows = Array.isArray(schemes) ? schemes : (schemes.items || []);
    const auditRows = (audit && audit.items) ? audit.items : [];
    el.content.innerHTML = `
      <div class="page-header"><div><h1 class="page-title">Access governance</h1><p class="page-subtitle">Clean-room custom roles, permission schemes, fine-grained NV-070 permissions and immutable audit. No upstream source is copied. No external service, licence server or hosted control plane is contacted. IP data is never invented.</p></div>
      <div class="page-actions"><button class="btn btn-secondary btn-sm" data-action="view-access-governance-contract">Contract</button></div></div>
      <div class="card-grid">
        <div class="card"><div class="card-title">Custom roles</div><div class="card-value">${roleRows.length}</div></div>
        <div class="card"><div class="card-title">Permission schemes</div><div class="card-value">${schemeRows.length}</div></div>
        <div class="card"><div class="card-title">Audit rows</div><div class="card-value">${audit.count ?? auditRows.length}</div></div>
        <div class="card"><div class="card-title">Allow-listed permissions</div><div class="card-value">${(perms.allow_list||[]).length}</div></div>
      </div>
      <div class="section-grid">
        <div class="section-panel">
          <div class="section-title">Create custom role (CW-130/PL-124)</div>
          <form data-form="ag-custom-role-create" class="stack-form">
            <label>Slug<input name="slug" required placeholder="auditor-lite"></label>
            <label>Name<input name="name" required placeholder="Auditor Lite"></label>
            <label>Permissions (comma separated)<input name="permissions" placeholder="audit:read,contact:read"></label>
            <button class="btn btn-primary btn-sm" type="submit">Create role</button>
          </form>
          <div class="section-title" style="margin-top:16px">Assign / revoke</div>
          <form data-form="ag-custom-role-assign" class="stack-form">
            <label>Role ID<input name="role_id" required></label>
            <label>User ID<input name="user_id" required></label>
            <button class="btn btn-secondary btn-sm" type="submit">Assign</button>
          </form>
          <form data-form="ag-custom-role-revoke" class="stack-form" style="margin-top:8px">
            <label>Role ID<input name="role_id" required></label>
            <label>User ID<input name="user_id" required></label>
            <button class="btn btn-secondary btn-sm" type="submit">Revoke</button>
          </form>
        </div>
        <div class="section-panel">
          <div class="section-title">Permission scheme (PL-125)</div>
          <form data-form="ag-scheme-create" class="stack-form">
            <label>Name<input name="name" required placeholder="Restricted project"></label>
            <label>Grants JSON<input name="grants" placeholder='{"read_only":["contact:read"]}'></label>
            <button class="btn btn-primary btn-sm" type="submit">Create scheme</button>
          </form>
          <form data-form="ag-scheme-assign" class="stack-form" style="margin-top:8px">
            <label>Scheme ID<input name="scheme_id" required></label>
            <label>Project ID<input name="project_id" required></label>
            <button class="btn btn-secondary btn-sm" type="submit">Assign scheme</button>
          </form>
          <div class="section-title" style="margin-top:16px">NV-070 permission check</div>
          <form data-form="ag-permission-check" class="stack-form">
            <label>Permission<input name="permission" required placeholder="notification_workflow:read"></label>
            <button class="btn btn-secondary btn-sm" type="submit">Check my permission</button>
          </form>
        </div>
      </div>
      <div class="section-panel" style="margin-top:16px">
        <div class="section-title">Recent audit (CW-139) - real stored fields only, ip_recorded=${String(audit.ip_recorded)}</div>
        <div class="table-wrap"><table class="data-table"><thead><tr><th>seq</th><th>type</th><th>actor</th><th>entity</th><th>occurred</th></tr></thead><tbody>
          ${auditRows.map(r => `<tr><td>${esc(r.seq)}</td><td>${esc(r.event_type)}</td><td>${esc(r.actor_id||'')}</td><td>${esc(r.entity_id||'')}</td><td>${esc(r.occurred_at||'')}</td></tr>`).join('') || '<tr><td colspan="5">No audit rows.</td></tr>'}
        </tbody></table></div>
      </div>
      <div class="section-panel" style="margin-top:16px"><div class="section-title">Custom roles</div><pre class="code-block">${esc(JSON.stringify(roleRows, null, 2))}</pre></div>
      <div class="section-panel" style="margin-top:16px"><div class="section-title">Schemes</div><pre class="code-block">${esc(JSON.stringify(schemeRows, null, 2))}</pre></div>
    `;
  } catch (err) {
    el.content.innerHTML = `<div class="error-state"><p>${esc(err.message)}</p></div>`;
  }
}

async function loadFlagGovernance(token) {
  if (!can(P.contactRead)) {
    renderViewHtml(pageHead('Operations', 'Flag governance', '') +
      errorBlock('Your role does not include insight access.'));
    return;
  }
  loadingView('Flag governance', 'Clean-room scheduling, secure attributes, sticky bucketing, prerequisites, redirects, inheritance, templates, guardrails, ramps, revisions and typed configs over local records.');
  const base = apiW('/flag-governance');
  let data;
  try {
    const contract = await api(base + '/api-contract') || {};
    const settings = await api(base + '/settings') || {};
    const templates = await api(base + '/templates') || [];
    const configs = await api(base + '/configs') || [];
    data = { contract: contract, settings: settings, templates: templates, configs: configs };
  } catch (err) {
    if (token !== state.viewToken) return;
    renderViewHtml(pageHead('Operations', 'Flag governance', '') + errorBlock(errMessage(err)));
    return;
  }
  if (token !== state.viewToken) return;

  const write = can(P.noteWrite);
  const contract = data.contract || {};
  let html = pageHead('Operations', 'Flag governance',
    (contract.capabilities || []).length + ' local capabilities',
    '<button class="btn" data-action="view-flag-governance-contract">' + icon('info', 15) +
      ' Local contract</button>');
  html += governanceNote('Fourteen GrowthBook commercial capabilities are implemented locally from the documented public method: scheduled flags, salted secure attributes, sticky bucketing, prerequisites and targeting, redirect results, environment inheritance, templates, guardrail safe rollouts, require-project settings, ramp schedules, scheduled revisions and typed configs. No GrowthBook source, SDK, hosted endpoint, licence server, warehouse or external service is used.');

  html += '<section class="card"><h2 class="page-title">Workspace settings</h2>' +
    '<p class="muted small">Projects required for features: ' +
    String(!!data.settings.require_project_for_features) + ' Â· projects required for SDK keys: ' +
    String(!!data.settings.require_project_for_sdk) + '</p>' +
    (write ? '<form data-form="fg-settings-save"><div class="form-grid">' +
      field('require_project_for_features', 'Require project for features', { type: 'select', options: selectOptions([['false', 'No'], ['true', 'Yes']], String(!!data.settings.require_project_for_features)) }) +
      field('require_project_for_sdk', 'Require project for SDK keys', { type: 'select', options: selectOptions([['false', 'No'], ['true', 'Yes']], String(!!data.settings.require_project_for_sdk)) }) +
      '</div><div class="form-actions"><button class="btn btn--sm" type="submit">Save settings</button></div></form>' : '') +
    '</section>';

  html += '<section class="card"><h2 class="page-title">Scheduling, security and bucketing</h2>' +
    '<div class="form-grid">' +
    (write ? '<form data-form="fg-schedule-create">' + field('flag_key', 'Flag key', { required: true }) +
      field('starts_at', 'Starts at (ISO)', { value: '2026-06-01T00:00:00Z', required: true }) +
      field('state_json', 'State (JSON)', { type: 'textarea', span: true, value: '{"state":"variant","value":"b"}' }) +
      '<div class="form-actions"><button class="btn btn--sm" type="submit">Add schedule</button></div></form>' : '') +
    (write ? '<form data-form="fg-secure-attr">' + field('flag_key', 'Flag key', { required: true }) +
      field('attribute', 'Attribute', { required: true }) + field('salt', 'Salt', { value: 'local-salt' }) +
      field('value', 'Value', { required: true }) +
      '<div class="form-actions"><button class="btn btn--sm" type="submit">Hash locally</button></div></form>' : '') +
    '<form data-form="fg-sticky">' + field('flag_key', 'Flag key', { required: true }) +
      field('user_key', 'User key', { required: true }) + field('percent', 'Rollout %', { type: 'number', value: '50' }) +
      '<div class="form-actions"><button class="btn btn--sm" type="submit">Assign sticky variant</button></div></form>' +
    '<form data-form="fg-schedule-resolve">' + field('flag_key', 'Flag key', { required: true }) +
      field('at', 'Resolve at (ISO)', { value: '2026-09-01T00:00:00Z', required: true }) +
      '<div class="form-actions"><button class="btn btn--sm" type="submit">Resolve state</button></div></form>' +
    '</div></section>';

  html += '<section class="card"><h2 class="page-title">Prerequisites and redirects</h2>' +
    '<div class="form-grid">' +
    (write ? '<form data-form="fg-prereq-create">' + field('flag_key', 'Flag key', { required: true }) +
      field('prerequisite_key', 'Prerequisite flag', { required: true }) +
      field('required_value', 'Required value', { value: 'on' }) +
      field('condition_json', 'Target condition (JSON, optional)', { type: 'textarea', span: true, value: '{}' }) +
      '<div class="form-actions"><button class="btn btn--sm" type="submit">Save prerequisite</button></div></form>' : '') +
    '<form data-form="fg-prereq-check">' + field('flag_key', 'Flag key', { required: true }) +
      field('flag_values_json', 'Flag values (JSON)', { type: 'textarea', span: true, value: '{"account_ready":"on"}' }) +
      field('attrs_json', 'Attributes (JSON)', { type: 'textarea', span: true, value: '{"plan":"pro"}' }) +
      '<div class="form-actions"><button class="btn btn--sm" type="submit">Check prerequisites</button></div></form>' +
    (write ? '<form data-form="fg-redirect-create">' + field('flag_key', 'Flag key', { required: true }) +
      field('rule_id', 'Rule id', { required: true }) + field('target_url', 'Local target', { value: '/checkout/v2' }) +
      '<div class="form-actions"><button class="btn btn--sm" type="submit">Save redirect</button></div></form>' : '') +
    '<form data-form="fg-redirect-resolve">' + field('flag_key', 'Flag key', { required: true }) +
      field('rule_id', 'Rule id', { required: true }) +
      '<div class="form-actions"><button class="btn btn--sm" type="submit">Resolve redirect</button></div></form>' +
    '</div></section>';

  html += '<section class="card"><h2 class="page-title">Environments and templates</h2>' +
    '<div class="form-grid">' +
    (write ? '<form data-form="fg-env-create">' + field('environment', 'Environment', { required: true }) +
      field('parent_environment', 'Parent (optional)', {}) +
      field('overrides_json', 'Overrides (JSON)', { type: 'textarea', span: true, value: '{"rollout":100}' }) +
      '<div class="form-actions"><button class="btn btn--sm" type="submit">Save environment</button></div></form>' : '') +
    '<form data-form="fg-env-resolve">' + field('environment', 'Environment', { required: true }) +
      '<div class="form-actions"><button class="btn btn--sm" type="submit">Resolve effective settings</button></div></form>' +
    (write ? '<form data-form="fg-template-create">' + field('key', 'Template key', { required: true }) +
      field('definition_json', 'Definition (JSON)', { type: 'textarea', span: true, value: '{"enabled":true,"default_value":"off"}' }) +
      '<div class="form-actions"><button class="btn btn--sm" type="submit">Save template</button></div></form>' : '') +
    '<form data-form="fg-template-instantiate">' + field('template_key', 'Template', { type: 'select', options: selectOptions(data.templates.map(function (t) { return [t.key, t.key]; })) }) +
      field('flag_key', 'New flag key', { required: true }) +
      '<div class="form-actions"><button class="btn btn--sm" type="submit">Instantiate</button></div></form>' +
    '</div></section>';

  html += '<section class="card"><h2 class="page-title">Safe rollouts, ramps, revisions and configs</h2>' +
    '<div class="form-grid">' +
    (write ? '<form data-form="fg-safe-rollout-create">' + field('flag_key', 'Flag key', { required: true }) +
      field('guardrail_metric', 'Guardrail metric', { value: 'error_rate' }) +
      field('threshold', 'Threshold', { type: 'number', value: '0.05' }) +
      field('current_percent', 'Current %', { type: 'number', value: '20' }) +
      '<div class="form-actions"><button class="btn btn--sm" type="submit">Start safe rollout</button></div></form>' : '') +
    '<form data-form="fg-safe-rollout-eval">' + field('flag_key', 'Flag key', { required: true }) +
      field('observed_rate', 'Observed rate', { type: 'number', value: '0.1' }) +
      field('baseline_rate', 'Baseline rate', { type: 'number', value: '0.1' }) +
      '<div class="form-actions"><button class="btn btn--sm" type="submit">Evaluate guardrail</button></div></form>' +
    (write ? '<form data-form="fg-ramp-create">' + field('flag_key', 'Flag key', { required: true }) +
      field('start_percent', 'From %', { type: 'number', value: '0' }) + field('end_percent', 'To %', { type: 'number', value: '100' }) +
      field('starts_at', 'Starts at', { value: '2026-01-01T00:00:00Z' }) + field('ends_at', 'Ends at', { value: '2026-01-11T00:00:00Z' }) +
      '<div class="form-actions"><button class="btn btn--sm" type="submit">Save ramp</button></div></form>' : '') +
    '<form data-form="fg-ramp-percent">' + field('flag_key', 'Flag key', { required: true }) +
      field('at', 'At (ISO)', { value: '2026-01-06T00:00:00Z' }) +
      '<div class="form-actions"><button class="btn btn--sm" type="submit">Traffic at time</button></div></form>' +
    (write ? '<form data-form="fg-revision-create">' + field('flag_key', 'Flag key', { required: true }) +
      field('effective_at', 'Effective at', { value: '2026-06-01T00:00:00Z' }) +
      field('config_json', 'Config (JSON)', { type: 'textarea', span: true, value: '{"enabled":true,"value":"v2"}' }) +
      '<div class="form-actions"><button class="btn btn--sm" type="submit">Save revision</button></div></form>' : '') +
    (write ? '<form data-form="fg-revision-apply">' + field('flag_key', 'Flag key', { required: true }) +
      field('revision_id', 'Revision id (optional)', {}) +
      '<div class="form-actions"><button class="btn btn--sm" type="submit">Apply pending revision</button></div></form>' : '') +
    '<form data-form="fg-revision-resolve">' + field('flag_key', 'Flag key', { required: true }) +
      field('at', 'At (ISO)', { value: '2026-09-01T00:00:00Z' }) +
      '<div class="form-actions"><button class="btn btn--sm" type="submit">Resolve revision</button></div></form>' +
    (write ? '<form data-form="fg-config-set">' + field('flag_key', 'Flag key', { required: true }) +
      field('environment', 'Environment', { value: 'production' }) +
      field('value_type', 'Type', { type: 'select', options: selectOptions([['json', 'JSON'], ['number', 'Number'], ['string', 'String'], ['boolean', 'Boolean']]) }) +
      field('value_json', 'Value (JSON)', { type: 'textarea', span: true, value: '{"timeout":30}' }) +
      '<div class="form-actions"><button class="btn btn--sm" type="submit">Save config</button></div></form>' : '') +
    '</div></section>';

  html += '<section class="card"><h2 class="page-title">Typed configurations</h2>' +
    (data.configs.length ? '<div class="table-wrap"><table class="data"><thead><tr>' +
      '<th>Flag</th><th>Environment</th><th>Type</th><th>Value</th></tr></thead><tbody>' +
      data.configs.map(function (c) {
        return '<tr><td>' + esc(c.flag_key) + '</td><td>' + esc(c.environment) + '</td><td>' +
          esc(c.value_type) + '</td><td><pre class="small">' + esc(JSON.stringify(c.value)) + '</pre></td></tr>';
      }).join('') + '</tbody></table></div>' : '<p class="muted small">No typed configurations saved yet.</p>') +
    '</section>';

  renderViewHtml(html);
}

async function loadSupportReporting(token) {
  if (!can(P.contactRead)) {
    renderViewHtml(pageHead('Operations', 'Support reporting', '') +
      errorBlock('Your role does not include support reporting access.'));
    return;
  }
  loadingView('Support reporting', 'Agent, team, inbox and label reports from persisted local tickets.');
  const dimension = state.supportReportDimension || 'agents';
  const status = state.supportReportStatus || '';
  let data;
  try {
    const base = apiW('/support-reporting');
    const suffix = status ? '?status=' + encodeURIComponent(status) : '';
    const [agents, teams, inboxes, labels, rules, responses, runs, surveys, contract] = await Promise.all([
      api(base + '/reports/agents' + suffix),
      api(base + '/reports/teams' + suffix),
      api(base + '/reports/inboxes' + suffix),
      api(base + '/reports/labels' + suffix),
      api(base + '/csat-rules'),
      api(base + '/csat-responses'),
      api(base + '/reports/runs'),
      api(apiW('/tickets/csat-surveys')),
      api(base + '/api-contract'),
    ]);
    data = {
      base: base, dimension: dimension,
      reports: {
        agents: agents || { rows: [], tickets_count: 0, avg_first_response_minutes: null },
        teams: teams || { rows: [], tickets_count: 0, avg_first_response_minutes: null },
        inboxes: inboxes || { rows: [], tickets_count: 0, avg_first_response_minutes: null },
        labels: labels || { rows: [], tickets_count: 0, avg_first_response_minutes: null },
      },
      rules: rules || [], responses: responses || [], runs: runs || [],
      surveys: (surveys || []).filter(function (s) { return s.status !== 'completed'; }),
      contract: contract || {},
    };
  } catch (err) {
    if (token !== state.viewToken) return;
    renderViewHtml(pageHead('Operations', 'Support reporting', '') + errorBlock(errMessage(err)));
    return;
  }
  if (token !== state.viewToken) return;

  const write = can(P.contactWrite);
  const report = data.reports[dimension] || data.reports.agents;
  const dimensionOptions = selectOptions([
    ['agents', 'Agents'], ['teams', 'Teams'], ['inboxes', 'Inboxes'], ['labels', 'Labels'],
  ], dimension);
  const statusOptions = selectOptions([
    ['', 'All statuses'], ['open', 'Open'], ['pending', 'Pending'],
    ['resolved', 'Resolved'], ['closed', 'Closed'],
  ], status);
  let html = pageHead('Operations', 'Support reporting',
    report.tickets_count + ' tickets in the selected report',
    '<button class="btn" data-action="view-support-reporting-contract">' + icon('info', 15) +
      ' Local contract</button>' +
      '<button class="btn" data-action="support-report-export">' + icon('download', 15) +
      ' CSV export</button>');
  html += governanceNote('Reports are derived from persisted workspace tickets, messages, labels and audit events. CSAT response tokens are opaque, one-use and never displayed. No Chatwoot source, hosted endpoint, webhook callback, outbound HTTP or message delivery is used.');

  html += '<section class="card"><h2 class="page-title">Report filters</h2>' +
    '<form data-form="support-report-filter"><div class="form-grid">' +
    field('dimension', 'Dimension', { type: 'select', options: dimensionOptions }) +
    field('status', 'Status', { type: 'select', options: statusOptions }) +
    '</div><div class="form-actions"><button type="submit" class="btn">' +
    icon('filter', 15) + ' Apply filters</button></div></form></section>';

  html += '<section class="card"><h2 class="page-title">' + esc(cap(dimension)) + '</h2>' +
    '<p class="muted small">Average first response: ' +
    esc(String(report.avg_first_response_minutes === null || report.avg_first_response_minutes === undefined
      ? '-' : report.avg_first_response_minutes)) + ' minutes Ã‚Â· source: ' +
    esc(String(report.source || 'persisted_local_support_rows')) + '</p>' +
    '<div class="table-wrap"><table class="data"><thead><tr><th>Key</th><th>Name</th>' +
    '<th>Tickets</th><th>Resolved</th><th>Avg first response</th></tr></thead><tbody>' +
    (report.rows || []).map(function (row) {
      return '<tr><td class="mono small">' + esc(String(row.key)) + '</td><td>' +
        esc(String(row.name || '')) + '</td><td>' + esc(String(row.tickets)) + '</td><td>' +
        esc(String(row.resolved)) + '</td><td>' +
        esc(String(row.avg_first_response_minutes === null ? '-' : row.avg_first_response_minutes)) +
        '</td></tr>';
    }).join('') + '</tbody></table></div></section>';

  html += '<section class="card"><h2 class="page-title">CSAT rules</h2>' +
    '<div class="table-wrap"><table class="data"><thead><tr><th>Name</th><th>Include</th>' +
    '<th>Exclude</th><th>Enabled</th></tr></thead><tbody>' +
    data.rules.map(function (rule) {
      return '<tr><td>' + esc(rule.name) + '</td><td>' +
        esc((rule.include_labels || []).join(', ') || '-') + '</td><td>' +
        esc((rule.exclude_labels || []).join(', ') || '-') + '</td><td>' +
        (rule.enabled ? 'yes' : 'no') + '</td></tr>';
    }).join('') + '</tbody></table></div>' +
    (write ? '<form data-form="support-csat-rule-create"><div class="form-grid">' +
      field('name', 'Rule name', { required: true }) +
      field('include_labels', 'Include labels (comma-separated)', { placeholder: 'billing, vip' }) +
      field('exclude_labels', 'Exclude labels (comma-separated)', { placeholder: 'do-not-survey' }) +
      '</div><div class="form-actions"><button type="submit" class="btn">' +
      icon('plus', 15) + ' Store rule</button></div></form>' : '') + '</section>';

  html += '<section class="card"><h2 class="page-title">One-time response tokens</h2>' +
    '<p class="muted small">Tokens are created only when a control is used, are stored as hashes and are never shown on screen.</p>' +
    (data.surveys.length ? '<div class="table-wrap"><table class="data"><thead><tr><th>Survey</th>' +
      '<th>Ticket</th><th>Action</th></tr></thead><tbody>' +
      data.surveys.map(function (survey) {
        return '<tr><td class="mono small">' + esc(survey.id) + '</td><td class="mono small">' +
          esc(survey.ticket_id) + '</td><td>' +
          (write ? '<button class="btn btn--sm" data-action="support-csat-token-issue" data-id="' +
            attr(survey.id) + '">Issue local token</button>' : 'No permission') + '</td></tr>';
      }).join('') + '</tbody></table></div>' : '<p class="muted small">No open local surveys.</p>') +
    '</section>';

  html += '<section class="card"><h2 class="page-title">Recorded responses and saved runs</h2>' +
    '<p class="muted small">Responses: ' + data.responses.length + ' Ã‚Â· saved report runs: ' +
    data.runs.length + ' Ã‚Â· contract routes: ' + esc(String(data.contract.route_count || 0)) + '</p>' +
    '<div class="table-wrap"><table class="data"><thead><tr><th>Type</th><th>Id</th>' +
    '<th>Detail</th></tr></thead><tbody>' +
    data.responses.map(function (row) {
      return '<tr><td>Response</td><td class="mono small">' + esc(row.id) + '</td><td>score ' +
        esc(String(row.score)) + '</td></tr>';
    }).join('') +
    data.runs.map(function (row) {
      return '<tr><td>Report run</td><td class="mono small">' + esc(row.id) + '</td><td>' +
        esc(row.dimension) + ' Ã‚Â· ' + esc(String(row.summary && row.summary.tickets_count || 0)) +
        ' tickets</td></tr>';
    }).join('') + '</tbody></table></div></section>';

  renderViewHtml(html);
}

async function loadMarketingContent(token) {
  if (!can(P.contactRead)) {
    renderViewHtml(pageHead('Operations', 'Marketing content', '') +
      errorBlock('Your role does not include marketing content access.'));
    return;
  }
  loadingView('Marketing content', 'Local contact types, landing pages, forms and content variants.');
  let data;
  try {
    const base = apiW('/marketing-content');
    const [pages, assets, dashboard, contract] = await Promise.all([
      api(base + '/landing-pages'), api(base + '/assets'),
      api(base + '/dashboard'), api(base + '/api-contract'),
    ]);
    data = { base: base, pages: pages || [], assets: assets || [],
      dashboard: dashboard || {}, contract: contract || {} };
  } catch (err) {
    if (token !== state.viewToken) return;
    renderViewHtml(pageHead('Operations', 'Marketing content', '') + errorBlock(errMessage(err)));
    return;
  }
  if (token !== state.viewToken) return;

  const write = can(P.contactWrite);
  let html = pageHead('Operations', 'Marketing content',
    data.pages.length + ' local landing pages Ã‚Â· ' + data.assets.length + ' local assets',
    '<button class="btn" data-action="view-marketing-content-contract">' + icon('info', 15) +
      ' Local contract</button>' +
      '<button class="btn" data-action="marketing-dashboard-view">' + icon('insights', 15) +
      ' Dashboard</button>');
  html += governanceNote('All content is stored in this workspace. Landing pages render locally, submit actions are recorded as local effects, and dashboard metrics read only local rows. No Mautic source, hosted service, external storage, email, SMS or outbound HTTP is used.');

  html += '<section class="card"><h2 class="page-title">Contact classification</h2>' +
    '<p class="muted small">Anonymous visitors and known contacts remain distinct local records.</p>' +
    (write ? '<form data-form="marketing-contact-classify"><div class="form-grid">' +
      field('contact_id', 'Contact id', { required: true }) +
      field('kind', 'Kind', { type: 'select', options: selectOptions([
        ['visitor', 'Visitor'], ['known', 'Known']]) }) +
      '</div><div class="form-actions"><button type="submit" class="btn">' +
      icon('plus', 15) + ' Classify locally</button></div></form>' +
      '<form data-form="marketing-contact-identify"><div class="form-grid">' +
      field('contact_id', 'Visitor contact id', { required: true }) +
      field('email', 'Known email', { required: true }) +
      '</div><div class="form-actions"><button type="submit" class="btn">' +
      icon('user', 15) + ' Identify visitor</button></div></form>' : '') +
    '<form data-form="marketing-contact-get"><div class="form-grid">' +
    field('contact_id', 'Inspect contact id', { required: true }) +
    '</div><div class="form-actions"><button type="submit" class="btn">' +
    icon('eye', 15) + ' Inspect</button></div></form></section>';

  html += '<section class="card"><h2 class="page-title">Landing pages</h2>' +
    '<div class="table-wrap"><table class="data"><thead><tr><th>Name</th><th>Slug</th>' +
    '<th>Published</th><th>Actions</th></tr></thead><tbody>' +
    data.pages.map(function (p) {
      return '<tr><td>' + esc(p.name) + '</td><td class="mono small">' + esc(p.slug) + '</td><td>' +
        (p.published ? 'yes' : 'no') + '</td><td>' +
        '<button class="btn btn--sm" data-action="marketing-page-preview" data-id="' + attr(p.id) +
        '">Preview</button> ' +
        (write ? '<button class="btn btn--sm" data-action="marketing-page-publish" data-id="' +
          attr(p.id) + '">Local publish</button>' : '') + '</td></tr>';
    }).join('') + '</tbody></table></div>' +
    (write ? '<form data-form="marketing-page-create"><div class="form-grid">' +
      field('name', 'Page name', { required: true }) +
      field('slug', 'Local slug', { required: true, placeholder: 'launch' }) +
      field('html_body', 'Body HTML', { type: 'textarea', span: true, value: '<h1>Welcome</h1>' }) +
      '</div><div class="form-actions"><button type="submit" class="btn">' +
      icon('plus', 15) + ' Store local page</button></div></form>' : '') + '</section>';

  html += '<section class="card"><h2 class="page-title">Forms and progressive profiling</h2>' +
    (write ? '<form data-form="marketing-form-create"><div class="form-grid">' +
      field('name', 'Form name', { required: true }) +
      field('fields', 'Fields (comma-separated)', { span: true, placeholder: 'email, phone, company' }) +
      '</div><div class="form-actions"><button type="submit" class="btn">' +
      icon('plus', 15) + ' Store form</button></div></form>' : '') +
    '<form data-form="marketing-form-progressive"><div class="form-grid">' +
    field('form_id', 'Form id', { required: true }) +
    field('contact_id', 'Contact id', { required: true }) +
    '</div><div class="form-actions"><button type="submit" class="btn">' +
    icon('filter', 15) + ' Pending fields</button></div></form>' +
    '<form data-form="marketing-form-submit"><div class="form-grid">' +
    field('form_id', 'Form id', { required: true }) +
    field('contact_id', 'Contact id', { required: true }) +
    field('email', 'Email answer', { required: true }) +
    field('actions', 'Local actions (comma-separated)', { placeholder: 'tag, notify' }) +
    '</div><div class="form-actions"><button type="submit" class="btn">' +
    icon('check', 15) + ' Record local submit</button></div></form></section>';

  html += '<section class="card"><h2 class="page-title">Dynamic content</h2>' +
    (write ? '<form data-form="marketing-content-create"><div class="form-grid">' +
      field('name', 'Content name', { required: true }) +
      field('segment_field', 'Segment field', { required: true, placeholder: 'plan' }) +
      field('variants', 'Variants (key: value per line)', { type: 'textarea', span: true,
        value: 'default: Hello\nvip: Welcome VIP' }) +
      '</div><div class="form-actions"><button type="submit" class="btn">' +
      icon('plus', 15) + ' Store variants</button></div></form>' : '') +
    '<form data-form="marketing-dynamic-resolve"><div class="form-grid">' +
    field('content_id', 'Content id', { required: true }) +
    field('segment_field', 'Segment field', { required: true, placeholder: 'plan' }) +
    field('value', 'Segment value', { required: true, placeholder: 'vip' }) +
    '</div><div class="form-actions"><button type="submit" class="btn">' +
    icon('eye', 15) + ' Resolve variant</button></div></form></section>';

  html += '<section class="card"><h2 class="page-title">Local assets and dashboard</h2>' +
    '<div class="table-wrap"><table class="data"><thead><tr><th>Name</th><th>Type</th>' +
    '<th>Bytes</th></tr></thead><tbody>' +
    data.assets.map(function (a) {
      return '<tr><td>' + esc(a.name) + '</td><td>' + esc(a.content_type) + '</td><td>' +
        esc(String(a.size_bytes)) + '</td></tr>';
    }).join('') + '</tbody></table></div>' +
    (write ? '<form data-form="marketing-asset-add"><div class="form-grid">' +
      field('name', 'Asset name', { required: true }) +
      field('content_type', 'Content type', { value: 'image/png' }) +
      field('content_base64', 'Base64 payload', { type: 'textarea', span: true, required: true }) +
      '</div><div class="form-actions"><button type="submit" class="btn">' +
      icon('plus', 15) + ' Store asset</button></div></form>' +
      '<form data-form="marketing-widget-create"><div class="form-grid">' +
      field('name', 'Widget name', { required: true }) +
      field('widget_type', 'Type', { type: 'select', options: selectOptions([
        ['counter', 'Counter'], ['breakdown', 'Breakdown'], ['timeline', 'Timeline']]) }) +
      field('source', 'Counter source', { placeholder: 'landing_pages' }) +
      '</div><div class="form-actions"><button type="submit" class="btn">' +
      icon('plus', 15) + ' Store widget</button></div></form>' : '') +
    '<p class="muted small">Dashboard source: ' + esc(String(data.dashboard.source || '-')) +
    ' Ã‚Â· widgets: ' + esc(String((data.dashboard.widgets || []).length)) + '</p></section>';

  renderViewHtml(html);
}

async function loadExperimentExposure(token) {
  if (!can(P.contactRead)) {
    renderViewHtml(pageHead('Operations', 'Experiment exposure', '') +
      errorBlock('Your role does not include experiment access.'));
    return;
  }
  loadingView('Experiment exposure', 'Local exposure-event tracker adapters for experiments.');
  let data;
  try {
    const base = apiW('/experiment-exposure');
    const [contract, providers, trackers, exposures, stats, rejections, batches] = await Promise.all([
      api(base + '/api-contract'), api(base + '/providers'), api(base + '/trackers'),
      api(base + '/exposures'), api(base + '/exposures/stats'), api(base + '/rejections'),
      api(base + '/batches'),
    ]);
    data = {
      contract: contract || {}, providers: providers || [], trackers: trackers || [],
      exposures: exposures || [], stats: stats || {}, rejections: rejections || [],
      batches: batches || [],
    };
  } catch (err) {
    if (token !== state.viewToken) return;
    renderViewHtml(pageHead('Operations', 'Experiment exposure', '') + errorBlock(errMessage(err)));
    return;
  }
  if (token !== state.viewToken) return;

  const write = can(P.noteWrite);
  const providerOptions = selectOptions(data.providers.map(function (p) {
    return [p.key, p.label];
  }));
  const trackerOptions = selectOptions(data.trackers.map(function (t) {
    return [t.id, t.provider_key];
  }));
  let html = pageHead('Operations', 'Experiment exposure',
    data.providers.length + ' local adapters Ã‚Â· ' + data.trackers.length + ' configured Ã‚Â· ' +
      (data.stats.total || 0) + ' exposures',
    '<button class="btn" data-action="view-exposure-contract">' + icon('info', 15) +
      ' Local contract</button>');
  html += governanceNote('Fourteen documented provider paths normalise into one local exposure shape and publish to NOVARA\'s event spine. No vendor SDK, hosted API, browser script, outbound traffic or upstream source is used. Retry keys are derived from the payload so duplicate deliveries deduplicate.');

  html += '<section class="card"><h2 class="page-title">Documented provider paths</h2>' +
    '<div class="table-wrap"><table class="data"><thead><tr><th>Provider</th><th>Event field</th>' +
    '<th>Properties field</th><th>Documentation</th><th></th></tr></thead><tbody>' +
    data.providers.map(function (p) {
      return '<tr><td>' + esc(p.label) + '</td><td class="mono small">' + esc(p.event_field || 'any') +
        '</td><td class="mono small">' + esc(p.properties_field || 'root') + '</td>' +
        '<td class="small">' + esc(p.documentation) + '</td><td>' +
        '<button class="btn btn--sm" data-action="view-exposure-sample" data-id="' +
        attr(p.key) + '">Sample</button></td></tr>';
    }).join('') + '</tbody></table></div></section>';

  html += '<section class="card"><h2 class="page-title">Configured trackers</h2>' +
    (data.trackers.length ? '<div class="table-wrap"><table class="data"><thead><tr><th>Provider</th>' +
      '<th>State</th><th>Note</th><th></th></tr></thead><tbody>' +
      data.trackers.map(function (t) {
        return '<tr><td class="mono">' + esc(t.provider_key) + '</td><td>' +
          statusBadge(t.enabled ? 'enabled' : 'disabled') + '</td><td>' + esc(t.note || '-') +
          '</td><td>' + (write ? '<button class="btn btn--sm" data-action="toggle-exposure-tracker" data-id="' +
            attr(t.id) + '" data-state="' + attr(String(t.enabled)) + '">' +
            (t.enabled ? 'Disable' : 'Enable') + '</button>' : '-') + '</td></tr>';
      }).join('') + '</tbody></table></div>' : '<p class="muted small">No trackers configured.</p>') +
    (write ? '<form data-form="exposure-tracker-create"><div class="form-grid">' +
      field('provider_key', 'Provider', { type: 'select', options: providerOptions }) +
      field('note', 'Note', { placeholder: 'local adapter purpose' }) +
      '</div><div class="form-actions"><button type="submit" class="btn">' +
      icon('plus', 15) + ' Configure tracker</button></div></form>' +
      (data.trackers.length ? '<form data-form="exposure-mapping-set"><div class="form-grid">' +
        field('tracker_id', 'Tracker', { type: 'select', options: trackerOptions }) +
        field('source_field', 'Source dotted path', { required: true, placeholder: 'ctx.experiment' }) +
        field('target_field', 'Target field', { type: 'select', options: selectOptions([
          ['subject', 'subject'], ['experiment', 'experiment'],
          ['variation', 'variation'], ['occurred_at', 'occurred_at'],
        ]) }) + '</div><div class="form-actions"><button type="submit" class="btn">' +
        icon('link', 15) + ' Set field mapping</button></div></form>' : '') : '') + '</section>';

  html += '<section class="card"><h2 class="page-title">Normalised exposures</h2>' +
    '<p class="muted small">' + esc(JSON.stringify(data.stats.by_provider || {})) + '</p>' +
    (data.exposures.length ? '<div class="table-wrap"><table class="data"><thead><tr><th>Provider</th>' +
      '<th>Experiment</th><th>Variation</th><th>Subject</th><th>Event id</th></tr></thead><tbody>' +
      data.exposures.map(function (e) {
        return '<tr><td class="mono">' + esc(e.provider_key) + '</td><td>' + esc(e.experiment_id) +
          '</td><td>' + esc(e.variation_id) + '</td><td class="mono">' + esc(e.subject) +
          '</td><td class="mono small">' + esc(e.event_id) + '</td></tr>';
      }).join('') + '</tbody></table></div>' : '<p class="muted small">No exposures ingested yet.</p>') +
    (write && data.trackers.length ? '<form data-form="exposure-ingest"><div class="form-grid">' +
      field('tracker_id', 'Tracker', { type: 'select', options: trackerOptions }) +
      field('event_id', 'Client event id (optional)', { placeholder: 'dedupe key' }) +
      field('payload', 'Provider payload JSON', { type: 'textarea', span: true, required: true,
        value: '{}', placeholder: '{"event":"Experiment Viewed", ...}' }) +
      '</div><div class="form-actions"><button type="submit" class="btn">' +
      icon('zap', 15) + ' Ingest locally</button></div></form>' +
      '<form data-form="exposure-batch-ingest"><div class="form-grid">' +
      field('tracker_id', 'Tracker', { type: 'select', options: trackerOptions }) +
      field('items', 'Batch payloads JSON', { type: 'textarea', span: true, required: true,
        value: '[]', placeholder: '[{"payload":{...},"event_id":"e1"}]' }) +
      '</div><div class="form-actions"><button type="submit" class="btn">' +
      icon('layers', 15) + ' Ingest batch locally</button></div></form>' : '') + '</section>';

  html += '<section class="card"><h2 class="page-title">Audit trail</h2>' +
    '<p class="muted small">Rejections: ' + data.rejections.length + ' Ã‚Â· Batches: ' +
    data.batches.length + '</p>' +
    (data.rejections.length ? '<div class="table-wrap"><table class="data"><thead><tr><th>Provider</th>' +
      '<th>Reason</th><th>When</th></tr></thead><tbody>' +
      data.rejections.map(function (r) {
        return '<tr><td>' + esc(r.provider_key || '-') + '</td><td>' + esc(r.reason) +
          '</td><td class="small">' + esc(r.created_at) + '</td></tr>';
      }).join('') + '</tbody></table></div>' : '') +
    (data.batches.length ? '<div class="table-wrap"><table class="data"><thead><tr><th>Batch</th>' +
      '<th>Total</th><th>Accepted</th><th>Duplicates</th><th>Rejected</th></tr></thead><tbody>' +
      data.batches.map(function (b) {
        return '<tr><td class="mono">' + esc(b.provider_key) + '</td><td>' + b.total +
          '</td><td>' + b.accepted + '</td><td>' + b.duplicates + '</td><td>' + b.rejected +
          '</td></tr>';
      }).join('') + '</tbody></table></div>' : '') + '</section>';
  renderViewHtml(html);
}

async function loadConversationOps(token) {
  if (!can(P.contactRead)) {
    renderViewHtml(pageHead('Operations', 'Conversation ops', '') +
      errorBlock('Your role does not include support access.'));
    return;
  }
  loadingView('Conversation ops', 'Local presence, snoozes, collision safety and business hours.');
  let data;
  try {
    const base = apiW('/conversation-ops');
    const [contract, tickets, presence, snoozes, mentions, folders, mutes, hours] = await Promise.all([
      api(base + '/api-contract'), api(apiW('/tickets')), api(base + '/presence'),
      api(base + '/snoozes'), api(base + '/mentions'), api(base + '/folders'),
      api(base + '/mutes'), api(base + '/inbox-hours'),
    ]);
    data = {
      contract: contract || {}, tickets: tickets || [], presence: presence || [],
      snoozes: snoozes || [], mentions: mentions || [], folders: folders || [],
      mutes: mutes || [], hours: hours || [],
    };
  } catch (err) {
    if (token !== state.viewToken) return;
    renderViewHtml(pageHead('Operations', 'Conversation ops', '') + errorBlock(errMessage(err)));
    return;
  }
  if (token !== state.viewToken) return;

  const write = can(P.noteWrite);
  const ticketOptions = selectOptions(data.tickets.map(function (t) {
    return [t.id, t.subject];
  }));
  const agentOptions = '<option value="">none</option>' + selectOptions(data.presence.map(function (p) {
    return [p.user_id, p.user_id];
  }));
  const hoursOptions = selectOptions(data.hours.map(function (h) {
    return [h.id, h.inbox_key + ' (' + h.timezone + ')'];
  }));
  const statusOptions = selectOptions([
    ['open', 'open'], ['pending', 'pending'], ['resolved', 'resolved'], ['closed', 'closed'],
  ], 'open');
  let html = pageHead('Operations', 'Conversation ops',
    data.presence.length + ' agents Ã‚Â· ' + data.tickets.length + ' conversations Ã‚Â· ' +
      data.hours.length + ' inbox schedules',
    '<button class="btn" data-action="view-conversation-contract">' + icon('info', 15) +
      ' Local contract</button>');
  html += governanceNote('All state is local and workspace-scoped. Typing indicators use polling, mentions publish local events only, replies are deduplicated and collision-guarded, and business hours use the system timezone database with a documented fixed-offset fallback. No Chatwoot source, ActionCable transport, outbound notification or external holiday service is used.');

  html += '<section class="card"><h2 class="page-title">Agent presence</h2>' +
    '<div class="table-wrap"><table class="data"><thead><tr><th>User</th><th>State</th>' +
    '<th>Last seen</th></tr></thead><tbody>' +
    (data.presence.length ? data.presence.map(function (p) {
      return '<tr><td class="mono">' + esc(p.user_id) + '</td><td>' + statusBadge(p.state) +
        '</td><td class="small">' + esc(p.last_seen_at) + '</td></tr>';
    }).join('') : '<tr><td colspan="3" class="muted">No presence recorded yet.</td></tr>') +
    '</tbody></table></div>' + (write ? '<form data-form="conversation-presence"><div class="form-grid">' +
    field('state', 'My presence', { type: 'select', options: selectOptions([
      ['online', 'online'], ['away', 'away'], ['offline', 'offline'],
    ]) }) + '</div><div class="form-actions"><button type="submit" class="btn">' +
    icon('settings', 15) + ' Update presence</button></div></form>' : '') + '</section>';

  html += '<section class="card"><h2 class="page-title">Snoozed conversations</h2>' +
    (data.snoozes.length ? '<div class="table-wrap"><table class="data"><thead><tr><th>Ticket</th>' +
      '<th>Until</th><th>Reason</th><th></th></tr></thead><tbody>' +
      data.snoozes.map(function (s) {
        return '<tr><td class="mono">' + esc(s.ticket_id) + '</td><td>' + esc(s.snoozed_until) +
          '</td><td>' + esc(s.reason || '-') + '</td><td>' +
          (write ? '<button class="btn btn--sm" data-action="unsnooze-conversation" data-id="' +
            attr(s.ticket_id) + '">Return to queue</button>' : '-') + '</td></tr>';
      }).join('') + '</tbody></table></div>' : '<p class="muted small">No snoozed conversations.</p>') +
    (write ? '<form data-form="conversation-snooze"><div class="form-grid">' +
      field('ticket_id', 'Conversation', { type: 'select', options: ticketOptions }) +
      field('minutes', 'Snooze for (minutes)', { type: 'number', value: '60', min: '1' }) +
      field('reason', 'Reason', { placeholder: 'waiting on customer' }) +
      '</div><div class="form-actions"><button type="submit" class="btn">' +
      icon('clock', 15) + ' Snooze</button></div></form>' +
      '<div class="form-actions"><button class="btn" data-action="expire-conversation-snoozes">' +
      icon('refresh', 15) + ' Expire due snoozes</button></div>' : '') + '</section>';

  html += '<section class="card"><h2 class="page-title">Mentions and collision safety</h2>' +
    '<p class="muted small">My mentions: ' + data.mentions.length + '</p>' +
    (write ? '<form data-form="conversation-mention-note"><div class="form-grid">' +
      field('ticket_id', 'Conversation', { type: 'select', options: ticketOptions }) +
      field('mentioned_user_id', 'Mention teammate', { type: 'select', options: agentOptions }) +
      field('body', 'Internal note', { type: 'textarea', span: true, required: true }) +
      '</div><div class="form-actions"><button type="submit" class="btn">' +
      icon('note', 15) + ' Save note with @mention</button></div></form>' +
      '<form data-form="conversation-reply"><div class="form-grid">' +
      field('ticket_id', 'Conversation', { type: 'select', options: ticketOptions }) +
      field('client_msg_id', 'Client message id (dedupe key)', { placeholder: 'optional' }) +
      field('body', 'Reply body', { type: 'textarea', span: true, required: true }) +
      checkboxField('force', 'Override typing warning', false) +
      '</div><div class="form-actions"><button type="submit" class="btn">' +
      icon('edit', 15) + ' Record reply locally</button></div></form>' +
      '<div class="form-actions"><button class="btn" data-action="conversation-set-typing" data-id="' +
      attr((data.tickets[0] || {}).id || '') + '">' + icon('activity', 15) +
      ' Signal typing (first conversation)</button></div>' : '') +
    (write ? '<form data-form="conversation-receipt"><div class="form-grid">' +
      field('message_id', 'Message id', { required: true }) +
      checkboxField('read', 'Mark as read', false) +
      '</div><div class="form-actions"><button type="submit" class="btn">' +
      icon('eye', 15) + ' Record receipt</button></div></form>' : '') +
    '<p class="muted small">Use a conversation-specific collision check from the bulk section by ticket id.</p>' +
    (write ? '<form data-form="conversation-collision"><div class="form-grid">' +
      field('ticket_id', 'Check collision for', { type: 'select', options: ticketOptions }) +
      '</div><div class="form-actions"><button type="submit" class="btn">' +
      icon('alert', 15) + ' Check collision</button></div></form>' : '') + '</section>';

  if (write) {
    html += '<section class="card"><h2 class="page-title">Bulk actions, folders and mutes</h2>' +
      '<form data-form="conversation-bulk"><div class="form-grid">' +
      field('ticket_ids', 'Ticket ids (comma-separated, max 100)', { required: true, span: true }) +
      field('status', 'Status', { type: 'select', options: statusOptions }) +
      field('assignee_id', 'Assignee', { type: 'select', options: agentOptions }) +
      field('label', 'Existing label name', { placeholder: 'optional' }) +
      '</div><div class="form-actions"><button type="submit" class="btn">' +
      icon('layers', 15) + ' Apply bulk action</button></div></form>' +
      (data.folders.length ? '<div class="table-wrap"><table class="data"><thead><tr><th>Folder</th>' +
        '<th>Filters</th><th>Live count</th><th></th></tr></thead><tbody>' +
        data.folders.map(function (f) {
          return '<tr><td>' + esc(f.name) + '</td><td class="mono small">' + esc(JSON.stringify(f.filters)) +
            '</td><td>' + f.count + '</td><td><button class="btn btn--sm" data-action="remove-conversation-folder" data-id="' +
            attr(f.id) + '">Remove</button></td></tr>';
        }).join('') + '</tbody></table></div>' : '') +
      '<form data-form="conversation-folder-create"><div class="form-grid">' +
      field('name', 'Folder name', { required: true }) +
      field('filters', 'Filters JSON', { type: 'textarea', span: true, value: '{}', placeholder: '{"status":"open"}' }) +
      '</div><div class="form-actions"><button type="submit" class="btn">' +
      icon('plus', 15) + ' Save folder</button></div></form>' +
      '<form data-form="conversation-mute"><div class="form-grid">' +
      field('ticket_id', 'Conversation', { type: 'select', options: ticketOptions }) +
      checkboxField('muted', 'Mute notifications for me', true) +
      '</div><div class="form-actions"><button type="submit" class="btn">' +
      icon('bell', 15) + ' Apply mute state</button></div></form>' +
      '<p class="muted small">Currently muted: ' +
      esc(data.mutes.map(function (m) { return m.ticket_id; }).join(', ') || 'none') + '</p></section>';
  }

  html += '<section class="card"><h2 class="page-title">Inbox hours and away messages</h2>' +
    (data.hours.length ? '<div class="table-wrap"><table class="data"><thead><tr><th>Inbox</th>' +
      '<th>Timezone</th><th>Slots</th></tr></thead><tbody>' +
      data.hours.map(function (h) {
        return '<tr><td>' + esc(h.inbox_key) + '</td><td>' + esc(h.timezone) + '</td><td>' +
          (h.slots || []).length + '</td></tr>';
      }).join('') + '</tbody></table></div>' : '<p class="muted small">No inbox schedules yet.</p>') +
    (write ? '<form data-form="conversation-hours-create"><div class="form-grid">' +
      field('inbox_key', 'Inbox key', { required: true }) +
      field('timezone', 'Timezone', { value: 'UTC' }) +
      field('slots', 'Weekly slots JSON', { type: 'textarea', span: true, value: '[]', placeholder: '[{"day_of_week":0,"start_minute":540,"end_minute":1020}]' }) +
      field('away_message', 'Away message', { span: true, placeholder: 'Back on Monday' }) +
      '</div><div class="form-actions"><button type="submit" class="btn">' +
      icon('plus', 15) + ' Add inbox schedule</button></div></form>' +
      (data.hours.length ? '<form data-form="conversation-hours-override"><div class="form-grid">' +
        field('hours_id', 'Schedule', { type: 'select', options: hoursOptions }) +
        field('date', 'Date (YYYY-MM-DD)', { required: true }) +
        checkboxField('closed', 'Closed all day', true) +
        field('start_minute', 'Open from minute (if reduced)', { type: 'number', min: '0' }) +
        field('end_minute', 'Open until minute (if reduced)', { type: 'number', min: '1' }) +
        '</div><div class="form-actions"><button type="submit" class="btn">' +
        icon('calendar', 15) + ' Add date override</button></div></form>' +
        '<form data-form="conversation-hours-holiday"><div class="form-grid">' +
        field('hours_id', 'Schedule', { type: 'select', options: hoursOptions }) +
        field('date', 'Date (YYYY-MM-DD)', { required: true }) +
        field('name', 'Holiday name', { required: true }) +
        field('region', 'Region', { placeholder: 'e.g. IN' }) +
        '</div><div class="form-actions"><button type="submit" class="btn">' +
        icon('calendar', 15) + ' Add holiday</button></div></form>' +
        '<form data-form="conversation-hours-close-region"><div class="form-grid">' +
        field('hours_id', 'Schedule', { type: 'select', options: hoursOptions }) +
        field('region', 'Region', { required: true }) +
        field('dates', 'Dates JSON', { type: 'textarea', span: true, value: '[]', placeholder: '["2026-11-27","2026-11-28"]' }) +
        '</div><div class="form-actions"><button type="submit" class="btn">' +
        icon('calendar', 15) + ' Close region dates</button></div></form>' : '') : '') +
    (data.hours.length ? '<form data-form="conversation-hours-availability"><div class="form-grid">' +
      field('hours_id', 'Schedule', { type: 'select', options: hoursOptions }) +
      field('at', 'Check at ISO datetime', { placeholder: 'leave blank for now' }) +
      '</div><div class="form-actions"><button type="submit" class="btn">' +
      icon('clock', 15) + ' Check availability</button></div></form>' : '') + '</section>';
  renderViewHtml(html);
}

async function loadSalesEngagement(token) {
  if (!can(P.contactRead)) {
    renderViewHtml(pageHead('Operations', 'Sales engagement', '') +
      errorBlock('Your role does not include sales access.'));
    return;
  }
  loadingView('Sales engagement', 'Local signals, cohorts, drafts and a governed outbox.');
  let data;
  try {
    const base = apiW('/sales-engagement');
    const [contract, signals, cohorts, drafts, sending, rules, outbox] = await Promise.all([
      api(base + '/api-contract'), api(base + '/signals'), api(base + '/cohorts'),
      api(base + '/drafts'), api(base + '/delivery-status'), api(base + '/delivery-rules'),
      api(base + '/local-queue'),
    ]);
    data = {
      contract: contract || {}, signals: signals || { signals: [] }, cohorts: cohorts || [],
      drafts: drafts || [], sending: sending || {}, rules: rules || [], outbox: outbox || [],
    };
  } catch (err) {
    if (token !== state.viewToken) return;
    renderViewHtml(pageHead('Operations', 'Sales engagement', '') + errorBlock(errMessage(err)));
    return;
  }
  if (token !== state.viewToken) return;

  const write = can(P.noteWrite);
  const cohortOptions = selectOptions(data.cohorts.map(function (c) { return [c.id, c.name]; }));
  const draftOptions = selectOptions(data.drafts.map(function (d) { return [d.id, d.campaign_key + ' #' + d.sequence_step]; }));
  let html = pageHead('Operations', 'Sales engagement',
    data.signals.total + ' signals Ã‚Â· ' + data.cohorts.length + ' cohorts Ã‚Â· ' +
      data.outbox.length + ' outbox messages',
    '<button class="btn" data-action="view-sales-contract">' + icon('info', 15) +
      ' Local contract</button>');
  html += governanceNote('Everything here is local: signals are a governed catalog, drafts and offers come from deterministic local templates, and the outbox is a durable queue whose only send state is a labelled simulated dry run. No Sellbird source, broker, outbound email or external AI provider is used.');

  html += '<section class="card"><h2 class="page-title">Signal catalog</h2>' +
    '<p class="muted small">' + data.signals.total + ' governed signals Ã‚Â· ' + data.signals.free +
    ' free Ã‚Â· ' + data.signals.paid + ' paid (explicit confirmation required)</p>' +
    (write ? '<div class="form-actions"><button class="btn" data-action="activate-free-signals">' +
      icon('plus', 15) + ' Activate free signals</button></div>' : '') +
    '<div class="table-wrap"><table class="data"><thead><tr><th>Code</th><th>Label</th>' +
    '<th>Tier</th><th>Active</th><th></th></tr></thead><tbody>' +
    (data.signals.signals || []).map(function (s) {
      return '<tr><td class="mono">' + esc(s.code) + '</td><td>' + esc(s.label) + '</td><td>' +
        statusBadge(s.tier) + '</td><td>' + statusBadge(s.active ? 'active' : 'inactive') + '</td><td>' +
        (write && !s.active ? '<button class="btn btn--sm" data-action="activate-sales-signal" data-id="' +
          attr(s.code) + '" data-tier="' + attr(s.tier) + '">Activate</button>' : '-') + '</td></tr>';
    }).join('') + '</tbody></table></div></section>';

  html += '<section class="card"><h2 class="page-title">Cohorts</h2>' +
    (data.cohorts.length ? '<div class="table-wrap"><table class="data"><thead><tr><th>Name</th>' +
      '<th>Filters</th><th></th></tr></thead><tbody>' +
      data.cohorts.map(function (c) {
        return '<tr><td>' + esc(c.name) + '</td><td class="mono small">' + esc(JSON.stringify(c.filters)) +
          '</td><td><button class="btn btn--sm" data-action="evaluate-sales-cohort" data-id="' + attr(c.id) +
          '">Evaluate</button></td></tr>';
      }).join('') + '</tbody></table></div>' : '<p class="muted small">No cohorts yet.</p>') +
    (write ? '<form data-form="sales-cohort-create"><div class="form-grid">' +
      field('name', 'Cohort name', { required: true }) +
      field('filters', 'Filters JSON', { type: 'textarea', span: true, value: '{}', placeholder: '{"status":"qualified","min_score":70}' }) +
      '</div><div class="form-actions"><button type="submit" class="btn">' +
      icon('plus', 15) + ' Build cohort</button></div></form>' : '') + '</section>';

  if (write) {
    html += '<section class="card"><h2 class="page-title">Offers and drafts</h2>' +
      '<form data-form="sales-offer-suggest"><div class="form-grid">' +
      field('industry', 'Industry', { placeholder: 'optional' }) +
      field('pain', 'Pain', { placeholder: 'e.g. manual reporting' }) +
      field('budget', 'Budget', { placeholder: 'low / normal' }) +
      '</div><div class="form-actions"><button type="submit" class="btn">' +
      icon('activity', 15) + ' Suggest offer</button></div></form>' +
      (data.drafts.length ? '<div class="table-wrap"><table class="data"><thead><tr><th>Campaign</th>' +
        '<th>Step</th><th>Subject</th><th>Status</th></tr></thead><tbody>' +
        data.drafts.map(function (d) {
          return '<tr><td class="mono">' + esc(d.campaign_key) + '</td><td>' + d.sequence_step +
            '</td><td>' + esc(d.subject) + '</td><td>' + statusBadge(d.status) + '</td></tr>';
        }).join('') + '</tbody></table></div>' : '') +
      '<form data-form="sales-drafts-generate"><div class="form-grid">' +
      field('campaign_key', 'Campaign key', { required: true }) +
      field('steps', 'Steps (1-5)', { type: 'number', value: '3', min: '1' }) +
      field('cohort_id', 'Cohort', { type: 'select', options: '<option value="">none</option>' + cohortOptions }) +
      '</div><div class="form-actions"><button type="submit" class="btn">' +
      icon('edit', 15) + ' Generate sequence drafts</button></div></form>' + '</section>';

    html += '<section class="card"><h2 class="page-title">Sending governance</h2>' +
      '<p class="muted small">Mode: ' + statusBadge(data.sending.mode || 'approval') +
      ' Ã‚Â· autopilot opt-in: ' + (data.sending.autopilot_opt_in ? 'yes' : 'no') +
      ' Ã‚Â· global pause: ' + (data.sending.global_paused ? 'yes' : 'no') +
      ' Ã‚Â· paused inboxes: ' + esc((data.sending.paused_inboxes || []).join(', ') || 'none') + '</p>' +
      '<form data-form="sales-sending-mode"><div class="form-grid">' +
      field('mode', 'Sending mode', { type: 'select', options: selectOptions([
        ['approval', 'approval (default)'], ['autopilot', 'autopilot (opt-in required)'],
      ], data.sending.mode) }) +
      '</div><div class="form-actions"><button type="submit" class="btn">' +
      icon('settings', 15) + ' Set mode</button></div></form>' +
      '<form data-form="sales-autopilot-optin"><div class="form-grid">' +
      checkboxField('opt_in', 'Opt in to autopilot', !!data.sending.autopilot_opt_in) +
      checkboxField('confirm', 'I explicitly confirm this change', false) +
      '</div><div class="form-actions"><button type="submit" class="btn">' +
      icon('activity', 15) + ' Save autopilot choice</button></div></form>' +
      '<form data-form="sales-sending-pause"><div class="form-grid">' +
      field('scope', 'Scope', { type: 'select', options: selectOptions([['global', 'global'], ['inbox', 'inbox']]) }) +
      field('inbox_key', 'Inbox key (inbox scope)', { placeholder: 'sales' }) +
      checkboxField('paused', 'Paused', true) +
      '</div><div class="form-actions"><button type="submit" class="btn">' +
      icon('settings', 15) + ' Apply pause</button></div></form>' + '</section>';

    html += '<section class="card"><h2 class="page-title">Send rules and headers</h2>' +
      (data.rules.length ? '<div class="table-wrap"><table class="data"><thead><tr><th>Name</th>' +
        '<th>Kind</th><th>Config</th><th></th></tr></thead><tbody>' +
        data.rules.map(function (r) {
          return '<tr><td>' + esc(r.name) + '</td><td>' + statusBadge(r.kind) + '</td>' +
            '<td class="mono small">' + esc(JSON.stringify(r.config)) + '</td>' +
            '<td><button class="btn btn--sm" data-action="remove-send-rule" data-id="' + attr(r.id) +
            '">Remove</button></td></tr>';
        }).join('') + '</tbody></table></div>' : '<p class="muted small">No extension rules registered.</p>') +
      '<form data-form="sales-send-rule-create"><div class="form-grid">' +
      field('name', 'Rule name', { required: true }) +
      field('kind', 'Kind', { type: 'select', options: selectOptions([['rule', 'rule'], ['header', 'header']]) }) +
      field('config', 'Config JSON', { type: 'textarea', span: true, value: '{}', placeholder: '{"max_per_day":20} or {"name":"X-Campaign","value":"q1"}' }) +
      '</div><div class="form-actions"><button type="submit" class="btn">' +
      icon('plus', 15) + ' Register extension</button></div></form>' + '</section>';

    html += '<section class="card"><h2 class="page-title">Outbox (local queue)</h2>' +
      (data.outbox.length ? '<div class="table-wrap"><table class="data"><thead><tr><th>Campaign</th>' +
        '<th>Recipient</th><th>Inbox</th><th>Status</th><th></th></tr></thead><tbody>' +
        data.outbox.map(function (m) {
          let buttons = '';
          if (m.status === 'awaiting_approval') {
            buttons = '<button class="btn btn--sm" data-action="outbox-transition" data-id="' + attr(m.id) +
              '" data-next="approve">Approve</button> ';
          }
          if (m.status === 'approved') {
            buttons = '<button class="btn btn--sm" data-action="outbox-transition" data-id="' + attr(m.id) +
              '" data-next="dry-run">Dry run</button> ';
          }
          if (m.status === 'awaiting_approval' || m.status === 'approved') {
            buttons += '<button class="btn btn--sm" data-action="outbox-transition" data-id="' + attr(m.id) +
              '" data-next="pause">Pause</button> ';
          }
          if (m.status === 'paused') {
            buttons = '<button class="btn btn--sm" data-action="outbox-transition" data-id="' + attr(m.id) +
              '" data-next="resume">Resume</button> ';
          }
          if (m.status !== 'simulated' && m.status !== 'cancelled') {
            buttons += '<button class="btn btn--sm" data-action="outbox-transition" data-id="' + attr(m.id) +
              '" data-next="cancel">Cancel</button>';
          }
          return '<tr><td class="mono">' + esc(m.campaign_key) + '</td><td>' + esc(m.recipient) +
            '</td><td>' + esc(m.inbox_key) + '</td><td>' + statusBadge(m.status) + '</td><td>' +
            (buttons || '-') + '</td></tr>';
        }).join('') + '</tbody></table></div>' : '<p class="muted small">Outbox is empty.</p>') +
      '<form data-form="sales-outbox-enqueue"><div class="form-grid">' +
      field('draft_id', 'Draft', { type: 'select', options: draftOptions }) +
      field('recipient', 'Recipient', { required: true, placeholder: 'buyer@corp.test' }) +
      field('inbox_key', 'Inbox key', { value: 'default' }) +
      '</div><div class="form-actions"><button type="submit" class="btn btn--primary">' +
      icon('plus', 15) + ' Enqueue (approval required)</button></div></form>' + '</section>';
  }
  renderViewHtml(html);
}

async function loadNotificationAutomation(token) {
  if (!can(P.contactRead)) {
    renderViewHtml(pageHead('Operations', 'Notification automation', '') +
      errorBlock('Your role does not include notification access.'));
    return;
  }
  loadingView('Notification automation', 'Local subscribers, sandboxed steps, routing and quotas.');
  let data;
  try {
    const base = apiW('/notification-automation');
    const [contract, quotas, flags, subscribers, codeSteps, httpStubs, routing, demo, deliveries] = await Promise.all([
      api(base + '/api-contract'), api(base + '/quotas'), api(base + '/feature-flags'),
      api(base + '/subscribers'), api(base + '/code-steps'), api(base + '/http-stubs'),
      api(base + '/routing-rules'), api(base + '/demo-providers'), api(base + '/deliveries'),
    ]);
    data = {
      contract: contract || {}, quotas: quotas || {}, flags: flags || [],
      subscribers: subscribers || [], codeSteps: codeSteps || [], httpStubs: httpStubs || [],
      routing: routing || [], demo: demo || [], deliveries: deliveries || [],
    };
  } catch (err) {
    if (token !== state.viewToken) return;
    renderViewHtml(pageHead('Operations', 'Notification automation', '') + errorBlock(errMessage(err)));
    return;
  }
  if (token !== state.viewToken) return;

  const write = can(P.noteWrite);
  const manage = can(P.workspaceManage);
  const subOptions = selectOptions(data.subscribers.map(function (s) { return [s.subscriber_key, s.subscriber_key]; }));
  const subIdOptions = selectOptions(data.subscribers.map(function (s) { return [s.id, s.subscriber_key]; }));
  const stepOptions = selectOptions(data.codeSteps.map(function (s) { return [s.id, s.workflow_key + '/' + s.step_key]; }));
  let html = pageHead('Operations', 'Notification automation',
    data.subscribers.length + ' subscribers Ã‚Â· ' + data.codeSteps.length + ' code steps Ã‚Â· ' +
      data.routing.length + ' routing rules',
    '<button class="btn" data-action="view-automation-contract">' + icon('info', 15) +
      ' Local contract</button>');
  html += governanceNote('All automation is local: code steps run in a restricted expression sandbox, HTTP steps resolve only against registered /local/ stubs, demo sends are simulated and broadcasts create local in-app records. No Novu source, outbound HTTP or real delivery provider is used.');

  html += '<section class="card"><h2 class="page-title">Platform quotas</h2>' +
    '<div class="table-wrap"><table class="data"><thead><tr><th>Cap</th><th>Documented</th>' +
    '<th>Effective</th></tr></thead><tbody>' +
    Object.keys(data.quotas.documented || {}).map(function (key) {
      return '<tr><td class="mono">' + esc(key) + '</td><td>' + data.quotas.documented[key] +
        '</td><td>' + (data.quotas.effective || {})[key] + '</td></tr>';
    }).join('') + '</tbody></table></div>' +
    (manage ? '<form data-form="automation-quota-override"><div class="form-grid">' +
      field('key', 'Cap', { type: 'select', options: selectOptions(
        Object.keys(data.quotas.documented || {}).map(function (k) { return [k, k]; })) }) +
      field('value', 'Override value', { type: 'number', required: true, min: '1' }) +
      '</div><div class="form-actions"><button type="submit" class="btn">' +
      icon('settings', 15) + ' Override cap</button></div></form>' : '') + '</section>';

  html += '<section class="card"><h2 class="page-title">Feature flags</h2>' +
    '<div class="table-wrap"><table class="data"><thead><tr><th>Flag</th><th>Env default</th>' +
    '<th>State</th><th></th></tr></thead><tbody>' +
    data.flags.map(function (f) {
      return '<tr><td class="mono">' + esc(f.key) + '</td><td class="mono small">' + esc(f.env_default) +
        '</td><td>' + statusBadge(f.enabled ? 'enabled' : 'disabled') + '</td><td>' +
        (write ? '<button class="btn btn--sm" data-action="toggle-automation-flag" data-id="' + attr(f.key) +
          '" data-enabled="' + (f.enabled ? '1' : '0') + '">' + (f.enabled ? 'Disable' : 'Enable') + '</button>' : '-') +
        '</td></tr>';
    }).join('') + '</tbody></table></div></section>';

  html += '<section class="card"><h2 class="page-title">Subscribers</h2>' +
    (data.subscribers.length ? '<div class="table-wrap"><table class="data"><thead><tr><th>Key</th>' +
      '<th>Email</th><th>Name</th></tr></thead><tbody>' +
      data.subscribers.map(function (s) {
        return '<tr><td class="mono">' + esc(s.subscriber_key) + '</td><td>' + esc(s.email || '-') +
          '</td><td>' + esc(s.name || '-') + '</td></tr>';
      }).join('') + '</tbody></table></div>'
      : '<p class="muted small">No subscribers yet.</p>') +
    '<form data-form="automation-subscriber-search"><div class="form-grid">' +
    field('q', 'Search key / email / name', { placeholder: 'leave blank for all' }) +
    '</div><div class="form-actions"><button type="submit" class="btn">' +
    icon('search', 15) + ' Search</button></div></form>' +
    (write ? '<form data-form="automation-subscriber-create"><div class="form-grid">' +
      field('subscriber_key', 'Subscriber key', { required: true }) +
      field('email', 'Email', { placeholder: 'optional' }) +
      field('name', 'Name', { placeholder: 'optional' }) +
      '</div><div class="form-actions"><button type="submit" class="btn">' +
      icon('plus', 15) + ' Add subscriber</button></div></form>' +
      '<form data-form="automation-subscriber-bulk"><div class="form-grid">' +
      field('keys', 'Bulk keys (comma-separated, max 500)', { required: true, span: true, placeholder: 'u1, u2, u3' }) +
      '</div><div class="form-actions"><button type="submit" class="btn">' +
      icon('plus', 15) + ' Bulk create</button></div></form>' +
      '<form data-form="automation-endpoint-add"><div class="form-grid">' +
      field('subscriber_id', 'Subscriber', { type: 'select', options: subIdOptions }) +
      field('channel', 'Channel', { type: 'select', options: selectOptions([
        ['email', 'email'], ['sms', 'sms'], ['push', 'push'], ['chat', 'chat'],
      ]) }) +
      field('endpoint', 'Endpoint / token / phone', { required: true }) +
      field('secret', 'Channel secret (stored hashed)', { placeholder: 'optional' }) +
      '</div><div class="form-actions"><button type="submit" class="btn">' +
      icon('plus', 15) + ' Add endpoint</button></div></form>' : '') + '</section>';

  if (write) {
    html += '<section class="card"><h2 class="page-title">Code steps (sandboxed)</h2>' +
      (data.codeSteps.length ? '<div class="table-wrap"><table class="data"><thead><tr><th>Workflow/step</th>' +
        '<th>Version</th><th>Published</th></tr></thead><tbody>' +
        data.codeSteps.map(function (s) {
          return '<tr><td class="mono">' + esc(s.workflow_key + '/' + s.step_key) + '</td><td>' + s.version +
            '</td><td>' + statusBadge(s.published ? 'published' : 'draft') + '</td></tr>';
        }).join('') + '</tbody></table></div>' : '') +
      '<form data-form="automation-code-step-create"><div class="form-grid">' +
      field('workflow_key', 'Workflow key', { required: true }) +
      field('step_key', 'Step key', { required: true }) +
      field('code', 'Expression', { type: 'textarea', required: true, span: true, placeholder: 'payload.amount * 2' }) +
      checkboxField('publish', 'Publish step', true) +
      '</div><div class="form-actions"><button type="submit" class="btn">' +
      icon('plus', 15) + ' Save code step</button></div></form>' +
      (data.codeSteps.length ? '<form data-form="automation-code-step-evaluate"><div class="form-grid">' +
      field('step_id', 'Published step', { type: 'select', options: stepOptions }) +
      field('payload', 'Payload JSON', { type: 'textarea', span: true, value: '{}' }) +
      '</div><div class="form-actions"><button type="submit" class="btn">' +
      icon('activity', 15) + ' Evaluate</button></div></form>' : '') + '</section>';

    html += '<section class="card"><h2 class="page-title">HTTP steps (local stubs only)</h2>' +
      (data.httpStubs.length ? '<div class="table-wrap"><table class="data"><thead><tr><th>Path</th>' +
        '<th>Method</th></tr></thead><tbody>' +
        data.httpStubs.map(function (s) {
          return '<tr><td class="mono">' + esc(s.path) + '</td><td>' + statusBadge(s.method) + '</td></tr>';
        }).join('') + '</tbody></table></div>' : '') +
      '<form data-form="automation-http-stub-create"><div class="form-grid">' +
      field('path', 'Stub path', { required: true, placeholder: '/local/pricing' }) +
      field('method', 'Method', { type: 'select', options: selectOptions([
        ['GET', 'GET'], ['POST', 'POST'], ['PUT', 'PUT'], ['PATCH', 'PATCH'], ['DELETE', 'DELETE'],
      ]) }) +
      field('response', 'Response JSON', { type: 'textarea', span: true, value: '{}' }) +
      '</div><div class="form-actions"><button type="submit" class="btn">' +
      icon('plus', 15) + ' Register stub</button></div></form>' +
      '<form data-form="automation-http-step-create"><div class="form-grid">' +
      field('workflow_key', 'Workflow key', { required: true }) +
      field('step_key', 'Step key', { required: true }) +
      field('method', 'Method', { type: 'select', options: selectOptions([['GET', 'GET'], ['POST', 'POST']]) }) +
      field('path', 'Local path', { required: true, placeholder: '/local/pricing' }) +
      checkboxField('authorized', 'Explicitly authorise this step', false) +
      '</div><div class="form-actions"><button type="submit" class="btn">' +
      icon('plus', 15) + ' Add HTTP step</button></div></form>' +
      '<p class="muted small">Run authorised steps from the contract modal; unauthorised steps fail closed with 403.</p>' +
      '</section>';

    html += '<section class="card"><h2 class="page-title">Provider routing</h2>' +
      (data.routing.length ? '<div class="table-wrap"><table class="data"><thead><tr><th>Workflow</th>' +
        '<th>Provider</th><th>Priority</th><th></th></tr></thead><tbody>' +
        data.routing.map(function (r) {
          return '<tr><td class="mono">' + esc(r.workflow_key) + '</td><td>' + statusBadge(r.provider) +
            '</td><td>' + r.priority + '</td><td><button class="btn btn--sm" data-action="remove-automation-routing-rule" data-id="' +
            attr(r.id) + '">Remove</button></td></tr>';
        }).join('') + '</tbody></table></div>' : '') +
      '<form data-form="automation-routing-rule-create"><div class="form-grid">' +
      field('workflow_key', 'Workflow key', { required: true }) +
      field('provider', 'Provider', { type: 'select', options: selectOptions([
        ['demo_email', 'demo_email'], ['demo_sms', 'demo_sms'], ['in_app', 'in_app'],
      ]) }) +
      field('priority', 'Priority (lower first)', { type: 'number', value: '100' }) +
      field('conditions', 'Conditions JSON', { type: 'textarea', span: true, value: '[]', placeholder: '[{"source":"context","key":"region","equals":"IN"}]' }) +
      '</div><div class="form-actions"><button type="submit" class="btn">' +
      icon('plus', 15) + ' Add rule</button></div></form>' +
      '<form data-form="automation-routing-evaluate"><div class="form-grid">' +
      field('workflow_key', 'Workflow key', { required: true }) +
      field('subscriber_key', 'Subscriber key', { placeholder: 'optional' }) +
      field('context', 'Context JSON', { type: 'textarea', span: true, value: '{}' }) +
      '</div><div class="form-actions"><button type="submit" class="btn">' +
      icon('activity', 15) + ' Evaluate routing</button></div></form>' + '</section>';

    html += '<section class="card"><h2 class="page-title">Demo providers and broadcast</h2>' +
      '<div class="table-wrap"><table class="data"><thead><tr><th>Provider</th><th>Daily limit</th>' +
      '<th>Used today</th><th>Remaining</th></tr></thead><tbody>' +
      data.demo.map(function (p) {
        return '<tr><td>' + statusBadge(p.provider) + '</td><td>' + p.daily_limit + '</td><td>' +
          p.used_today + '</td><td>' + p.remaining + '</td></tr>';
      }).join('') + '</tbody></table></div>' +
      '<form data-form="automation-demo-send"><div class="form-grid">' +
      field('provider', 'Demo provider', { type: 'select', options: selectOptions([
        ['demo_email', 'demo_email'], ['demo_sms', 'demo_sms'],
      ]) }) +
      field('subscriber_key', 'Subscriber', { type: 'select', options: subOptions }) +
      field('payload', 'Payload JSON', { type: 'textarea', span: true, value: '{}' }) +
      '</div><div class="form-actions"><button type="submit" class="btn">' +
      icon('activity', 15) + ' Simulated send</button></div></form>' +
      '<form data-form="automation-broadcast"><div class="form-grid">' +
      field('workflow_key', 'Workflow key', { required: true }) +
      field('payload', 'Payload JSON', { type: 'textarea', span: true, value: '{}' }) +
      checkboxField('authorized', 'Explicitly authorise broadcast to all subscribers', false) +
      '</div><div class="form-actions"><button type="submit" class="btn btn--primary">' +
      icon('bell', 15) + ' Broadcast (local only)</button></div></form>' +
      (data.deliveries.length ? '<div class="table-wrap"><table class="data"><thead><tr><th>Provider</th>' +
        '<th>Workflow</th><th>Status</th></tr></thead><tbody>' +
        data.deliveries.slice(0, 20).map(function (d) {
          return '<tr><td>' + statusBadge(d.provider) + '</td><td class="mono">' + esc(d.workflow_key || '-') +
            '</td><td>' + statusBadge(d.status) + '</td></tr>';
        }).join('') + '</tbody></table></div>' : '') + '</section>';
  }
  renderViewHtml(html);
}

async function loadNotificationWorkflows(token) {
  if (!can(P.contactRead)) {
    renderViewHtml(pageHead('Operations', 'Notification workflows', '') +
      errorBlock('Your role does not include notification access.'));
    return;
  }
  loadingView('Notification workflows', 'Local, workspace-scoped notification workflows.');
  let data;
  try {
    const base = apiW('/notification-workflows');
    const [workflows, templates, feeds, contexts, layouts, endpoints, contract] = await Promise.all([
      api(base + '/workflows'), api(base + '/templates'), api(base + '/feeds'),
      api(base + '/contexts'), api(base + '/layouts'), api(base + '/webhooks/endpoints'),
      api(base + '/api-contract'),
    ]);
    data = { workflows: workflows || [], templates: templates || [], feeds: feeds || [],
      contexts: contexts || [], layouts: layouts || [], endpoints: endpoints || [],
      contract: contract || {} };
  } catch (err) {
    if (token !== state.viewToken) return;
    renderViewHtml(pageHead('Operations', 'Notification workflows', '') + errorBlock(errMessage(err)));
    return;
  }
  if (token !== state.viewToken) return;

  let html = pageHead('Operations', 'Notification workflows',
    data.workflows.length + ' workflow' + (data.workflows.length === 1 ? '' : 's') +
    ' Ã‚Â· stable API v' + esc(String(data.contract.version || '1')),
    can(P.noteWrite)
      ? '<button class="btn btn--primary" data-action="create-notification-workflow">' +
        icon('plus', 15) + ' New workflow</button>' +
        '<button class="btn" data-action="instantiate-notification-template">From template</button>'
      : '');
  html += governanceNote('Everything here is stored in this workspace. No email, push or webhook is sent externally; webhook deliveries are signed records for local verification.');

  html += '<section class="card"><h2 class="page-title">Workflows</h2>';
  if (!data.workflows.length) {
    html += emptyState('bell', 'No workflows yet', 'Create one or instantiate a clean-room template.');
  } else {
    html += '<div class="table-wrap"><table class="data"><thead><tr><th>Key</th><th>Severity</th>' +
      '<th>Channel</th><th>Feed</th><th>Context</th><th>Status</th><th>Actions</th></tr></thead><tbody>' +
      data.workflows.map(function (w) {
        return '<tr><td>' + esc(w.key) + (w.critical ? ' <span class="badge">critical</span>' : '') +
          '</td><td>' + esc(w.severity) + '</td><td class="small">' + esc(w.channel) + '</td>' +
          '<td class="small">' + esc(w.feed_key || '-') + '</td><td class="small">' +
          esc(w.context_key || '-') + '</td><td>' + (w.active ? 'Active' : 'Disabled') + '</td><td>' +
          (can(P.noteWrite)
            ? '<button class="btn btn--sm" data-action="trigger-notification-workflow" data-id="' +
              attr(w.id) + '">Trigger</button> ' +
              (w.digest_rule ? '<button class="btn btn--sm" data-action="evaluate-notification-digest" data-id="' +
                attr(w.id) + '">Digest</button>' : '')
            : '-') + '</td></tr>';
      }).join('') + '</tbody></table></div>';
  }
  html += '</section>';

  html += '<section class="card"><h2 class="page-title">Message feed</h2>' +
    '<form data-form="filter-notification-messages"><div class="form-grid">' +
    field('feed', 'Feed', { type: 'select', options: selectOptions(
      [['', 'All feeds']].concat(data.feeds.map(function (f) { return [f.key, f.name]; })),
      state.lastNotificationFeed || '') }) +
    field('context', 'Context', { type: 'select', options: selectOptions(
      [['', 'All contexts']].concat(data.contexts.map(function (c) { return [c.key, c.name]; })),
      state.lastNotificationContext || '') }) +
    '</div><div class="form-actions"><button type="submit" class="btn btn--primary">' +
    icon('filter', 15) + ' Apply filters</button></div></form>';
  const feedParam = state.lastNotificationFeed ? '?feed=' + encodeURIComponent(state.lastNotificationFeed) : '';
  let messages = [];
  try {
    messages = await api(base + '/messages' + feedParam) || [];
  } catch (err) { messages = []; }
  if (messages.length) {
    html += '<div class="table-wrap"><table class="data"><thead><tr><th>Title</th><th>Feed</th>' +
      '<th>Status</th><th>Context</th></tr></thead><tbody>' +
      messages.map(function (m) {
        return '<tr><td>' + esc(m.title) + '</td><td class="small">' + esc(m.feed_key || '-') +
          '</td><td class="small">' + esc(m.status) + '</td><td class="small">' +
          esc(m.context_key || '-') + '</td></tr>';
      }).join('') + '</tbody></table></div>';
  } else {
    html += emptyState('bell', 'No messages', 'Trigger a workflow to record a local message.');
  }
  html += '</section>';

  html += '<section class="card"><h2 class="page-title">Routing building blocks</h2>' +
    '<p class="muted small">' + data.feeds.length + ' feeds Ã‚Â· ' + data.contexts.length +
    ' contexts Ã‚Â· ' + data.layouts.length + ' layouts Ã‚Â· ' + data.endpoints.length +
    ' webhook endpoints</p>' +
    (can(P.noteWrite)
      ? '<div class="form-actions">' +
        '<button class="btn btn--sm" data-action="create-notification-feed">New feed</button>' +
        '<button class="btn btn--sm" data-action="create-notification-context">New context</button>' +
        '<button class="btn btn--sm" data-action="create-notification-layout">New layout</button>' +
        (can(P.workspaceManage)
          ? '<button class="btn btn--sm" data-action="create-notification-webhook">New webhook endpoint</button>'
          : '') + '</div>'
      : '') + '</section>';
  renderViewHtml(html);
}

async function loadFeedbackIntelligence(token) {
  if (!can(P.contactRead)) {
    renderViewHtml(pageHead('Operations', 'Feedback intelligence', '') +
      errorBlock('Your role does not include feedback access.'));
    return;
  }
  loadingView('Feedback intelligence', 'Local, workspace-scoped feedback datasets, sources and insights.');
  let data;
  try {
    const base = apiW('/feedback-intelligence');
    const [contract, datasets, fields, segments, dashboards, insights, reserved] = await Promise.all([
      api(base + '/api-contract'), api(base + '/datasets'), api(base + '/fields'),
      api(base + '/segments'), api(base + '/dashboards'), api(base + '/unify/insights'),
      api(base + '/reserved-fields'),
    ]);
    data = { contract: contract || {}, datasets: datasets || [], fields: fields || [],
      segments: segments || [], dashboards: dashboards || [], insights: insights || {},
      reserved: reserved || [] };
  } catch (err) {
    if (token !== state.viewToken) return;
    renderViewHtml(pageHead('Operations', 'Feedback intelligence', '') + errorBlock(errMessage(err)));
    return;
  }
  if (token !== state.viewToken) return;

  let html = pageHead('Operations', 'Feedback intelligence',
    data.insights.total_records + ' records Ã‚Â· ' + data.datasets.length + ' datasets Ã‚Â· ' +
    data.fields.length + ' library fields',
    can(P.noteWrite)
      ? '<button class="btn btn--primary" data-action="create-feedback-dataset">' +
        icon('plus', 15) + ' New dataset</button>' +
        '<button class="btn" data-action="create-feedback-field">New field</button>' +
        '<button class="btn" data-action="create-feedback-segment">New segment</button>' +
        '<button class="btn" data-action="create-feedback-dashboard">New dashboard</button>'
      : '');
  html += governanceNote('All feedback is stored in this workspace. Insights are computed from persisted records. No external feedback provider, analytics service or model is contacted.');

  html += '<section class="card"><h2 class="page-title">Unified insights</h2>' +
    '<p><span class="badge badge--plain">Records: ' + esc(String(data.insights.total_records || 0)) +
    '</span> <span class="badge badge--plain">Datasets: ' +
    esc(String(data.insights.dataset_count || 0)) +
    '</span> <span class="badge badge--plain">Sources: ' +
    esc(String(data.insights.source_count || 0)) + '</span></p>';
  const bySentiment = data.insights.by_sentiment || {};
  const sentimentParts = Object.keys(bySentiment).map(function (k) {
    return esc(k) + ': ' + esc(String(bySentiment[k]));
  });
  html += '<p class="muted small">' +
    (sentimentParts.length ? sentimentParts.join(' Ã‚Â· ') : 'No records ingested yet') + '</p>';
  html += '</section>';

  html += '<section class="card"><h2 class="page-title">Datasets and sources</h2>';
  if (!data.datasets.length) {
    html += emptyState('layers', 'No feedback datasets', 'Create a dataset and a source to start ingesting feedback.');
  } else {
    html += '<div class="table-wrap"><table class="data"><thead><tr><th>Dataset</th>' +
      '<th>Detail</th><th>Actions</th></tr></thead><tbody>' +
      data.datasets.map(function (d) {
        return '<tr><td>' + esc(d.name) + ' <span class="muted small">' + esc(d.key) +
          '</span></td><td class="small muted">see records</td><td>' +
          (can(P.noteWrite)
            ? '<button class="btn btn--sm" data-action="create-feedback-source" data-id="' +
              attr(d.id) + '">Add source</button> ' +
              '<button class="btn btn--sm" data-action="ingest-feedback" data-id="' +
              attr(d.id) + '">Ingest</button> ' +
              '<button class="btn btn--sm" data-action="view-feedback-records" data-id="' +
              attr(d.id) + '">Records</button>'
            : '-') + '</td></tr>';
      }).join('') + '</tbody></table></div>';
  }
  html += '</section>';

  html += '<section class="card"><h2 class="page-title">Field library, segments and dashboards</h2>' +
    '<p class="muted small">' + data.fields.length + ' reusable fields Ã‚Â· ' +
    data.segments.length + ' audience segments Ã‚Â· ' + data.dashboards.length + ' dashboards</p>';
  if (data.dashboards.length) {
    html += '<div class="form-actions">' + data.dashboards.map(function (d) {
      return '<button class="btn btn--sm" data-action="view-feedback-dashboard" data-id="' +
        attr(d.id) + '">' + icon('insights', 14) + ' ' + esc(d.name) + '</button>';
    }).join('') + '</div>';
  }
  html += '<p class="muted small">Reserved fields captured on every record: ' +
    data.reserved.map(function (r) { return esc(r.name); }).join(', ') + '</p>';
  html += '</section>';
  renderViewHtml(html);
}

async function loadExperimentStats(token) {
  if (!can(P.contactRead)) {
    renderViewHtml(pageHead('Operations', 'Experiment statistics', '') +
      errorBlock('Your role does not include experiment access.'));
    return;
  }
  loadingView('Experiment statistics', 'Workspace-scoped experiment definitions, observations and local statistics.');
  let data;
  try {
    const base = apiW('/experiment-stats');
    const [contract, metrics, experiments] = await Promise.all([
      api(base + '/api-contract'), api(base + '/metrics'), api(base + '/experiments'),
    ]);
    data = { contract: contract || {}, metrics: metrics || [], experiments: experiments || [] };
  } catch (err) {
    if (token !== state.viewToken) return;
    renderViewHtml(pageHead('Operations', 'Experiment statistics', '') + errorBlock(errMessage(err)));
    return;
  }
  if (token !== state.viewToken) return;

  let html = pageHead('Operations', 'Experiment statistics',
    data.experiments.length + ' experiments Ã‚Â· ' + data.metrics.length + ' metrics',
    can(P.noteWrite)
      ? '<button class="btn btn--primary" data-action="create-experiment-definition">' +
        icon('plus', 15) + ' New experiment</button>' +
        '<button class="btn" data-action="create-experiment-metric">New metric</button>'
      : '');
  html += governanceNote('Statistics are computed locally from persisted workspace observations. No GrowthBook source, hosted experiment platform or external statistics service is used.');

  html += '<section class="card"><h2 class="page-title">Statistics tools</h2>' +
    '<div class="form-actions">' +
    '<button class="btn btn--sm" data-action="run-power-analysis">' + icon('activity', 14) + ' Power analysis</button>' +
    '<button class="btn btn--sm" data-action="run-correction">Multiple-testing correction</button>' +
    '</div><p class="muted small">Engines: ' + esc((data.contract.engines || []).join(', ')) +
    ' Ã‚Â· Metric types: ' + esc((data.contract.metric_types || []).join(', ')) + '</p></section>';

  html += '<section class="card"><h2 class="page-title">Metric definitions</h2>';
  if (!data.metrics.length) {
    html += emptyState('insights', 'No metrics yet', 'Define a proportion, mean or ratio metric to analyse an experiment.');
  } else {
    html += '<div class="table-wrap"><table class="data"><thead><tr><th>Key</th><th>Name</th>' +
      '<th>Type</th></tr></thead><tbody>' + data.metrics.map(function (m) {
        return '<tr><td class="mono">' + esc(m.key) + '</td><td>' + esc(m.name) + '</td><td>' +
          statusBadge(m.type) + '</td></tr>';
      }).join('') + '</tbody></table></div>';
  }
  html += '</section>';

  html += '<section class="card"><h2 class="page-title">Experiments</h2>';
  if (!data.experiments.length) {
    html += emptyState('insights', 'No experiments yet', 'Create an experiment with 2-10 variants and a traffic split.');
  } else {
    html += '<div class="table-wrap"><table class="data"><thead><tr><th>Experiment</th>' +
      '<th>Variants</th><th>Actions</th></tr></thead><tbody>' + data.experiments.map(function (e) {
        return '<tr><td>' + esc(e.name) + ' <span class="muted small mono">' + esc(e.key) +
          '</span></td><td class="small">' + esc(String(e.variants.length)) + '</td><td>' +
          (can(P.noteWrite)
            ? '<button class="btn btn--sm" data-action="record-experiment-observation" data-id="' +
              attr(e.id) + '">Record</button> '
            : '') +
          '<button class="btn btn--sm" data-action="analyze-experiment" data-id="' + attr(e.id) +
          '">Analyze</button> ' +
          '<button class="btn btn--sm" data-action="check-experiment-srm" data-id="' + attr(e.id) +
          '">SRM</button> ' +
          '<button class="btn btn--sm" data-action="check-experiment-health" data-id="' + attr(e.id) +
          '">Health</button></td></tr>';
      }).join('') + '</tbody></table></div>';
  }
  html += '</section>';
  renderViewHtml(html);
}

async function loadExperimentOps(token) {
  if (!can(P.contactRead)) {
    renderViewHtml(pageHead('Operations', 'Experiment operations', '') +
      errorBlock('Your role does not include experiment access.'));
    return;
  }
  loadingView('Experiment operations', 'Projects, saved groups, revisions, segments and diagnostics.');
  let data;
  try {
    const base = apiW('/experiment-ops');
    const [contract, projects, dimensions, segments, tests, stale, flags] = await Promise.all([
      api(base + '/api-contract'), api(base + '/projects'), api(base + '/dimensions'),
      api(base + '/segments'), api(base + '/aa-tests'), api(base + '/stale-flags'),
      api(apiW('/flags')),
    ]);
    data = { contract: contract || {}, projects: projects || [], dimensions: dimensions || [],
      segments: segments || [], tests: tests || [], stale: stale || {}, flags: flags || [] };
  } catch (err) {
    if (token !== state.viewToken) return;
    renderViewHtml(pageHead('Operations', 'Experiment operations', '') + errorBlock(errMessage(err)));
    return;
  }
  if (token !== state.viewToken) return;

  let html = pageHead('Operations', 'Experiment operations',
    data.projects.length + ' projects Ã‚Â· ' + data.flags.length + ' flags Ã‚Â· ' +
    data.stale.count + ' stale candidates',
    can(P.noteWrite)
      ? '<button class="btn btn--primary" data-action="create-experiment-project">' +
        icon('plus', 15) + ' New project</button>' +
        '<button class="btn" data-action="create-experiment-dimension">New dimension</button>' +
        '<button class="btn" data-action="create-experiment-segment">New segment</button>'
      : '');
  html += governanceNote('All definitions and change history live in this workspace. No GrowthBook server, warehouse or hosted experiment platform is contacted.');

  html += '<section class="card"><h2 class="page-title">Projects and saved groups</h2>';
  if (!data.projects.length) {
    html += emptyState('layers', 'No projects', 'Create a project to namespace flags and experiments.');
  } else {
    html += '<div class="table-wrap"><table class="data"><thead><tr><th>Project</th><th>Key</th>' +
      '<th>State</th><th>Actions</th></tr></thead><tbody>' + data.projects.map(function (p) {
        return '<tr><td>' + esc(p.name) + '</td><td class="mono">' + esc(p.key) + '</td><td>' +
          statusBadge(p.archived ? 'archived' : 'active') + '</td><td>' +
          (can(P.noteWrite)
            ? '<button class="btn btn--sm" data-action="create-saved-group" data-id="' +
              attr(p.id) + '">Add saved group</button> ' +
              '<button class="btn btn--sm" data-action="archive-experiment-project" data-id="' +
              attr(p.id) + '">Archive</button>'
            : '-') + '</td></tr>';
      }).join('') + '</tbody></table></div>';
  }
  html += '</section>';

  html += '<section class="card"><h2 class="page-title">Flags, revisions and diagnostics</h2>' +
    '<div class="form-actions">' +
    '<button class="btn btn--sm" data-action="view-stale-flags">' + icon('activity', 14) +
    ' Stale flag candidates</button></div>';
  if (!data.flags.length) {
    html += '<p class="muted small">No feature flags in this workspace yet.</p>';
  } else {
    html += '<div class="table-wrap"><table class="data"><thead><tr><th>Flag</th><th>State</th>' +
      '<th>Actions</th></tr></thead><tbody>' + data.flags.map(function (f) {
        return '<tr><td class="mono">' + esc(f.key) + '</td><td>' +
          statusBadge(f.enabled ? 'active' : 'disabled') + '</td><td>' +
          '<button class="btn btn--sm" data-action="view-flag-history" data-id="' + attr(f.id) +
          '">History</button> ' +
          '<button class="btn btn--sm" data-action="diagnose-flag" data-id="' + attr(f.id) +
          '">Diagnose</button> ' +
          (can(P.noteWrite)
            ? '<button class="btn btn--sm" data-action="create-flag-revision" data-id="' +
              attr(f.id) + '">New revision</button> ' +
              '<button class="btn btn--sm" data-action="archive-flag" data-id="' + attr(f.id) +
              '">Archive</button>'
            : '') + '</td></tr>';
      }).join('') + '</tbody></table></div>';
  }
  html += '</section>';

  html += '<section class="card"><h2 class="page-title">Segments, A/A tests and time series</h2>' +
    '<p class="muted small">' + data.segments.length + ' segments Ã‚Â· ' + data.tests.length +
    ' A/A tests Ã‚Â· ' + esc((data.contract.resources || []).join(', ')) + '</p>';
  if (!data.tests.length) {
    html += emptyState('activity', 'No A/A tests', 'A/A tests validate assignment and metric plumbing.');
  } else {
    html += '<div class="table-wrap"><table class="data"><thead><tr><th>A/A test</th><th>Status</th>' +
      '<th>Action</th></tr></thead><tbody>' + data.tests.map(function (t) {
        return '<tr><td>' + esc(t.name) + ' <span class="muted small mono">' + esc(t.key) +
          '</span></td><td>' + statusBadge(t.status) + '</td><td>' +
          '<button class="btn btn--sm" data-action="view-aa-result" data-id="' + attr(t.id) +
          '">Result</button></td></tr>';
      }).join('') + '</tbody></table></div>';
  }
  html += '<div class="form-actions">' +
    '<button class="btn btn--sm" data-action="create-aa-test">New A/A test</button>' +
    '<button class="btn btn--sm" data-action="create-timeseries-point">Record time series point</button>' +
    '<button class="btn btn--sm" data-action="view-timeseries">View time series</button>' +
    '</div></section>';
  renderViewHtml(html);
}

async function loadExperimentQueries(token) {
  if (!can(P.contactRead)) {
    renderViewHtml(pageHead('Operations', 'Experiment queries', '') +
      errorBlock('Your role does not include experiment access.'));
    return;
  }
  loadingView('Experiment queries', 'Local fact tables, discovery, assignment, identifiers, funnels and reports.');
  let data;
  try {
    const base = apiW('/experiment-queries');
    const [contract, facts, discovery, assignments, identifiers, joins, funnels, reports, carryover] = await Promise.all([
      api(base + '/api-contract'), api(base + '/fact-tables'), api(base + '/discovery-queries'),
      api(base + '/assignment-queries'), api(base + '/identifier-types'), api(base + '/identifier-joins'),
      api(base + '/funnels'), api(base + '/reports'), api(base + '/carryover'),
    ]);
    data = { contract: contract || {}, facts: facts || [], discovery: discovery || [],
      assignments: assignments || [], identifiers: identifiers || [], joins: joins || [],
      funnels: funnels || [], reports: reports || [], carryover: carryover || [] };
  } catch (err) {
    if (token !== state.viewToken) return;
    renderViewHtml(pageHead('Operations', 'Experiment queries', '') + errorBlock(errMessage(err)));
    return;
  }
  if (token !== state.viewToken) return;

  const create = can(P.noteWrite);
  let html = pageHead('Operations', 'Experiment queries',
    data.facts.length + ' fact tables Ã‚Â· ' + data.discovery.length + ' queries Ã‚Â· ' +
    data.reports.length + ' reports',
    create
      ? '<button class="btn btn--primary" data-action="create-query-fact-table">' +
        icon('plus', 15) + ' New fact table</button>' +
        '<button class="btn" data-action="create-discovery-query">New discovery query</button>' +
        '<button class="btn" data-action="create-assignment-query">New assignment query</button>'
      : '');
  html += governanceNote('Definitions and results are local logical views over this workspace\'s experiment, assignment, exposure and time-series rows. No warehouse SQL, external source or hosted platform is contacted.');

  html += '<section class="card"><h2 class="page-title">Fact tables and discovery</h2>' +
    '<p class="muted small">Sources: ' + esc((data.contract.fact_sources || []).join(', ')) + '</p>';
  if (!data.facts.length) {
    html += emptyState('layers', 'No fact tables', 'Describe a local row set before running discovery queries.');
  } else {
    html += '<div class="table-wrap"><table class="data"><thead><tr><th>Fact table</th><th>Source</th>' +
      '<th>Fields</th><th>Action</th></tr></thead><tbody>' + data.facts.map(function (f) {
        return '<tr><td>' + esc(f.name) + ' <span class="muted small mono">' + esc(f.key) + '</span></td>' +
          '<td>' + statusBadge(f.source) + '</td><td class="small">' + esc((f.fields || []).join(', ')) + '</td>' +
          '<td><button class="btn btn--sm" data-action="preview-query-fact-table" data-id="' +
          attr(f.id) + '">Preview</button></td></tr>';
      }).join('') + '</tbody></table></div>';
  }
  if (data.discovery.length) {
    html += '<h3 class="page-title small">Discovery queries</h3><div class="table-wrap"><table class="data">' +
      '<thead><tr><th>Query</th><th>Key</th><th>Action</th></tr></thead><tbody>' + data.discovery.map(function (q) {
        return '<tr><td>' + esc(q.name) + '</td><td class="mono">' + esc(q.key) + '</td><td>' +
          '<button class="btn btn--sm" data-action="run-discovery-query" data-id="' + attr(q.id) +
          '">Run</button></td></tr>';
      }).join('') + '</tbody></table></div>';
  }
  html += '</section>';

  html += '<section class="card"><h2 class="page-title">Assignment queries and identifiers</h2>' +
    (create
      ? '<div class="form-actions"><button class="btn btn--sm" data-action="create-identifier-type">' +
        'New identifier type</button><button class="btn btn--sm" data-action="create-identifier-join">' +
        'New identifier join</button></div>'
      : '');
  if (!data.assignments.length) {
    html += emptyState('search', 'No assignment queries', 'Define a query to identify exposed units in a local experiment.');
  } else {
    html += '<div class="table-wrap"><table class="data"><thead><tr><th>Query</th><th>Experiment</th>' +
      '<th>Action</th></tr></thead><tbody>' + data.assignments.map(function (q) {
        return '<tr><td>' + esc(q.name) + '</td><td class="mono">' + esc(q.experiment_key) + '</td><td>' +
          '<button class="btn btn--sm" data-action="run-assignment-query" data-id="' + attr(q.id) +
          '">Run</button></td></tr>';
      }).join('') + '</tbody></table></div>';
  }
  if (data.identifiers.length) {
    html += '<h3 class="page-title small">Identifier types</h3><div class="table-wrap"><table class="data">' +
      '<thead><tr><th>Type</th><th>Attribute</th><th>Normalisation</th><th>Action</th></tr></thead><tbody>' +
      data.identifiers.map(function (t) {
        return '<tr><td>' + esc(t.name) + ' <span class="muted small mono">' + esc(t.key) + '</span></td>' +
          '<td class="mono">' + esc(t.attribute) + '</td><td>' + statusBadge(t.normalization) + '</td><td>' +
          '<button class="btn btn--sm" data-action="normalize-identifier" data-id="' + attr(t.id) +
          '" data-value="u1">Normalise sample</button></td></tr>';
      }).join('') + '</tbody></table></div>';
  }
  if (data.joins.length) {
    html += '<h3 class="page-title small">Identifier joins</h3><div class="table-wrap"><table class="data">' +
      '<thead><tr><th>Join</th><th>Mappings</th><th>Action</th></tr></thead><tbody>' +
      data.joins.map(function (j) {
        return '<tr><td>' + esc(j.name) + '</td><td>' + Number(j.mappings || 0) + '</td><td>' +
          '<button class="btn btn--sm" data-action="resolve-identifier-join" data-id="' + attr(j.id) +
          '">Resolve</button></td></tr>';
      }).join('') + '</tbody></table></div>';
  }
  html += '</section>';

  html += '<section class="card"><h2 class="page-title">Funnels, reports and carryover</h2>' +
    (create
      ? '<div class="form-actions"><button class="btn btn--sm" data-action="create-experiment-funnel">' +
        'New funnel</button><button class="btn btn--sm" data-action="create-experiment-report">' +
        'New report</button><button class="btn btn--sm" data-action="assess-carryover">' +
        'Assess carryover</button></div>'
      : '');
  if (!data.funnels.length && !data.reports.length) {
    html += emptyState('insights', 'No funnels or reports', 'Create a funnel or report over local experiment data.');
  } else {
    html += '<div class="table-wrap"><table class="data"><thead><tr><th>Definition</th><th>Type</th>' +
      '<th>Action</th></tr></thead><tbody>' +
      data.funnels.map(function (f) {
        return '<tr><td>' + esc(f.name) + '</td><td>' + statusBadge('funnel') + '</td><td>' +
          '<button class="btn btn--sm" data-action="view-experiment-funnel" data-id="' + attr(f.id) +
          '">Result</button></td></tr>';
      }).join('') +
      data.reports.map(function (r) {
        return '<tr><td>' + esc(r.name) + '</td><td>' + statusBadge(r.report_type) + '</td><td>' +
          '<button class="btn btn--sm" data-action="run-experiment-report" data-id="' + attr(r.id) +
          '">Run</button></td></tr>';
      }).join('') + '</tbody></table></div>';
  }
  if (data.carryover.length) {
    html += '<div class="table-wrap"><table class="data"><thead><tr><th>Assessment</th><th>Warning</th>' +
      '<th>Action</th></tr></thead><tbody>' + data.carryover.map(function (c) {
        return '<tr><td>' + esc(c.key) + '</td><td>' + statusBadge(c.warning ? 'warning' : 'clear') +
          '</td><td>' + (c.acknowledged ? 'Acknowledged' :
            '<button class="btn btn--sm" data-action="acknowledge-carryover" data-id="' + attr(c.id) +
            '">Acknowledge</button>') + '</td></tr>';
      }).join('') + '</tbody></table></div>';
  }
  html += '</section>';
  renderViewHtml(html);
}

async function loadExperimentPlatform(token) {
  if (!can(P.contactRead)) {
    renderViewHtml(pageHead('Operations', 'Experiment platform', '') +
      errorBlock('Your role does not include experimentation access.'));
    return;
  }
  loadingView('Experiment platform', 'Generated API contract, default roles and scoped credential policies.');
  let data;
  try {
    const base = apiW('/experiment-platform');
    const [contract, openapi, inventory, credentials, roles, bindings] = await Promise.all([
      api(base + '/api-contract'), api(base + '/openapi-status'), api(base + '/rest-inventory'),
      api(base + '/credentials'), api(base + '/roles'), api(base + '/roles/bindings'),
    ]);
    data = { contract: contract || {}, openapi: openapi || {}, inventory: inventory || {},
      credentials: credentials || {}, roles: roles || [], bindings: bindings || [] };
  } catch (err) {
    if (token !== state.viewToken) return;
    renderViewHtml(pageHead('Operations', 'Experiment platform', '') + errorBlock(errMessage(err)));
    return;
  }
  if (token !== state.viewToken) return;

  const manage = can(P.workspaceManage);
  let html = pageHead('Operations', 'Experiment platform',
    data.openapi.operation_count + ' live operations Ã‚Â· ' + data.roles.length + ' default roles',
    '<button class="btn" data-action="view-experiment-openapi">' + icon('info', 15) +
      ' API contract</button>' +
      (manage ? '<button class="btn btn--primary" data-action="bind-experiment-role">' +
        icon('plus', 15) + ' Bind role</button>' : '') +
      '<button class="btn" data-action="check-experiment-role">Check permission</button>');
  html += governanceNote('The OpenAPI status is computed from the live NOVARA app. Credentials are the existing scoped API-key layer; no secret is shown after creation and no external provider is contacted.');

  html += '<section class="card"><h2 class="page-title">API contract and REST surface</h2>' +
    '<p class="muted small">Version ' + esc(data.contract.version || '1') + ' Ã‚Â· delivery ' +
    esc(data.contract.delivery || 'local-only') + '</p>' +
    '<div class="stat-grid">' +
    statCard('activity', 'Live operations', String(data.inventory.operation_count || 0), 'Generated OpenAPI') +
    statCard('layers', 'Route modules', String((data.inventory.route_modules || []).length), 'Experimentation surface') +
    statCard('check', 'Contract clean', data.openapi.clean ? 'Yes' : 'No', 'Unique operation IDs') +
    '</div><p class="small">' + esc((data.inventory.route_modules || []).join(' Ã‚Â· ')) + '</p></section>';

  html += '<section class="card"><h2 class="page-title">Credential layers</h2>';
  Object.keys(data.credentials).forEach(function (name) {
    const policy = data.credentials[name] || {};
    html += '<div class="list-row"><div><strong>' + esc(name.replaceAll('_', ' ')) + '</strong>' +
      '<div class="muted small">' + esc(policy.implementation || '') + '</div></div>' +
      statusBadge(policy.external_provider ? 'external' : 'local') + '</div>';
  });
  html += '</section>';

  html += '<section class="card"><h2 class="page-title">Default experimentation roles</h2>' +
    '<div class="table-wrap"><table class="data"><thead><tr><th>Role</th><th>Permissions</th>' +
    '</tr></thead><tbody>' + data.roles.map(function (r) {
      return '<tr><td>' + statusBadge(r.role) + '</td><td class="small mono">' +
        esc((r.permissions || []).join(', ')) + '</td></tr>';
    }).join('') + '</tbody></table></div>';
  if (!data.bindings.length) {
    html += '<p class="muted small">No experiment role bindings in this workspace.</p>';
  } else {
    html += '<h3 class="page-title small">Workspace bindings</h3><div class="table-wrap"><table class="data">' +
      '<thead><tr><th>User</th><th>Role</th></tr></thead><tbody>' + data.bindings.map(function (b) {
        return '<tr><td class="mono">' + esc(b.user_id) + '</td><td>' + statusBadge(b.role) + '</td></tr>';
      }).join('') + '</tbody></table></div>';
  }
  html += '</section>';
  renderViewHtml(html);
}

async function loadExperimentDelivery(token) {
  if (!can(P.contactRead)) {
    renderViewHtml(pageHead('Operations', 'Experiment delivery', '') +
      errorBlock('Your role does not include experimentation access.'));
    return;
  }
  loadingView('Experiment delivery', 'Local webhooks, notifier, cache, proxy and refresh jobs.');
  let data;
  try {
    const base = apiW('/experiment-delivery');
    const [contract, webhooks, messages, cache, proxy, jobs] = await Promise.all([
      api(base + '/api-contract'), api(base + '/webhooks'), api(base + '/notifier'),
      api(base + '/cache'), api(base + '/proxy'), api(base + '/refresh-jobs'),
    ]);
    data = { contract: contract || {}, webhooks: webhooks || [], messages: messages || [],
      cache: cache || [], proxy: proxy || [], jobs: jobs || [] };
  } catch (err) {
    if (token !== state.viewToken) return;
    renderViewHtml(pageHead('Operations', 'Experiment delivery', '') + errorBlock(errMessage(err)));
    return;
  }
  if (token !== state.viewToken) return;

  const write = can(P.noteWrite);
  let html = pageHead('Operations', 'Experiment delivery',
    data.webhooks.length + ' webhooks Ã‚Â· ' + data.jobs.length + ' refresh jobs',
    '<button class="btn" data-action="view-delivery-contract">' + icon('info', 15) +
      ' Local contract</button>' +
      (write ? '<button class="btn btn--primary" data-action="create-delivery-webhook">' +
        icon('plus', 15) + ' New webhook</button>' +
        '<button class="btn" data-action="purge-delivery-cache">Purge cache</button>' +
        '<button class="btn" data-action="schedule-refresh-job">Schedule refresh</button>' : ''));
  html += governanceNote('Every delivery here is recorded in NOVARA only. No outbound webhook, Slack message, CDN call or external proxy fetch is made.');

  html += '<section class="card"><h2 class="page-title">Webhooks (local records)</h2>' +
    (data.webhooks.length ? '<div class="table-wrap"><table class="data"><thead><tr><th>Key</th>' +
      '<th>Scope</th><th>Event types</th><th>Target</th><th></th></tr></thead><tbody>' +
      data.webhooks.map(function (w) {
        return '<tr><td class="mono">' + esc(w.key) + '</td><td>' + statusBadge(w.scope) + '</td>' +
          '<td class="small">' + esc((w.event_types || []).join(', ') || 'all') + '</td>' +
          '<td class="small">' + esc(w.target_label) + '</td><td>' +
          (write ? '<button class="btn btn--sm" data-action="emit-delivery-webhook" data-id="' + attr(w.id) +
            '">Emit</button>' : '') + '</td></tr>';
      }).join('') + '</tbody></table></div>'
      : '<p class="muted small">No webhooks recorded. Create one to capture local deliveries.</p>') + '</section>';

  html += '<section class="card"><h2 class="page-title">Notifier, cache, proxy and jobs</h2>' +
    '<div class="stat-grid">' +
    statCard('activity', 'Notifier messages', String(data.messages.length), 'Local drafts/records') +
    statCard('layers', 'Cache entries', String(data.cache.length), 'Workspace-scoped') +
    statCard('check', 'Proxy snapshots', String(data.proxy.length), 'Local payloads') +
    statCard('clock', 'Refresh jobs', String(data.jobs.length), 'Local scheduler rows') +
    '</div>';
  if (data.jobs.length) {
    html += '<div class="table-wrap"><table class="data"><thead><tr><th>Key</th><th>Type</th>' +
      '<th>Target</th><th>Status</th><th></th></tr></thead><tbody>' + data.jobs.map(function (j) {
        return '<tr><td class="mono">' + esc(j.key) + '</td><td>' + esc(j.job_type) + '</td>' +
          '<td class="mono">' + esc(j.target_key) + '</td><td>' + statusBadge(j.status) + '</td><td>' +
          (write ? '<button class="btn btn--sm" data-action="run-refresh-job" data-id="' + attr(j.id) +
            '">Run</button>' : '') + '</td></tr>';
      }).join('') + '</tbody></table></div>';
  }
  html += '</section>';
  renderViewHtml(html);
}

async function loadSurveyDelivery(token) {
  if (!can(P.contactRead)) {
    renderViewHtml(pageHead('Operations', 'Survey delivery', '') +
      errorBlock('Your role does not include feedback access.'));
    return;
  }
  loadingView('Survey delivery', 'Local survey channels, flows, branding and creatives.');
  let data;
  try {
    const base = apiW('/survey-delivery');
    const [contract, configs, creatives] = await Promise.all([
      api(base + '/api-contract'), api(base + '/configs'), api(base + '/creatives'),
    ]);
    data = { contract: contract || {}, configs: configs || [], creatives: creatives || [] };
  } catch (err) {
    if (token !== state.viewToken) return;
    renderViewHtml(pageHead('Operations', 'Survey delivery', '') + errorBlock(errMessage(err)));
    return;
  }
  if (token !== state.viewToken) return;

  const write = can(P.noteWrite);
  let html = pageHead('Operations', 'Survey delivery',
    data.configs.length + ' configs Ã‚Â· ' + data.creatives.length + ' creatives',
    '<button class="btn" data-action="view-survey-contract">' + icon('info', 15) +
      ' Local contract</button>' +
      (write ? '<button class="btn btn--primary" data-action="create-survey-config">' +
        icon('plus', 15) + ' New config</button>' : ''));
  html += governanceNote('Delivery here is local configuration only. No Formbricks server, hosted widget, survey email, tracking pixel or external SDK is contacted.');

  html += '<section class="card"><h2 class="page-title">Survey delivery configs</h2>' +
    (data.configs.length ? '<div class="table-wrap"><table class="data"><thead><tr><th>Survey</th>' +
      '<th>Channels</th><th>Embed</th><th>PIN</th><th>Status</th></tr></thead><tbody>' +
      data.configs.map(function (c) {
        return '<tr><td class="mono">' + esc(c.survey_id) + '</td><td class="small">' +
          esc((c.channels || []).join(', ')) + '</td><td>' + esc(c.embed_mode) + '</td><td>' +
          statusBadge(c.pin_protected ? 'protected' : 'open') + '</td><td>' +
          statusBadge(c.status) + '</td></tr>';
      }).join('') + '</tbody></table></div>'
      : '<p class="muted small">No delivery configs yet. Create one to configure a survey.</p>') + '</section>';

  html += '<section class="card"><h2 class="page-title">Local creatives</h2>' +
    (data.creatives.length ? '<div class="table-wrap"><table class="data"><thead><tr><th>Key</th>' +
      '<th>Type</th><th>Label</th><th>Position</th><th>Status</th><th></th></tr></thead><tbody>' +
      data.creatives.map(function (c) {
        return '<tr><td class="mono">' + esc(c.key) + '</td><td>' + statusBadge(c.type) + '</td>' +
          '<td>' + esc(c.label) + '</td><td class="small">' + esc(c.position) + '</td><td>' +
          statusBadge(c.status) + '</td><td>' +
          '<button class="btn btn--sm" data-action="evaluate-survey-creative" data-id="' + attr(c.id) +
          '">Evaluate</button></td></tr>';
      }).join('') + '</tbody></table></div>'
      : '<p class="muted small">No creatives registered.</p>') + '</section>';
  renderViewHtml(html);
}

/* ------------------------------------------------------------------ *
 * Global search dropdown - server contacts + loaded leads/tasks/contacts
 * ------------------------------------------------------------------ */

const runGlobalSearch = debounce(async function () {
  const input = document.getElementById('global-search');
  const host = document.getElementById('search-results-host');
  if (!input || !host) return;
  const query = input.value.trim();
  if (!query) { host.innerHTML = ''; return; }
  if (!can(P.contactRead)) {
    host.innerHTML = '<div class="search-results"><div class="search-foot">Your role does not include search access.</div></div>';
    return;
  }
  host.innerHTML = '<div class="search-results"><div class="search-group">SearchingÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦</div></div>';

  let data;
  try {
    data = await api(apiW('/search') + '?q=' + encodeURIComponent(query) + '&limit=12');
  } catch (err) {
    if (input.isConnected && input.value.trim() === query) {
      host.innerHTML = '<div class="search-results"><div class="search-foot">Search is unavailable right now.</div></div>';
    }
    return;
  }
  if (!input.isConnected || input.value.trim() !== query) return;

  const results = (data && data.results) || [];
  const rows = results.map(searchResultButton).join('');
  host.innerHTML = '<div class="search-results">' +
    (rows || '<div class="search-foot">No matches. Try a different search term.</div>') +
    '<button class="search-result" data-action="search-all">' + icon('search', 14) +
    '<span class="search-result-main"><span class="search-result-title">Open universal search</span>' +
    '<span class="search-result-sub">Full results for "' + esc(query) + '"</span></span></button>' +
    '</div>';
}, 260);

const debouncedContactsRefresh = debounce(function () { refreshContactsTable(state.viewToken); }, 280);

/* ------------------------------------------------------------------ *
 * Event wiring
 * ------------------------------------------------------------------ */

document.addEventListener('submit', function (e) {
  const form = e.target.closest('form[data-form]');
  if (!form) return;
  e.preventDefault();
  handleFormSubmit(form);
});

document.addEventListener('click', function (e) {
  if (!e.target.closest('.search-box')) {
    const host = document.getElementById('search-results-host');
    if (host && host.innerHTML) host.innerHTML = '';
  }
  const el = e.target.closest('[data-action]');
  if (!el) return;
  e.preventDefault();
  processAction(el.dataset.action, el).catch(function (err) { toast(errMessage(err), 'error'); });
});

document.addEventListener('input', function (e) {
  const el = e.target.closest('[data-input]');
  if (!el) return;
  const kind = el.dataset.input;
  if (kind === 'global-search') runGlobalSearch();
  if (kind === 'contact-search') {
    state.contactFilters.search = el.value;
    state.contactFilters.skip = 0;
    debouncedContactsRefresh();
  }
  if (kind === 'contact-tag') {
    state.contactFilters.tag = el.value;
    state.contactFilters.skip = 0;
    debouncedContactsRefresh();
  }
});

document.addEventListener('change', async function (e) {
  const el = e.target.closest('[data-change]');
  if (!el) return;
  const kind = el.dataset.change;
  if (kind === 'contact-filter') {
    state.contactFilters[el.dataset.key] = el.value;
    state.contactFilters.skip = 0;
    refreshContactsTable(state.viewToken);
  } else if (kind === 'lead-status') {
    state.leadStatus = el.value; loadView();
  } else if (kind === 'task-status') {
    state.taskStatus = el.value; loadView();
  } else if (kind === 'ticket-status') {
    state.ticketStatus = el.value; loadView();
  } else if (kind === 'ticket-owner') {
    state.ticketOwner = el.value; loadView();
  } else if (kind === 'ticket-inbox') {
    state.ticketInbox = el.value; loadView();
  } else if (kind === 'ticket-label') {
    state.ticketLabel = el.value; loadView();
  } else if (kind === 'ticket-segment') {
    const segmentId = el.value;
    state.ticketSegment = segmentId;
    if (!segmentId) {
      state.ticketSegmentContactIds = null;
      state.ticketSegmentInfo = null;
      loadView();
      return;
    }
    const [segmentContacts, segmentCount] = await Promise.all([
      api(apiW('/tickets/segments/' + encodeURIComponent(segmentId) + '/contacts')),
      api(apiW('/tickets/segments/' + encodeURIComponent(segmentId) + '/count')),
    ]);
    const segment = (state.caches.supportSegments || []).find(function (s) { return s.id === segmentId; });
    state.ticketSegmentContactIds = (segmentContacts || []).map(function (c) { return c.id; });
    state.ticketSegmentInfo = {
      name: segment ? segment.name : segmentId,
      count: segmentCount && segmentCount.count !== undefined
        ? segmentCount.count : state.ticketSegmentContactIds.length,
    };
    loadView();
    return;
  } else if (kind === 'member-role') {
    api(apiW('/members/' + encodeURIComponent(el.dataset.userId)), {
      method: 'PATCH', body: { role: el.value },
    }).then(function () { loadView(); toast('Member role updated.', 'success'); })
      .catch(function (err) { toast(errMessage(err), 'error'); loadView(); });
  } else if (kind === 'flag-environment') {
    state.flagEnvironment = el.value; loadView();
  } else if (kind === 'item-priority') {
    state.itemPriority = el.value; loadView();
  } else if (kind === 'saved-view') {
    await applySavedView(el.value); return;
  } else if (kind === 'item-filter') {
    state.itemFilter = el.value; loadView();
  } else if (kind === 'project-member-role') {
    const parts = currentRoute().split('/');
    api(apiW('/projects/' + encodeURIComponent(parts[1] || '') + '/members/' + encodeURIComponent(el.dataset.uid)), {
      method: 'PATCH', body: { role: el.value },
    }).then(function () { loadView(); toast('Project role updated.', 'success'); })
      .catch(function (err) { toast(errMessage(err), 'error'); loadView(); });
  } else if (kind === 'item-status' || kind === 'item-assignee') {
    const parts = currentRoute().split('/');
    const body = kind === 'item-status' ? { status: el.value } : { assignee_id: el.value || null };
    api(apiW('/projects/' + encodeURIComponent(parts[1] || '') + '/items/' + encodeURIComponent(el.dataset.id)), {
      method: 'PATCH', body: body,
    }).then(function () { loadView(); toast('Work item updated.', 'success'); })
      .catch(function (err) { toast(errMessage(err), 'error'); });
  } else if (kind === 'ticket-assignee') {
    api(apiW('/tickets/' + encodeURIComponent(el.dataset.id)), {
      method: 'PATCH', body: { assignee_id: el.value || null },
    }).then(function () { loadView(); toast('Assignment updated.', 'success'); })
      .catch(function (err) { toast(errMessage(err), 'error'); });
  } else if (kind === 'campaign-status') {
    state.campaignStatus = el.value; loadView();
  } else if (kind === 'deal-stage') {
    state.dealStage = el.value; loadView();
  } else if (kind === 'search-type') {
    state.searchType = el.value; loadView();
  } else if (kind === 'event-filter') {
    state.eventFilter = el.value; loadView();
  }
});

document.addEventListener('keydown', function (e) {
  if (e.key === 'Escape') {
    const modal = document.querySelector('#modal-root .modal');
    if (modal) { closeModal(); return; }
    const host = document.getElementById('search-results-host');
    if (host) host.innerHTML = '';
    document.body.classList.remove('sidebar-open');
    return;
  }
  const tag = document.activeElement ? document.activeElement.tagName : '';
  if ((e.key === '/' || (e.key.toLowerCase() === 'k' && (e.ctrlKey || e.metaKey))) &&
    ['INPUT', 'TEXTAREA', 'SELECT'].indexOf(tag) === -1) {
    const input = document.getElementById('global-search');
    if (input) { e.preventDefault(); input.focus(); }
  }
});

/* ------------------------------------------------------------------ *
 * Boot and hash routing
 * ------------------------------------------------------------------ */

async function loadAdvancedExperiments(token) {
  if (!can(P.contactRead)) {
    renderViewHtml(pageHead('Operations', 'Advanced experimentation', '') +
      errorBlock('Your role does not include insight access.'));
    return;
  }
  loadingView('Advanced experimentation', 'Clean-room CUPED, stratification, sequential testing, quantile, retention, compound, bandit and correlation analysis over local records.');
  const base = apiW('/advanced-experiments');
  let data;
  try {
    const contract = await api(base + '/api-contract') || {};
    const analyses = await api(base + '/analyses') || [];
    const holdouts = await api(base + '/holdouts') || [];
    const banditKey = state.advBanditKey || 'onboarding';
    const bandit = await api(base + '/bandits/' + encodeURIComponent(banditKey)) || {};
    const analysisId = state.advAnalysisId || (analyses[0] && analyses[0].id) || '';
    const analysis = analysisId ? await api(base + '/analyses/' + encodeURIComponent(analysisId)) : null;
    data = { contract: contract, analyses: analyses, holdouts: holdouts,
      bandit: bandit, banditKey: banditKey, analysisId: analysisId, analysis: analysis };
  } catch (err) {
    if (token !== state.viewToken) return;
    renderViewHtml(pageHead('Operations', 'Advanced experimentation', '') + errorBlock(errMessage(err)));
    return;
  }
  if (token !== state.viewToken) return;

  const write = can(P.noteWrite);
  const contract = data.contract || {};
  const bandit = data.bandit || {};
  let html = pageHead('Operations', 'Advanced experimentation',
    data.analyses.length + ' saved analyses Ã‚Â· ' + data.holdouts.length + ' holdouts',
    '<button class="btn" data-action="view-adv-contract">' + icon('info', 15) +
      ' Local contract</button>');
  html += governanceNote('Eight GrowthBook commercial capabilities are implemented locally from the documented public method: CUPED variance reduction, size-weighted post-stratification, mSPRT and O\'Brien-Fleming sequential boundaries, quantile metrics with deterministic bootstrap intervals, retention curves, weighted compound scores, Thompson/UCB bandits and Pearson correlation. No GrowthBook source, stats package, hosted platform, warehouse, SDK or external statistics service is claimed.');

  html += '<section class="card"><h2 class="page-title">Local contract</h2>' +
    '<p class="muted small">external_calls: ' + String(contract.external_calls) +
    ' Ã‚Â· analysis kinds: ' + (contract.analysis_kinds || []).length +
    ' Ã‚Â· bandit policies: ' + (contract.bandit_policies || []).join(', ') +
    ' Ã‚Â· capabilities: ' + (contract.capabilities || []).join(', ') + '</p>' +
    '<p class="muted small">Algorithms are computed locally with the Python standard library and persisted in workspace-scoped records. No paid dependency is required.</p></section>';

  if (write) {
    html += '<section class="card"><h2 class="page-title">Run an analysis</h2>' +
      '<form data-form="adv-analysis-create"><div class="form-grid">' +
      field('name', 'Analysis name', { value: 'Local analysis', required: true }) +
      field('kind', 'Method', { type: 'select', options: selectOptions(
        (contract.analysis_kinds || []).map(function (k) { return [k, k]; }), 'cuped') }) +
      field('experiment_key', 'Experiment key (optional)', {}) +
      field('inputs_json', 'Inputs (JSON object)', { type: 'textarea', span: true, required: true,
        value: '{"control":[1,2,3,4],"treatment":[2,3,4,6],"control_pre":[0.5,1,1.5,2],"treatment_pre":[1,1.5,2,2.5]}' }) +
      '</div><div class="form-actions"><button class="btn btn--primary" type="submit">' +
      icon('activity', 15) + ' Run and save</button></div></form></section>';
  }

  html += '<section class="card"><h2 class="page-title">Saved analyses</h2>' +
    (data.analyses.length ? '<div class="table-wrap"><table class="data"><thead><tr>' +
      '<th>Name</th><th>Method</th><th>Experiment</th><th>Result</th></tr></thead><tbody>' +
      data.analyses.map(function (a) {
        const r = a.result || {};
        const summary = r.method === 'cuped' ? ('effect ' + Number(r.adjusted_effect).toFixed(3))
          : r.method === 'correlation' ? ('r ' + Number(r.r).toFixed(3))
          : r.method === 'quantile' ? ('q' + r.q + ' = ' + Number(r.value).toFixed(2))
          : r.method === 'compound' ? ('score ' + Number(r.score).toFixed(3))
          : r.method === 'retention' ? ('last ' + Number(r.last_retention).toFixed(3))
          : r.method === 'sequential' ? ((r.msprt_stop ? 'stop' : 'continue'))
          : ('effect ' + Number(r.effect || 0).toFixed(3));
        return '<tr><td><button class="btn btn--sm btn--ghost" data-action="adv-open-analysis" data-id="' +
          attr(a.id) + '">' + esc(a.name) + '</button></td><td>' + esc(a.kind) + '</td><td>' +
          esc(a.experiment_key || 'Ã¢â‚¬â€') + '</td><td>' + esc(summary) + '</td></tr>';
      }).join('') + '</tbody></table></div>' : '<p class="muted small">No analyses saved yet.</p>') +
    (data.analysis ? '<div class="callout"><strong>' + esc(data.analysis.name) + '</strong><pre class="small">' +
      esc(JSON.stringify(data.analysis.result, null, 2)) + '</pre></div>' : '') + '</section>';

  html += '<section class="card"><h2 class="page-title">Multi-armed bandit Ã‚Â· ' +
    esc(data.banditKey) + '</h2>' +
    '<p class="muted small">Arms: ' + (bandit.arms || []).map(function (a) {
      return esc(a.arm) + ' (ÃŽÂ±' + Number(a.alpha).toFixed(1) + ' ÃŽÂ²' + Number(a.beta).toFixed(1) +
        ' pulls ' + a.pulls + ')';
    }).join(' Ã‚Â· ') + '</p>' + (write ? '<div class="form-grid">' +
      '<form data-form="adv-bandit-arm">' + field('arm', 'Arm', { required: true }) +
      field('alpha', 'Alpha', { type: 'number', value: '1' }) +
      field('beta', 'Beta', { type: 'number', value: '1' }) +
      field('pulls', 'Pulls', { type: 'number', value: '0' }) +
      '<div class="form-actions"><button class="btn btn--sm" type="submit">Save arm</button></div></form>' +
      '<form data-form="adv-bandit-reward">' + field('arm', 'Arm to reward', { required: true }) +
      field('reward', 'Reward (0-1)', { type: 'number', value: '1' }) +
      '<div class="form-actions"><button class="btn btn--sm" type="submit">Apply reward</button></div></form>' +
      '</div>' : '') +
    '<form data-form="adv-bandit-recommend"><div class="form-grid">' +
    field('policy', 'Policy', { type: 'select', options: selectOptions(
      [['thompson', 'Thompson sampling'], ['ucb', 'Upper confidence bound']], 'thompson') }) +
    field('seed', 'Seed', { type: 'number', value: '11' }) +
    '</div><div class="form-actions"><button class="btn btn--sm" type="submit">Recommend arm</button></div></form></section>';

  html += '<section class="card"><h2 class="page-title">Global holdouts</h2>' +
    (data.holdouts.length ? '<div class="table-wrap"><table class="data"><thead><tr>' +
      '<th>Name</th><th>Fraction</th><th>Experiments</th></tr></thead><tbody>' +
      data.holdouts.map(function (h) {
        return '<tr><td>' + esc(h.name) + '</td><td>' + Number(h.fraction).toFixed(3) +
          '</td><td>' + esc((h.experiment_keys || []).join(', ')) + '</td></tr>';
      }).join('') + '</tbody></table></div>' : '<p class="muted small">No holdouts configured.</p>') +
    (write ? '<form data-form="adv-holdout-create"><div class="form-grid">' +
      field('name', 'Holdout name', { required: true }) +
      field('fraction', 'Traffic fraction (0-1)', { type: 'number', value: '0.1' }) +
      field('experiment_keys', 'Experiment keys (comma separated)', { span: true }) +
      '</div><div class="form-actions"><button class="btn btn--sm" type="submit">Create holdout</button></div></form>' : '') +
    '<form data-form="adv-holdout-check"><div class="form-grid">' +
    field('holdout_id', 'Holdout', { type: 'select', options: selectOptions(
      data.holdouts.map(function (h) { return [h.id, h.name]; })) }) +
    field('user_key', 'User key', { required: true }) +
    '</div><div class="form-actions"><button class="btn btn--sm" type="submit">Check assignment</button></div></form></section>';

  renderViewHtml(html);
}


async function boot() {
  const route = currentRoute();
  if (!state.access) { renderAuth(route); return; }
  try {
    state.me = await api('/api/v1/auth/me');
    state.workspaceId = state.me.workspace_id;
  } catch (err) {
    clearTokens();
    state.me = null;
    renderAuth('login', errMessage(err));
    return;
  }
  await loadMyWorkspaces();
  if (AUTH_ROUTES.indexOf(route) !== -1) { navigate('dashboard'); return; }
  renderApp();
  loadView();
  loadNotificationsSilently();
  subscribeNotificationStream();
  subscribeTicketStream();
}

function onHashChange() {
  const route = currentRoute();
  if (!state.access) { renderAuth(route); return; }
  if (!state.me) { boot(); return; }
  if (AUTH_ROUTES.indexOf(route) !== -1) { navigate('dashboard'); return; }
  closeModal();
  renderApp();
  loadView();
  loadNotificationsSilently();
}

window.addEventListener('hashchange', onHashChange);
boot();


ener('hashchange', onHashChange);
boot();


