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

test('a stalled request times out with an actionable message', async () => {
  const original = globalThis.fetch;
  // Never resolves unless aborted, like a dropped tunnel connection.
  globalThis.fetch = (url, {signal}) => new Promise((_, reject) => signal.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError'))));
  try {
    await assert.rejects(apiRequest('', 't', '/members/1/password', {method:'POST', timeout:20}, () => {}), /did not respond in time/);
  } finally {globalThis.fetch = original;}
});

test('caller cancellation is forwarded and network failures are explained', async () => {
  const original = globalThis.fetch;
  globalThis.fetch = (url, {signal}) => new Promise((_, reject) => signal.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError'))));
  try {
    const controller = new AbortController();
    const pending = apiRequest('', 't', '/slips/1/preview', {signal:controller.signal}, () => {});
    controller.abort();
    await assert.rejects(pending, {name:'AbortError'});
    globalThis.fetch = async () => {throw new TypeError('Failed to fetch');};
    await assert.rejects(apiRequest('', 't', '/me', {}, () => {}), /Could not reach the server/);
  } finally {globalThis.fetch = original;}
});
