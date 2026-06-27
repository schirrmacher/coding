---
name: deepspec
description: Implement a technical specification into the current project, conformance-first. Pins the spec version and profile, extracts normative requirements into a traceable register, ports or synthesizes a conformance suite, derives the processing model into stubs, implements bottom-up until the suite passes, then audits the result against the spec section by section and iterates. Use when building from a standard, RFC, or spec document rather than from reference source code.
triggers:
  - phrase: "/deepspec"
  - phrase: "implement this spec"
  - phrase: "implement the spec"
  - phrase: "build from the RFC"
  - phrase: "conform to"
  - phrase: "implement the standard"
---

# Deepspec — Implement a Specification, Conformance-First

## Purpose

Take a technical specification (an RFC, W3C/ECMA/ISO standard, or spec document, given via `$ARGUMENTS`) and build a faithful, well-tested, conformant implementation in the current project. The spec's *normative requirements* are the contract; its *prose and grammar* are the algorithm to distill; its *conformance suite* — official or synthesized — is how "done" is proven.

A spec breaks the two assumptions a code port relies on: there is no executable contract (tests) and no unambiguous algorithm (code). Both must be manufactured — the contract by extracting requirements and synthesizing tests, the algorithm by distilling prose. That manufacturing is front-loaded into a scoping stage that a code port does not need.

Related but distinct:
- **`/deepcopy`** ports an executable reference (code + tests) into this project.
- **`/deepspec`** implements a prose specification, conformance-first.
- **`/reduce`** simplifies code that already exists in this project.
- **`/propose`** explores design options before any code exists.

Use `/deepcopy` when your source is code; use `/deepspec` when your source is a document. They share DNA and both lean on `/reduce`, `/deeptest`, and `/propose`.

## When to Use

1. **Manual invocation** — `/deepspec <path-or-url-to-spec>`
2. **Standards conformance** — implement an RFC, W3C/ECMA/ISO standard, or wire format from its normative text
3. **Re-implementation from prose** — rebuild a behavior from its specification rather than from an existing implementation
4. **Proactive** — user says "implement this spec", "conform to `<standard>`", "build from the RFC"

## Workflow

The backbone is **explore → test → implement → audit**, and the order is non-negotiable:

- **Explore first** (Stage 0): understand the spec — version, profile, requirements, ambiguities — before writing a single line. No stubs, no code.
- **Test next** (Stage 1): the contract is written and made to *fail* before any behavior exists. This is strict test-driven design: a requirement without a failing test is not ready to implement.
- **Implement last** (Stages 2–3): only once requirements are mapped and tests are red. Code exists to turn red tests green, nothing more.
- **Audit closes the loop** (Stage 4): prove conformance against the spec, not just against the tests you happened to write.

Five stages, run in order. Stage 0 is the addition a code port does not need: a spec must be explored and its requirements extracted before anything testable exists. Each stage ends at a natural checkpoint so the user can review before the next begins. Do not skip ahead: implementing before requirements are extracted produces a plausible-but-unconformant guess, and writing code before tests are red abandons the test-driven contract.

### Stage 0: Scope & Requirement Register

A spec is large, ambiguous, and versioned. Pin it down before writing anything.

- **Pin the exact version and errata.** Name the precise draft/edition (e.g. `JSON Schema 2020-12`, `RFC 8259`), and locate published errata and clarifying issues. Mixing versions is the classic spec bug.
- **Map normative references and decide each.** A spec normatively pulls in others (URI, JSON Pointer, regex dialect, character encoding…). List them; for each, decide library-vs-open-code. This is the same escalation as deepcopy's "new dependency", but resolved up front rather than discovered mid-implementation — surface the options and tradeoffs and ask.
- **Declare a conformance profile.** You rarely implement the whole spec. Choose the sections, modules, or vocabularies in scope, and decide every optional (`MAY`) feature explicitly. Escalate `MAY`-level scope choices to the user; do not silently default them.
- **Extract atomic, testable requirements.** Apply `/reduce` to the *prose*: turn each normative statement into one atomic requirement with a stable ID traceable to its section number, tagged by its RFC 2119 keyword (`MUST`/`SHOULD`/`MAY`). This is the spec analogue of reading the reference's functions.
- Record every clause that admits more than one reading in an **ambiguity register** — do not resolve them by guessing yet.

**Checkpoint**: a requirements register (`REQ-### → § → keyword → summary`), a normative-reference decision table, a declared conformance profile, and an ambiguity register. Report the version pinned and the profile chosen.

### Stage 1: Tests as the Contract

Normative requirements are the contract; an executable suite is its proof. Build that suite before any implementation.

- **Port the official suite if one exists.** Many specs ship a conformance suite (often data-driven). Wire it as a harness in the target's test idiom — this is pure deepcopy Stage 1.
- **Synthesize the rest.** For every requirement the suite does not cover — especially every `MUST` — write a positive and a negative test, each tied back to its `REQ-ID`. Where the official suite is data-driven, add fixtures; where there is no suite at all, this is the whole step.
- Audit the resulting suite with `/deeptest`: confirm each test has a clear purpose, a name that reflects the requirement, and an API-level focus. Fix vague names and setup noise now, while the tests are the only thing written.
- Define the public surface as stubs only — types, signatures, exports — with every body an unimplemented marker (`todo!()`, `throw new Error("unimplemented")`, `pytest.fail(...)`).

**Checkpoint**: the project builds; the suite runs and fails with the unimplemented marker; every `MUST` has at least one test; gaps left uncovered by the official suite are listed.

### Stage 2: Derive the Processing Model

Distill the spec's behavior into the stubs before writing real code.

- For each unit of the processing model or data model, distill its recipe via `/reduce` and place it as comments inside the corresponding stub, immediately above the unimplemented marker. Label each block with the `REQ-ID`s and sections it implements (e.g. `// REQ-VAL-017 §6.2.1`), keeping the requirement → location mapping traceable.
- **Transcribe formal grammar and normative keyword tables verbatim.** This inverts deepcopy's "never transcribe syntax": ABNF/EBNF and normative tables are already precise and normative, so copy them exactly. Distill the prose *around* them; do not paraphrase the grammar itself.
- Record each normative reference resolved by open-coding in a substitution table.
- **Escalation points** — stop, lay out the options and tradeoffs, and ask the user; resume only after they choose:
  - a needed **new dependency** or a normative reference whose library-vs-open-code call was deferred;
  - a **target capability gap** (a weaker standard library, a missing construct);
  - an **ambiguity** from the register — present every plausible reading plus what published errata and existing implementations do, and let the user decide.

**Checkpoint**: still builds; tests still fail as expected; every in-scope requirement has a labeled home; ambiguities are resolved or escalated.

### Stage 3: Implement

Replace the stubs with real code, layer by layer.

- Work **bottom-up along the dependency graph** so each layer is testable before the next lands (e.g. encoding → reference resolution → core keywords → higher-level features).
- After each layer, run the suite and report the expected progression — which tests, and which official-suite categories, now pass.
- Match the target project's style and mirror neighbor conventions.
- If implementation reveals a new dependency or a capability gap not seen in Stage 2, apply the same escalation rule: stop, present options and tradeoffs, and ask before adding anything.

**Checkpoint**: all ported and synthesized tests pass; build, lint, and format are clean; report the official suite's pass rate.

### Stage 4: Conformance Audit and Iterate

A passing suite is necessary but not sufficient. Now compare the implementation against the spec itself, section by section.

- Re-read the spec end to end. Produce a **conformance matrix**: for each `REQ-ID`, its implementation location, its test, any deviation, and a verdict (conformant / partial / deviation-justified / gap / bug).
- For every **gap**, add a test that exposes it, then fix.
- For every **deviation**, decide deliberately: keep it (and document why it is justified) or correct it.
- Iterate until every `MUST` is conformant or a documented deviation, and no row is unresolved.
- Write the **conformance claim**: the version, the profile implemented, optional features included or excluded, and known deviations. This is a deliverable a code port does not produce.

**Checkpoint**: conformance matrix with all rows resolved; full suite green; official-suite pass rate reported; conformance claim written.

## Principles

1. **Requirements are the contract** — extract normative statements into a traceable register before any code; the conformance suite is their executable form.
2. **Pin the version, declare the profile** — name the exact edition and decide every optional feature explicitly; scope is documented, never implicit.
3. **Distill prose, transcribe grammar** — read narrative text for semantics, but copy formal grammar and normative keyword tables verbatim.
4. **1:1 requirement traceability, weighted by keyword** — every in-scope requirement gets a home and a test; `MUST` is mandatory, `SHOULD` deviations are documented, `MAY` is an explicit decision.
5. **Manufacture the contract** — where no official suite exists, synthesize positive and negative tests from the normative text; nothing untested is "done".
6. **Bottom-up to green** — implement along the dependency graph, verifying layer by layer.
7. **Audit closes the loop** — the final pass compares against the spec section by section and resolves every deviation on purpose, ending in a written conformance claim.
8. **Escalate, don't assume** — a new dependency, a capability gap, or a prose ambiguity is the user's call; surface the options, errata, and what existing implementations do, then wait for a decision.

## Output Shape

```markdown
## Stage 0 — Scope
- Spec: <name> <version>; errata: <source>
- Profile: <sections / modules / vocabularies in scope>; optional features: <included / excluded>

### Requirement register (excerpt)
| REQ-ID | § | Keyword | Summary |
|---|---|---|---|
| REQ-### | <§> | MUST/SHOULD/MAY | <atomic requirement> |

### Normative references
| Reference | Decision | Rationale |
|---|---|---|
| <RFC/standard> | library X / open-code / out of scope | <why> |

### Ambiguity register
| REQ-ID | § | Readings | Resolution |
|---|---|---|---|
| REQ-### | <§> | <A vs B> | open / escalated / decided: <which> |

## Stage 1 — Tests
- Ported: <official suite> → <harness>
- Synthesized: <REQ-ID> — <positive/negative test>
- Public surface stubbed; every body unimplemented

## Stage 2 — Requirement → implementation map
| REQ-ID / § | Stub location | Notes |
|---|---|---|
| REQ-### | <file:fn> | grammar transcribed / distilled / collapsed-into |

### Substitutions
| Normative reference | Open-coded equivalent |
|---|---|
| <reference> | <equivalent> |

## Stage 3 — Test-pass progression
1. After <layer>: <n> tests pass (<suite category>)
2. After <layer>: <n> tests pass

## Stage 4 — Conformance matrix
| REQ-ID | Impl location | Test | Deviation | Verdict |
|---|---|---|---|---|
| REQ-### | <file:fn> | <test> | <none / what changed> | conformant / partial / deviation-justified / gap / bug |

### Conformance claim
Implements <spec> <version>, profile <…>; includes <optional features>; excludes <…>; known deviations: <…>.
```

## Example

**Input**: `/deepspec https://json-schema.org/draft/2020-12/json-schema-core` → implement as a validator in `src/jsonschema/`

**Output** (compressed across the five stages):

````markdown
## Stage 0 — Scope
- Spec: JSON Schema 2020-12 (Core + Validation); errata: json-schema-org GitHub issues
- Profile: Core, Applicator, Validation vocabularies; Format-Annotation only (assertion is MAY — excluded); Content & Format-Assertion out of scope

### Normative references
| Reference | Decision | Rationale |
|---|---|---|
| RFC 3986 (URI) | open-code resolver | escalated: no new dep; only resolution + base needed |
| RFC 6901 (JSON Pointer) | open-code | small, self-contained |
| ECMA-262 (regex dialect) | host regex engine | escalated: accept dialect gap, documented |
| RFC 8259 (JSON) | host JSON parser | already a dependency |

### Ambiguity register
| REQ-ID | § | Readings | Resolution |
|---|---|---|---|
| REQ-CORE-031 | §8.2.3.2 | `$dynamicRef` resolves over full dynamic scope vs nearest `$dynamicAnchor` | escalated → decided: full dynamic scope, matches official suite |

## Stage 1 — Tests
- Ported: JSON-Schema-Test-Suite (draft2020-12, data-driven) → `suite_runner` harness
- Synthesized: REQ-CORE-031 `$dynamicRef` scope cases; REQ-VAL-044 `multipleOf` float edge
- Public surface stubbed: `Schema`, `Validator`, `RefResolver`, `Annotation`; bodies unimplemented

## Stage 2 — Requirement → implementation map
| REQ-ID / § | Stub location | Notes |
|---|---|---|
| REQ-CORE-012 §8.2.1 ($id base URI) | `resolver.rs:resolve_base` | RFC 3986 resolution open-coded |
| REQ-VAL-* §6 (assertions) | `validation.rs:assert_*` | distilled per keyword |
| ABNF for JSON Pointer §6.5 (RFC 6901) | `pointer.rs` | grammar transcribed verbatim |

### Substitutions
| Normative reference | Open-coded equivalent |
|---|---|
| RFC 3986 reference resolution | `resolve_base` (scheme/authority/path merge) |
| ECMA-262 `pattern` | host regex, dialect gap documented |

## Stage 3 — Test-pass progression
1. After resolver + pointer: ref tests pass
2. After core + applicator: applicator suite passes
3. After validation: all in-scope suite categories pass; clippy + fmt clean

## Stage 4 — Conformance matrix
| REQ-ID | Impl location | Test | Deviation | Verdict |
|---|---|---|---|---|
| REQ-CORE-031 | `resolver.rs:resolve_dynamic` | dynamic-scope cases | none | conformant |
| REQ-VAL-044 | `validation.rs:multiple_of` | float edge | uses rational compare | deviation-justified |
| REQ-FMT-009 | `format.rs:annotate` | format suite | assertion not enforced | conformant (annotation profile) |

### Conformance claim
Implements JSON Schema 2020-12, profile Core+Applicator+Validation; Format-Annotation only; excludes Content & Format-Assertion vocabularies; known deviation: `pattern` follows the host regex dialect, not full ECMA-262.
````
