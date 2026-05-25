---
name: propose
description: Present 1-3 design options as concrete proposals so the user can feel the choice before any implementation begins. Works for code APIs, architectural designs, and naming. Each option leads with a tangible artifact and a one-line tradeoff, with a closing recommendation.
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
- **Naming** — candidate names in context (a signature, a path, a header), not bare strings. Triggered by phrases like "propose a name", "what should we call…", "rename…"

If the user's phrasing is ambiguous, pick the mode that matches the question; don't ask unless the modes would produce wildly different answers.

## When to Use

1. **Manual invocation** — user types `/propose <design question>`
2. **Pre-implementation** — user asks "what's the best way to..." or "how should I design..."
3. **Naming** — user asks "what should we call this" or "propose a name for…"
4. **Architecture** — user asks "how should this be structured" or "where should X live"
5. **Proactive** — when there are multiple viable shapes and you'd otherwise pick one silently

Skip if there's only one reasonable option or the design is trivial — proposing has a cost too.

## What It Produces

A short response with 1-3 options. Each option has:

- A **label** that captures its character (not "Option A" — say what it is)
- A **concrete artifact**, matched to the mode:
  - *Code:* a usage snippet — the API as the caller would write it
  - *Architecture:* a sketch of components, boundaries, or flow (ASCII diagram, file tree, or short bullet structure)
  - *Naming:* the name shown in context — a signature, path, header, or call site — never a bare string
- A **supporting snippet** only when the artifact doesn't fully reveal the shape (signatures for code, a one-line responsibility statement for components, a sibling for names)
- A **one-line tradeoff** — what this option costs

Closing **Recommendation** — one or two sentences picking an option and the deciding factor.

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

*Naming:*
- verb-first vs noun-first (`computeX` vs `xCompute`)
- domain term vs generic term (`enroll` vs `add`)
- consistent suffix family (`xFor`, `xBy`, `xWith`) vs bare names
- abbreviation vs full word

Cap at 3. If more come to mind, drop the weakest.

### Step 4: Show the Artifact First

For each option, lead with the **concrete artifact** — the thing the user can read and react to:

- *Code:* the caller's code — what they'd type to use it
- *Architecture:* the structure — components and their relationships, a small ASCII diagram, or a directory tree
- *Naming:* the name in context — a function signature, file path, URL, or call site that includes nearby siblings so the name reads in situ

This is the load-bearing part of the proposal. Prose around the artifact is supporting only.

### Step 5: Add the Minimum Supporting Detail

Add a small extra only when the artifact alone doesn't reveal the shape:

- *Code:* signatures, types, or interfaces — never implementation bodies
- *Architecture:* a one-line responsibility per component, or the key invariant the boundary enforces
- *Naming:* a sibling or two to show how the name reads alongside neighbors (e.g., other methods on the same type)

### Step 6: Name the Tradeoff

One line per option. Name what it **costs**, not what it's good at — strengths are visible in the usage code; costs need to be stated.

### Step 7: Recommend

Pick one. Even if close, state which option you'd pick and the deciding factor. Leaving the choice open is not neutral — it pushes the work back to the user.

## Principles

1. **Concrete over prose** — a snippet, sketch, or in-context name beats a paragraph
2. **Idiomatic to the stack** — every option must look native to the language, framework, or domain already in use; match existing repo patterns before importing outside ones
3. **Show the artifact first** — the reader's view (caller's code, structure sketch, name in context) drives the shape
4. **Distinct shapes** — options must differ on a real axis, not cosmetics
5. **At most three** — more options dilute the decision
6. **Name the cost, not the win** — strengths are obvious; costs need to be stated
7. **Always recommend** — leaving the choice open is lazy, not neutral

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
## Proposal: Name for the permission resolution function

### Option 1: `resolvePermissions`

```ts
const perms = resolvePermissions(user)
// alongside: applyOverrides(user, rules), loadRoles(user)
```

Tradeoff: "resolve" is vague — could be read as resolving a promise or a path.

### Option 2: `effectivePermissionsFor`

```ts
const perms = effectivePermissionsFor(user)
// alongside: rolesFor(user), overridesFor(user)
```

Tradeoff: longer; the `For` suffix has to be applied consistently across siblings.

### Option 3: `computeEffectivePermissions`

```ts
const perms = computeEffectivePermissions(user)
// alongside: computeRoleSet(user), computeOverrideSet(user)
```

Tradeoff: the `compute` prefix implies expensive work — callers may cache defensively.

### Recommendation

Option 2. `effectivePermissionsFor` names the actual concept ("effective" vs raw) and reads naturally next to the existing `rolesFor` / `overridesFor` helpers.
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
