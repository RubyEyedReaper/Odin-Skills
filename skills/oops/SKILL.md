---
name: oops
description: Use when something happened that should not have — a bug just shipped, a wrong assumption, a missed validation, an unsafe or destructive action, a stale value used, an edge case nobody handled, or any preventable error. Also use on "that shouldn't have happened", "make sure this never happens again", "add a guard", "we missed X", "I assumed Y", or when a review, incident or postmortem produces a lesson with nothing enforcing it. Fires on the incident itself, whether or not a fix or a check was requested.
---

# OOPS

An incident is worth exactly one thing: the guard it buys. Fixing the symptom and moving on spends
the incident and gets nothing back.

**The deliverable is a check a machine runs — a test, an assertion, a lint or type rule, a hook, or
a CI gate.** Not a resolution, not a note, not a paragraph in a commit message. A rule nobody checks
is wrong by the second change.

## When this fires

- code did the wrong thing, or did something right for the wrong reason
- an assumption was held that was never verified — a file exists, a field is non-null, an API
  returns in order, a value is fresh
- validation was missing at a boundary
- an unsafe, destructive or irreversible action ran, or nearly ran
- a review, audit or postmortem produced a "we should always…" with nothing behind it
- a guard was found to pass when it should have failed

**Not for a bug you have not diagnosed yet.** A failing test is a symptom; run
`systematic-debugging` / `diagnosing-bugs` first. OOPS starts once the cause is known — you cannot
guard a mechanism you have not identified.

## The procedure

### 1. Name the incident — 1–3 sentences, with its artifact

State what happened, and paste the exact thing that shows it: the input, the stack trace, the diff,
the path, the value. Then name the **failure mode** in the vocabulary of the check that will catch
it — "no input validation", "missing null check", "assumed the file exists", "used a stale read",
"unbounded retry", "no test for the empty case".

"Links were wrong" is not an incident. "`getUser(id)` returned `undefined` for a deleted user and
the caller dereferenced `.email`" is. The artifact matters because it becomes the first test case: a
guard built from a remembered *category* checks the category you imagined rather than the one that
happened.

### 2. Root cause — the condition, not the symptom

Ask **what condition allowed this**, then ask it again of the answer. Stop when you reach something
you can express as a predicate.

| Symptom | Condition that allowed it |
|---|---|
| Crash on `.email` of undefined | Return type says `User`, actually `User \| undefined`; no check at the boundary |
| Wrong total in a report | Two code paths compute it; one was updated |
| Flaky integration test | No retry, and the fixture assumes ordering the API does not promise |
| Destructive command ran | The command's target was inferred from ambient state, never named |

The test of a real root cause: **you can state the guard from it in one sentence.** If you cannot,
you are still on the symptom.

### 3. Classify the guard — where does it live?

This is the fork that decides everything after it.

| The condition is… | Guard class | Where it lives | Hand off to |
|---|---|---|---|
| A predicate over **repository state** — a reference resolves, a count matches, a generated file matches its source, a convention holds | **CI gate** | a checker script + the repo's single gate list | **`mistake-to-gate`** — it owns this branch end to end; do not rebuild it here |
| Untrusted data entering the system | **Input guard** | the boundary function — parser, route handler, CLI arg, config load | `test-driven-development` |
| Required state assumed to exist | **Precondition** | top of the function that assumed it | `test-driven-development` |
| A result used without being checked | **Postcondition** | between producing and returning/using | `test-driven-development` |
| A failure path nobody exercised | **Error-path guard** | the call site — bounded retry, fallback, explicit surfaced error | `error-handling-patterns` |
| Judgment: a naming, a design, a "this is confusing" | **Not mechanically checkable** | say so out loud, then `rules-distill` | `rules-distill` |

**The last row is an escape hatch that must be spoken, never taken silently.** A guard that encodes
taste produces false positives; a guard people disagree with gets disabled, taking its true
positives with it. Saying "this one is judgment, here is the rule instead" is a valid OOPS outcome.
Quietly writing no guard is not.

### 4. Specify the guard: where, what, how it fails

Every guard is stated as three things before it is written:

- **Where** — file, function, or pipeline step. Precisely.
- **What** — the exact predicate. `items.length > 0`, not "check the input is okay".
- **How it fails safely** — throw, early return, documented default, surfaced user message, non-zero
  exit. **Never a silent swallow, and never a default that hides the condition.**

Two failure modes to refuse by construction:

- **A guard that disables itself.** A check depending on a tool that may be absent, treating absence
  as "nothing found", passes forever without ever asserting. Prefer builtins; where an external tool
  is genuinely needed, detect its absence and **fail closed** naming it.
- **A guard keyed on a correlate.** Check the thing that actually breaks — the consumer — not
  something that merely travels with it. A correlate drifts, and the check keeps passing.

### 5. Write the test first — the incident is the test case

The exact input from step 1 becomes a test that **fails before the guard exists**. Run it, watch it
fail, then add the guard, then watch it pass. A test written after the fix proves the fix is present;
only a test seen red proves it is *load-bearing*.

Then add the near misses — the legitimate inputs that resemble the incident and must still pass. A
guard that rejects everything gets deleted, and then it protects nothing.

```ts
// RED — the incident, reconstructed exactly. Fails today.
it('rejects a deleted user instead of dereferencing undefined', async () => {
  await expect(sendReceipt(deletedUserId)).rejects.toThrow(/user not found/i)
})

// ALLOW — the near miss that must keep working.
it('sends to an active user', async () => {
  await expect(sendReceipt(activeUserId)).resolves.toBeDefined()
})
```

```ts
// BEFORE — assumed the lookup succeeds.
async function sendReceipt(userId: string) {
  const user = await getUser(userId)
  return mailer.send(user.email, renderReceipt(user))   // 💥 on a deleted user
}

// AFTER — precondition at the boundary, failing loudly with the id that failed.
async function sendReceipt(userId: string) {
  const user = await getUser(userId)
  if (!user) throw new NotFoundError(`user not found: ${userId}`)   // WHERE: entry
  return mailer.send(user.email, renderReceipt(user))
}
```

### 6. Widen once — same class, other sites

Search for the same shape elsewhere: other callers of `getUser`, other handlers taking that input,
other places the assumption is made. One incident of a class usually means several instances of it.

Fix what the search finds **in the same change** when it is the same one-line guard; file an issue
per distinct concern when it is not (CLAUDE.md item 8). Do not let widening turn the change into an
unrelated refactor.

### 7. Prove the guard fires

Not optional, and not satisfied by a green suite:

- the incident test was **seen red** before the guard existed
- near-miss cases pass
- **assert behaviour, never source** — run the thing and read its output or exit code; never grep
  the guard for the string it is supposed to emit. A source-grep stays green through a rename of the
  very thing it checks.
- for a CI gate: break the checker deliberately, watch a case go red, restore it

### 8. Record it where it changes a contract

A **new** obligation earns an ADR. Something already agreed needs only the commit message — and that
message opens with **the incident**, concretely, because months later it is the only surviving
explanation of why the guard exists, and a guard whose reason is lost is a guard somebody deletes.

## Red flags — the OOPS is not done

| Thought | Reality |
|---|---|
| "Fixed it, moving on" | The fix is not the deliverable. The guard is. |
| "I'll be more careful there" | Care is not a check. Nothing runs it. |
| "Too obvious to test" | The incident already proved it was not obvious. 30 seconds. |
| "Added a comment warning about it" | A comment is read by whoever already knew. |
| "The type system covers it now" | Only if the boundary actually validates — a cast is not a check. |
| "It only happens in that one edge case" | That edge case just happened. |
| "Wrote the test after the fix, it passes" | A test never seen red asserts nothing. |
| "This is really a process problem" | Then the guard is a lint rule, a hook, or a CI gate — still mechanical. |

## What this is not

- **Not a postmortem document.** The output is a diff, not a report.
- **Not a substitute for diagnosis.** Cause first (`systematic-debugging`), guard second.
- **Not a linter.** One incident, one condition, one guard.
- **Not `mistake-to-gate`'s replacement.** When the condition is a predicate over repository state,
  step 3 hands the whole build to that skill.

## OOPS Guards Implemented — closing checklist

Emit this at the end of every OOPS, filled in:

- [ ] **Failure mode** — named in check vocabulary, with the artifact that shows it
- [ ] **Root cause** — the condition that allowed it, stated as a predicate
- [ ] **Guard class** — input / precondition / postcondition / error-path / CI gate / (judgment →
      `rules-distill`, stated explicitly)
- [ ] **Where** it lives, **what** it checks, **how** it fails safely
- [ ] **Test written first and seen red**, plus near-miss cases that still pass
- [ ] **Same class swept** elsewhere; issue filed per distinct out-of-scope concern
- [ ] **Guard proven to fire** — behaviour asserted, never source
- [ ] **Wired to run unattended** — test suite, hook, or the repo's single gate list
- [ ] **Recorded** — ADR if it is a new obligation; commit message opens with the incident
