// Exercise the installed package without credentials or inference; use one fixture command.
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import { mkdtempSync, readFileSync, rmSync, mkdirSync, writeFileSync } from 'node:fs';
import { createServer } from 'node:net';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { setTimeout as delay } from 'node:timers/promises';
import { test } from 'node:test';

test('installed HTTP assets, authentication and SQLite sessions survive a restart', { timeout: 60_000 }, async () => {
  const root = mkdtempSync(join(tmpdir(), 'pocket-package-'));
  mkdirSync(join(root, '.pi/prompts'), { recursive: true });
  writeFileSync(join(root, '.pi/prompts/food.md'), '---\ndescription: Fixture CLI food template\n---\nFixture food request: $@\n');
  mkdirSync(join(root, 'data/extensions'), { recursive: true });
  writeFileSync(join(root, 'data/extensions/notes-food.ts'), '/** Fixture food command, no helper or model. */\nexport default function(_host, web) { web.command("food", { description: "Fixture command", scope: "global", handler: () => ({ type: "card", output: "fixture" }) }); }\n');
  const listener = createServer().listen(0, '127.0.0.1');
  await once(listener, 'listening');
  const port = listener.address().port;
  await new Promise(resolve => listener.close(resolve));
  const base = `http://127.0.0.1:${port}`;
  let child;
  let exited;
  // Captured only in memory, never print owner links (including on failure).
  const start = async () => {
    child = spawn(join(process.env.PI_POCKET_TEST_PACKAGE, 'bin/pi-pocket'), [
      '--access', 'local', '--host', '127.0.0.1', '--port', String(port),
      '--data', join(root, 'data'), '--cwd', root,
    ], { env: { HOME: root, PATH: '', TMPDIR: tmpdir(), PI_CODING_AGENT_DIR: join(root, 'agent') }, stdio: 'ignore' });
    exited = once(child, 'exit');
    for (let attempt = 0; attempt < 150; attempt++) {
      assert.equal(child.exitCode, null, 'installed launcher remains running');
      try {
        if ((await fetch(base, { signal: AbortSignal.timeout(500) })).status === 200) return;
      } catch { /* wait for startup */ }
      await delay(100);
    }
    throw new Error('installed server did not become ready');
  };
  const stop = async () => {
    if (!child || child.exitCode !== null) return;
    child.kill('SIGTERM');
    const timer = setTimeout(() => child.kill('SIGKILL'), 15_000);
    try { await exited; } finally { clearTimeout(timer); }
    assert.equal(child.exitCode, 0, 'clean shutdown');
  };
  const config = () => JSON.parse(readFileSync(join(root, 'data/config.json'), 'utf8'));
  const api = async (path, body) => {
    const response = await fetch(`${base}/api/${path}`, {
      method: body === undefined ? 'GET' : 'POST',
      headers: { Authorization: `Bearer ${config().ownerToken}`, 'X-Pocket': '1', 'Content-Type': 'application/json' },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
      signal: AbortSignal.timeout(3000),
    });
    assert.equal(response.status, 200, path);
    return response.json();
  };
  try {
    await start();
    for (const asset of ['/', '/app.js', '/vendor/preact.mjs', '/vendor/marked.mjs', '/vendor/purify.mjs']) {
      const response = await fetch(base + asset);
      assert.equal(response.status, 200, asset);
      assert.ok((await response.text()).length > 0, asset);
    }
    assert.equal((await fetch(base + '/api/sessions')).status, 401, 'private API rejects anonymous requests');
    const token = config().ownerToken;
    const session = await api('sessions', { title: 'Package smoke test' });
    assert.ok((await api(`c/${session.id}/prompts`)).some(p => p.name === 'food'), 'CLI template is available while command is off');
    await api('extensions/notes-food.ts', { enabled: true });
    assert.ok((await api('me')).server.extensionCommands.some(c => c.name === 'food'), 'exact notes-food command is allowed');
    assert.ok(!(await api(`c/${session.id}/prompts`)).some(p => p.name === 'food'), 'Pocket command wins over same-name CLI template');
    await api('extensions/notes-food.ts', { enabled: false });
    assert.ok((await api(`c/${session.id}/prompts`)).some(p => p.name === 'food'), 'disabling command restores the unmodified template');
    await stop();
    await start();
    assert.equal(config().ownerToken, token, 'owner identity persists');
    assert.ok((await api('sessions')).some(each => each.id === session.id && each.title === 'Package smoke test'));
  } finally {
    await stop();
    rmSync(root, { recursive: true, force: true });
  }
});
