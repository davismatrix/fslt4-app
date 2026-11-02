import test from 'node:test';
import assert from 'node:assert/strict';
import {apiRequest, logoutSession} from '../src/apiClient.js';

test('expired or revoked session clears local state', async () => {
  let cleared = 0;
  const original = globalThis.fetch;
  globalThis.fetch = async () => new Response(JSON.stringify({detail:'Please sign in again.'}), {status:401});
  try {
    await assert.rejects(apiRequest('', 'expired', '/slips', {}, () => cleared++), /sign in again/);
    assert.equal(cleared, 1);
    await assert.rejects(apiRequest('', '', '/login', {}, () => cleared++));
    assert.equal(cleared, 1);
  } finally {globalThis.fetch = original;}
});

test('logout clears local state even when the server is unavailable', async () => {
  let cleared = false;
  await assert.rejects(logoutSession(async () => {throw Error('offline');}, () => {cleared = true;}), /offline/);
  assert.equal(cleared, true);
});
