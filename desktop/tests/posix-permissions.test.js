/* Native POSIX chmod check for the modes used by the packaged desktop shell.
 * Skipped on Windows because POSIX mode bits do not describe ACLs there.
 */
'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const test = require('node:test');

const { dataMode } = require('../src/security-helpers');

const posixTest = process.platform === 'win32' ? test.skip : test;

posixTest('data directories stay traversable and files stay private', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'novara-perms-'));
  try {
    const nested = path.join(root, 'storage');
    const file = path.join(nested, 'object.bin');
    fs.mkdirSync(nested, { recursive: true });
    fs.writeFileSync(file, 'x');

    for (const target of [root, nested, file]) {
      fs.chmodSync(target, dataMode(target === file));
    }

    assert.equal(fs.statSync(root).mode & 0o777, 0o700);
    assert.equal(fs.statSync(nested).mode & 0o777, 0o700);
    assert.equal(fs.statSync(file).mode & 0o777, 0o600);
    assert.equal(fs.statSync(nested).mode & 0o007, 0);
  } finally {
    fs.rmSync(root, { recursive: true, force: true });
  }
});
