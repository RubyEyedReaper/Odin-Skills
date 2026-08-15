/**
 * Regression coverage for the hook's cwd resolution (RM-0016, ADR-0042).
 *
 * The hook resolves two different directories from one event, and they want
 * different answers:
 *
 *   - state   — where `.impeccable/hook.cache.json` and the config live. Must be
 *               the anchored project root, because the session's cwd drifts
 *               (`cd projects/<slug> && …` persists across tool calls) and a
 *               drifted state path leaves untracked cache directories scattered
 *               through the tree.
 *   - target  — what a relative file path in the tool call resolves against.
 *               Must stay the frame the harness reported, or a shell-inferred
 *               write (`cp a.css styles.css`) is scanned against the wrong file.
 *
 * The subprocess case is the one that matters: it spawns the real wired entry
 * point (`hook.mjs`) with an event whose cwd has drifted into a subtree, and
 * asserts the cache lands at the root and *not* in the subtree.
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

import { resolveStateCwd, resolveProjectCwd } from './hook-lib.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const HOOK = path.join(HERE, 'hook.mjs');

function withEnv(vars, fn) {
  const saved = {};
  for (const [k, v] of Object.entries(vars)) {
    saved[k] = process.env[k];
    if (v === null) delete process.env[k];
    else process.env[k] = v;
  }
  try {
    return fn();
  } finally {
    for (const [k, v] of Object.entries(saved)) {
      if (v === undefined) delete process.env[k];
      else process.env[k] = v;
    }
  }
}

const NO_ENV = { CLAUDE_PROJECT_DIR: null, CURSOR_PROJECT_DIR: null };

test('resolveStateCwd prefers the anchored project root over a drifted event.cwd', () => {
  withEnv({ ...NO_ENV, CLAUDE_PROJECT_DIR: '/repo' }, () => {
    assert.equal(resolveStateCwd({ cwd: '/repo/projects/thing' }, '/fallback'), '/repo');
  });
});

test('resolveStateCwd falls back to event.cwd when no harness env var is set', () => {
  withEnv(NO_ENV, () => {
    assert.equal(resolveStateCwd({ cwd: '/repo/projects/thing' }, '/fallback'), '/repo/projects/thing');
  });
});

test('resolveStateCwd honours CURSOR_PROJECT_DIR when CLAUDE_PROJECT_DIR is absent', () => {
  withEnv({ ...NO_ENV, CURSOR_PROJECT_DIR: '/cursor-root' }, () => {
    assert.equal(resolveStateCwd({ cwd: '/elsewhere' }, '/fallback'), '/cursor-root');
  });
});

test('resolveStateCwd falls through workspace_roots then the fallback', () => {
  withEnv(NO_ENV, () => {
    assert.equal(resolveStateCwd({ workspace_roots: ['/ws'] }, '/fallback'), '/ws');
    assert.equal(resolveStateCwd({}, '/fallback'), '/fallback');
    assert.equal(resolveStateCwd(null, '/fallback'), '/fallback');
  });
});

// The target-side resolver keeps event.cwd first on purpose: relative paths in a
// tool call belong to the frame the harness reported. ADR-0042 records why these
// two are separate functions; a test that lets them converge would hide the bug.
test('resolveProjectCwd still prefers event.cwd even when the env var is set', () => {
  withEnv({ ...NO_ENV, CLAUDE_PROJECT_DIR: '/repo' }, () => {
    assert.equal(resolveProjectCwd({ cwd: '/repo/projects/thing' }, '/fallback'), '/repo/projects/thing');
  });
});

test('hook.mjs writes its cache at the anchored root, not the drifted subtree', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'impeccable-cwd-'));
  try {
    const subtree = path.join(root, 'projects', 'nested');
    fs.mkdirSync(subtree, { recursive: true });
    const target = path.join(subtree, 'Widget.tsx');
    fs.writeFileSync(target, 'export const Widget = () => <div>hi</div>;\n');

    const event = {
      session_id: 'test-session',
      cwd: subtree, // the drift: a prior `cd` left the session here
      tool_name: 'Write',
      tool_input: { file_path: target },
    };

    // Build the child env explicitly. Spreading process.env would inherit
    // IMPECCABLE_HOOK_DEPTH from any hook running above this test and trip the
    // re-entrancy guard, making the assertion pass for the wrong reason.
    execFileSync(process.execPath, [HOOK], {
      input: JSON.stringify(event),
      cwd: subtree,
      env: {
        PATH: process.env.PATH,
        HOME: process.env.HOME,
        CLAUDE_PROJECT_DIR: root,
      },
      encoding: 'utf-8',
    });

    assert.equal(
      fs.existsSync(path.join(subtree, '.impeccable')),
      false,
      'hook leaked a .impeccable directory into the drifted subtree',
    );
    assert.equal(
      fs.existsSync(path.join(root, '.impeccable', 'hook.cache.json')),
      true,
      'hook did not write its cache at the anchored project root',
    );
  } finally {
    fs.rmSync(root, { recursive: true, force: true });
  }
});
