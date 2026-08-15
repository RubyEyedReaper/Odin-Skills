#!/usr/bin/env node
/**
 * Smoke test for scripts/visual.mjs — no external deps.
 *
 * Runs the visual generator against known fixtures and asserts the output
 * is a complete, self-contained, themable, accessible HTML document with
 * zero external URLs.
 *
 * Usage: node tests/visual-smoke.mjs
 */

import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import path from "node:path";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const skillRoot = path.resolve(__dirname, "..");
const visualScript = path.join(skillRoot, "scripts", "visual.mjs");

const fixtures = [
  path.join(skillRoot, "evals", "fixtures", "choose-a-database.expected.json"),
  path.join(skillRoot, "evals", "fixtures", "architecture-pattern.expected.json"),
];

const REQUIRED_SUBSTRINGS = [
  { label: "doctype html", test: (html) => /<!doctype html/i.test(html) },
  { label: "prefers-color-scheme", test: (html) => html.includes("prefers-color-scheme") },
  { label: 'role="img"', test: (html) => html.includes('role="img"') },
  { label: "<table", test: (html) => html.includes("<table") },
];

const FORBIDDEN_PATTERN = /https?:\/\//i;

let failures = 0;

for (const fixturePath of fixtures) {
  const fixtureName = path.basename(fixturePath);
  let html;
  try {
    html = execFileSync(process.execPath, [visualScript, fixturePath], {
      encoding: "utf8",
      maxBuffer: 10 * 1024 * 1024,
    });
  } catch (err) {
    console.error(`FAIL: ${fixtureName} — generator exited with error: ${err.message}`);
    failures += 1;
    continue;
  }

  for (const check of REQUIRED_SUBSTRINGS) {
    if (!check.test(html)) {
      console.error(`FAIL: ${fixtureName} — missing required content: ${check.label}`);
      failures += 1;
    }
  }

  if (FORBIDDEN_PATTERN.test(html)) {
    const match = html.match(FORBIDDEN_PATTERN);
    console.error(
      `FAIL: ${fixtureName} — output contains an external URL reference (${match[0]})`
    );
    failures += 1;
  }
}

// Bad-input handling: missing file path arg should fail gracefully via stdin,
// and a clearly invalid JSON file should error to stderr with a non-zero exit.
try {
  execFileSync(process.execPath, [visualScript, "/nonexistent/path/result.json"], {
    encoding: "utf8",
  });
  console.error("FAIL: expected non-zero exit for missing input file, got success");
  failures += 1;
} catch (err) {
  if (err.status !== 1) {
    console.error(`FAIL: expected exit code 1 for missing input file, got ${err.status}`);
    failures += 1;
  }
}

if (failures > 0) {
  console.error(`FAIL: ${failures} check(s) failed`);
  process.exit(1);
}

console.log("PASS: visual.mjs smoke tests passed for all fixtures");
process.exit(0);
