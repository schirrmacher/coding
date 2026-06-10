---
name: propose
description: Present 1-3 design options as concrete proposals so the user can feel the choice before any implementation begins. Works for code APIs and architectural designs. For naming requests, scans project conventions and returns a ranked list of 3-10 candidate names with a pick recommendation.
triggers:
  - phrase: "/propose"
  - phrase: "propose options"
  - phrase: "design proposal"
  - phrase: "what are the options"
  - phrase: "show me a few options"
  - phrase: "propose a name"
  - phrase: "propose an architecture"
---

# Propose — Concrete Design Options

## Purpose

Before committing to a direction, present 1-3 options as **tangible artifacts** — code snippets, architecture sketches, or candidate names — so the user can feel the choice instead of reading prose about it. A small concrete sample communicates a design faster than a paragraph.

## Modes

The artifact changes by what's being proposed; the structure does not.

- **Code / API** (default) — usage snippets showing how the caller would write it
- **Architecture** — a short structural sketch: components, boundaries, data flow, or a small ASCII diagram. Triggered by phrases like "propose an architecture", "how should we structure…", "service boundaries", "data flow"
- **Naming** — a list of 3–10 candidate names. Triggered by phrases like "propose a name", "what should we call…", "rename…", "name ideas", "suggest a name". Does **not** use the full options + tradeoffs format — just a ranked list with a one-line note per entry.

If the user's phrasing is ambiguous, pick the mode that matches the question; don't ask unless the modes would produce wildly different answers.

## When to Use

1. **Manual invocation** — user types `/propose <design question>`
2. **Pre-implementation** — user asks "what's the best way to..." or "how should I design..."
3. **Naming** — user asks "what should we call this" or "propose a name for…"
4. **Architecture** — user asks "how should this be structured" or "where should X live"
5. **Proactive** — when there are multiple viable shapes and you'd otherwise pick one silently

Skip if there's only one reasonable option or the design is trivial — proposing has a cost too.

## What It Produces

**Code / Architecture** — a short response with 1–3 options. Each option has:

- A **label** that captures its character (not "Option A" — say what it is)
- A **concrete artifact**, matched to the mode:
  - *Code:* a usage snippet — the API as the caller would write it
  - *Architecture:* a sketch of components, boundaries, or flow (ASCII diagram, file tree, or short bullet structure)
- A **supporting snippet** only when the artifact alone doesn't reveal the shape
- A **one-line tradeoff** — what this option costs

Closing **Recommendation** — one or two sentences picking an option and the deciding factor.

**Naming** — a ranked list of 3–10 candidates (no full option blocks, no tradeoffs section):

```
## Name suggestions for <thing>

Conventions detected: <casing, prefix family, abbreviation policy>

1. `candidateName` — one-line note on why it fits
2. `anotherName` — one-line note
...

**Pick**: `recommendedName` — one sentence on the deciding factor.
```

The detected conventions line keeps the list grounded. The pick line is required — never leave the choice open.

## Workflow

### Step 1: Frame the Decision

State in one sentence what's being designed. If the question is ambiguous, ask before drafting options.

### Step 2: Anchor in Stack Idioms

Identify the language, framework, and libraries already in play. Each option must be a shape that's **idiomatic to that stack** — not a generic pattern transplanted from elsewhere.

- React → hooks and composition before class wrappers
- Go → small interfaces, errors as values, no exceptions
- Rust → traits and ownership before runtime checks
- TypeScript → discriminated unions before string enums
- Python → context managers, dataclasses, async if already async

Check the repo for existing patterns first. If the codebase already solves similar problems a certain way, that's the strongest signal — match it unless there's a real reason to diverge.

### Step 3: Generate Distinct Shapes

Brainstorm options that differ on a meaningful axis — not cosmetic variations. Examples of real axes:

*Code:*
- positional args vs options object vs builder
- sync vs streaming vs callback
- free function vs class vs module
- explicit config vs convention vs inference
- one general interface vs several specific ones

*Architecture:*
- monolith vs split services
- sync call vs queue vs event stream
- shared database vs per-service storage
- library vs sidecar vs service
- one boundary vs several smaller ones

*Naming:* scan the project first, then generate names.
- Grep for naming patterns: casing style, prefix/suffix families (`xFor`, `xBy`, `handle*`, `on*`), abbreviation policy
- Match existing patterns unless the user asks to diverge
- Generate 3–10 candidates that differ on a meaningful axis: verb-first vs noun-first, domain term vs generic, suffix family vs bare name, abbreviation vs full word
- Skip the options + tradeoffs structure — use the Names List format instead (see below)

Cap at 3 for code/architecture options. If more come to mind, drop the weakest.

### Step 4: Show the Artifact First

**For Naming mode** — skip the options format entirely. Instead output the Names List:

1. State detected conventions in one line (casing, prefix/suffix families, abbreviation policy).
2. List 3–10 numbered candidates, each with a one-line note on why it fits.
3. End with a **Pick** line naming the recommended candidate and the deciding factor.

**For Code / Architecture mode** — lead each option with the **concrete artifact**:

- *Code:* the caller's code — what they'd type to use it
- *Architecture:* the structure — components and their relationships, a small ASCII diagram, or a directory tree

This is the load-bearing part of the proposal. Prose around the artifact is supporting only.

### Step 5: Add the Minimum Supporting Detail

*(Code / Architecture only — Naming mode ends at step 4.)*

Add a small extra only when the artifact alone doesn't reveal the shape:

- *Code:* signatures, types, or interfaces — never implementation bodies
- *Architecture:* a one-line responsibility per component, or the key invariant the boundary enforces

### Step 6: Name the Tradeoff

One line per option. Name what it **costs**, not what it's good at — strengths are visible in the usage code; costs need to be stated.

### Step 7: Recommend

Pick one. Even if close, state which option you'd pick and the deciding factor. Leaving the choice open is not neutral — it pushes the work back to the user.

## Principles

1. **Concrete over prose** — a snippet, sketch, or in-context name beats a paragraph
2. **Idiomatic to the stack** — every option must look native to the language, framework, or domain already in use; match existing repo patterns before importing outside ones
3. **Show the artifact first** — the reader's view (caller's code, structure sketch, name in context) drives the shape
4. **Distinct shapes** — options must differ on a real axis, not cosmetics
5. **At most three** — more options dilute the decision (naming: 3–10 candidates)
6. **Name the cost, not the win** — strengths are obvious; costs need to be stated
7. **Always recommend** — leaving the choice open is lazy, not neutral
8. **Match conventions before inventing** — grep the project; names that look native are immediately usable

## Examples

**Input**: `/propose how should the new HTTP client handle retries?`

**Output**:

````markdown
## Proposal: HTTP retry handling

### Option 1: Inline per call

```ts
const user = await client.get('/users/1', {
  retry: { attempts: 3, backoff: 'exponential' },
})
```

Tradeoff: every call site repeats the policy; easy to drift.

### Option 2: Configured at construction

```ts
const client = new HttpClient({
  retry: { attempts: 3, backoff: 'exponential' },
})

const user = await client.get('/users/1')
```

Tradeoff: one policy per client — endpoints with different needs need their own client.

### Option 3: Configured default with per-call override

```ts
const client = new HttpClient({ retry: { attempts: 3 } })

const user = await client.get('/users/1')
const report = await client.get('/reports/heavy', { retry: { attempts: 0 } })
```

Tradeoff: two layers to reason about — defaults plus overrides.

### Recommendation

Option 3. Most calls take the default and stay terse; outliers opt out without spawning a second client.
````

**Input**: `/propose API for feature flag checks in TypeScript`

**Output**:

````markdown
## Proposal: Feature flag API

### Option 1: Single function, string key

```ts
if (isEnabled('checkout.v2', { userId })) {
  renderCheckoutV2()
}
```

Tradeoff: typos in flag names are silent until runtime.

### Option 2: Generated flag constants

```ts
import { Flags } from './flags.gen'

if (Flags.CheckoutV2.isEnabled({ userId })) {
  renderCheckoutV2()
}
```

```ts
// flags.gen.ts (generated)
export const Flags = {
  CheckoutV2: defineFlag('checkout.v2'),
  // ...
}
```

Tradeoff: needs a codegen step wired into the build.

### Recommendation

Option 2 if codegen already runs in the build; otherwise Option 1 with a lint rule that pins valid flag names.
````

**Input**: `/propose a name for the function that resolves a user's effective permissions across roles and overrides`

**Output**:

````markdown
## Name suggestions for permission resolution function

Conventions detected: camelCase, verb-first helpers (`rolesFor`, `overridesFor`), no abbreviations

1. `effectivePermissionsFor` — matches the `xFor(user)` family already in the codebase
2. `resolvePermissions` — verb-first, clear intent; "resolve" could be misread as async
3. `computeEffectivePermissions` — explicit about computation cost; `compute` prefix implies callers may want to cache
4. `permissionsFor` — shortest option; drops "effective" so it's less precise
5. `mergedPermissionsFor` — names the mechanism (merge of roles + overrides); slightly implementation-flavored

**Pick**: `effectivePermissionsFor` — names the actual concept ("effective" vs raw) and fits the existing `rolesFor` / `overridesFor` suffix family without needing a new convention.
````

**Input**: `/propose an architecture for the new ingestion pipeline`

**Output**:

````markdown
## Proposal: Ingestion pipeline architecture

### Option 1: Single service, in-process stages

```
[ HTTP intake ] → [ validate → enrich → persist ]  (one service)
                                       ↓
                                   Postgres
```

- One deployable; stages are function calls inside one request.

Tradeoff: a slow enrichment step blocks intake throughput; no isolation between failures.

### Option 2: Queue between intake and processing

```
[ HTTP intake ] → SQS → [ worker: validate → enrich → persist ] → Postgres
```

- Intake acks fast; workers scale independently.

Tradeoff: introduces a queue to operate; end-to-end latency is harder to reason about.

### Option 3: Stage-per-service with a queue between each

```
[ intake ] → Q1 → [ validate ] → Q2 → [ enrich ] → Q3 → [ persist ] → Postgres
```

- Each stage scales and fails on its own; clear replay points.

Tradeoff: three services and three queues to own for a pipeline that isn't yet at that scale.

### Recommendation

Option 2. Decouples intake from variable enrichment cost without paying the operational tax of Option 3; we can split further later if a single stage becomes the bottleneck.
````

**Input**: `/propose how to expose pagination on the list endpoints`

**Output**:

````markdown
## Proposal: Pagination shape

### Option 1: Offset + limit

```http
GET /api/users?offset=40&limit=20
```

```json
{ "data": [...], "total": 1284 }
```

Tradeoff: degrades on large tables; skipping rows gets expensive.

### Option 2: Cursor

```http
GET /api/users?limit=20&cursor=eyJpZCI6NDB9
```

```json
{ "data": [...], "next_cursor": "eyJpZCI6NjB9" }
```

Tradeoff: clients can't jump to an arbitrary page — only forward.

### Recommendation

Option 2. The list endpoints are append-mostly feeds; nobody needs random-access paging, and the perf curve stays flat.
````
