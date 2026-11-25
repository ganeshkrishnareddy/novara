/* NOVARA Desktop Client Edition — Electron main process.
 *
 * The existing NOVARA web client is served by the existing FastAPI app on a
 * loopback-only port. The shell starts that backend, waits for /health, then
 * loads it as a same-origin client. No frontend logic is duplicated here.
 */
'use strict';

const { app, BrowserWindow, Menu, ipcMain, session, shell, dialog } = require('electron');
const { spawn } = require('child_process');
const crypto = require('crypto');
const fs = require('fs');
const http = require('http');
const net = require('net');
const path = require('path');
const {
  INHERITED_BACKEND_KEYS,
  sanitizeBackendEnv,
  healthGet,
  dataMode
} = require('./security-helpers');

const DEV = process.argv.includes('--dev') || !app.isPackaged;
const PROJECT_ROOT = path.resolve(__dirname, '..', '..');
const SETTINGS_PATH = path.join(app.getPath('userData'), 'settings.json');
const SECRETS_PATH = path.join(app.getPath('userData'), 'secrets.json');
const DATA_DIR = path.join(app.getPath('userData'), 'data');
const LOG_PATH = path.join(app.getPath('userData'), 'backend.log');

const DEFAULT_SETTINGS = Object.freeze({
  backendMode: 'local',
  remoteUrl: 'http://127.0.0.1:8000'
});

let mainWindow = null;
let aboutWindow = null;
let settingsWindow = null;
let backendProcess = null;
let backendUrl = null;
let backendStatus = 'idle';
let backendError = null;
let shuttingDown = false;
let presignSecret = null;

/* ---------------------------------------------------------------- helpers */

function redact(text) {
  let value = String(text);
  for (const secret of [presignSecret, process.env.NOVARA_PRESIGN_SECRET]) {
    if (typeof secret === 'string' && secret.length >= 8) {
      value = value.split(secret).join('[REDACTED]');
    }
  }
  return value
    .replace(/(Bearer\s+)[A-Za-z0-9._~+/=-]{12,}/gi, '$1[REDACTED]')
    .replace(/([?&](?:token|signature|sig|key)=)[^&\s'"]+/gi, '$1[REDACTED]');
}

function appendLog(line) {
  try {
    fs.mkdirSync(path.dirname(LOG_PATH), { recursive: true, mode: 0o700 });
    fs.appendFileSync(LOG_PATH, redact(String(line)).replace(/\s+$/, '') + '\n');
  } catch (_) {
    /* logging must never break startup */
  }
}

function ensurePresignSecret() {
  if (presignSecret) return presignSecret;
  try {
    const stored = JSON.parse(fs.readFileSync(SECRETS_PATH, 'utf8'));
    const candidate = stored && stored.presignSecret;
    if (typeof candidate === 'string' && /^[A-Za-z0-9_-]{43,44}$/.test(candidate)) {
      presignSecret = candidate;
      return presignSecret;
    }
  } catch (_) {
    /* no usable stored secret; create one below */
  }
  presignSecret = crypto.randomBytes(32).toString('base64url');
  const writeOptions = { encoding: 'utf8' };
  if (process.platform !== 'win32') writeOptions.mode = 0o600;
  fs.mkdirSync(path.dirname(SECRETS_PATH), { recursive: true, mode: 0o700 });
  fs.writeFileSync(SECRETS_PATH,
    JSON.stringify({ presignSecret: presignSecret }, null, 2) + '\n', writeOptions);
  if (process.platform !== 'win32') {
    try { fs.chmodSync(SECRETS_PATH, 0o600); } catch (_) { /* best effort */ }
  }
  return presignSecret;
}

function validHttpUrl(raw) {
  try {
    const parsed = new URL(String(raw));
    if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') return null;
    if (!parsed.hostname || parsed.username || parsed.password) return null;
    return parsed.toString().replace(/\/$/, '');
  } catch (_) {
    return null;
  }
}

function isLoopbackHost(hostname) {
  const host = String(hostname || '').toLowerCase().replace(/^\[|\]$/g, '');
  return host === 'localhost' || host === '127.0.0.1' || host === '::1' ||
    /^127\./.test(host);
}

/* Remote backends must use TLS. Plain HTTP is accepted only for loopback
 * addresses so local development and the existing local-mode QA still work. */
function validRemoteUrl(raw) {
  const url = validHttpUrl(raw);
  if (!url) return null;
  const parsed = new URL(url);
  if (parsed.protocol === 'http:' && !isLoopbackHost(parsed.hostname)) return null;
  return url;
}

function sanitizeSettings(input) {
  const source = input && typeof input === 'object' ? input : {};
  const mode = source.backendMode === 'remote' ? 'remote' : 'local';
  return {
    backendMode: mode,
    remoteUrl: validRemoteUrl(source.remoteUrl) || DEFAULT_SETTINGS.remoteUrl
  };
}

function loadSettings() {
  try {
    return sanitizeSettings(JSON.parse(fs.readFileSync(SETTINGS_PATH, 'utf8')));
  } catch (_) {
    return { ...DEFAULT_SETTINGS };
  }
}

function saveSettings(patch) {
  const next = sanitizeSettings({ ...loadSettings(), ...patch });
  fs.mkdirSync(path.dirname(SETTINGS_PATH), { recursive: true });
  fs.writeFileSync(SETTINGS_PATH, JSON.stringify(next, null, 2) + '\n', 'utf8');
  return next;
}

function getFreePort() {
  return new Promise((resolve, reject) => {
    const probe = net.createServer();
    probe.once('error', reject);
    probe.listen(0, '127.0.0.1', () => {
      const address = probe.address();
      probe.close(() => resolve(address.port));
    });
  });
}

function tightenDataPermissions() {
  if (process.platform === 'win32') return;
  const walk = (dir) => {
    let entries;
    try {
      entries = fs.readdirSync(dir, { withFileTypes: true });
    } catch (_) {
      return;
    }
    for (const entry of entries) {
      const full = path.join(dir, entry.name);
      try {
        fs.chmodSync(full, dataMode(entry.isDirectory()));
      } catch (_) { /* best effort on filesystems without POSIX modes */ }
      if (entry.isDirectory()) walk(full);
    }
  };
  try {
    fs.chmodSync(DATA_DIR, 0o700);
  } catch (_) { /* best effort */ }
  walk(DATA_DIR);
}

function setStatus(status, error = null, url = null) {
  backendStatus = status;
  backendError = error;
  if (url) backendUrl = url;
  const payload = currentState();
  for (const win of [mainWindow, settingsWindow, aboutWindow]) {
    if (win && !win.isDestroyed()) win.webContents.send('desktop:status', payload);
  }
}

function currentState() {
  return {
    status: backendStatus,
    error: backendError,
    backendUrl,
    settings: loadSettings(),
    version: app.getVersion(),
    versions: {
      electron: process.versions.electron || 'unknown',
      chrome: process.versions.chrome || 'unknown',
      node: process.versions.node || 'unknown'
    }
  };
}

function iconPath() {
  const candidate = path.join(__dirname, '..', 'build', 'icon.png');
  return fs.existsSync(candidate) ? candidate : undefined;
}

/* ------------------------------------------------------------ backend run */

function pythonExecutable() {
  if (process.env.NOVARA_PYTHON) return process.env.NOVARA_PYTHON;
  if (app.isPackaged) {
    const candidates = process.platform === 'win32'
      ? [
          path.join(process.resourcesPath, 'backend', 'runtime', 'python.exe'),
          path.join(process.resourcesPath, 'backend', 'runtime', 'Scripts', 'python.exe')
        ]
      : [path.join(process.resourcesPath, 'backend', 'runtime', 'bin', 'python3')];
    for (const candidate of candidates) {
      if (fs.existsSync(candidate)) return candidate;
    }
    return process.platform === 'win32' ? 'python.exe' : 'python3';
  }
  const local = process.platform === 'win32'
    ? path.join(PROJECT_ROOT, '.venv', 'Scripts', 'python.exe')
    : path.join(PROJECT_ROOT, '.venv', 'bin', 'python');
  return fs.existsSync(local) ? local : (process.platform === 'win32' ? 'python.exe' : 'python3');
}

function backendRoot() {
  return app.isPackaged
    ? path.join(process.resourcesPath, 'backend')
    : path.join(PROJECT_ROOT, 'apps', 'api');
}

function findApiDir() {
  const root = backendRoot();
  const candidates = [path.join(root, 'deps'), root];
  for (const candidate of candidates) {
    if (fs.existsSync(path.join(candidate, 'novara_core', 'main.py'))) return candidate;
  }
  return null;
}

function waitForHealth(baseUrl, timeoutMs, child) {
  const started = Date.now();
  const target = baseUrl + '/health';
  return new Promise((resolve) => {
    const attempt = () => {
      if (shuttingDown) return resolve(false);
      if (child && child.exitCode !== null) return resolve(false);
      let req;
      try {
        req = healthGet(target, (res) => {
          res.resume();
          if (res.statusCode === 200) return resolve(true);
          retry();
        });
      } catch (_) {
        return retry();
      }
      req.setTimeout(2000, () => req.destroy());
      req.on('error', retry);
    };
    const retry = () => {
      if (Date.now() - started > timeoutMs) return resolve(false);
      setTimeout(attempt, 400);
    };
    attempt();
  });
}

async function startBackend() {
  stopBackend();
  const settings = loadSettings();

  if (settings.backendMode === 'remote') {
    const url = validRemoteUrl(settings.remoteUrl);
    if (!url) {
      setStatus('error', 'Remote servers require an https:// address. Plain http:// is allowed only for loopback development addresses.');
      return false;
    }
    setStatus('starting', null, url);
    const ok = await waitForHealth(url, 10000, null);
    setStatus(ok ? 'connected' : 'error',
      ok ? null : `Could not reach the NOVARA backend at ${url}. Start it and choose Retry, or switch to the bundled local backend.`,
      url);
    return ok;
  }

  setStatus('starting', null, null);
  const apiDir = findApiDir();
  if (!apiDir) {
    setStatus('error', 'The bundled NOVARA backend files are missing from this installation.');
    return false;
  }

  let port;
  try {
    port = await getFreePort();
  } catch (error) {
    setStatus('error', 'Could not reserve a local port: ' + error.message);
    return false;
  }

  fs.mkdirSync(DATA_DIR, { recursive: true, mode: 0o700 });
  const depsDir = path.join(backendRoot(), 'deps');
  const pythonPath = [apiDir, backendRoot()];
  if (fs.existsSync(depsDir)) pythonPath.unshift(depsDir);

  const inherited = Object.keys(process.env).filter(
    (key) => INHERITED_BACKEND_KEYS.includes(key) || key.startsWith('NOVARA_S3_')
  );
  if (inherited.length) {
    appendLog(`[desktop] removed inherited backend overrides: ${inherited.sort().join(', ')}`);
  }
  const env = sanitizeBackendEnv(process.env, {
    PYTHONPATH: pythonPath.join(path.delimiter),
    NOVARA_DB_PATH: path.join(DATA_DIR, 'novara.sqlite3'),
    NOVARA_STORAGE_DIR: path.join(DATA_DIR, 'storage'),
    NOVARA_PRESIGN_SECRET: ensurePresignSecret(),
    NOVARA_STORAGE_BACKEND: 'local',
    PYTHONUNBUFFERED: '1',
    PYTHONDONTWRITEBYTECODE: '1'
  });
  const args = [
    '-m', 'uvicorn', 'novara_core.main:app',
    '--host', '127.0.0.1', '--port', String(port),
    '--app-dir', apiDir, '--no-access-log'
  ];
  const python = pythonExecutable();
  appendLog(`[desktop] starting backend: ${python} ${args.join(' ')}`);
  try {
    backendProcess = spawn(python, args, {
      cwd: DATA_DIR, env, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe']
    });
  } catch (error) {
    setStatus('error', 'Could not start Python: ' + error.message);
    return false;
  }
  const child = backendProcess;
  child.stdout.on('data', (chunk) => appendLog('[backend] ' + chunk.toString()));
  child.stderr.on('data', (chunk) => appendLog('[backend:err] ' + chunk.toString()));
  child.on('error', (error) => {
    appendLog('[desktop] spawn error: ' + error.message);
    if (backendProcess === child) {
      backendProcess = null;
      setStatus('error', 'Python could not be started: ' + error.message);
    }
  });
  child.on('exit', (code, signal) => {
    appendLog(`[desktop] backend exited code=${code} signal=${signal}`);
    if (backendProcess === child && !shuttingDown) {
      backendProcess = null;
      setStatus('error', `The NOVARA backend stopped unexpectedly (exit ${code ?? signal}). Choose Retry to start it again.`);
    }
  });

  const url = `http://127.0.0.1:${port}`;
  const ok = await waitForHealth(url, 45000, child);
  if (ok) {
    tightenDataPermissions();
    setStatus('connected', null, url);
  } else {
    setStatus('error', 'The NOVARA backend did not become healthy within 45 seconds. See backend.log in the application data folder.');
  }
  return ok;
}

function stopBackend() {
  const child = backendProcess;
  backendProcess = null;
  if (!child || child.exitCode !== null) return;
  appendLog(`[desktop] stopping backend pid=${child.pid}`);
  try {
    if (process.platform === 'win32') {
      spawn('taskkill', ['/pid', String(child.pid), '/T', '/F'], { windowsHide: true });
    } else {
      child.kill('SIGTERM');
    }
  } catch (error) {
    appendLog('[desktop] stop error: ' + error.message);
  }
}

async function loadBackendIntoMainWindow() {
  if (!mainWindow || mainWindow.isDestroyed() || !backendUrl) return;
  if (backendStatus !== 'connected') return;
  try {
    await mainWindow.loadURL(backendUrl + '/');
  } catch (error) {
    appendLog('[desktop] load error: ' + error.message);
    setStatus('error', 'The dashboard could not be loaded: ' + error.message);
  }
}

async function startBackendSequence() {
  setStatus('starting', null, null);
  const ok = await startBackend();
  if (ok) await loadBackendIntoMainWindow();
}

/* ----------------------------------------------------------- window setup */

function isLocalAppFile(raw) {
  try {
    const parsed = new URL(raw);
    if (parsed.protocol !== 'file:') return false;
    let filePath = decodeURIComponent(parsed.pathname).replace(/^\/([A-Za-z]:)/, '$1');
    if (process.platform !== 'win32') filePath = decodeURIComponent(parsed.pathname);
    return path.normalize(filePath).toLowerCase().startsWith(path.normalize(__dirname).toLowerCase());
  } catch (_) {
    return false;
  }
}

function isAllowedUrl(raw) {
  try {
    const parsed = new URL(raw);
    if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') {
      return isLocalAppFile(raw);
    }
    const settings = loadSettings();
    const allowed = settings.backendMode === 'remote' ? settings.remoteUrl : backendUrl;
    if (!allowed) return false;
    return parsed.origin === new URL(allowed).origin;
  } catch (_) {
    return false;
  }
}

function openExternalSafely(url) {
  const safe = validHttpUrl(url);
  if (!safe) return;
  shell.openExternal(safe).catch(() => {});
}

function guardNavigation(event, url) {
  if (isAllowedUrl(url)) return;
  event.preventDefault();
  openExternalSafely(url);
}

function guardWindow(win) {
  win.webContents.on('will-navigate', (event, url) => guardNavigation(event, url));
  win.webContents.on('will-frame-navigate', (event, url) => guardNavigation(event, url));
  win.webContents.setWindowOpenHandler(({ url }) => {
    if (isAllowedUrl(url)) return { action: 'allow' };
    openExternalSafely(url);
    return { action: 'deny' };
  });
}

function createMainWindow() {
  mainWindow = new BrowserWindow({
    width: 1360,
    height: 860,
    minWidth: 960,
    minHeight: 640,
    title: 'NOVARA',
    backgroundColor: '#F7F8F7',
    icon: iconPath(),
    show: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      webSecurity: true,
      spellcheck: false
    }
  });
  mainWindow.loadFile(path.join(__dirname, 'loading.html'));
  mainWindow.once('ready-to-show', () => mainWindow.show());
  mainWindow.on('closed', () => { mainWindow = null; });
  guardWindow(mainWindow);
}

function openSmallWindow(file, title) {
  const win = new BrowserWindow({
    width: 560,
    height: 560,
    resizable: false,
    title,
    backgroundColor: '#F7F8F7',
    icon: iconPath(),
    parent: mainWindow || undefined,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      webSecurity: true
    }
  });
  win.loadFile(path.join(__dirname, file));
  guardWindow(win);
  return win;
}

function openAbout() {
  if (aboutWindow && !aboutWindow.isDestroyed()) return aboutWindow.focus();
  aboutWindow = openSmallWindow('about.html', 'About NOVARA');
  aboutWindow.on('closed', () => { aboutWindow = null; });
}

function openSettings() {
  if (settingsWindow && !settingsWindow.isDestroyed()) return settingsWindow.focus();
  settingsWindow = openSmallWindow('settings.html', 'NOVARA settings');
  settingsWindow.on('closed', () => { settingsWindow = null; });
}

function installMenu() {
  const template = [
    {
      label: 'File',
      submenu: [
        { label: 'Settings…', accelerator: 'Ctrl+,', click: openSettings },
        { type: 'separator' },
        { role: 'quit' }
      ]
    },
    {
      label: 'View',
      submenu: [
        { role: 'reload' },
        { role: 'forceReload' },
        { type: 'separator' },
        { role: 'resetZoom' },
        { role: 'zoomIn' },
        { role: 'zoomOut' },
        { type: 'separator' },
        { role: 'togglefullscreen' },
        { role: 'toggleDevTools', visible: DEV }
      ]
    },
    {
      label: 'Help',
      submenu: [
        { label: 'About NOVARA', click: openAbout },
        { label: 'Installation guide', click: () => shell.openExternal('https://ganeshkrishnareddy.github.io/novara/#download').catch(() => {}) }
      ]
    }
  ];
  Menu.setApplicationMenu(Menu.buildFromTemplate(template));
}

function activeBackendOrigin() {
  const settings = loadSettings();
  const candidate = settings.backendMode === 'remote' ? settings.remoteUrl : backendUrl;
  try {
    return new URL(candidate).origin;
  } catch (_) {
    return null;
  }
}

function installCsp() {
  session.defaultSession.webRequest.onHeadersReceived((details, callback) => {
    const sources = ["'self'"];
    const origin = activeBackendOrigin();
    if (origin && !sources.includes(origin)) sources.push(origin);
    const csp = [
      "default-src 'self' data: blob:",
      "script-src 'self'",
      "style-src 'self' 'unsafe-inline'",
      "img-src 'self' data: blob:",
      "font-src 'self' data:",
      'connect-src ' + sources.join(' '),
      "media-src 'self' blob:",
      "object-src 'none'",
      "base-uri 'none'",
      "frame-ancestors 'none'",
      "form-action 'self'"
    ].join('; ');
    const headers = { ...details.responseHeaders };
    headers['Content-Security-Policy'] = [csp];
    callback({ responseHeaders: headers });
  });
}

/* ------------------------------------------------------------------- IPC */

function registerIpc() {
  ipcMain.handle('desktop:getState', () => currentState());

  ipcMain.handle('desktop:saveSettings', (_event, patch) => {
    if (!patch || typeof patch !== 'object' || Array.isArray(patch)) {
      return { ok: false, error: 'Invalid settings.' };
    }
    const allowed = Object.keys(patch).every((key) => key === 'backendMode' || key === 'remoteUrl');
    if (!allowed) return { ok: false, error: 'Unknown setting.' };
    if (patch.remoteUrl !== undefined && !validRemoteUrl(patch.remoteUrl)) {
      return { ok: false, error: 'Use https:// for a remote server. Plain http:// is allowed only for loopback addresses.' };
    }
    try {
      saveSettings(patch);
      return { ok: true, settings: loadSettings() };
    } catch (error) {
      return { ok: false, error: error.message };
    }
  });

  ipcMain.handle('desktop:restartBackend', async () => {
    await startBackendSequence();
    return currentState();
  });

  ipcMain.handle('desktop:openSettings', () => {
    openSettings();
    return { ok: true };
  });

  ipcMain.handle('desktop:openExternal', async (_event, raw) => {
    const parsed = validHttpUrl(raw);
    if (!parsed) return { ok: false };
    try {
      await shell.openExternal(parsed);
      return { ok: true };
    } catch (error) {
      return { ok: false, error: error.message };
    }
  });

  ipcMain.handle('desktop:chooseDataFolder', async () => {
    if (!mainWindow) return { ok: false };
    const result = await dialog.showOpenDialog(mainWindow, {
      properties: ['openDirectory'], title: 'NOVARA application data'
    });
    return result.canceled ? { ok: false } : { ok: true, path: result.filePaths[0] };
  });
}

/* ------------------------------------------------------------------ boot */

const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
  app.quit();
} else {
  app.on('second-instance', () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.focus();
    }
  });

  app.whenReady().then(() => {
    const DENIED_PERMISSIONS = new Set([
      'media', 'geolocation', 'midiSysex', 'pointerLock'
    ]);
    session.defaultSession.setPermissionRequestHandler((_webContents, permission, callback) => {
      callback(!DENIED_PERMISSIONS.has(permission));
    });
    if (process.platform !== 'win32') {
      process.umask(0o077);
    }
    installCsp();
    registerIpc();
    installMenu();
    createMainWindow();
    startBackendSequence();
  });

  app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') app.quit();
  });
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createMainWindow();
  });
  app.on('before-quit', () => {
    shuttingDown = true;
    stopBackend();
  });
}
