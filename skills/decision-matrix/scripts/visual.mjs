#!/usr/bin/env node
/**
 * decision-matrix visual generator (Node stdlib only — zero external deps).
 *
 * Reads a result.json produced by `python3 -m scripts.score` and writes a
 * complete, self-contained HTML document (inline CSS + inline SVG, no
 * external network resources of any kind) to stdout.
 *
 * Usage:
 *   node scripts/visual.mjs path/to/result.json
 *   cat result.json | node scripts/visual.mjs
 */

import { readFileSync } from "node:fs";

// ── palette (perceptually distinct, colorblind-aware-ish, not all-purple) ──
const PALETTE = [
  "#1b6ca8", // blue
  "#d9622b", // orange
  "#1f9e6b", // green
  "#b8336a", // magenta/rose
  "#9a7d0a", // olive/gold
  "#5b5bd6", // indigo
  "#c23b22", // red-orange
  "#0e8f8f", // teal
];

// ── small helpers ───────────────────────────────────────────────────────────

function escapeHtml(value) {
  if (value === null || value === undefined) return "";
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function labelFromId(id) {
  if (!id) return "";
  return id
    .split("-")
    .map((part) => (part.length ? part[0].toUpperCase() + part.slice(1) : part))
    .join(" ");
}

function readInput(argv) {
  const path = argv[2];
  if (path) {
    return readFileSync(path, "utf8");
  }
  return readFileSync(0, "utf8"); // stdin
}

function fmtScore(n) {
  if (typeof n !== "number" || Number.isNaN(n)) return "—";
  return Math.round(n).toString();
}

function fmtNum(n, digits = 2) {
  if (typeof n !== "number" || Number.isNaN(n)) return "—";
  return n.toFixed(digits);
}

// Map a 0-100 mean score to a green(high)->red(low) background color (OKLCH-ish
// via HSL for stdlib simplicity — no external color libs).
function heatColor(mean) {
  if (typeof mean !== "number" || Number.isNaN(mean)) return "transparent";
  const clamped = Math.max(0, Math.min(100, mean));
  // hue 0 (red) at 0, hue 130 (green) at 100
  const hue = (clamped / 100) * 130;
  return `hsl(${hue.toFixed(0)} 65% 88%)`;
}

function heatTextColor(mean) {
  // Keep text dark; backgrounds are kept light enough for contrast.
  return "#1a1a1a";
}

// ── data shaping ─────────────────────────────────────────────────────────

function getOptionLabels(result) {
  const ids = new Set([
    ...(result.active_options || []),
    ...(result.vetoed_options || []),
  ]);
  const labels = {};
  for (const id of ids) labels[id] = labelFromId(id);
  // Prefer recommendation.winner_label when it matches the winner id.
  const rec = result.recommendation || {};
  if (rec.winner && rec.winner_label) labels[rec.winner] = rec.winner_label;
  return labels;
}

function getCriteriaIds(result) {
  const ids = new Set();
  const agg = result.aggregated_scores || {};
  for (const optId of Object.keys(agg)) {
    for (const critId of Object.keys(agg[optId] || {})) ids.add(critId);
  }
  return Array.from(ids);
}

// ── section builders ────────────────────────────────────────────────────

function buildRecommendation(result) {
  const rec = result.recommendation || {};
  const labels = getOptionLabels(result);
  const winnerLabel = rec.winner_label || labels[rec.winner] || rec.winner || "No recommendation";
  const confidence = rec.confidence || "low";
  const caveats = Array.isArray(rec.caveats) ? rec.caveats : [];

  const caveatItems = caveats.length
    ? `<ul class="caveat-list">${caveats
        .map((c) => `<li>${escapeHtml(c)}</li>`)
        .join("")}</ul>`
    : `<p class="muted">No caveats recorded.</p>`;

  return `
<section aria-labelledby="rec-heading">
  <header>
    <h2 id="rec-heading">Recommendation</h2>
  </header>
  <div class="rec-panel">
    <div class="rec-winner">
      <span class="rec-winner-label">${escapeHtml(winnerLabel)}</span>
      <span class="badge badge-${escapeHtml(confidence)}" role="status">
        Confidence: ${escapeHtml(confidence)}
      </span>
    </div>
    <p class="rec-rationale">${escapeHtml(rec.rationale || "No rationale provided.")}</p>
    <h3 class="caveats-heading">Caveats</h3>
    ${caveatItems}
  </div>
</section>`;
}

function buildHeatmap(result) {
  const agg = result.aggregated_scores || {};
  const labels = getOptionLabels(result);
  const criteriaIds = getCriteriaIds(result);
  const active = result.active_options || [];
  const vetoed = result.vetoed_options || [];
  const orderedOptions = [...active, ...vetoed];

  const wsRanking = (result.method_results?.["weighted-sum"]?.ranking) || [];
  const wsByOption = {};
  for (const r of wsRanking) wsByOption[r.option] = r.score;

  if (orderedOptions.length === 0 || criteriaIds.length === 0) {
    return `
<section aria-labelledby="heatmap-heading">
  <header><h2 id="heatmap-heading">Scored Matrix</h2></header>
  <p class="muted">No scored options to display.</p>
</section>`;
  }

  const headerCells = criteriaIds
    .map((cid) => `<th scope="col">${escapeHtml(labelFromId(cid))}</th>`)
    .join("");

  const rows = orderedOptions
    .map((optId) => {
      const isVetoed = vetoed.includes(optId);
      const rowLabel = escapeHtml(labels[optId] || optId);
      const rowClass = isVetoed ? "row-vetoed" : "";
      const nameCell = isVetoed
        ? `<th scope="row" class="${rowClass}"><s>${rowLabel}</s> <span class="vetoed-tag">(vetoed)</span></th>`
        : `<th scope="row">${rowLabel}</th>`;

      const scoreCells = criteriaIds
        .map((cid) => {
          const entry = agg[optId]?.[cid];
          if (!entry) return `<td class="cell-empty">—</td>`;
          const bg = heatColor(entry.mean);
          const fg = heatTextColor(entry.mean);
          return `<td style="background-color:${bg};color:${fg}" title="mean ${fmtNum(
            entry.mean,
            1
          )}, confidence-adjusted ${fmtNum(entry.confidence_adjusted, 1)}">${fmtScore(
            entry.mean
          )}</td>`;
        })
        .join("");

      const wsScore = wsByOption[optId];
      const wsCell = `<td class="cell-weighted-sum">${
        typeof wsScore === "number" ? fmtNum(wsScore, 1) : "—"
      }</td>`;

      return `<tr class="${rowClass}">${nameCell}${scoreCells}${wsCell}</tr>`;
    })
    .join("");

  return `
<section aria-labelledby="heatmap-heading">
  <header><h2 id="heatmap-heading">Scored Matrix</h2></header>
  <div class="table-scroll">
    <table>
      <caption>Mean criterion scores per option (0–100, green = higher, red = lower); vetoed options are struck through. Final column is the weighted-sum total.</caption>
      <thead>
        <tr>
          <th scope="col">Option</th>
          ${headerCells}
          <th scope="col">Weighted-sum</th>
        </tr>
      </thead>
      <tbody>
        ${rows}
      </tbody>
    </table>
  </div>
</section>`;
}

function buildRadar(result) {
  const agg = result.aggregated_scores || {};
  const labels = getOptionLabels(result);
  const criteriaIds = getCriteriaIds(result);
  const active = result.active_options || [];

  if (active.length === 0 || criteriaIds.length < 3) {
    return `
<section aria-labelledby="radar-heading">
  <header><h2 id="radar-heading">Radar Comparison</h2></header>
  <p class="muted">Radar chart requires at least 3 criteria and 1 active option.</p>
</section>`;
  }

  const size = 420;
  const center = size / 2;
  const radius = size / 2 - 60;
  const n = criteriaIds.length;
  const angleStep = (2 * Math.PI) / n;

  function pointFor(index, value0to100) {
    const angle = -Math.PI / 2 + index * angleStep;
    const r = (Math.max(0, Math.min(100, value0to100)) / 100) * radius;
    return [center + r * Math.cos(angle), center + r * Math.sin(angle)];
  }

  // Axis lines + labels
  const axisLines = criteriaIds
    .map((cid, i) => {
      const [x, y] = pointFor(i, 100);
      return `<line x1="${center}" y1="${center}" x2="${fmtNum(x, 2)}" y2="${fmtNum(
        y,
        2
      )}" class="radar-axis" />`;
    })
    .join("");

  const axisLabels = criteriaIds
    .map((cid, i) => {
      const [x, y] = pointFor(i, 112);
      const anchor = Math.abs(x - center) < 4 ? "middle" : x > center ? "start" : "end";
      return `<text x="${fmtNum(x, 2)}" y="${fmtNum(
        y,
        2
      )}" text-anchor="${anchor}" class="radar-axis-label">${escapeHtml(
        labelFromId(cid)
      )}</text>`;
    })
    .join("");

  // Concentric grid rings at 25/50/75/100
  const rings = [25, 50, 75, 100]
    .map((pct) => {
      const pts = criteriaIds
        .map((_, i) => pointFor(i, pct).map((v) => fmtNum(v, 2)).join(","))
        .join(" ");
      return `<polygon points="${pts}" class="radar-ring" />`;
    })
    .join("");

  const polygons = active
    .map((optId, idx) => {
      const color = PALETTE[idx % PALETTE.length];
      const pts = criteriaIds
        .map((cid, i) => {
          const mean = agg[optId]?.[cid]?.mean ?? 0;
          return pointFor(i, mean).map((v) => fmtNum(v, 2)).join(",");
        })
        .join(" ");
      return `<polygon points="${pts}" fill="${color}" fill-opacity="0.18" stroke="${color}" stroke-width="2.5" class="radar-series" />`;
    })
    .join("");

  const legend = active
    .map((optId, idx) => {
      const color = PALETTE[idx % PALETTE.length];
      return `<li><span class="swatch" style="background:${color}"></span>${escapeHtml(
        labels[optId] || optId
      )}</li>`;
    })
    .join("");

  const descText = `Radar chart comparing ${active.length} option(s) across ${n} criteria: ${criteriaIds
    .map((c) => labelFromId(c))
    .join(", ")}.`;

  return `
<section aria-labelledby="radar-heading">
  <header><h2 id="radar-heading">Radar Comparison</h2></header>
  <figure>
    <svg viewBox="0 0 ${size} ${size}" role="img" aria-labelledby="radar-svg-title radar-svg-desc" class="radar-svg">
      <title id="radar-svg-title">Per-option radar chart across all criteria</title>
      <desc id="radar-svg-desc">${escapeHtml(descText)}</desc>
      ${rings}
      ${axisLines}
      ${polygons}
      ${axisLabels}
    </svg>
    <figcaption>
      <ul class="legend">${legend}</ul>
    </figcaption>
  </figure>
</section>`;
}

function buildTornado(result) {
  const tornado = result.sensitivity?.tornado_data || result.sensitivity?.tornado || [];

  if (!Array.isArray(tornado) || tornado.length === 0) {
    return `
<section aria-labelledby="tornado-heading">
  <header><h2 id="tornado-heading">Sensitivity Tornado</h2></header>
  <p class="muted">No sensitivity data available.</p>
</section>`;
  }

  const sorted = [...tornado].sort(
    (a, b) => (b.swing_impact ?? 0) - (a.swing_impact ?? 0)
  );
  const maxImpact = Math.max(...sorted.map((d) => d.swing_impact ?? 0), 0.0001);

  const width = 640;
  const rowHeight = 36;
  const leftMargin = 180;
  const rightMargin = 80;
  const barAreaWidth = width - leftMargin - rightMargin;
  const height = sorted.length * rowHeight + 20;

  const bars = sorted
    .map((d, i) => {
      const y = i * rowHeight + 10;
      const impact = d.swing_impact ?? 0;
      const barWidth = maxImpact > 0 ? (impact / maxImpact) * barAreaWidth : 0;
      const label = labelFromId(d.criterion);
      const color = PALETTE[i % PALETTE.length];
      return `
        <g>
          <text x="${leftMargin - 10}" y="${y + rowHeight / 2 + 4}" text-anchor="end" class="tornado-label">${escapeHtml(
        label
      )}</text>
          <rect x="${leftMargin}" y="${y}" width="${fmtNum(
        barWidth,
        2
      )}" height="${rowHeight - 10}" fill="${color}" class="tornado-bar" />
          <text x="${leftMargin + barWidth + 8}" y="${y + rowHeight / 2 + 4}" class="tornado-value">${fmtNum(
        impact,
        2
      )}</text>
        </g>`;
    })
    .join("");

  const descText = `Tornado chart of sensitivity swing impact per criterion, sorted descending: ${sorted
    .map((d) => `${labelFromId(d.criterion)} (${fmtNum(d.swing_impact ?? 0, 2)})`)
    .join(", ")}.`;

  return `
<section aria-labelledby="tornado-heading">
  <header><h2 id="tornado-heading">Sensitivity Tornado</h2></header>
  <figure>
    <svg viewBox="0 0 ${width} ${height}" role="img" aria-labelledby="tornado-svg-title tornado-svg-desc" class="tornado-svg">
      <title id="tornado-svg-title">Sensitivity tornado chart</title>
      <desc id="tornado-svg-desc">${escapeHtml(descText)}</desc>
      ${bars}
    </svg>
  </figure>
</section>`;
}

function buildMethodTable(result) {
  const methodResults = result.method_results || {};
  const labels = getOptionLabels(result);
  const disagreement = result.disagreement_report || {};
  const winnerByMethod = disagreement.winner_by_method || {};
  const methodsAgree = disagreement.methods_agree !== false;

  const validMethods = Object.entries(methodResults).filter(
    ([, v]) => v && Array.isArray(v.ranking)
  );
  const errorMethods = Object.entries(methodResults).filter(
    ([, v]) => v && typeof v === "object" && "error" in v
  );

  if (validMethods.length === 0) {
    return `
<section aria-labelledby="methods-heading">
  <header><h2 id="methods-heading">Method Comparison</h2></header>
  <p class="muted">No method rankings available.</p>
</section>`;
  }

  // Collect all options that appear in any method ranking
  const optionSet = new Set();
  for (const [, v] of validMethods) {
    for (const entry of v.ranking) optionSet.add(entry.option);
  }
  const options = Array.from(optionSet);

  const methodNames = validMethods.map(([name]) => name);
  const headerCells = methodNames
    .map((name) => `<th scope="col">${escapeHtml(labelFromId(name))}</th>`)
    .join("");

  const rankByMethodOption = {};
  for (const [name, v] of validMethods) {
    rankByMethodOption[name] = {};
    for (const entry of v.ranking) {
      rankByMethodOption[name][entry.option] = entry.rank;
    }
  }

  const rows = options
    .map((optId) => {
      const rowLabel = escapeHtml(labels[optId] || optId);
      const cells = methodNames
        .map((name) => {
          const rank = rankByMethodOption[name][optId];
          const isWinner = winnerByMethod[name] === optId;
          const disagreeClass =
            !methodsAgree && isWinner ? " class=\"cell-disagree\"" : "";
          const text = typeof rank === "number" ? `#${rank}` : "—";
          const marker = isWinner ? ` <span class="winner-marker" aria-hidden="true">★</span>` : "";
          return `<td${disagreeClass}>${text}${marker}</td>`;
        })
        .join("");
      return `<tr><th scope="row">${rowLabel}</th>${cells}</tr>`;
    })
    .join("");

  const errorNote = errorMethods.length
    ? `<p class="method-error-note"><strong>Methods that did not run:</strong> ${errorMethods
        .map(([name, v]) => `${escapeHtml(labelFromId(name))} — ${escapeHtml(v.error)}`)
        .join("; ")}</p>`
    : "";

  const disagreeNote = !methodsAgree
    ? `<p class="method-disagree-note" role="note">Methods disagree on the winner (highlighted cells, ★ marks each method's rank-1 pick).</p>`
    : `<p class="muted">All methods agree on the winner.</p>`;

  return `
<section aria-labelledby="methods-heading">
  <header><h2 id="methods-heading">Method Comparison</h2></header>
  <div class="table-scroll">
    <table>
      <caption>Rank per option (1 = best) across scoring methods. ★ marks each method's top pick; highlighted cells show disagreement.</caption>
      <thead>
        <tr><th scope="col">Option</th>${headerCells}</tr>
      </thead>
      <tbody>
        ${rows}
      </tbody>
    </table>
  </div>
  ${disagreeNote}
  ${errorNote}
</section>`;
}

// ── styles ───────────────────────────────────────────────────────────────

function buildStyles() {
  return `
:root {
  color-scheme: light dark;
  --color-bg: #fafaf9;
  --color-surface: #ffffff;
  --color-text: #1a1a1a;
  --color-muted: #5a5a5a;
  --color-border: #d8d8d4;
  --color-accent: #1b6ca8;
  --color-high: #1f9e6b;
  --color-medium: #b8860b;
  --color-low: #c23b22;
  --radius: 10px;
  --space-section: 2.5rem;
  --duration-normal: 200ms;
}

@media (prefers-color-scheme: dark) {
  :root {
    --color-bg: #15161a;
    --color-surface: #1e2027;
    --color-text: #f0f0ee;
    --color-muted: #b4b4ae;
    --color-border: #3a3c44;
    --color-accent: #6fb3e0;
    --color-high: #4fd39b;
    --color-medium: #e0b94f;
    --color-low: #ef7a63;
  }
}

* { box-sizing: border-box; }

body {
  margin: 0;
  padding: 0 1.5rem 4rem;
  background: var(--color-bg);
  color: var(--color-text);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  line-height: 1.5;
}

header.page-header {
  max-width: 1000px;
  margin: 0 auto;
  padding: 2rem 0 1rem;
}

main {
  max-width: 1000px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: var(--space-section);
}

h1 { font-size: 1.75rem; margin: 0 0 0.25rem; }
h2 { font-size: 1.25rem; margin: 0 0 1rem; }
h3.caveats-heading { font-size: 1rem; margin: 1rem 0 0.5rem; color: var(--color-muted); }

section {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  padding: 1.5rem;
}

.muted { color: var(--color-muted); }

.rec-panel { display: flex; flex-direction: column; gap: 0.5rem; }
.rec-winner { display: flex; align-items: center; gap: 0.75rem; flex-wrap: wrap; }
.rec-winner-label { font-size: 1.4rem; font-weight: 700; }
.rec-rationale { margin: 0.25rem 0 0; }

.badge {
  display: inline-block;
  padding: 0.2rem 0.65rem;
  border-radius: 999px;
  font-size: 0.8rem;
  font-weight: 600;
  border: 1px solid currentColor;
}
.badge-high { color: var(--color-high); }
.badge-medium { color: var(--color-medium); }
.badge-low { color: var(--color-low); }

.caveat-list { margin: 0; padding-left: 1.25rem; }
.caveat-list li { margin-bottom: 0.35rem; }

.table-scroll { overflow-x: auto; }

table {
  border-collapse: collapse;
  width: 100%;
  font-size: 0.92rem;
}

caption {
  text-align: left;
  color: var(--color-muted);
  font-size: 0.85rem;
  margin-bottom: 0.5rem;
  caption-side: top;
}

th, td {
  border: 1px solid var(--color-border);
  padding: 0.5rem 0.65rem;
  text-align: center;
}

thead th {
  background: var(--color-bg);
  font-weight: 600;
}

tbody th[scope="row"] {
  text-align: left;
  font-weight: 600;
  background: var(--color-bg);
}

.row-vetoed { opacity: 0.7; }
.vetoed-tag { font-size: 0.75rem; color: var(--color-muted); font-weight: 400; }

.cell-weighted-sum { font-weight: 700; }
.cell-empty { color: var(--color-muted); }
.cell-disagree {
  outline: 2px solid var(--color-low);
  outline-offset: -2px;
  font-weight: 700;
}

.winner-marker { color: var(--color-medium); }

figure { margin: 0; display: flex; flex-direction: column; align-items: center; gap: 1rem; }

.radar-svg, .tornado-svg { width: 100%; height: auto; max-width: 640px; }

.radar-axis { stroke: var(--color-border); stroke-width: 1; }
.radar-ring { fill: none; stroke: var(--color-border); stroke-width: 1; }
.radar-axis-label { fill: var(--color-muted); font-size: 11px; }
.radar-series { transition: fill-opacity var(--duration-normal) ease; }

.legend { list-style: none; margin: 0; padding: 0; display: flex; flex-wrap: wrap; gap: 0.75rem 1.25rem; justify-content: center; }
.legend li { display: flex; align-items: center; gap: 0.4rem; font-size: 0.85rem; }
.swatch { width: 12px; height: 12px; border-radius: 3px; display: inline-block; }

.tornado-label { fill: var(--color-text); font-size: 12px; }
.tornado-value { fill: var(--color-text); font-size: 12px; }
.tornado-bar { transition: width var(--duration-normal) ease; }

.method-error-note, .method-disagree-note {
  margin-top: 0.75rem;
  font-size: 0.88rem;
  color: var(--color-muted);
}

@media (prefers-reduced-motion: no-preference) {
  .radar-series, .tornado-bar { transition-duration: var(--duration-normal); }
}

@media (prefers-reduced-motion: reduce) {
  .radar-series, .tornado-bar { transition: none; }
}

footer.page-footer {
  max-width: 1000px;
  margin: 2rem auto 0;
  color: var(--color-muted);
  font-size: 0.8rem;
}
`;
}

// ── document assembly ───────────────────────────────────────────────────

function buildDocument(result) {
  const rec = result.recommendation || {};
  const title = `Decision Matrix — ${rec.winner_label || rec.winner || "Result"}`;

  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>${escapeHtml(title)}</title>
<style>${buildStyles()}</style>
</head>
<body>
<header class="page-header">
  <h1>Decision Matrix Report</h1>
  <p class="muted">Generated from decision-matrix scoring results.</p>
</header>
<main>
${buildRecommendation(result)}
${buildHeatmap(result)}
${buildRadar(result)}
${buildTornado(result)}
${buildMethodTable(result)}
</main>
<footer class="page-footer">
  <p>Self-contained report — no external network resources.</p>
</footer>
</body>
</html>`;
}

// ── entry point ──────────────────────────────────────────────────────────

function main() {
  let raw;
  try {
    raw = readInput(process.argv);
  } catch (err) {
    process.stderr.write(`visual.mjs: failed to read input: ${err.message}\n`);
    process.exit(1);
  }

  let result;
  try {
    result = JSON.parse(raw);
  } catch (err) {
    process.stderr.write(`visual.mjs: invalid JSON input: ${err.message}\n`);
    process.exit(1);
  }

  if (!result || typeof result !== "object" || Array.isArray(result)) {
    process.stderr.write("visual.mjs: result JSON must be an object\n");
    process.exit(1);
  }

  let html;
  try {
    html = buildDocument(result);
  } catch (err) {
    process.stderr.write(`visual.mjs: failed to build report: ${err.message}\n`);
    process.exit(1);
  }

  process.stdout.write(html);
}

main();
