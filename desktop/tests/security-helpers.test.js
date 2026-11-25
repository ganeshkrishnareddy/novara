/* Focused unit tests for the shell's security helpers. Run with:
 * node --test desktop/tests/security-helpers.test.js
 */
'use strict';

const assert = require('node:assert/strict');
const http = require('node:http');
const https = require('node:https');
const test = require('node:test');

const {
  sanitizeBackendEnv,
  healthClientFor,
  healthGet,
  dataMode
} = require('../src/security-helpers');

test('inherited backend overrides are removed', () => {
  const result = sanitizeBackendEnv({
    NOVARA_DEV_MODE: '1',
    NOVARA_DATABASE_URL: 'sqlite:///C:/outside.sqlite3',
    NOVARA_CORS_ORIGINS: '*',
    NOVARA_STORAGE_BACKEND: 's3',
    NOVARA_S3_SECRET_KEY: 'leaked',
    NOVARA_S3_BUCKET: 'outside',
    PATH: 'C:/bin'
  });
  assert.equal(result.NOVARA_DEV_MODE, undefined);
  assert.equal(result.NOVARA_DATABASE_URL, undefined);
  assert.equal(result.NOVARA_CORS_ORIGINS, undefined);
  assert.equal(result.NOVARA_STORAGE_BACKEND, undefined);
  assert.equal(result.NOVARA_S3_SECRET_KEY, undefined);
  assert.equal(result.NOVARA_S3_BUCKET, undefined);
  assert.equal(result.PATH, 'C:/bin');
});

test('explicit overrides are applied after sanitizing', () => {
  const result = sanitizeBackendEnv(
    { NOVARA_DEV_MODE: '1', NOVARA_S3_ENDPOINT: 'http://outside' },
    { NOVARA_DEV_MODE: undefined, NOVARA_STORAGE_BACKEND: 'local', NOVARA_DB_PATH: '/data/app.sqlite3' }
  );
  assert.equal(result.NOVARA_DEV_MODE, undefined);
  assert.equal(result.NOVARA_S3_ENDPOINT, undefined);
  assert.equal(result.NOVARA_STORAGE_BACKEND, 'local');
  assert.equal(result.NOVARA_DB_PATH, '/data/app.sqlite3');
});

test('health checks use the protocol of the configured URL', () => {
  assert.equal(healthClientFor('http://127.0.0.1:8000'), http);
  assert.equal(healthClientFor('https://novara.example.com'), https);
  assert.throws(() => healthClientFor('file:///etc/passwd'), /Unsupported/);
  assert.throws(() => healthClientFor('not a url'), /Invalid/);
});

test('healthGet delegates to the matching client', () => {
  const original = https.get;
  let calledWith = null;
  https.get = (url) => { calledWith = url; return { destroy() {} }; };
  try {
    healthGet('https://novara.example.com/health', () => {});
    assert.equal(calledWith, 'https://novara.example.com/health');
  } finally {
    https.get = original;
  }
});

test('data modes keep directories traversable', () => {
  assert.equal(dataMode(true), 0o700);
  assert.equal(dataMode(false), 0o600);
});
