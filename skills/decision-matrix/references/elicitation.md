# Elicitation — getting criteria, weights, and scores worth trusting

The engine's arithmetic is exact. Its inputs are not. Everything that makes a decision
matrix honest happens before `scripts/score.py` runs, and it happens in an interview.

This protocol is `grilling` applied to a scoring spec: **one question at a time, always
with a recommended answer, and never asked at all when the codebase can answer it.**

---

## The three rules

### 1. One question at a time

A batch of six questions gets six shallow answers, and the sixth answer contradicts the
first. Ask one, take the answer, let it change the next question. That is the whole
technique — the sequencing is what surfaces the fork nobody had noticed.

### 2. Every question carries a recommendation

Never ask an open question you already have a view on. Ask:

> Weight for *ops burden*: I recommend **25** — this team has no on-call rotation, so an
> option that needs one is expensive in a way "cost" does not capture. Higher, lower, or
> leave it?

not:

> How important is ops burden?

The recommendation is what turns an interview into a review. A user reviewing a number
corrects it in five seconds; a user generating a number from nothing stalls.

### 3. Read the repo before asking

Anything on disk is not a question. Before asking about:

| Question | Look here first |
|---|---|
| "Do we already use X?" | `package.json`, lockfiles, imports |
| "What's our test story?" | test dirs, CI config, coverage settings |
| "Have we decided this before?" | `.claude/docs/adr/`, `docs/decisions/`, `CHANGELOG.md` |
| "How big is this codebase?" | the files themselves |
| "What did we try last time?" | git log, closed issues/PRs |

Asking a user to recite their own repository is how an interview loses its authority.

---

## Criteria

Aim for **4–6**. Fewer than 3 and the matrix is theatre; more than 8 and the weights are
noise.

**Do not start from a blank set when a template covers the shape.** Four worked specs ship
with the skill — `assets/templates/{build-vs-buy,technical-architecture,product-prioritization,hiring-candidate}.json`,
catalogued in `SKILL.md` step 3 — each with criteria, weights, directions and constraints
already argued. Open the nearest one, then run the four tests below on every criterion it
gives you: an inherited criterion the decision does not turn on is worse than one you forgot,
because it arrives looking considered.

**Test each candidate criterion:**

1. *Does it discriminate?* If every option scores the same, drop it — the engine will flag
   it as `non-discriminating`, but you should have caught it first.
2. *Is it independent?* "Developer experience", "ease of use", and "learning curve" are one
   criterion wearing three hats, and entering all three triples its weight in secret.
3. *Is it a must-have?* Then it is a **constraint**, not a criterion. A veto eliminates; a
   heavy weight merely disadvantages, and a strong option can still win without it.
4. *Which direction?* Cost, latency, effort, and ops burden are `lower-is-better`. Getting
   the direction wrong inverts the whole column and the result still looks plausible.

**Weights:** start from a proposed set that sums to 100, then justify the largest one out
loud. If the top criterion is over 60 % of the total, either the decision is really about
that one thing — say so and stop scoring — or the weights need rebalancing.

---

## Scores

The scale is 0–100 against the criterion, not against the other options. Anchor it before
scoring anything:

- **0** — fails this dimension outright
- **50** — adequate, no advantage
- **100** — best available in the market today, not merely best in this option set

Anchoring matters because an unanchored scorer compresses everything into 60–80 and the
weights then decide nothing.

**Confidence is not a score.** Use `confidence` for how well you know the value; use the
value for the value. A `{"value": 90, "confidence": 0.4}` says "probably excellent, barely
researched" — which is exactly the signal sensitivity analysis needs, and it is lost if you
hedge by scoring 65 instead.

**Never invent a score to complete the matrix.** If nobody knows how option C handles
concurrent writes, that gap is a task (go find out), not a number. The engine's refusal to
run an incomplete spec is a feature.

---

## Multiple scorers

When several people or agent perspectives score the same spec, disagreement is the most
valuable output in the run — more than the winner. `std_dev` per cell shows exactly where
the room disagrees, and that cell is usually where the real decision lives. Aggregate
after recording the spread, never by averaging it away in conversation first. How the engine
combines them, and what `multi_scorer_analysis` reports back: [multi-scorer.md](multi-scorer.md).

---

## When the interview should stop

Stop and record when one of these is true:

- The ranking is stable under the weights anyone would plausibly argue for
- The remaining uncertainty is in a criterion that cannot change rank 1 (the tornado shows this)
- The decision is two-way and cheap to revisit — take the lead option and move

Stop and **escalate to the user** only for scope, spend, external visibility, or anything
irreversible. Every other fork is the agent's to resolve and record.
