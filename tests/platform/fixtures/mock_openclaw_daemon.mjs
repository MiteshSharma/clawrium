#!/usr/bin/env node
// Mock openclaw gateway daemon for pair_device.mjs behavioral tests (issue #608).
//
// Mimics the connect.challenge -> connect -> hello-ok handshake from
// openclaw's WS gateway. Parameterized by --expected-protocol so we can
// assert pair_device.mjs negotiates the correct range against different
// daemon versions.
//
// Usage:
//   node mock_openclaw_daemon.mjs --port <port> --expected-protocol <N>
//
// Behavior:
//   - On client connect, immediately emit { type: 'event', event:
//     'connect.challenge', payload: { nonce } }.
//   - On receiving a 'connect' request, verify
//     params.minProtocol <= expectedProtocol <= params.maxProtocol.
//     If not, reply with error.details.code = 'PROTOCOL_MISMATCH' and the
//     expectedProtocol field, matching the real daemon's error shape from
//     packages/gateway-host/src/message-handler.ts (v2026.5.28).
//   - On signature, accept any non-empty signature (the test focuses on
//     protocol negotiation, not crypto verification).
//   - On success, reply with payload.auth.deviceToken populated.

import { WebSocketServer } from 'ws';
import crypto from 'crypto';

function parseArgs() {
  const args = process.argv.slice(2);
  const out = {};
  for (let i = 0; i < args.length; i += 2) {
    const key = args[i].replace(/^--/, '');
    out[key] = args[i + 1];
  }
  return out;
}

const { port, 'expected-protocol': expectedProtocolRaw } = parseArgs();
const portNum = Number(port);
const expectedProtocol = Number(expectedProtocolRaw);

if (!Number.isInteger(portNum) || !Number.isInteger(expectedProtocol)) {
  console.error('usage: mock_openclaw_daemon.mjs --port <port> --expected-protocol <N>');
  process.exit(2);
}

const wss = new WebSocketServer({ port: portNum, host: '127.0.0.1' });

wss.on('listening', () => {
  // Stdout signal so the parent process knows the server is ready.
  console.log(JSON.stringify({ event: 'ready', port: portNum }));
});

wss.on('connection', (ws) => {
  const nonce = crypto.randomBytes(16).toString('hex');

  ws.send(JSON.stringify({
    type: 'event',
    event: 'connect.challenge',
    payload: { nonce },
  }));

  ws.on('message', (raw) => {
    let msg;
    try {
      msg = JSON.parse(raw.toString());
    } catch {
      return;
    }

    if (msg.type !== 'req' || msg.method !== 'connect') return;

    const { minProtocol, maxProtocol } = msg.params || {};
    const supportsCurrent =
      Number.isInteger(minProtocol) &&
      Number.isInteger(maxProtocol) &&
      minProtocol <= expectedProtocol &&
      maxProtocol >= expectedProtocol;

    if (!supportsCurrent) {
      ws.send(JSON.stringify({
        type: 'res',
        id: msg.id,
        ok: false,
        error: {
          code: 'INVALID_REQUEST',
          message: 'protocol mismatch',
          details: {
            code: 'PROTOCOL_MISMATCH',
            clientMinProtocol: minProtocol,
            clientMaxProtocol: maxProtocol,
            expectedProtocol,
            minimumProbeProtocol: expectedProtocol,
          },
        },
      }));
      ws.close(1002, 'protocol mismatch');
      return;
    }

    if (!msg.params?.device?.signature || !msg.params?.device?.nonce) {
      ws.send(JSON.stringify({
        type: 'res',
        id: msg.id,
        ok: false,
        error: { code: 'INVALID_REQUEST', message: 'missing device signature' },
      }));
      return;
    }

    ws.send(JSON.stringify({
      type: 'res',
      id: msg.id,
      ok: true,
      payload: {
        auth: {
          role: 'operator',
          scopes: msg.params.scopes || [],
          deviceToken: `mock-device-token-${crypto.randomBytes(8).toString('hex')}`,
          issuedAtMs: Date.now(),
        },
        policy: { maxPayload: 1048576 },
        negotiatedProtocol: expectedProtocol,
      },
    }));
  });
});

// Self-exit after 30s so a hung test never leaks the process.
setTimeout(() => process.exit(0), 30000).unref();
