/* NOVARA Desktop Client Edition — pure security helpers shared by the shell.
 *
 * These functions have no Electron dependency so they can be unit-tested with
 * plain Node. The shell uses them to keep inherited environment variables out
 * of the bundled backend and to select the right HTTP client for health checks.
 */
'use strict';

const http = require('http');
const https = require('https');

/* Values inherited from a developer's shell must not silently reconfigure the
 * packaged backend: dev mode exposes tokens, a database URL breaks the
 * per-user data boundary, and storage settings can redirect files off-box. */
const INHERITED_BACKEND_KEYS = Object.freeze([
  'NOVARA_DEV_MODE',
  'NOVARA_DATABASE_URL',
  'NOVARA_CORS_ORIGINS',
  'NOVARA_STORAGE_BACKEND'
]);

function sanitizeBackendEnv(baseEnv, overrides) {
  const env = { ...(baseEnv || {}) };
  for (const key of INHERITED_BACKEND_KEYS) delete env[key];
  for (const key of Object.keys(env)) {
    if (key.startsWith('NOVARA_S3_')) delete env[key];
  }
  for (const [key, value] of Object.entries(overrides || {})) {
    if (value === undefined || value === null) delete env[key];
    else env[key] = String(value);
  }
  return env;
}

function healthClientFor(rawUrl) {
  let parsed;
  try {
    parsed = new URL(String(rawUrl));
  } catch (_) {
    throw new Error('Invalid health URL');
  }
  if (parsed.protocol === 'https:') return https;
  if (parsed.protocol === 'http:') return http;
  throw new Error(`Unsupported health URL protocol: ${parsed.protocol}`);
}

function healthGet(rawUrl, callback) {
  return healthClientFor(rawUrl).get(rawUrl, callback);
}

/* A directory needs search permission (x); a regular file does not. */
function dataMode(isDirectory) {
  return isDirectory ? 0o700 : 0o600;
}

module.exports = {
  INHERITED_BACKEND_KEYS,
  sanitizeBackendEnv,
  healthClientFor,
  healthGet,
  dataMode
};
