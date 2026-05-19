---
name: propose
description: Present 1-3 design options as code-first proposals so the user can feel the API before any implementation begins. Each option leads with a usage snippet and a one-line tradeoff, with a closing recommendation.
triggers:
  - phrase: "/propose"
  - phrase: "propose options"
  - phrase: "design proposal"
  - phrase: "what are the options"
  - phrase: "show me a few options"
---

# Propose — Code-First Design Options

## Purpose

Before writing implementation code, present 1-3 design options as **code samples** showing how the API would be used. Code communicates a design faster than prose — the user can read the snippet and immediately judge whether the shape feels right.

## When to Use

1. **Manual invocation** — user types `/propose <design question>`
2. **Pre-implementation** — user asks "what's the best way to..." or "how should I design..."
3. **Proactive** — when there are multiple viable shapes and you'd otherwise pick one silently

Skip if there's only one reasonable option or the design is trivial — proposing has a cost too.

## What It Produces

A short response with 1-3 options. Each option has:

- A **name** that captures its character (not "Option A" — say what it is)
- A **usage snippet** — the API as the caller would write it
- A **definition snippet** only when usage doesn't reveal the shape (signatures, not bodies)
- A **one-line tradeoff** — what this option costs

Closing **Recommendation** — one or two sentences picking an option and the deciding factor.

## Workflow

### Step 1: Frame the Decision

State in one sentence what's being designed. If the question is ambiguous, ask before drafting options.

### Step 2: Generate Distinct Shapes

Brainstorm options that differ on a meaningful axis — not cosmetic variations. Examples of real axes:

- positional args vs options object vs builder
- sync vs streaming vs callback
- free function vs class vs module
- explicit config vs convention vs inference
- one general interface vs several specific ones

Cap at 3. If more come to mind, drop the weakest.

### Step 3: Write Usage First

For each option, write the **caller's code** first — what they would type to use it. This is the load-bearing part of the proposal.

### Step 4: Add the Minimum Definition

Show signatures, types, or interfaces only when the usage doesn't fully reveal the API. Never include implementation bodies — they're not the point.

### Step 5: Name the Tradeoff

One line per option. Name what it **costs**, not what it's good at — strengths are visible in the usage code; costs need to be stated.

### Step 6: Recommend

Pick one. Even if close, state which option you'd pick and the deciding factor. Leaving the choice open is not neutral — it pushes the work back to the user.

## Principles

1. **Code over prose** — a 4-line snippet beats a paragraph
2. **Usage before definition** — the caller's view drives the shape
3. **Distinct shapes** — options must differ on a real axis, not cosmetics
4. **At most three** — more options dilute the decision
5. **Name the cost, not the win** — strengths are obvious; costs need to be stated
6. **Always recommend** — leaving the choice open is lazy, not neutral

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
