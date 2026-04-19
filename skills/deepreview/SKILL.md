---
name: deepreview
description: Audit interfaces by tracing call-chains and challenging whether the API surface could be simplified. Targets public interfaces by default, or a specific scope chosen by the user. Detects inconsistent conventions, redundant parameters, mismatched abstractions, and narrow APIs that could be generalized and merged.
triggers:
  - phrase: "/deepreview"
  - phrase: "review the API"
  - phrase: "simplify the interface"
  - phrase: "audit public interfaces"
  - phrase: "challenge the API"
---

# Deep Review — Interface Audit

## Purpose

Audit interfaces in the target code and challenge whether the API surface is as simple as it could be. Focus on **public interfaces by default**, or narrow to a specific scope when the user specifies one (e.g., internal helpers, a single class, a specific layer). Trace how each interface is actually called, then ask hard questions:

- **Consistency** — do all call-chains follow the same conventions?
- **Parameters** — do similar operations use similar parameter shapes?
- **Abstractions** — do related interfaces sit at the same level of abstraction?
- **Surface area** — are narrow APIs hiding a simpler, more general one?

## When to Use

1. **Manual invocation** — user types `/deepreview <folder|file|class>` to audit public interfaces, or `/deepreview <target> --scope internal|all|<pattern>` to choose a different scope
2. **Pre-release** — user asks to "review the API" or "audit public interfaces"
3. **Proactive** — user says "simplify the interface" or "challenge the API"
4. **Scoped** — user asks to review specific APIs, e.g., "review the internal helpers in cache.ts" or "audit all methods in OrderProcessor"

## What It Produces

A structured audit report output directly in the conversation:

```
## Deep Review: <target>

### Interfaces (<scope>)
<table of every function, method, or endpoint in scope with signature>

### Call-Chain Analysis
<per-interface: who calls it, with what arguments, in what context>

### Findings
<numbered list of inconsistencies, redundancies, and simplification opportunities>

### Recommendations
<table: action | before | after | why>
```

## Workflow

### Step 1: Inventory Interfaces

- Determine the scope: public interfaces by default, or the scope the user specified (internal, all, specific class/layer)
- Scan the target folder, file, or class for all interfaces matching the scope
- List every function, method, endpoint, or symbol in scope
- Record each signature: name, parameters, return type, visibility

### Step 2: Trace Call-Chains

For each public interface:

- Find every call site across the codebase
- Record what arguments callers pass and in what shape
- Note which interfaces are called together or in sequence
- Identify clusters of interfaces that serve the same workflow

### Step 3: Challenge Calling Convention

Compare all call-chains and ask:

- **Uniform convention?** — do all interfaces follow the same pattern for similar operations? (e.g., one takes positional args while another takes an options object)
- **Consistent ordering?** — do parameters appear in the same order across related interfaces?
- **Symmetric naming?** — do paired operations use matching verb patterns? (e.g., `get`/`set` vs `fetch`/`update` vs `load`/`save` in the same module)

Flag every deviation.

### Step 4: Challenge Parameter Patterns

Compare parameter shapes across related interfaces and ask:

- **Similar inputs, different shapes?** — do two interfaces accept the same data but structured differently?
- **Repeated parameter groups?** — do multiple interfaces share 3+ parameters that could be a single object?
- **Boolean flags hiding variants?** — does a flag argument mean there are really two separate operations?
- **Optional sprawl?** — do too many optional parameters signal a missing configuration object or builder?

Flag every redundancy.

### Step 5: Challenge Abstraction Level

Compare the abstraction level across interfaces and ask:

- **Mixed levels?** — does a high-level `createUser()` sit next to a low-level `insertRow()`?
- **Leaking internals?** — does a public interface expose storage details, wire formats, or implementation types?
- **Wrapper without value?** — does an interface just forward to another without adding meaning?

Flag every mismatch.

### Step 6: Challenge Surface Area

Look at the full interface map and ask:

- **Narrow siblings?** — are there 2+ interfaces that differ only in one parameter and could be merged into one with that parameter made explicit?
- **Overlapping scope?** — do two interfaces do nearly the same thing for slightly different inputs?
- **Missing general form?** — would a single, more general interface replace several specific ones without losing clarity?
- **Dead surface?** — are any public interfaces never called externally?

Propose concrete merges or generalizations.

### Step 7: Report

- List all interfaces in scope in a table
- Summarize each call-chain briefly
- Number every finding with a severity (convention / redundancy / simplification)
- Present recommendations as a table: action, before, after, why

## Principles

1. **Minimize complexity** — every recommendation must reduce the API surface or make it more uniform, never add to it
2. **Improve UX** — judge interfaces from the caller's perspective, not the implementer's
3. **Trace before judging** — never challenge an interface without seeing how it is actually called
4. **Consistency over cleverness** — a uniform API is better than individually "optimal" signatures
5. **Fewer interfaces, broader reach** — prefer one general interface over three narrow ones
6. **Same level of abstraction** — public interfaces in the same module should speak the same language
7. **Evidence-based** — every finding references concrete call sites and signatures, not theory

## Examples

**Input**: `/deepreview src/api/users`

**Output**:

```
## Deep Review: src/api/users

### Public Interfaces

| Interface            | Parameters                    | Return   |
|----------------------|-------------------------------|----------|
| getUser(id)          | id: string                    | User     |
| fetchUserByEmail(e)  | email: string                 | User     |
| listUsers(opts)      | opts: { page, limit, sort }   | User[]   |
| createUser(data)     | data: CreateUserInput         | User     |
| updateUser(id, data) | id: string, data: Partial     | User     |
| deleteUser(id)       | id: string                    | void     |
| disableUser(id)      | id: string                    | void     |
| enableUser(id)       | id: string                    | void     |

### Call-Chain Analysis

- getUser: called by ProfilePage, OrderService, AuthMiddleware
- fetchUserByEmail: called only by AuthService.login
- deleteUser: called by AdminPanel
- disableUser / enableUser: called by AdminPanel, always in pair

### Findings

1. **Convention** — getUser vs fetchUserByEmail use different
   verb patterns for the same operation (lookup by identifier)
2. **Redundancy** — disableUser and enableUser differ only in
   the target status, same call sites use both
3. **Simplification** — fetchUserByEmail is a narrow variant
   of getUser that could accept a query object instead

### Recommendations

| Action    | Before                             | After                                  | Why                                  |
|-----------|------------------------------------|----------------------------------------|--------------------------------------|
| Merge     | getUser(id), fetchUserByEmail(e)   | getUser({ id } \| { email })          | One lookup with discriminated input  |
| Merge     | disableUser(id), enableUser(id)    | setUserStatus(id, 'active'\|'disabled')| Differ only in target status         |
| Align     | get/fetch/list/create/update/delete| get/list/create/update/delete          | Uniform verb set across module       |
```

**Input**: `/deepreview lib/cache.ts`

**Output**:

```
## Deep Review: lib/cache.ts

### Public Interfaces

| Interface                     | Parameters                          | Return       |
|-------------------------------|-------------------------------------|--------------|
| get(key)                      | key: string                         | T | null     |
| set(key, value, ttl?)        | key: string, value: T, ttl?: number | void         |
| getOrSet(key, fn, ttl?)      | key: string, fn: () => T, ttl?: num | T            |
| invalidate(key)               | key: string                         | void         |
| invalidateByPrefix(prefix)    | prefix: string                      | void         |
| invalidateAll()               | none                                | void         |

### Call-Chain Analysis

- get/set: called throughout, always with string keys
- getOrSet: called by 4 services as a cache-aside pattern
- invalidate: called after mutations
- invalidateByPrefix: called only by UserService.updateRole
- invalidateAll: called only in tests

### Findings

1. **Surface area** — three invalidation methods where one
   could suffice with a pattern parameter
2. **Parameter pattern** — ttl appears in set and getOrSet
   but not as a default on the cache instance
3. **Dead surface** — invalidateAll is only called in tests,
   not a genuine public need

### Recommendations

| Action    | Before                                            | After                          | Why                                    |
|-----------|---------------------------------------------------|--------------------------------|----------------------------------------|
| Merge     | invalidate(key), invalidateByPrefix(p), invalidateAll() | invalidate(pattern?: string)  | One method, pattern selects scope      |
| Extract   | ttl param repeated in set() and getOrSet()        | Default ttl in constructor     | Configure once, override per call      |
| Remove    | invalidateAll()                                   | (drop from public API)         | Only called in tests, not public need  |
```
