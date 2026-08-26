# The overdevelopment catalogue

Six patterns. Each is code that **works** — that is what makes it hard. None of these is a bug; all
of them are cost the reader pays on every future visit.

Every entry has the same three parts:

1. **Recognition signal** — the observable thing that puts the pattern on the table. A signal is a
   fact about the code, not a feeling about it. No signal, no finding.
2. **Simpler alternative** — the recipe. Not "simplify this", but the specific smaller shape, stated
   concretely enough that someone could apply it without asking a follow-up question.
3. **The behaviour-preservation sentence** — the sentence that must appear in the finding, asserting
   that the alternative preserves the original behaviour, and naming what would have to be true for
   that to be false. **A finding without this sentence is not a finding.** It is a proposal to change
   behaviour wearing a simplification's clothes, and it is how a review breaks working code.

The sentence is a real claim, checkable and refutable. If it cannot be written honestly, the right
finding is a different one: *this does more than the caller needs, and removing it would change
behaviour X* — reported under questions and assumptions, not as a simplification.

---

## 1. Excess abstraction

An interface, base class, factory, strategy registry, generic parameter or indirection layer
introduced before a second concrete case exists.

**Recognition signal.** The abstraction has exactly one implementation, one caller, or one call site
that ever selects a variant. Count them: `grep` for implementers of the interface, callers of the
factory, values ever passed to the strategy key. One is the signal. A comment saying "so we can swap
this later" with no second implementation is the signal in prose.

**Simpler alternative.** Inline the single implementation into its one caller and delete the
interface, the factory and the registration. Keep the concrete type at the boundary. When the second
case genuinely arrives, extract the seam then, informed by two real cases instead of one imagined
one — the extraction is cheap and the guess is not.

**Behaviour-preservation sentence.** *"Deleting the `<name>` indirection and calling `<concrete>`
directly preserves behaviour: `<concrete>` is the only implementation (`<evidence>`) and the
dispatch never selects anything else. This would be false only if a caller resolves the
implementation dynamically — by name, by config, by plugin discovery — and I checked `<how>`."*

## 2. Duplicated layers

Two or more layers that each transform the same data without adding a decision — a DTO that mirrors
the model field for field, a service that only forwards to a repository, a wrapper whose every
method is a one-line delegation.

**Recognition signal.** A type or class whose members map one-to-one onto another's, with no field
renamed, no field dropped, no validation, no default applied. Or a method body that is a single
delegating call with the arguments unchanged. Read three methods; if all three only forward, the
layer adds nothing.

**Simpler alternative.** Delete the pass-through layer and let the caller use the thing it was
forwarding to. Where the layer exists to keep a dependency direction honest — a boundary type
keeping a database model out of a public API — that is a decision and the layer stays; say so and
move on. The test is whether the layer would ever diverge, not whether it is conceptually tidy.

**Behaviour-preservation sentence.** *"Removing `<layer>` and calling `<target>` directly preserves
behaviour: every member forwards unchanged (`<evidence>`), so no transformation, default or
validation is lost. This would be false only if `<layer>` is a published boundary that external
callers depend on, and I checked `<how>`."*

## 3. Premature optimization

A cache, memo, pool, batch, index, custom data structure or hand-rolled loop introduced with no
measurement behind it.

**Recognition signal.** The optimization exists and nothing in the change — no benchmark, no
profile, no issue, no comment with a number — says what it made faster. Cache with no eviction
policy and no measured hit rate. A `Map` built for a lookup over a list whose realistic size is in
the tens. A manual loop replacing a standard library call "for speed".

**Simpler alternative.** Delete the optimization and use the obvious form: the direct call, the
plain list, the library function. Then, if speed is genuinely a concern, state the realistic input
size and measure — the number is the deliverable, not the optimization. Bullet 7 of the rubric wants
that same number, which is why the two rows meet here.

**Behaviour-preservation sentence.** *"Replacing `<optimization>` with `<direct form>` preserves
behaviour: both return the same values for the same inputs (`<evidence>`), and the only difference
is cost at `<size>`, which is unmeasured. This would be false only if `<optimization>` also provides
`<semantic effect — deduplication, ordering, idempotence>`, and I checked `<how>`."*

Note the asymmetry: a cache that silently deduplicates or serializes concurrent calls is not only an
optimization, and deleting it *does* change behaviour. Look for that before writing the sentence.

## 4. Redundant dependencies

A package added for something the standard library, the framework, or an already-present dependency
does.

**Recognition signal.** The dependency is new in this change, and the imported surface is one or two
functions. Read what is actually imported — a date library for one format call, a utility package
for `groupBy`, an HTTP client where the runtime already has `fetch`, a second validation library
next to the one the project already uses. Two libraries in the same manifest doing the same job is
the signal even when neither is new.

**Simpler alternative.** Replace the imported call with the built-in or the existing dependency's
equivalent, and remove the package from the manifest and the lockfile in the same change. Where the
package genuinely earns it — correctness that is hard to get right, such as time zones, parsing, or
cryptography — keep it and say which of those it is. Never hand-roll crypto to remove a dependency.

**Behaviour-preservation sentence.** *"Replacing `<pkg>.<fn>` with `<builtin>` preserves behaviour
for this call site: same inputs produce the same output including `<the edge case that differs
between implementations>` (`<evidence>`). This would be false only if `<pkg>` handles `<edge case>`
differently, and I checked `<how>`."*

## 5. Overly broad frameworks

A general mechanism built to solve one specific problem — a plugin system with one plugin, a rules
engine with three hard-coded rules, a config schema for values that never vary, an event bus with
one publisher and one subscriber.

**Recognition signal.** The mechanism's generality is unused: count the plugins, the rules, the
distinct config values across every environment, the subscribers. One, or all-identical, is the
signal. A second signal is a mechanism that must be *configured* to do the only thing anyone ever
asks it to do.

**Simpler alternative.** Write the specific thing the mechanism is currently configured to do,
directly, and delete the mechanism, its configuration, its registration and its tests. This is
distinct from pattern 1: excess abstraction wraps one implementation, a broad framework builds
machinery to select among implementations that do not exist. The remedy is the same shape and the
deletion is larger.

**Behaviour-preservation sentence.** *"Replacing `<framework>` with the direct `<specific
implementation>` preserves behaviour: the only registered `<plugin/rule/subscriber>` is `<name>`
(`<evidence>`) and its effect is reproduced exactly. This would be false only if a
`<plugin/rule/subscriber>` is registered at runtime from outside this repository, and I checked
`<how>`."*

## 6. Verbose implementation

The right shape, expressed at three times the length — intermediate variables used once, a
conditional whose branches are identical but for a constant, defensive checks for conditions the
type system or the caller already guarantees, comments restating the line beneath them, a five-step
sequence the standard library does in one call.

**Recognition signal.** A function longer than the floors in `.claude/rules/common/coding-style.md`
whose body contains no decision — no branch that matters, no error path, no loop with real work.
Or the same three lines appearing in each arm of a conditional. Or a null check on a value the
signature declares non-nullable.

**Simpler alternative.** Delete the single-use intermediates, hoist the common part out of the
conditional so only the differing constant remains inside, remove guarantees the caller already
provides, and replace the hand-rolled sequence with the library call. Length is the symptom; the
target is the count of things the reader must hold in mind at once.

**Behaviour-preservation sentence.** *"Collapsing `<lines>` to `<shorter form>` preserves behaviour:
the intermediates are single-use and side-effect-free, and the removed guard is already guaranteed
by `<signature/validator at file:line>`. This would be false only if `<intermediate>` has a side
effect or the guard catches a runtime value the type does not, and I checked `<how>`."*

---

## When the catalogue does not apply

Say so, per pattern, and mean it. An abstraction with two real callers earns its keep. A cache with
a measured hit rate is not premature. A dependency that handles time zones is doing something hard
correctly. The verdict `ship` requires naming the part the review tried hardest to cut and why it
held — which is what stops "no findings" from meaning "no review".

The failure mode of this catalogue is a reviewer who flags every abstraction because the catalogue
lists abstractions. Each entry's recognition signal is what makes a finding evidenced rather than
reflexive; a finding whose signal was never actually checked is the same fluent, plausible, too-much
output this skill exists to refuse.
