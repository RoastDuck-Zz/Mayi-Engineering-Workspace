// Executes production frontend functions with stubbed HTTP/DOM; no robot I/O.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test } = require('node:test');
const source = fs.readFileSync(path.join(__dirname, '../web/app.js'), 'utf8');

function excerpt(start, end) {
  const a = source.indexOf(start), b = source.indexOf(end, a + start.length);
  assert.ok(a >= 0 && b > a);
  return source.slice(a, b);
}

const pollDog = excerpt('async function pollStatus()', '\nfunction runStatusPoll()');

function clientIdFunctions() {
  return excerpt('function generateClientId()', '\nconst state =');
}

test('client ID prefers crypto.randomUUID when available', () => {
  const result = vm.runInNewContext(clientIdFunctions() + '; generateClientId()', {
    crypto: { randomUUID: () => 'native-random-uuid' },
  });
  assert.equal(result, 'native-random-uuid');
});

test('client ID falls back to a standards-compliant UUID v4', () => {
  const result = vm.runInNewContext(clientIdFunctions() + '; generateClientId()', {
    crypto: {
      getRandomValues: (bytes) => {
        for (let index = 0; index < bytes.length; index += 1) bytes[index] = index;
        return bytes;
      },
    },
  });
  assert.equal(result, '00010203-0405-4607-8809-0a0b0c0d0e0f');
  assert.match(result, /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
});

test('client ID final fallback is non-empty', () => {
  const result = vm.runInNewContext(clientIdFunctions() + '; generateClientId()', {
    crypto: {},
    Date: { now: () => 123456789 },
    Math: { random: () => 0.5 },
  });
  assert.ok(result);
  assert.match(result, /^client-123456789-/);
});

test('existing localStorage client ID is reused without regeneration', () => {
  let writes = 0;
  const result = vm.runInNewContext(clientIdFunctions() + '; getOrCreateClientId()', {
    crypto: { randomUUID: () => { throw new Error('must not regenerate'); } },
    localStorage: {
      getItem: (key) => key === 'robotdog-client-id' ? 'stored-client-id' : null,
      setItem: () => { writes += 1; },
    },
  });
  assert.equal(result, 'stored-client-id');
  assert.equal(writes, 0);
});

test('lateral buttons clear the BPX Walk start threshold without exceeding the limit', () => {
  const current = excerpt('function currentCommand()', '\nasync function sendVelocity(');
  for (const [direction, expected] of [[1, 0.25], [-1, -0.25]]) {
    const result = vm.runInNewContext(current + '; currentCommand()', {
      state: { speed: 0.35, held: new Map([['button', { axis: 'y', direction }]]) },
    });
    assert.equal(result.x, 0);
    assert.equal(result.y, expected);
    assert.equal(result.yaw, 0);
  }
  const maximum = vm.runInNewContext(current + '; currentCommand()', {
    state: { speed: 1, held: new Map([['button', { axis: 'y', direction: 1 }]]) },
  });
  assert.equal(maximum.y, 0.35);
});

for (const [name, owner, expected] of [
  ['owner renews', 'local', '/api/heartbeat'],
  ['observer reads only', 'other', '/api/status'],
  ['expired lease reads only', null, '/api/status'],
]) {
  test(`dog ${name}`, async () => {
    const requests = [];
    await vm.runInNewContext(pollDog + '; pollStatus()', {
      state: { pin: 'mock', clientId: 'local', pageLeaving: false, status: { connected: true, estopped: false, controller_id: owner } },
      api: async (route) => requests.push(route),
    });
    assert.deepEqual(requests, [expected]);
  });
}

test('HTTP deadline also aborts a stalled response body', async () => {
  const apiSource = excerpt('async function api(', '\nfunction formatNumber(');
  await assert.rejects(vm.runInNewContext(apiSource + '; api("/api/status", null, true, 20)', {
    state: { pin: 'mock' }, AbortController, setTimeout, clearTimeout,
    fetch: async (_url, options) => ({
      json: () => new Promise((_resolve, reject) => {
        options.signal.addEventListener('abort', () => reject(Object.assign(new Error('abort'), { name: 'AbortError' })));
      }),
    }),
  }), /状态请求超时/);
});
