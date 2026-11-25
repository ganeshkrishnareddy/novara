'use strict';

const api = window.novaraDesktop;
const page = document.body.className.includes('utility-page')
  ? (document.querySelector('main')?.dataset.name || 'connection')
  : 'connection';

function setText(id, value) {
  const el = document.getElementById(id);
  if (el) el.textContent = value;
}

function renderState(state) {
  if (!state) return;
  if (page === 'connection') {
    const labels = {
      idle: 'Waiting to start…',
      starting: 'Starting the NOVARA backend…',
      connected: 'Connected — opening NOVARA…',
      error: 'Connection problem'
    };
    setText('status-text', labels[state.status] || state.status);
    setText('detail-text', state.error || (
      state.status === 'connected'
        ? 'The dashboard loads from the same origin as the API, so no separate login connection is needed.'
        : 'Preparing a secure loopback connection on this machine.'
    ));
    setText('url-text', state.backendUrl || '');
    document.getElementById('status-dot')?.setAttribute('data-status', state.status);
    document.getElementById('retry').hidden = state.status !== 'error';
    document.getElementById('settings').hidden = false;
  }
  if (page === 'about') {
    setText('app-version', state.version || '—');
    setText('electron-version', state.versions?.electron || '—');
    setText('chrome-version', state.versions?.chrome || '—');
    setText('node-version', state.versions?.node || '—');
    setText('backend-url', state.backendUrl || 'not connected');
    setText('backend-status', state.status || 'unknown');
  }
  if (page === 'backend-settings' && !document.getElementById('settings-form').dataset.loaded) {
    const form = document.getElementById('settings-form');
    form.elements.backendMode.value = state.settings?.backendMode || 'local';
    form.elements.remoteUrl.value = state.settings?.remoteUrl || 'http://127.0.0.1:8000';
    form.dataset.loaded = '1';
  }
}

if (api?.onStatus) api.onStatus(renderState);
api?.getState().then(renderState).catch(() => {});

if (page === 'connection') {
  document.getElementById('retry')?.addEventListener('click', () => api?.restartBackend().then(renderState));
  document.getElementById('settings')?.addEventListener('click', () => api?.openSettings());
}

if (page === 'about') {
  document.getElementById('close')?.addEventListener('click', () => window.close());
  document.getElementById('website')?.addEventListener('click', () =>
    api?.openExternal('https://ganeshkrishnareddy.github.io/novara/'));
}

if (page === 'backend-settings') {
  const form = document.getElementById('settings-form');
  const error = document.getElementById('form-error');
  document.getElementById('cancel')?.addEventListener('click', () => window.close());
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    error.hidden = true;
    const patch = {
      backendMode: form.elements.backendMode.value,
      remoteUrl: form.elements.remoteUrl.value.trim()
    };
    const saved = await api?.saveSettings(patch);
    if (!saved?.ok) {
      error.textContent = saved?.error || 'Could not save the settings.';
      error.hidden = false;
      return;
    }
    await api?.restartBackend();
    window.close();
  });
}
