import test from 'node:test';
import assert from 'node:assert/strict';
import {parsePasswordLink} from '../src/passwordLink.js';

test('reads invite and reset tokens from the URL fragment', () => {
  assert.deepEqual(parsePasswordLink('https://members.example.com/password#invite=abc123'), {token:'abc123', invite:true});
  assert.deepEqual(parsePasswordLink('https://members.example.com/password#reset=xyz789'), {token:'xyz789', invite:false});
  assert.deepEqual(parsePasswordLink('/#reset=xyz789'), {token:'xyz789', invite:false});
});

test('ignores links without a token, query-string tokens, and malformed URLs', () => {
  assert.equal(parsePasswordLink('https://members.example.com/'), null);
  assert.equal(parsePasswordLink('https://members.example.com/password?reset=leaky'), null);
  assert.equal(parsePasswordLink('http://['), null);
});
