#!/usr/bin/env python3
"""leek — leak and hygiene scanner for a Claude Code environment.

Eight check families, one finding schema, one exit contract. Read-only by
construction: this module opens no file for writing, issues no mutating SQL, and
runs no subprocess that changes state. That property is asserted by
`.claude/tests/leek.test.sh`, not merely claimed here (ADR-0088).

Exit codes are the interface:
    0   scanned, no findings
    1   findings (an unreadable evidence channel IS a finding — never a clean 0)
    2   usage error

Every path outside LEEK_ROOT is reached through exactly one environment
override, so the regression matrix can point the whole scanner at a fixture tree
and its verdict never moves with host state:

    LEEK_ROOT              repository root under audit
    LEEK_CLAUDE_HOME       Claude Code state dir            (default ~/.claude)
    LEEK_MEM_DB            claude-mem sqlite db     (default ~/.claude-mem/claude-mem.db)
    LEEK_TRANSCRIPT_DIR    session transcripts      (default $LEEK_CLAUDE_HOME/projects)
    LEEK_PROC_CMD          process listing command  (default ps -eo pid,ppid,etimes,rss,args)

The claude-mem home is derived from LEEK_MEM_DB's parent rather than taking a
sixth override, so there is exactly one way to redirect that channel.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path

# --------------------------------------------------------------------------- #
# Thresholds. Constants, not a config file: an audit tool whose thresholds live
# in a file it also audits is a loop, and a config-absent path is one more way a
# check disables itself silently (Fork 4 of the plan).
# --------------------------------------------------------------------------- #

KB = 1024
MB = 1024 * KB
GB = 1024 * MB
DAY = 86400

ALWAYS_ON_RULE_BYTES = 45 * KB      # total always-on rule text before it is a tax
RULE_FILE_BYTES = 8 * KB            # one always-on rule file
CLAUDE_MD_BYTES = 32 * KB           # the project instruction file
AGENT_DESC_WORDS = 30               # description loads on every dispatch
AGENT_FILE_LINES = 200
SKILL_BODY_LINES = 400
SKILL_STUB_BYTES = 400              # below this a SKILL.md is a stub, not a skill
MCP_SERVER_MAX = 10
MCP_TOOL_TOKENS = 500               # per-tool schema estimate, ECC's measurement

TRANSCRIPT_BYTES = 20 * MB          # one session's transcript
BIG_RESULT_BYTES = 100 * KB         # one tool result
DUP_TOOL_RESULT = 3                 # identical results in one session
RETRY_LOOP = 5                      # identical tool inputs in one session
TRANSCRIPT_READ_CAP = 40 * MB       # per file; truncation is reported, never silent

MEM_RETENTION_DAYS = 180
MEM_DUP_MIN = 2

CACHE_BYTES_HIGH = 1 * GB
CACHE_BYTES_MED = 256 * MB
CACHE_STALE_DAYS = 30
WALK_FILE_CAP = 200_000             # per cache root; truncation is reported

ORPHAN_MIN_ETIMES = 3600            # a young child is not yet an orphan
RUNAWAY_MIN_ETIMES = 7200
RUNAWAY_MIN_RSS_KB = 1_500_000
RUNAWAY_CPU_RATIO = 0.30            # cumulative CPU / elapsed: above this it is looping

HOOK_MAX_BYTES = 24 * KB            # a hook runs on every matching event
HOOK_OUTPUT_BOUND = re.compile(r"\|\s*(head|tail|cut -c|fold)\b|\bhead -c\b|%\.[0-9]+s")
HOOK_SWALLOW_MIN = 8                # below this it is the idiom, not a pattern

# Every pattern below runs against a NORMALIZED copy of the source — comments and quoted
# spans removed — and matches at a command position. The unnormalized versions of these
# flagged 15 of 16 real hooks at HIGH, all of them on the word `eval` inside a comment or
# a grep pattern, and on `$(cat "$f")`, which is the *recommended* form for reading a file
# into a variable rather than shell composition. A check that fires on 94% of its
# population is a check that gets deleted.
CMD_POS = r"(?:^|[;&|]|\bthen\b|\bdo\b|\belse\b)\s*"
HOOK_UNSAFE = re.compile(
    CMD_POS + r"eval\b" r"|\bcurl\b[^|;]*\|\s*(?:ba)?sh\b" r"|\bwget\b[^|;]*\|\s*(?:ba)?sh\b",
    re.M,
)
HOOK_ENV_DUMP = re.compile(CMD_POS + r"(?:env|printenv|set)\s*(?:\||>|$)", re.M)
# The standard hook-input read. Correct, universal, and not a swallowed failure.
HOOK_STDIN_IDIOM = re.compile(r"\$\(\s*cat\b[^)]*\)|2>\s*/dev/null\s*\|\|\s*(?:true|:)\s*\)")
HOOK_SWALLOW = re.compile(r"\|\|\s*true\b|\|\|\s*:\s*$|2>\s*/dev/null\s*(?:\||;|$)", re.M)

PLAN_STALE_DAYS = 14                # a spent plan is deleted, not archived
RUNTIME_STALE_HOURS = 24
CLAIM_TICKET_TTL_MIN = 15           # ADR-0051

SEVERITIES = ("critical", "high", "medium", "low")

FAMILIES = (
    "context",
    "tokens",
    "memory",
    "cache",
    "sessions",
    "isolation",
    "state",
    "components",
)

# `skills-unused` is a sub-check of `components`, promoted to its own selector
# because it was asked for by name.
SUBCHECKS = {"skills-unused": "components"}

# Secret shapes. Each pattern is written so it cannot match its own source text,
# which is what keeps this module clean under `.claude/scripts/secret-scan.sh`.
SECRET_SHAPES = (
    ("aws-access-key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("anthropic-key", re.compile(r"sk-ant-[A-Za-z0-9_\-]{24,}")),
    ("openai-key", re.compile(r"sk-[A-Za-z0-9]{40,}")),
    ("github-token", re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}")),
    ("slack-token", re.compile(r"xox[abprs]-[A-Za-z0-9-]{10,}")),
    ("private-key-block", re.compile(r"BEGIN [A-Z ]*PRIVATE KEY")),
    ("bearer-literal", re.compile(r"[Aa]uthorization[\"'\s:]+Bearer\s+[A-Za-z0-9._\-]{20,}")),
    ("password-assignment", re.compile(r"(?i)(password|passwd|secret)\s*[:=]\s*[\"'][^\"']{8,}")),
)

CACHE_ROOTS = (
    # (relative path under the state dir, what it holds)
    ("jobs", "background job workspaces"),
    ("projects", "session transcripts"),
    ("plugins", "installed plugin payloads"),
    ("file-history", "pre-edit file snapshots"),
    ("paste-cache", "pasted content"),
    ("shell-snapshots", "captured shell environments"),
    ("telemetry", "local telemetry spool"),
    ("debug", "debug logs"),
    ("cache", "generic tool cache"),
    ("tasks", "task state"),
    ("backups", "settings backups"),
)

MEM_CACHE_ROOTS = (
    ("logs", "claude-mem logs"),
    ("chroma", "claude-mem embeddings"),
    ("backups", "claude-mem db backups"),
)


# --------------------------------------------------------------------------- #
# Finding record — one shape for every family.
# --------------------------------------------------------------------------- #

class Report:
    """Accumulates findings and per-channel evidence status."""

    def __init__(self) -> None:
        self.findings: list[dict] = []
        self.channels: dict[str, str] = {}

    def channel(self, family: str, status: str) -> None:
        """Record whether a family could look at all. `ok`, `skipped`, or
        `unavailable: <reason>` — a family that reports nothing and never says
        which of those applied is the silence ADR-0069 forbids."""
        self.channels[family] = status

    def add(
        self,
        severity: str,
        family: str,
        code: str,
        component: str,
        summary: str,
        evidence: str,
        remediation: str,
        *,
        scope: str = "host",
        impact: str = "",
        remediable_by: str = "issue",
    ) -> None:
        if severity not in SEVERITIES:
            raise ValueError(f"unknown severity: {severity}")
        self.findings.append(
            {
                "severity": severity,
                "family": family,
                "code": code,
                "component": component,
                "scope": scope,
                "summary": summary,
                "evidence": evidence,
                "impact": impact,
                "remediation": remediation,
                "remediable_by": remediable_by,
            }
        )

    def unavailable(self, family: str, code: str, component: str, reason: str) -> None:
        """An instrument that could not look is a finding, not a clean result.
        `no drift` from a blind channel is the failure that let 76 of 77 open
        issues go uncaptured (ADR-0069)."""
        self.channel(family, f"unavailable: {reason}")
        self.add(
            "medium",
            family,
            "evidence-unavailable",
            component,
            f"{family} could not be inspected",
            reason,
            "Restore the evidence channel, then re-run — a clean report from a blind "
            "channel is indistinguishable from a healthy one.",
            remediable_by="issue",
        )


# --------------------------------------------------------------------------- #
# Environment resolution
# --------------------------------------------------------------------------- #

class Env:
    def __init__(self) -> None:
        here = Path(__file__).resolve()
        default_root = here.parents[4]  # scripts/ -> leek/ -> skills/ -> .claude/ -> root
        self.root = Path(os.environ.get("LEEK_ROOT", str(default_root))).resolve()
        home = Path.home()
        self.claude_home = Path(
            os.environ.get("LEEK_CLAUDE_HOME", str(home / ".claude"))
        )
        self.mem_db = Path(
            os.environ.get("LEEK_MEM_DB", str(home / ".claude-mem" / "claude-mem.db"))
        )
        self.mem_home = self.mem_db.parent
        self.transcripts = Path(
            os.environ.get("LEEK_TRANSCRIPT_DIR", str(self.claude_home / "projects"))
        )
        # `times` and `user` are in the default layout deliberately. Cumulative CPU
        # against elapsed time is what separates an idle orphan holding memory from a
        # process spinning without progress — the two findings have opposite remediations
        # and the same age and RSS. `user` is the owner a report has to name.
        self.proc_cmd = os.environ.get(
            "LEEK_PROC_CMD", "ps -eo pid,ppid,etimes,rss,times,user,args"
        )
        self.now = int(time.time())
        # `tokens` and `components/skills-unused` both need one pass over every
        # transcript. Memoized so `--check all` pays for that pass once — twelve
        # thousand transcripts is twelve seconds, and an audit that doubles its
        # own cost is one of the things it exists to find.
        self._transcript_cache: dict[str, dict] = {}

    def transcript_stats(self, path: Path) -> dict:
        key = str(path)
        if key not in self._transcript_cache:
            self._transcript_cache[key] = scan_transcript(path)
        return self._transcript_cache[key]


def read_text(path: Path, cap: int = 4 * MB) -> str:
    """Read a file as text, bounded. Returns '' on any read failure — callers
    that need to distinguish absence from failure test the path first."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read(cap)
    except OSError:
        return ""


# Names git uses to point at a repository, index or object store without directory
# discovery (harness:RM-0317, .claude/scripts/lib/git-env.sh). A hook or `git rebase -x`
# exports GIT_DIR into every child process, so a plain `subprocess.run` here would silently
# inspect whatever repository the environment names instead of `cwd`.
_GIT_ENV_VARS = (
    "GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_PREFIX", "GIT_COMMON_DIR",
    "GIT_OBJECT_DIRECTORY", "GIT_NAMESPACE", "GIT_QUARANTINE_PATH",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
)


def run_ro(cmd: str, cwd: Path | None = None, timeout: int = 60) -> tuple[int, str]:
    """Run a read-only command. Every call site passes an inspection command;
    nothing here composes a command from scanned content."""
    env = {k: v for k, v in os.environ.items() if k not in _GIT_ENV_VARS}
    try:
        proc = subprocess.run(
            shlex.split(cmd),
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
        return proc.returncode, (proc.stdout or "") + (proc.stderr or "")
    except (OSError, subprocess.SubprocessError) as exc:
        return 127, f"{type(exc).__name__}: {exc}"


def dir_size(root: Path) -> tuple[int, int, int, bool]:
    """(bytes, file count, newest mtime, truncated). stat only — no reads."""
    total = 0
    count = 0
    newest = 0
    truncated = False
    for dirpath, _dirnames, filenames in os.walk(root, onerror=lambda _e: None):
        for name in filenames:
            if count >= WALK_FILE_CAP:
                truncated = True
                return total, count, newest, truncated
            try:
                st = os.stat(os.path.join(dirpath, name), follow_symlinks=False)
            except OSError:
                continue
            total += st.st_size
            count += 1
            if st.st_mtime > newest:
                newest = int(st.st_mtime)
    return total, count, newest, truncated


def human(n: int) -> str:
    for unit, size in (("GB", GB), ("MB", MB), ("KB", KB)):
        if n >= size:
            return f"{n / size:.1f} {unit}"
    return f"{n} B"


def strip_shell_noise(text: str) -> str:
    """Remove comments and quoted spans from shell source, line by line.

    Deliberately crude: it is not a parser, and it does not need to be. Every check that
    uses it asks "does this script *execute* X", and the two things that make that
    question answerable are dropping the `#` tail and blanking quoted text — the places
    where a dangerous word appears without being run.
    """
    out: list[str] = []
    for line in text.splitlines():
        quoted = re.sub(r"'[^']*'", "''", line)
        quoted = re.sub(r'"[^"]*"', '""', quoted)
        # A `#` inside what was a quoted span is already gone, so this tail-cut is safe.
        cut = quoted.find("#")
        out.append(quoted if cut < 0 else quoted[:cut])
    return "\n".join(out)


def est_tokens(text: str) -> int:
    """ECC's estimator: words x 1.3 for prose. Deliberately not a tokenizer —
    the number ranks findings, it does not bill anything."""
    return int(len(text.split()) * 1.3)


def frontmatter(text: str) -> dict[str, str]:
    """Flat top-level frontmatter keys. Nested blocks are ignored on purpose;
    every key this module reads is top-level and scalar."""
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end < 0:
        return {}
    out: dict[str, str] = {}
    for line in text[3:end].splitlines():
        if line.startswith((" ", "\t")) or ":" not in line:
            continue
        key, _, value = line.partition(":")
        out[key.strip()] = value.strip()
    return out


# --------------------------------------------------------------------------- #
# Family: context — what every session pays before it reads a word of the task
# --------------------------------------------------------------------------- #

def check_context(env: Env, rep: Report) -> None:
    rules_dir = env.root / ".claude" / "rules"
    if not rules_dir.is_dir():
        rep.unavailable("context", "rules-dir-missing", str(rules_dir),
                        f"{rules_dir} is not a directory")
        return
    rep.channel("context", "ok")

    always_on: list[tuple[Path, int]] = []
    for path in sorted(rules_dir.rglob("*.md")):
        text = read_text(path)
        head = "\n".join(text.splitlines()[:6])
        if re.search(r"^paths:", head, re.M):
            continue  # conditional — costs nothing until a path matches
        size = len(text.encode("utf-8"))
        always_on.append((path, size))
        if size > RULE_FILE_BYTES:
            rep.add(
                "medium", "context", "always-on-rule-oversized",
                str(path.relative_to(env.root)),
                "Always-on rule file exceeds the per-file budget",
                f"{human(size)} with no `paths:` frontmatter, so it loads every turn",
                "Give the file `paths:` frontmatter so it loads on demand, or split the "
                "always-needed half out and demote the rest.",
                impact=f"~{est_tokens(text)} tokens every turn",
            )

    total = sum(size for _p, size in always_on)
    if total > ALWAYS_ON_RULE_BYTES:
        worst = ", ".join(
            f"{p.relative_to(env.root)} ({human(s)})"
            for p, s in sorted(always_on, key=lambda t: -t[1])[:5]
        )
        rep.add(
            "medium", "context", "always-on-rule-budget",
            ".claude/rules/",
            "Always-on rule text exceeds the documented budget",
            f"{len(always_on)} files without `paths:`, {human(total)} total; heaviest: {worst}",
            "Demote the files that are not needed to choose the next action or to guard a "
            "destructive one — that is the always-on bar.",
            impact=f"~{total // 4} tokens every session",
        )

    for name in ("CLAUDE.md", "AGENTS.md"):
        path = env.root / name
        if not path.is_file():
            continue
        size = path.stat().st_size
        if size > CLAUDE_MD_BYTES:
            rep.add(
                "medium", "context", "instruction-file-oversized", name,
                "Project instruction file exceeds the per-file budget",
                f"{human(size)}, loaded on every turn of every session",
                "Move detail behind a pointer index; keep only what decides the next action.",
                impact=f"~{est_tokens(read_text(path))} tokens every turn",
            )

    agents_dir = env.root / ".claude" / "agents"
    for path in sorted(agents_dir.glob("*.md")) if agents_dir.is_dir() else []:
        text = read_text(path)
        desc = frontmatter(text).get("description", "")
        words = len(desc.split())
        if words > AGENT_DESC_WORDS:
            rep.add(
                "low", "context", "agent-description-bloated",
                str(path.relative_to(env.root)),
                "Agent description is loaded on every dispatch, however rarely the agent runs",
                f"description is {words} words (budget {AGENT_DESC_WORDS})",
                "Compress the description to its trigger vocabulary; the body carries the detail.",
                impact=f"~{est_tokens(desc)} tokens per dispatch context",
            )
        lines = text.count("\n") + 1
        if lines > AGENT_FILE_LINES:
            rep.add(
                "low", "context", "agent-body-heavy",
                str(path.relative_to(env.root)),
                "Agent body inflates every spawn of that agent",
                f"{lines} lines (budget {AGENT_FILE_LINES})",
                "Move reference material into the agent's skill; keep the definition to its role.",
                impact=f"~{est_tokens(text)} tokens per spawn",
            )

    skills_dir = env.root / ".claude" / "skills"
    seen: dict[str, list[str]] = {}
    for path in sorted(skills_dir.glob("*/SKILL.md")) if skills_dir.is_dir() else []:
        text = read_text(path)
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        seen.setdefault(digest, []).append(str(path.relative_to(env.root)))
        lines = text.count("\n") + 1
        if lines > SKILL_BODY_LINES:
            rep.add(
                "low", "context", "skill-body-heavy",
                str(path.relative_to(env.root)),
                "Skill body is large enough that invoking it costs real context",
                f"{lines} lines (budget {SKILL_BODY_LINES})",
                "Move detail into `references/` so progressive disclosure can work.",
                impact=f"~{est_tokens(text)} tokens per invocation",
            )
    for digest, paths in seen.items():
        if len(paths) > 1:
            rep.add(
                "medium", "context", "duplicate-skill-body", ", ".join(paths),
                "Two skills ship byte-identical bodies",
                f"sha256 {digest[:12]} shared by {len(paths)} files",
                "Keep one and route the other name to it, or delete the copy.",
            )

    servers, source = read_mcp_servers(env)
    if servers is None:
        rep.add(
            "low", "context", "mcp-config-unreadable", source,
            "MCP configuration could not be parsed, so its tool-schema cost is unknown",
            f"no parseable `mcpServers` in {source}",
            "Confirm the MCP config location; an unmeasured channel is not a cheap one.",
        )
    elif len(servers) > MCP_SERVER_MAX:
        rep.add(
            "medium", "context", "mcp-over-subscription", source,
            "More MCP servers are configured than the budget allows",
            f"{len(servers)} servers in {source}: {', '.join(sorted(servers))}",
            "Drop servers that wrap a CLI already on PATH; each tool schema is paid every turn.",
            impact=f"~{len(servers) * 5 * MCP_TOOL_TOKENS} tokens at 5 tools/server",
        )


def read_mcp_servers(env: Env) -> tuple[dict | None, str]:
    for candidate in (
        env.root / ".mcp.json",
        env.claude_home / "settings.json",
        env.claude_home.parent / ".claude.json",
    ):
        if not candidate.is_file():
            continue
        try:
            data = json.loads(read_text(candidate))
        except (ValueError, TypeError):
            return None, str(candidate)
        servers = data.get("mcpServers")
        if isinstance(servers, dict):
            return servers, str(candidate)
    return None, "no MCP config found"


# --------------------------------------------------------------------------- #
# Family: tokens — avoidable burn, ranked in burn order
# --------------------------------------------------------------------------- #

def transcript_files(env: Env) -> list[Path]:
    if not env.transcripts.is_dir():
        return []
    return sorted(env.transcripts.rglob("*.jsonl"))


def check_tokens(env: Env, rep: Report) -> None:
    files = transcript_files(env)
    if not files:
        rep.unavailable(
            "tokens", "no-transcripts", str(env.transcripts),
            f"no *.jsonl transcripts under {env.transcripts}",
        )
        return
    rep.channel("tokens", f"ok: {len(files)} transcripts")

    for path in files:
        size = path.stat().st_size
        if size > TRANSCRIPT_BYTES:
            rep.add(
                "medium", "tokens", "transcript-oversized", path.name,
                "Session transcript is large enough that its history is a standing cost",
                f"{human(size)} at {path}",
                "Hand the session off (`/relay`) instead of growing it; a transcript this "
                "size means context was re-sent many times.",
                scope="session", impact=human(size) + " of replayed history",
            )
        stats = env.transcript_stats(path)
        if stats["truncated"]:
            rep.add(
                "low", "tokens", "transcript-read-truncated", path.name,
                "Transcript exceeded the read cap, so its burn numbers are a lower bound",
                f"read {human(TRANSCRIPT_READ_CAP)} of {human(size)}",
                "Treat the counts for this session as a floor, not a total.",
                scope="session",
            )
        for digest, count in stats["dup_results"].items():
            if count > DUP_TOOL_RESULT:
                rep.add(
                    "high", "tokens", "repeated-tool-output", path.name,
                    "The same tool output was returned into context repeatedly",
                    f"result sha256 {digest[:12]} appeared {count}x in one session "
                    f"({human(stats['dup_bytes'].get(digest, 0))} each)",
                    "Read once and keep the result; a re-read of unchanged content is pure burn. "
                    "Where a loop needs it, cache the value in the plan or a runtime file.",
                    scope="session",
                    impact=f"~{(count - 1) * stats['dup_bytes'].get(digest, 0) // 4} tokens wasted",
                )
        for digest, count in stats["retry_inputs"].items():
            if count > RETRY_LOOP:
                rep.add(
                    "high", "tokens", "retry-loop", path.name,
                    "One tool was invoked with identical input many times — a retry loop",
                    f"input sha256 {digest[:12]} invoked {count}x "
                    f"(tool: {stats['retry_tools'].get(digest, 'unknown')})",
                    "A deterministic failure repeated is burn with no progress. Replace the "
                    "retry with a check on the failing precondition.",
                    scope="session",
                )
        if stats["big_results"]:
            worst = max(stats["big_results"])
            rep.add(
                "medium", "tokens", "oversized-tool-result", path.name,
                "Tool results larger than the budget entered context whole",
                f"{len(stats['big_results'])} results over {human(BIG_RESULT_BYTES)}; "
                f"largest {human(worst)}",
                "Bound the tool's output at the call site — a range, a count, a head — rather "
                "than paying for content the task did not need.",
                scope="session", impact=f"~{sum(stats['big_results']) // 4} tokens",
            )


def scan_transcript(path: Path) -> dict:
    """One bounded pass over a JSONL transcript. Counts identical tool results,
    identical tool inputs, and oversized results."""
    out = {
        "dup_results": {},
        "dup_bytes": {},
        "retry_inputs": {},
        "retry_tools": {},
        "big_results": [],
        "skills": set(),
        "truncated": False,
        "lines": 0,
    }
    read = 0
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                read += len(line)
                if read > TRANSCRIPT_READ_CAP:
                    out["truncated"] = True
                    break
                out["lines"] += 1
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                collect_transcript_record(rec, out)
    except OSError:
        out["truncated"] = True
    return out


def collect_transcript_record(rec: dict, out: dict) -> None:
    message = rec.get("message")
    if not isinstance(message, dict):
        return
    content = message.get("content")
    if not isinstance(content, list):
        return
    for block in content:
        if not isinstance(block, dict):
            continue
        kind = block.get("type")
        if kind == "tool_use":
            name = str(block.get("name", "?"))
            payload = json.dumps(block.get("input", {}), sort_keys=True)
            digest = hashlib.sha256((name + payload).encode("utf-8")).hexdigest()
            out["retry_inputs"][digest] = out["retry_inputs"].get(digest, 0) + 1
            out["retry_tools"][digest] = name
            if name == "Skill":
                skill = block.get("input", {})
                if isinstance(skill, dict) and skill.get("skill"):
                    out["skills"].add(str(skill["skill"]).strip())
        elif kind == "tool_result":
            body = block.get("content")
            text = body if isinstance(body, str) else json.dumps(body, sort_keys=True)
            size = len(text.encode("utf-8"))
            if size >= BIG_RESULT_BYTES:
                out["big_results"].append(size)
            if size > 512:  # tiny results repeat harmlessly; ignore the noise
                digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
                out["dup_results"][digest] = out["dup_results"].get(digest, 0) + 1
                out["dup_bytes"][digest] = size


# --------------------------------------------------------------------------- #
# Family: memory — retention, scope, provenance, and what must never be stored
# --------------------------------------------------------------------------- #

def open_mem_db(env: Env):
    """Read-only handle. `mode=ro` is the invariant the matrix asserts: this
    module must be unable to write the memory service even if a future edit
    tried to."""
    import sqlite3

    uri = f"file:{env.mem_db}?mode=ro"
    return sqlite3.connect(uri, uri=True, timeout=5)


def check_memory(env: Env, rep: Report) -> None:
    if not env.mem_db.is_file():
        rep.unavailable("memory", "mem-db-missing", str(env.mem_db),
                        f"{env.mem_db} does not exist")
        check_file_tier_memory(env, rep)
        return
    try:
        con = open_mem_db(env)
        tables = {r[0] for r in con.execute(
            "select name from sqlite_master where type='table'")}
    except Exception as exc:  # sqlite3.Error, plus a missing module
        rep.unavailable("memory", "mem-db-unreadable", str(env.mem_db),
                        f"{type(exc).__name__}: {exc}")
        check_file_tier_memory(env, rep)
        return

    rep.channel("memory", "ok")
    if "observations" not in tables:
        rep.add(
            "medium", "memory", "mem-schema-unknown", str(env.mem_db),
            "Memory database has no `observations` table, so scope cannot be checked",
            f"tables present: {', '.join(sorted(tables)) or 'none'}",
            "Confirm the memory service version; a schema this scanner cannot read is an "
            "unaudited store, not an empty one.",
        )
        con.close()
        check_file_tier_memory(env, rep)
        return

    cols = {r[1] for r in con.execute("pragma table_info(observations)")}
    total = con.execute("select count(*) from observations").fetchone()[0]

    if "project" in cols:
        rows = list(con.execute(
            "select coalesce(nullif(trim(project),''),'<unscoped>') p, count(*) "
            "from observations group by p order by 2 desc"))
        spread = ", ".join(f"{p}={c}" for p, c in rows[:8])
        unscoped = next((c for p, c in rows if p == "<unscoped>"), 0)
        if unscoped:
            rep.add(
                "high", "memory", "memory-unscoped", "claude-mem/observations",
                "Memory records carry no project, so any project can retrieve them",
                f"{unscoped} of {total} records have an empty `project`",
                "Scope or expire the unscoped records — an unscoped memory is a cross-project "
                "channel by default, not by configuration.",
                scope="host", impact=f"{unscoped} records retrievable from every project",
            )
        if len(rows) > 1:
            rep.add(
                "low", "memory", "memory-project-spread", "claude-mem/observations",
                "One memory store holds records for several projects",
                f"{len(rows)} distinct projects: {spread}",
                "Confirm retrieval is filtered by project at query time; co-location is only "
                "safe if every read is scoped.",
            )

    if "merged_into_project" in cols:
        merged = con.execute(
            "select count(*) from observations where merged_into_project is not null "
            "and trim(coalesce(merged_into_project,'')) <> ''").fetchone()[0]
        if merged:
            rep.add(
                "high", "memory", "memory-relabelled-across-projects",
                "claude-mem/observations",
                "Records were relabelled into another project after creation",
                f"{merged} records carry a non-empty `merged_into_project`",
                "Verify each relabel was intended. A record that moved project silently is "
                "one project's context answering another project's query.",
            )

    if "content_hash" in cols:
        dups = list(con.execute(
            "select content_hash, count(*) c from observations "
            "where content_hash is not null and trim(content_hash) <> '' "
            "group by content_hash having c >= ? order by c desc limit 10",
            (MEM_DUP_MIN + 1,)))
        if dups:
            extra = sum(c - 1 for _h, c in dups)
            rep.add(
                "low", "memory", "memory-duplicates", "claude-mem/observations",
                "Duplicate memory records are accumulating",
                f"{len(dups)} content hashes repeat; worst {dups[0][1]}x "
                f"({dups[0][0][:12]}); {extra}+ redundant records",
                "Deduplicate on `content_hash` at write time; a duplicated memory is recalled "
                "twice and costs context twice.",
            )

    if "created_at_epoch" in cols:
        cutoff = env.now - MEM_RETENTION_DAYS * DAY
        old = con.execute(
            "select count(*) from observations where created_at_epoch is not null "
            "and created_at_epoch < ?", (cutoff,)).fetchone()[0]
        if old:
            rep.add(
                "medium", "memory", "memory-past-retention", "claude-mem/observations",
                "Records are older than the retention window with no expiry applied",
                f"{old} of {total} records predate {MEM_RETENTION_DAYS} days",
                "Define and apply a retention policy. A memory with no expiry keeps asserting "
                "what was true when it was written.",
                impact=f"{old} records recalled indefinitely",
            )
        undated = con.execute(
            "select count(*) from observations where created_at_epoch is null").fetchone()[0]
        if undated:
            rep.add(
                "medium", "memory", "memory-provenance-gap", "claude-mem/observations",
                "Records have no creation date, so retention cannot be applied to them",
                f"{undated} records with a null `created_at_epoch`",
                "Backfill or expire them; a record with no date has no retention story and no "
                "reason for continued retention.",
            )

    scan_memory_secrets(con, cols, rep)
    con.close()
    check_file_tier_memory(env, rep)


def scan_memory_secrets(con, cols: set[str], rep: Report) -> None:
    """Report the record id, project and match class only. A finding that quotes
    the matched text has copied the secret into a report and an issue."""
    text_cols = [c for c in ("text", "facts", "narrative", "title", "subtitle") if c in cols]
    if not text_cols:
        return
    select = ", ".join(["id"] + (["project"] if "project" in cols else ["''"]) + text_cols)
    hits: dict[str, list[str]] = {}
    for row in con.execute(f"select {select} from observations"):
        rid, project = row[0], row[1]
        blob = "\n".join(str(v) for v in row[2:] if v)
        for label, pattern in SECRET_SHAPES:
            if pattern.search(blob):
                hits.setdefault(label, []).append(f"id={rid} project={project or '<unscoped>'}")
    for label, records in hits.items():
        rep.add(
            "critical", "memory", "memory-holds-secret-shape",
            "claude-mem/observations",
            f"Memory records match a credential shape ({label})",
            f"{len(records)} record(s): {', '.join(records[:5])}"
            + (" …" if len(records) > 5 else "")
            + " — matched text deliberately not quoted",
            "Expire these records and rotate anything they may hold. Credential material must "
            "never reach a recall layer; add a write-time filter so the next one cannot.",
            impact=f"{len(records)} records retrievable by any session",
            remediable_by="gate",
        )


def check_file_tier_memory(env: Env, rep: Report) -> None:
    """The committed file tier: one fact per file, indexed by MEMORY.md. An
    un-indexed memory file is never recalled; an index row with no file is a
    pointer to nothing."""
    base = env.claude_home / "projects"
    if not base.is_dir():
        return
    for mem_dir in sorted(base.glob("*/memory")):
        index = mem_dir / "MEMORY.md"
        files = {p.name for p in mem_dir.glob("*.md") if p.name != "MEMORY.md"}
        if not index.is_file():
            if files:
                rep.add(
                    "medium", "memory", "memory-index-missing", str(mem_dir),
                    "Memory files exist with no index, so none of them is loaded at session start",
                    f"{len(files)} memory files, no MEMORY.md",
                    "Write the index; the file tier is only recalled through it.",
                    scope="project",
                )
            continue
        text = read_text(index)
        linked = set(re.findall(r"\(([^)]+\.md)\)", text))
        orphans = sorted(f for f in files if f not in linked)
        dangling = sorted(l for l in linked if l not in files and "/" not in l)
        if orphans:
            rep.add(
                "low", "memory", "memory-file-unindexed", str(mem_dir),
                "Memory files are not referenced by the index that loads them",
                f"{len(orphans)} unindexed: {', '.join(orphans[:6])}",
                "Add a one-line pointer per file to MEMORY.md, or delete the file — an "
                "unindexed memory costs disk and recalls nothing.",
                scope="project",
            )
        if dangling:
            rep.add(
                "medium", "memory", "memory-index-dangling", str(index),
                "Index rows point at memory files that no longer exist",
                f"{len(dangling)} dangling: {', '.join(dangling[:6])}",
                "Resolve each row against disk; a dangling pointer is read as a fact that "
                "exists somewhere.",
                scope="project",
            )


# --------------------------------------------------------------------------- #
# Family: cache — buildup and staleness
# --------------------------------------------------------------------------- #

def check_cache(env: Env, rep: Report) -> None:
    roots: list[tuple[Path, str]] = []
    if env.claude_home.is_dir():
        roots += [(env.claude_home / rel, what) for rel, what in CACHE_ROOTS]
    if env.mem_home.is_dir():
        roots += [(env.mem_home / rel, what) for rel, what in MEM_CACHE_ROOTS]
    present = [(p, w) for p, w in roots if p.is_dir()]
    if not present:
        rep.unavailable(
            "cache", "no-cache-roots", str(env.claude_home),
            f"none of the known cache roots exist under {env.claude_home} or {env.mem_home}",
        )
        return
    rep.channel("cache", f"ok: {len(present)} roots")

    for path, what in present:
        size, count, newest, truncated = dir_size(path)
        rel = str(path)
        if truncated:
            rep.add(
                "low", "cache", "cache-walk-truncated", rel,
                "Cache root exceeded the walk cap, so its size is a lower bound",
                f"stopped after {WALK_FILE_CAP} files",
                "Treat the size as a floor. A cache with this many files is itself the finding.",
            )
        if size >= CACHE_BYTES_HIGH:
            severity = "high"
        elif size >= CACHE_BYTES_MED:
            severity = "medium"
        else:
            severity = ""
        if severity:
            rep.add(
                severity, "cache", "cache-oversized", rel,
                f"Cache root holding {what} is oversized",
                f"{human(size)} across {count} files",
                "Confirm a retention policy exists for this root, then clear the expired "
                "portion in a separate, deliberate act — never as part of an audit.",
                impact=human(size) + " on disk",
            )
        age_days = (env.now - newest) // DAY if newest else None
        if age_days is not None and age_days > CACHE_STALE_DAYS and size > 0:
            rep.add(
                "medium", "cache", "cache-stale", rel,
                f"Cache root holding {what} has had no write in a month",
                f"newest entry {age_days} days old, {human(size)} retained",
                "A cache nothing has written in a month is not warm. Confirm whether anything "
                "still reads it before it is trusted as current.",
                impact=human(size) + " of possibly outdated state",
            )


# --------------------------------------------------------------------------- #
# Family: sessions — liveness, orphans, runaways
# --------------------------------------------------------------------------- #

def check_sessions(env: Env, rep: Report) -> None:
    rep.channel("sessions", "ok")
    fleet = env.root / ".claude" / "scripts" / "fleet-health.sh"
    if fleet.is_file():
        rc, out = run_ro(f"bash {fleet}")
        # Liveness is never read from the subject (ADR-0072) — that script's
        # signal is the daemon's control socket, which a dead daemon cannot fake.
        if rc == 2:
            rep.add(
                "critical", "sessions", "session-daemon-down", "fleet-health.sh",
                "Sessions are registered but no live control socket exists",
                out.strip()[:600] or "fleet-health.sh exit 2",
                "Every registered session is dead regardless of the state it reports. Confirm "
                "before believing any per-session status.",
            )
        elif rc == 3:
            rep.add(
                "medium", "sessions", "evidence-unavailable", "fleet-health.sh",
                "Session registry could not be read",
                out.strip()[:600] or "fleet-health.sh exit 3",
                "Restore the registry channel; refusing to report healthy on no evidence is "
                "correct, and leaves this unanswered until it is fixed.",
            )
    else:
        rep.add(
            "low", "sessions", "fleet-health-missing", str(fleet),
            "Daemon liveness could not be checked from its own signal",
            f"{fleet} not found",
            "Restore the liveness script rather than deriving liveness from session state — "
            "a subject's report of its own liveness is worthless once it is gone.",
        )

    procs = read_procs(env)
    if procs is None:
        rep.add(
            "medium", "sessions", "evidence-unavailable", env.proc_cmd,
            "Process table could not be read, so orphans and runaways are unknown",
            f"`{env.proc_cmd}` produced nothing parseable",
            "Restore the process channel; no orphan findings from a blind channel is not a "
            "clean host.",
        )
        return

    by_pid = {p["pid"]: p for p in procs}
    claude_pids = {p["pid"] for p in procs if is_claude_proc(p["args"])}

    orphans = []
    for proc in procs:
        if not is_mcp_proc(proc["args"]):
            continue
        if proc["etimes"] < ORPHAN_MIN_ETIMES:
            continue
        if has_claude_ancestor(proc, by_pid, claude_pids):
            continue
        orphans.append(proc)

    if orphans:
        rss = sum(p["rss"] for p in orphans)
        listing = "; ".join(
            f"pid={p['pid']} ppid={p['ppid']} {owner_of(env, p)} "
            f"age={p['etimes'] // 60}m cpu={p['cputime']}s "
            f"rss={human(p['rss'] * KB)} args={p['args'][:70]}"
            for p in orphans[:8]
        )
        rep.add(
            "high", "sessions", "orphaned-mcp-server", "MCP servers",
            "MCP servers are running with no live session anywhere in their ancestry",
            f"{len(orphans)} processes, {human(rss * KB)} resident: {listing}"
            + (" …" if len(orphans) > 8 else ""),
            "Terminate each by PID after confirming it with `pgrep -a -x <name>`, one at a time "
            "— never by command-line pattern, which matches the harness's own wrapper shells "
            "including the one running the probe (harness:RM-0603). Where a pattern is "
            "unavoidable, filter your own shell: "
            "`pgrep -af <pattern> | awk -v me=$$ -v up=$PPID '$1 != me && $1 != up'`. Do that "
            "as a separate, deliberate act; this audit does not do it.",
            impact=f"{human(rss * KB)} resident memory held by dead sessions",
        )

    # Two different failures wear the same age and RSS, and their remediations are
    # opposite. Cumulative CPU against elapsed time is what separates them: a process
    # burning CPU for hours is looping; one burning almost none is holding memory and
    # waiting for a session that is gone.
    for proc in procs:
        if proc["etimes"] < RUNAWAY_MIN_ETIMES:
            continue
        if not (is_claude_proc(proc["args"]) or is_mcp_proc(proc["args"])):
            continue
        ratio = proc["cputime"] / proc["etimes"] if proc["cputime"] >= 0 else -1.0
        if ratio >= RUNAWAY_CPU_RATIO:
            rep.add(
                "high", "sessions", "runaway-process", f"pid {proc['pid']}",
                "A harness process has spent hours burning CPU — looping, polling or retrying",
                f"pid={proc['pid']} ppid={proc['ppid']} {owner_of(env, proc)} "
                f"age={proc['etimes'] // 3600}h cpu={proc['cputime']}s "
                f"({ratio * 100:.0f}% of elapsed) rss={human(proc['rss'] * KB)} "
                f"args={proc['args'][:120]}",
                "A process at this CPU fraction is not waiting on anything. Find what it is "
                "retrying before acting, then terminate it by PID — never by pattern. This "
                "audit does not do it.",
                scope="session",
                impact=f"{proc['cputime']}s CPU with no recorded progress",
            )
        elif proc["rss"] >= RUNAWAY_MIN_RSS_KB:
            rep.add(
                "medium", "sessions", "idle-process-holding-memory", f"pid {proc['pid']}",
                "A harness process has held a large resident set for hours while near-idle",
                f"pid={proc['pid']} ppid={proc['ppid']} {owner_of(env, proc)} "
                f"age={proc['etimes'] // 3600}h cpu={proc['cputime']}s "
                f"({'unknown' if ratio < 0 else f'{ratio * 100:.1f}%'} of elapsed) "
                f"rss={human(proc['rss'] * KB)} args={proc['args'][:120]}",
                "Confirm which session owns it before acting — near-zero CPU is also what a "
                "healthy server between requests looks like. Cross-check against the "
                "orphaned-MCP finding above.",
                scope="session", impact=human(proc["rss"] * KB) + " resident while idle",
            )


PROC_COLUMNS = {
    "PID": "pid",
    "PPID": "ppid",
    "ETIMES": "etimes",
    "ELAPSED": "etimes",
    "RSS": "rss",
    "TIME": "cputime",
    "TIMES": "cputime",
    "USER": "user",
    "UID": "user",
    "ARGS": "args",
    "COMMAND": "args",
    "CMD": "args",
}


def read_procs(env: Env) -> list[dict] | None:
    """Parse the injected process listing, taking the layout from its HEADER row.

    The layout is read from the data, not from the command string. An earlier version
    sniffed `"user" in env.proc_cmd`, which is true for the default `ps -eo …` format and
    false for every injected override — so the matrix's own fixture parsed one column
    short, `cputime` came back unknown, and the runaway case could not fire. `ps` prints a
    header; so must any override. A listing with no recognizable header is refused rather
    than guessed at, because a wrong column mapping produces plausible numbers.
    """
    rc, out = run_ro(env.proc_cmd)
    if rc not in (0, 1) or not out.strip():
        return None
    lines = out.splitlines()
    header = [PROC_COLUMNS.get(tok.upper()) for tok in lines[0].split()]
    if "pid" not in header or "args" not in header or header.index("args") != len(header) - 1:
        return None
    fixed = len(header) - 1
    procs: list[dict] = []
    for line in lines[1:]:
        parts = line.split(None, fixed)
        if len(parts) < fixed + 1:
            continue
        rec: dict = {"cputime": -1, "user": "unknown", "etimes": 0, "rss": 0, "ppid": 0}
        try:
            for name, value in zip(header, parts):
                if name in ("pid", "ppid", "etimes", "rss"):
                    rec[name] = int(value)
                elif name == "cputime":
                    rec[name] = parse_cputime(value)
                elif name == "user":
                    rec[name] = value
        except ValueError:
            continue
        if "pid" not in rec:
            continue
        rec["args"] = parts[fixed]
        procs.append(rec)
    return procs or None


def parse_cputime(token: str) -> int:
    """`ps times` prints plain seconds; `ps time` prints [[DD-]HH:]MM:SS. Accept both,
    and return -1 for anything unparseable rather than a plausible zero — a zero here
    reads as 'idle', which is a finding."""
    token = token.strip()
    if token.isdigit():
        return int(token)
    days = 0
    if "-" in token:
        head, _, token = token.partition("-")
        if not head.isdigit():
            return -1
        days = int(head)
    bits = token.split(":")
    if not all(b.isdigit() for b in bits) or not 1 <= len(bits) <= 3:
        return -1
    while len(bits) < 3:
        bits.insert(0, "0")
    h, m, s = (int(b) for b in bits)
    return days * 86400 + h * 3600 + m * 60 + s


def owner_of(env: Env, proc: dict) -> str:
    """Owner plus the project the process is most likely serving. The project is a guess
    from the command line and says so — a wrong guess in a report costs a reader one
    check, while omitting it costs them the whole search."""
    # Only a path segment that actually names a project counts. The first version matched
    # `/home/<user>/.claude/…` and reported the home directory's name as the project for
    # every process on the host — a guess that is always present and never right is worse
    # than `unknown`, because a reader believes it.
    args = proc["args"]
    project = "unknown"
    for pattern in (
        rf"{re.escape(str(env.root))}/projects/([A-Za-z0-9_.-]+)",
        r"/projects/([A-Za-z0-9_.-]+)/",
        rf"^{re.escape(str(env.root))}$|({re.escape(env.root.name)})/\.claude/",
    ):
        m = re.search(pattern, args)
        if m and m.lastindex:
            project = m.group(m.lastindex)
            break
    return f"user={proc['user']} project={project}"


def is_mcp_proc(args: str) -> bool:
    low = args.lower()
    return ("mcp" in low or "chroma" in low) and "leek" not in low


def is_claude_proc(args: str) -> bool:
    low = args.lower()
    return "claude" in low and "mcp" not in low and "chroma" not in low


def has_claude_ancestor(proc: dict, by_pid: dict[int, dict], claude_pids: set[int]) -> bool:
    """Walk the parent chain. `ppid == 1` finds ZERO orphans on a systemd-user
    host, because user services are reparented to the user manager rather than
    to init — so the predicate is 'no live session anywhere above me', not
    'my parent is gone' (harness:RM-0184)."""
    seen: set[int] = set()
    cur = proc
    for _hop in range(64):
        parent = cur["ppid"]
        if parent in claude_pids:
            return True
        if parent in seen or parent <= 1 or parent not in by_pid:
            return False
        seen.add(parent)
        cur = by_pid[parent]
    return False


# --------------------------------------------------------------------------- #
# Family: isolation — what one session or project can reach in another
# --------------------------------------------------------------------------- #

# A rule is broad only when its argument is a bare wildcard or absent: `Bash`,
# `Bash()`, `Bash(*)`, `Bash(:*)`. A prefix rule like `Bash(git status:*)` is the
# NARROW form and must not be flagged — the first version of this pattern matched
# the trailing `:*)` of every prefix rule and reported all 45 of them.
BROAD_PERMISSION = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:\(\s*(?:\*|:\s*\*)?\s*\))?$")

MUTATING_TOOLS = frozenset(
    {"Bash", "Write", "Edit", "MultiEdit", "NotebookEdit", "WebFetch", "Agent", "Task"}
)


def check_isolation(env: Env, rep: Report) -> None:
    rep.channel("isolation", "ok")

    for name in ("settings.json", "settings.local.json"):
        path = env.root / ".claude" / name
        if not path.is_file():
            continue
        try:
            data = json.loads(read_text(path))
        except ValueError:
            rep.add(
                "medium", "isolation", "settings-unparseable", str(path.relative_to(env.root)),
                "Settings file is not valid JSON, so its permissions are unknown",
                f"{path} failed to parse",
                "Fix the file; an unparseable permission set is not an empty one.",
            )
            continue
        allow = (data.get("permissions") or {}).get("allow") or []
        broad = [r for r in allow if isinstance(r, str) and BROAD_PERMISSION.search(r)]
        # Breadth is not the only axis — a bare `Read` grants every read, which is
        # the documented default posture; a bare `Bash` grants arbitrary execution
        # to every session in the workspace. Same shape, different consequence, so
        # they are not the same finding.
        mutating = [r for r in broad if r.split("(")[0] in MUTATING_TOOLS]
        reading = [r for r in broad if r not in mutating]
        if mutating:
            rep.add(
                "high", "isolation", "permission-too-broad", str(path.relative_to(env.root)),
                "A permission rule grants a whole write-or-execute tool class workspace-wide",
                f"{len(mutating)} rule(s): {', '.join(mutating[:6])}",
                "Narrow each rule to the command or path it was added for; a workspace-wide "
                "grant is inherited by every session including ones nobody is watching.",
            )
        if reading:
            rep.add(
                "low", "isolation", "permission-broad-readonly",
                str(path.relative_to(env.root)),
                "A permission rule grants a whole read-only tool class workspace-wide",
                f"{len(reading)} rule(s): {', '.join(reading[:6])}",
                "Usually intended. Confirm it is, and that no path exclusion was meant to "
                "narrow it — a read grant still crosses project boundaries on this host.",
            )

    # Odin's own file-tier memories naming another project. A memory that names a
    # second project's slug is available to whichever project loads the file.
    base = env.claude_home / "projects"
    slugs = {p.name for p in base.glob("*") if p.is_dir()} if base.is_dir() else set()
    project_names = {
        p.name.lower() for p in (env.root / "projects").glob("*") if p.is_dir()
    } if (env.root / "projects").is_dir() else set()
    for mem_dir in sorted(base.glob("*/memory")) if base.is_dir() else []:
        owner = mem_dir.parent.name.lower()
        for path in sorted(mem_dir.glob("*.md")):
            text = read_text(path).lower()
            foreign = sorted(n for n in project_names if n and n not in owner and n in text)
            if len(foreign) >= 2:
                rep.add(
                    "medium", "isolation", "memory-names-other-projects", str(path),
                    "A memory file scoped to one project names several others",
                    f"owner={mem_dir.parent.name}; also names: {', '.join(foreign[:6])}",
                    "Split the record so each project's fact lives in that project's scope. A "
                    "shared file is loaded whole by whichever session loads it.",
                    scope="project",
                )
    if len(slugs) > 1:
        rep.channel("isolation", f"ok: {len(slugs)} project scopes on disk")

    # Secret-shaped strings in caches every session can read.
    shared = [
        env.claude_home / "history.jsonl",
        env.claude_home / "stats-cache.json",
        env.claude_home / "gh-pr-status-cache.json",
    ]
    for path in shared:
        if not path.is_file():
            continue
        blob = read_text(path, cap=2 * MB)
        classes = sorted({label for label, pat in SECRET_SHAPES if pat.search(blob)})
        if classes:
            rep.add(
                "critical", "isolation", "shared-cache-holds-secret-shape", str(path),
                "A cache readable by every session matches a credential shape",
                f"match classes: {', '.join(classes)} (first {human(2 * MB)} scanned; "
                "matched text deliberately not quoted)",
                "Rotate anything that may be exposed and stop the write path that put it there. "
                "This file is not scoped to a project or a session.",
                remediable_by="gate",
            )


# --------------------------------------------------------------------------- #
# Family: state — stale working state that misleads the next session
# --------------------------------------------------------------------------- #

def check_state(env: Env, rep: Report) -> None:
    rep.channel("state", "ok")

    plans = env.root / ".claude" / "docs" / "plans"
    stale = []
    for path in sorted(plans.glob("*.md")) if plans.is_dir() else []:
        age = (env.now - int(path.stat().st_mtime)) // DAY
        if age > PLAN_STALE_DAYS:
            stale.append((path, age))
    if stale:
        listing = ", ".join(
            f"{p.relative_to(env.root)} ({a}d)" for p, a in sorted(stale, key=lambda t: -t[1])[:8]
        )
        rep.add(
            "medium", "state", "spent-plan-retained", ".claude/docs/plans/",
            "Plan documents are older than the staleness window and may be spent",
            f"{len(stale)} plans untouched for over {PLAN_STALE_DAYS} days: {listing}",
            "For each, confirm the work landed and is recorded in CHANGELOG.md, then delete the "
            "plan in that change. A spent plan reads as active work to the next session.",
        )

    runtime = env.root / ".claude" / ".runtime"
    if runtime.is_dir():
        cutoff = env.now - RUNTIME_STALE_HOURS * 3600
        residue = [p for p in runtime.rglob("*") if p.is_file() and p.stat().st_mtime < cutoff]
        if residue:
            rep.add(
                "low", "state", "runtime-residue", ".claude/.runtime/",
                "Runtime state files outlived the session that wrote them",
                f"{len(residue)} files older than {RUNTIME_STALE_HOURS}h; "
                f"e.g. {', '.join(str(p.relative_to(env.root)) for p in residue[:5])}",
                "Confirm no live session owns them, then clear them separately from this audit.",
            )
        claims = runtime / "autonomous"
        ttl = env.now - CLAIM_TICKET_TTL_MIN * 60
        expired = [
            p for p in claims.glob("*") if p.is_file() and p.stat().st_mtime < ttl
        ] if claims.is_dir() else []
        if expired:
            rep.add(
                "medium", "state", "claim-ticket-expired", ".claude/.runtime/autonomous/",
                "Autonomous posture claim tickets are past their TTL",
                f"{len(expired)} ticket(s) older than {CLAIM_TICKET_TTL_MIN} minutes: "
                f"{', '.join(p.name for p in expired[:5])}",
                "An expired ticket means the session that armed the posture never claimed it, so "
                "gates silently reverted to warn. Re-arm per session rather than leaving residue.",
            )

    rc, out = run_ro("git worktree list --porcelain", cwd=env.root)
    # "not a git repository" is a SKIP, not a blind channel: a directory that is not a
    # repository has no worktrees and no uncommitted diff to miss. Collapsing the two would
    # make every non-repo root report a finding it can never resolve — and would make the
    # distinction the channel block exists to draw meaningless.
    not_a_repo = "not a git repository" in out.lower()
    if rc != 0 and not_a_repo:
        rep.channel("state", "ok: git checks skipped (root is not a git repository)")
    elif rc != 0:
        rep.add(
            "low", "state", "evidence-unavailable", "git worktree list",
            "Worktree state could not be read",
            out.strip()[:300],
            "Restore the git channel before trusting a clean worktree report.",
        )
    else:
        worktrees = [
            line.split(" ", 1)[1] for line in out.splitlines() if line.startswith("worktree ")
        ]
        idle = []
        for wt in worktrees[1:]:
            path = Path(wt)
            if not path.is_dir():
                idle.append((wt, "path missing"))
                continue
            age = (env.now - int(path.stat().st_mtime)) // DAY
            if age > 7:
                idle.append((wt, f"{age}d untouched"))
        if idle:
            rep.add(
                "medium", "state", "worktree-abandoned", "git worktrees",
                "Worktrees exist that nothing has touched in a week",
                f"{len(idle)} of {max(len(worktrees) - 1, 0)}: "
                + "; ".join(f"{w} ({why})" for w, why in idle[:6]),
                "Reconcile each against git log before reclaiming it — a worktree may hold an "
                "unmerged branch, and a resumed one may hold a bad conflict resolution.",
            )

    rc, out = run_ro("git status --porcelain", cwd=env.root)
    if rc == 0 and out.strip() and not not_a_repo:
        lines = [l for l in out.splitlines() if l.strip()]
        untracked = [l for l in lines if l.startswith("??")]
        if len(lines) > 20:
            rep.add(
                "low", "state", "working-tree-dirty", str(env.root),
                "The working tree carries many uncommitted changes",
                f"{len(lines)} changed paths, {len(untracked)} untracked",
                "Commit or discard deliberately. A large uncommitted diff reads to the next "
                "session as work in progress it must not disturb.",
            )


# --------------------------------------------------------------------------- #
# Family: components — agents, hooks, MCP, skills, project config
# --------------------------------------------------------------------------- #

def check_components(env: Env, rep: Report, only_unused: bool = False) -> None:
    rep.channel("components", "ok")
    if not only_unused:
        check_agents(env, rep)
        check_hooks(env, rep)
        check_mcp_permissions(env, rep)
        check_config_conflicts(env, rep)
    check_unused_skills(env, rep)


def check_agents(env: Env, rep: Report) -> None:
    agents_dir = env.root / ".claude" / "agents"
    if not agents_dir.is_dir():
        return
    names: dict[str, list[str]] = {}
    for path in sorted(agents_dir.glob("*.md")):
        fm = frontmatter(read_text(path))
        name = fm.get("name", path.stem)
        names.setdefault(name, []).append(path.name)
        tools = fm.get("tools", "")
        if tools.strip() in ("*", '"*"', "'*'"):
            rep.add(
                "low", "components", "agent-tools-unbounded", path.name,
                "Agent is granted every tool rather than the set its role needs",
                f"tools: {tools}",
                "Narrow the tool list to the role. A catch-all agent inherits every guard's "
                "surface without any of its role's constraints.",
            )
    for name, files in names.items():
        if len(files) > 1:
            rep.add(
                "high", "components", "agent-name-duplicated", ", ".join(files),
                "Two agent definitions claim the same name, so which one dispatches is undefined",
                f"name `{name}` declared in {len(files)} files: {', '.join(files)}",
                "Rename or delete one. A duplicate agent name is resolved by load order, which "
                "no caller can see.",
            )


def check_hooks(env: Env, rep: Report) -> None:
    settings = env.root / ".claude" / "settings.json"
    hooks_dir = env.root / ".claude" / "hooks"
    if not settings.is_file() or not hooks_dir.is_dir():
        return
    try:
        data = json.loads(read_text(settings))
    except ValueError:
        return
    registered: set[str] = set()
    for entries in (data.get("hooks") or {}).values():
        for entry in entries if isinstance(entries, list) else []:
            for hook in entry.get("hooks", []) if isinstance(entry, dict) else []:
                cmd = str(hook.get("command", ""))
                registered.update(re.findall(r"[\w./-]+\.(?:sh|mjs|js|py)", cmd))
    on_disk = {p.name for p in hooks_dir.glob("*.sh")}
    registered_names = {Path(r).name for r in registered}
    unregistered = sorted(on_disk - registered_names)
    if unregistered:
        rep.add(
            "low", "components", "hook-unregistered", ".claude/hooks/",
            "Hook scripts exist on disk that no settings entry runs",
            f"{len(unregistered)}: {', '.join(unregistered[:8])}",
            "Register the hook or delete it. A hook nothing runs is a guard that reads as "
            "present and enforces nothing.",
        )
    missing = sorted(
        n for n in registered_names
        if n.endswith(".sh") and not (hooks_dir / n).is_file()
        and not (env.root / ".claude" / "scripts" / n).is_file()
    )
    if missing:
        rep.add(
            "high", "components", "hook-command-missing", ".claude/settings.json",
            "A registered hook points at a script that does not exist",
            f"{len(missing)}: {', '.join(missing[:8])}",
            "Restore or unregister each. A hook whose command is absent fails on every event, "
            "and a failure a hook swallows is indistinguishable from a pass.",
        )

    check_hook_hygiene(env, rep, hooks_dir, registered_names)


def check_hook_hygiene(env: Env, rep: Report, hooks_dir: Path, registered: set[str]) -> None:
    """A hook's cost and its failure behaviour are properties of its source, not of its
    registration. These are static shapes, so each is reported as a shape to check rather
    than as a proven defect — a hook that legitimately silences one command reads the same
    as one that swallows every failure, and only the author can tell them apart."""
    for path in sorted(hooks_dir.glob("*.sh")):
        name = path.name
        live = name in registered
        text = read_text(path)
        code = strip_shell_noise(text)
        rel = str(path.relative_to(env.root))
        size = len(text.encode("utf-8"))

        if live and size > HOOK_MAX_BYTES:
            rep.add(
                "low", "components", "hook-oversized", rel,
                "A registered hook is large enough that its parse and run cost is paid often",
                f"{human(size)} on a hook that runs on every matching event",
                "Move the body into a script the hook calls, or narrow the matcher so it runs "
                "on fewer events.",
                impact="per-event latency on every matching tool call",
            )

        # Unbounded output: a hook that prints into the transcript with no cap turns one
        # noisy event into context spend on every future turn of the session.
        prints = len(re.findall(r"^\s*(echo|printf|cat)\b", text, re.M))
        if live and prints >= 8 and not HOOK_OUTPUT_BOUND.search(text):
            rep.add(
                "low", "components", "hook-output-unbounded", rel,
                "A registered hook writes many lines with no visible bound on any of them",
                f"{prints} print statements, no `head`/`tail`/`cut`/width-limited format found",
                "Cap what the hook emits. Hook output enters the transcript, so an unbounded "
                "line is paid on every later turn of that session, not once.",
            )

        # Subtract the standard stdin read before counting: `input="$(cat 2>/dev/null || true)"`
        # appears in nearly every hook here and is the correct idiom, not a swallow.
        swallowed = len(HOOK_SWALLOW.findall(HOOK_STDIN_IDIOM.sub("", code)))
        if live and swallowed >= HOOK_SWALLOW_MIN:
            rep.add(
                "low", "components", "hook-swallows-failure", rel,
                "A registered hook discards failures in many places",
                f"{swallowed} occurrences of `|| true`, `|| :` or a terminal `2>/dev/null`, "
                "excluding the standard stdin read",
                "A shape to check, not a proven defect: a guard whose failure is discarded "
                "passes identically to one that ran and approved. Where the silence is "
                "intended, say so at the line.",
            )

        if HOOK_UNSAFE.search(code):
            rep.add(
                "high", "components", "hook-unsafe-shell", rel,
                "A hook composes or executes shell from data",
                "an `eval` at a command position, or a download piped into a shell "
                "(comments and quoted spans excluded)",
                "Replace with an argument array or a read into a variable. A hook runs on the "
                "agent's own events, so anything it evaluates is reachable from tool input.",
                remediable_by="gate",
            )

        if HOOK_ENV_DUMP.search(code):
            rep.add(
                "high", "components", "hook-env-exposure", rel,
                "A hook prints the environment",
                "a bare `env`/`printenv`/`set` at the start of a line",
                "Print the named variables the hook needs. A full environment dump reaches the "
                "transcript and any log the hook's output lands in, credentials included.",
                remediable_by="gate",
            )

        if live and not re.search(r"^set -[a-z]*u", text, re.M):
            rep.add(
                "low", "components", "hook-no-nounset", rel,
                "A registered hook does not set `-u`, so an unset variable reads as empty",
                "no `set -u` (or `set -eu`/`set -uo pipefail`) found",
                "Add it. In a guard, an empty value is usually the permissive branch, which is "
                "the direction a hook must never fail in.",
            )


def check_mcp_permissions(env: Env, rep: Report) -> None:
    servers, source = read_mcp_servers(env)
    if not servers:
        return
    for name, spec in servers.items():
        if not isinstance(spec, dict):
            continue
        args = " ".join(str(a) for a in spec.get("args", []) if a is not None)
        env_block = spec.get("env") or {}
        broad = [tok for tok in ("/", str(Path.home())) if re.search(
            rf"(^|\s){re.escape(tok)}(\s|$)", args)]
        if broad:
            rep.add(
                "high", "components", "mcp-filesystem-too-broad", f"{source}:{name}",
                "An MCP server is given a filesystem root wide enough to cross projects",
                f"args: {args[:200]}",
                "Scope the server to the project directory it serves. A root-level or "
                "home-level mount makes every project's files reachable from every session.",
            )
        secret_keys = sorted(
            k for k in env_block
            if isinstance(k, str) and re.search(r"(?i)(key|token|secret|password)", k)
            and isinstance(env_block.get(k), str)
            and not str(env_block[k]).startswith("$")
        )
        if secret_keys:
            rep.add(
                "critical", "components", "mcp-credential-inline", f"{source}:{name}",
                "MCP server configuration holds credential material inline",
                f"literal (non-$-referenced) values for: {', '.join(secret_keys)}",
                "Reference an environment variable instead and rotate the exposed value. A "
                "credential in a config file is readable by every session that loads it.",
                remediable_by="gate",
            )
        if "timeout" not in spec and "timeoutMs" not in spec:
            rep.add(
                "low", "components", "mcp-no-timeout", f"{source}:{name}",
                "MCP server has no configured timeout",
                "no `timeout`/`timeoutMs` key",
                "Set a timeout. A stalled server without one holds the turn indefinitely.",
            )


def check_config_conflicts(env: Env, rep: Report) -> None:
    base = env.root / ".claude" / "settings.json"
    local = env.root / ".claude" / "settings.local.json"
    if not (base.is_file() and local.is_file()):
        return
    try:
        a = json.loads(read_text(base))
        b = json.loads(read_text(local))
    except ValueError:
        return
    conflicts = sorted(
        k for k in set(a) & set(b)
        if k not in ("permissions", "hooks") and a[k] != b[k]
    )
    if conflicts:
        rep.add(
            "medium", "components", "settings-conflict", ".claude/settings*.json",
            "The committed and local settings disagree on the same keys",
            f"{len(conflicts)} conflicting keys: {', '.join(conflicts[:8])}",
            "Resolve each, or move the local override to a key the committed file does not set. "
            "A silently-shadowed setting is read from the file nobody is looking at.",
        )
    for key in ("model", "env"):
        if key in b and key in a and a[key] != b[key]:
            rep.add(
                "medium", "components", "settings-override-inherited", str(local.name),
                f"A local `{key}` override shadows the committed value for every session here",
                f"committed={json.dumps(a[key])[:80]} local={json.dumps(b[key])[:80]}",
                "Confirm the override is intended workspace-wide; local settings are inherited "
                "by unattended sessions nobody is watching.",
            )


def check_unused_skills(env: Env, rep: Report) -> None:
    """Which skills have never been used? Answered from transcripts that already
    exist, so the answer is retroactive and costs nothing when not running. The
    window is reported, because transcript retention bounds it."""
    skills_dir = env.root / ".claude" / "skills"
    if not skills_dir.is_dir():
        return
    on_disk = {p.name for p in skills_dir.glob("*/") if (p / "SKILL.md").is_file()}
    if not on_disk:
        on_disk = {p.parent.name for p in skills_dir.glob("*/SKILL.md")}
    files = transcript_files(env)
    if not files:
        rep.add(
            "medium", "components", "evidence-unavailable", str(env.transcripts),
            "Skill usage could not be measured — no transcripts to read",
            f"no *.jsonl under {env.transcripts}",
            "Restore the transcript channel. Zero recorded invocations from an unreadable "
            "channel is not the same as an unused skill.",
        )
        return

    invoked: set[str] = set()
    oldest = env.now
    for path in files:
        stats = env.transcript_stats(path)
        invoked |= stats["skills"]
        try:
            oldest = min(oldest, int(path.stat().st_mtime))
        except OSError:
            pass
    window_days = max((env.now - oldest) // DAY, 0)
    never = sorted(on_disk - {s.split(":")[-1] for s in invoked})
    rep.channel(
        "components",
        f"ok: {len(files)} transcripts spanning {window_days}d, "
        f"{len(invoked)} distinct skills invoked",
    )
    if never:
        rep.add(
            "low", "components", "skill-never-invoked", ".claude/skills/",
            "Skills have no recorded invocation in the transcript window",
            f"{len(never)} of {len(on_disk)} skills, window {window_days}d across "
            f"{len(files)} transcripts: {', '.join(never[:20])}"
            + (" …" if len(never) > 20 else ""),
            "For each: confirm it is routed in the decision matrix, then either fix the route "
            "or retire the skill. Never-invoked plus unrouted is a deletion candidate; "
            "never-invoked but routed is a routing defect.",
            impact=f"{len(never)} skills carrying description cost with no recorded use",
        )

    for path in sorted(skills_dir.glob("*/SKILL.md")):
        size = path.stat().st_size
        if size < SKILL_STUB_BYTES:
            rep.add(
                "low", "components", "skill-is-stub", str(path.relative_to(env.root)),
                "A skill body is too small to carry a procedure",
                f"{size} B (below {SKILL_STUB_BYTES} B)",
                "Grow it into a real procedure or retire it. A stub that is routed sends the "
                "agent somewhere that answers nothing.",
            )


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #

CHECKS = {
    "context": check_context,
    "tokens": check_tokens,
    "memory": check_memory,
    "cache": check_cache,
    "sessions": check_sessions,
    "isolation": check_isolation,
    "state": check_state,
    "components": check_components,
}

SEVERITY_MEANING = {
    "critical": "immediate privacy, security or cost risk",
    "high": "significant wasted usage or unstable behaviour",
    "medium": "inefficient, stale or poorly scoped state",
    "low": "cleanup or optimization opportunity",
}


def render_text(rep: Report, families: list[str], env: Env) -> str:
    order = {s: i for i, s in enumerate(SEVERITIES)}
    findings = sorted(rep.findings, key=lambda f: (order[f["severity"]], f["family"], f["code"]))
    lines = [
        "Leek — leak and hygiene report",
        "=" * 62,
        f"root:        {env.root}",
        f"state dir:   {env.claude_home}",
        f"memory db:   {env.mem_db}",
        f"families:    {', '.join(families)}",
        "",
        "Evidence channels",
    ]
    for family in families:
        lines.append(f"  {family:<12} {rep.channels.get(family, 'not run')}")
    counts = {s: sum(1 for f in findings if f["severity"] == s) for s in SEVERITIES}
    lines += [
        "",
        "Findings by severity",
        "  " + "  ".join(f"{s}={counts[s]}" for s in SEVERITIES),
        "",
    ]
    if not findings:
        lines.append("No findings. Every channel above reported `ok`; a channel reading")
        lines.append("`unavailable` would have produced a finding, so this is a measured clean.")
        return "\n".join(lines) + "\n"

    for severity in SEVERITIES:
        group = [f for f in findings if f["severity"] == severity]
        if not group:
            continue
        lines.append(f"{severity.upper()} — {SEVERITY_MEANING[severity]}")
        lines.append("-" * 62)
        for f in group:
            lines.append(f"  [{f['family']}/{f['code']}] {f['summary']}")
            lines.append(f"    component:   {f['component']}  (scope: {f['scope']})")
            lines.append(f"    evidence:    {f['evidence']}")
            if f["impact"]:
                lines.append(f"    impact:      {f['impact']}")
            lines.append(f"    remediation: {f['remediation']}")
            lines.append(f"    file as:     {f['remediable_by']}")
            lines.append("")
    lines.append("Leek does not act on any of the above. Record them: one issue per distinct")
    lines.append("concern, a report doc for the pass, and `mistake-to-gate` where a finding has")
    lines.append("a repo-state predicate (ADR-0088).")
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #

def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="leek",
        description="Leak and hygiene scanner for a Claude Code environment. Read-only.",
    )
    parser.add_argument(
        "--check",
        default="all",
        help="comma-separated families, or `all` (default). "
             f"Families: {', '.join(FAMILIES)}. Sub-checks: {', '.join(SUBCHECKS)}",
    )
    parser.add_argument("--json", action="store_true", help="emit JSON instead of a text report")
    parser.add_argument(
        "--min-severity",
        choices=SEVERITIES,
        default="low",
        help="drop findings below this severity from the output (default: low)",
    )
    return parser.parse_args(argv)


def resolve_checks(spec: str) -> tuple[list[str], bool]:
    """Returns (families, components_only_unused)."""
    if spec.strip() == "all":
        return list(FAMILIES), False
    requested = [s.strip() for s in spec.split(",") if s.strip()]
    families: list[str] = []
    only_unused = False
    for name in requested:
        if name in FAMILIES:
            families.append(name)
        elif name in SUBCHECKS:
            parent = SUBCHECKS[name]
            if parent not in families:
                families.append(parent)
            only_unused = True
        else:
            raise SystemExit(
                f"leek: unknown check `{name}`. "
                f"Families: {', '.join(FAMILIES)}; sub-checks: {', '.join(SUBCHECKS)}"
            )
    # An explicit `components` alongside `skills-unused` means the full family.
    if "components" in requested:
        only_unused = False
    return families, only_unused


def main(argv: list[str]) -> int:
    try:
        args = parse_args(argv)
        families, only_unused = resolve_checks(args.check)
    except SystemExit as exc:
        if isinstance(exc.code, str):
            print(exc.code, file=sys.stderr)
            return 2
        return 2 if exc.code else 0

    env = Env()
    rep = Report()
    for family in families:
        fn = CHECKS[family]
        if family == "components":
            fn(env, rep, only_unused)
        else:
            fn(env, rep)

    floor = SEVERITIES.index(args.min_severity)
    rep.findings = [f for f in rep.findings if SEVERITIES.index(f["severity"]) <= floor]

    if args.json:
        print(json.dumps(
            {
                "root": str(env.root),
                "generated_at": env.now,
                "families": families,
                "channels": {f: rep.channels.get(f, "not run") for f in families},
                "counts": {s: sum(1 for x in rep.findings if x["severity"] == s)
                           for s in SEVERITIES},
                "findings": rep.findings,
            },
            indent=2,
            sort_keys=False,
        ))
    else:
        sys.stdout.write(render_text(rep, families, env))

    return 1 if rep.findings else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
