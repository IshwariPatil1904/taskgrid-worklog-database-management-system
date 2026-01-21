// Lightweight API helper used across the frontend

(function () {
  // Ensure CONFIG exists
  if (typeof CONFIG === 'undefined') {
    window.CONFIG = {
      API_BASE_URL: '',
      STORAGE_PREFIX: 'taskgrid_'
    };
  }

  const tokenKey = `${CONFIG.STORAGE_PREFIX}token`;
  const userKey = `${CONFIG.STORAGE_PREFIX}user`;

  function getToken() {
    return localStorage.getItem(tokenKey);
  }
  function setToken(t) {
    if (t) localStorage.setItem(tokenKey, t);
    else localStorage.removeItem(tokenKey);
  }

  function buildQs(params) {
    if (!params) return '';
    const s = new URLSearchParams();
    Object.keys(params).forEach(k => {
      const v = params[k];
      if (v !== undefined && v !== null && String(v) !== '') s.append(k, v);
    });
    const qs = s.toString();
    return qs ? `?${qs}` : '';
  }

  async function apiCall(endpoint, arg1 = {}) {
    // backward-compatible signature:
    // apiCall('/data/tasks', 'POST', data)  OR apiCall('/data/tasks', { method:'POST', data })
    let method = 'GET', data = null;
    if (typeof arg1 === 'string') {
      method = arg1 || 'GET';
      data = arguments[2] || null;
    } else if (typeof arg1 === 'object' && arg1 !== null) {
      method = (arg1.method || 'GET').toUpperCase();
      data = arg1.data || null;
    }

    const headers = { 'Content-Type': 'application/json' };
    const token = getToken();
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const res = await fetch(`${CONFIG.API_BASE_URL}${endpoint}`, {
      method,
      headers,
      body: data ? JSON.stringify(data) : null
    });

    let payload = null;
    try { payload = await res.json(); } catch (_) { payload = null; }

    if (res.status === 401) {
      // Clear auth and force login
      localStorage.removeItem(tokenKey);
      localStorage.removeItem(userKey);
      // redirect — adjust path if your login is in a subfolder
      window.location.href = '/login.html';
      throw new Error('Unauthorized');
    }

    if (!res.ok) {
      const msg = (payload && (payload.error || payload.message)) || `HTTP ${res.status}`;
      throw new Error(msg);
    }

    return payload;
  }

  // Convenience wrappers used in many pages
  const api = {
    call: apiCall,
    request: apiCall,
    getToken,
    setToken,
    getUser: () => {
      try { return JSON.parse(localStorage.getItem(userKey) || 'null'); } catch { return null; }
    },
    setUser: (u) => { if (u) localStorage.setItem(userKey, JSON.stringify(u)); else localStorage.removeItem(userKey); },

    // Data helpers
    getProjects: () => apiCall('/data/projects'),
    getTasks: (params) => apiCall(`/data/tasks${buildQs(params)}`),
    getWorkLogs: (params) => apiCall(`/data/work-logs${buildQs(params)}`),
    getDashboard: () => apiCall('/data/dashboard'),
    getUsers: () => apiCall('/data/users'),
    createTask: (payload) => apiCall('/data/tasks', { method: 'POST', data: payload }),
    createProject: (payload) => apiCall('/data/projects', { method: 'POST', data: payload }),
  };

  // Expose both for backwards compatibility
  window.apiCall = apiCall;
  window.api = api;

  // ...existing code...
})();
