# The task brief

The unit blueprint produces. One brief goes to one agent that has read nothing else.

Everything here exists to survive that condition. A brief that only makes sense after
reading the previous task is not a brief — it is a paragraph of a document.

## Template

````markdown
### Task N: <what this task delivers, as a noun phrase>

**Context:** <2–4 sentences. What this part of the system does, why this change is
wanted, and the one constraint the executor would otherwise violate. Written for
someone who has never opened this repository.>

**Files:**
- Create: `exact/path/to/new.py`
- Modify: `exact/path/to/existing.py:120-160`
- Test: `tests/exact/path/to/test_new.py`

**Interfaces:**
- Consumes: `parse_offer(raw: dict) -> Offer` from Task 2
- Produces: `normalise_mpn(value: str) -> str | None` — Task 6 calls this

**Depends on:** Task 2 (nothing else)

- [ ] **Step 1: Write the failing test**

```python
def test_normalise_strips_separators():
    assert normalise_mpn("ab-12 34") == "AB1234"
```

- [ ] **Step 2: Run it, confirm it fails**

Run: `python3 -m pytest tests/test_ident.py -q`
Expected: FAIL — `normalise_mpn` not defined

- [ ] **Step 3: Implement the minimum that passes**

```python
def normalise_mpn(value):
    ...
```

- [ ] **Step 4: Run the suite**

Run: `python3 -m pytest -q`
Expected: PASS, no other test changes behaviour

- [ ] **Step 5: Commit**

```bash
git -C . add tests/test_ident.py src/ident.py
git -C . commit -m "feat(ident): normalise MPNs for matching"
```

**Verification:** `python3 -m pytest tests/test_ident.py -q`
**Exit criteria:** `normalise_mpn` handles separators, case, and empty input; full
suite green; no other module imports it yet.
**Rollback:** revert the commit — nothing else consumes the function yet.
````

## Why each block is mandatory

| Block | Removing it costs |
|---|---|
| **Context** | the executor infers intent from the diff and optimises for the wrong thing |
| **Files** | it explores, edits an adjacent file that looked right, and the review is a mess |
| **Interfaces** | Task 6 invents a second name for the same function; both survive |
| **Depends on** | tasks get dispatched in a wave they cannot run in |
| **Steps** | the work happens in one commit that cannot be reviewed or bisected |
| **Verification** | "done" is a claim, not an observation |
| **Exit criteria** | the task ends when the executor loses interest, usually early |
| **Rollback** | a bad task blocks the whole plan because undoing it is unresearched |

## Step granularity

One action, 2–5 minutes: *write the failing test* / *run it and watch it fail* /
*implement the minimum* / *run the suite* / *commit*. If a step needs a paragraph to
explain, it is two steps.

Code steps carry the actual code. "Write tests for the above" is not a step — the test
body is the step.

## Interfaces are contracts between briefs

The `Interfaces` block is the only channel between tasks. Names and types written there
are binding: if Task 3 produces `clearLayers()`, Task 7 must not consume
`clearFullLayers()`. This mismatch is the single most common blueprint defect and the
one no mechanical check catches — it reads as correct in both briefs.

Copy signatures verbatim between the producing and consuming brief. Do not paraphrase.

## Self-review before the gate

Run over the finished draft, in this order:

1. **Coverage** — every requirement of the objective maps to a task. Name the gap.
2. **Cold read** — take the middle task, read only it, and ask what you would have to
   go looking for. Anything you would look up belongs in the brief.
3. **Names** — grep the plan for each identifier in every `Produces:` line; every
   `Consumes:` spelling must match one of them exactly.
4. **Placeholders** — `plancheck` finds the literal ones; you find the ones phrased as
   English ("the usual validation", "wire it up the normal way").

Then run the gate:

```sh
cd .claude/skills/blueprint && python3 -m scripts.plancheck <plan.md>
```
