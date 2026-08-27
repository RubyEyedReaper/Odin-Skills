# The redundant-call check

Before automating a call, ask whether its result was already derivable from what the session held.
Automating a redundant call does not remove the waste; it makes the waste reliable and puts a name on
it, after which it is defended rather than deleted.

**This is a judgment, and it carries no threshold.** There is no count of prior turns that makes a
call redundant. A number here would be fabricated on a quantity nobody computes, and a fabricated
threshold is how a procedure becomes theatre — cited constantly, evaluated never. What follows is a
procedure with an evidence standard, which is the strongest honest form.

## The procedure

**1. Name the call and its output in one line.**
Not "checking the state of things" — *`git status --porcelain`, to learn whether the tree is dirty.*
A call you cannot state in one line is two calls; split them and run this check on each.

**2. Enumerate what the session already held at the moment of the call.**
Look at, in this order:

- the outputs of prior tool calls in this session, in full — not your memory of them;
- files already read this session, and the parts actually read;
- the plan document, the handoff, and the roadmap entry for this work;
- what the current turn's own instructions state as fact.

If enumerating this is hard because the material has scrolled out of reach, that is itself the
finding — see *When the answer is yes* below.

**3. Ask the derivability question.**
*Could this output have been produced from that material by reasoning alone, with no new
observation?* Three answers: **derivable**, **partly derivable**, **not derivable**. Partly
derivable is a real answer and usually means the call should be narrowed rather than removed.

**4. Produce evidence, or the answer is "not derivable".**
Evidence is a **named prior artifact** — this tool call, that file at those lines, this line of the
plan — that contains the result or entails it. "I probably knew that already" is not evidence. A
call you cannot refute with a named artifact is not redundant, and the check ends there.

## Staleness beats derivability

**A result that could have changed between the earlier observation and now is not derivable, no
matter how plainly the earlier turn contains it.**

This is the rule that actually changes answers. Repository state, branch tips, process lists, file
contents in a tree other sessions share, the output of any gate — all of them go stale, and a session
that re-derives them from an earlier turn reports the past with the confidence of the present.

Ask what could have moved: your own writes, a concurrent session, another worktree, a background job,
the clock. If anything could have, re-observe. The cost of one redundant call is small; the cost of a
confident wrong answer is the whole task.

## Derivable means entailed, never guessable

The one distinction that decides most disputed cases. **Entailed:** the material the session holds
determines the answer — the plan states the branch name, so the branch name is derivable. **Guessable:**
the material makes an answer likely — the last three gates passed, so this one probably passes.

Treating guessable as derivable produces a fabrication with a citation attached, which is worse than
the call it saved. When the two are hard to tell apart, write the entailment down in one sentence. If
that sentence needs "probably", it is a guess.

## When the answer is yes

Do not automate. The verdict is `eliminate`, and the work is:

1. **Stop making the call.** Record where the result already lives, so the next reader finds it
   instead of re-deriving it.
2. **Ask why it recurred.** A call repeated because its earlier result was *lost* is a retention
   defect, not an automation opportunity. The repair is in the handoff, the plan document or the
   ledger — the places a result is supposed to survive in — never in a script that fetches it faster.
3. **Say so where the decision is visible.** A recorded `eliminate` stops the third person from
   re-litigating it; an unrecorded one is re-proposed within the week.

Automating a call whose result is lost between turns builds a faster path to something you already
had. The fix is to stop losing it.

## Red flags

| Thought | Reality |
|---|---|
| "It's one command, it costs nothing" | It costs a tool call, its output in context, and the attention that output displaces. Cheapness is why redundant calls survive review |
| "Re-running is more reliable than trusting an earlier turn" | Sometimes exactly right — that is the staleness rule, and it has to be *argued*, not assumed. Say what could have changed |
| "I'll script it so it's fast next time" | Speed is not the question. Whether the call should happen at all is |
| "The check is subjective, so I'll skip it" | Judgment is not the same as arbitrariness. The evidence standard is what makes it checkable by someone else |
| "I remember reading that" | Then name the file and the lines. If you cannot, you are guessing |
| "Three prior turns mention it, so it's redundant" | There is no threshold. One named artifact that entails the result is stronger than three that mention it |
