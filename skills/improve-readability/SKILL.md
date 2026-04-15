---
name: improve-readability
description: Flatten nested code, reorder by importance, extract inline complexity, and clarify names. Reduces deep indentation, puts main logic first, moves complex inline structures into named variables, and renames unclear identifiers.
triggers:
  - phrase: "/improve-readability"
  - phrase: "improve readability"
  - phrase: "make this more readable"
  - phrase: "clean up this code"
  - phrase: "flatten nesting"
  - phrase: "refactor for clarity"
---

# Improve Readability — Code Clarity Framework

## Purpose

Improve the **readability** of the code specified by `$ARGUMENTS`. Apply six targeted transformations that make code easier to scan, understand, and maintain:

- **Flatten nesting** — guard clauses and early exits first, main logic at one indent level
- **Extract inline complexity** — move complex inline data structures and closures into named variables or functions
- **Rename for clarity** — names must be understandable in their surrounding context
- **Group by cohesion** — cluster related lines together, separate groups with blank lines
- **Comment only the why** — only when the reason cannot be expressed as code
- **Order deliberately** — arrange code by what the reader needs to understand first

## When to Use

1. **Manual invocation** — user types `/improve-readability <file|code-target>`
2. **Post-implementation** — user asks to "clean up" or "make this more readable"
3. **Proactive** — user says "flatten nesting", "refactor for clarity", or "improve readability"

## What It Produces

In-place edits that preserve identical behavior:

| Before | After |
|---|---|
| brief description of how the code was | what changed |

## Workflow

### Step 1: Flatten Nesting

- Find deeply nested conditionals and loops
- Convert to guard clauses and early exits
- Keep main logic at a single indent level

### Step 2: Extract Inline Complexity

- Find complex inline data structures, closures, and deeply nested object literals passed as arguments
- Pull them into named variables or functions above the call
- Make the call site scannable at a glance

### Step 3: Rename for Clarity

- Find single-letter, abbreviated, or ambiguous names
- Rename to be understandable in context
- Match the abstraction level of the surrounding code

### Step 4: Group by Cohesion

- Cluster related lines together
- Separate groups with blank lines
- Add a short comment above a group only if its purpose is not obvious from the code

### Step 5: Comment Only the Why

- Remove comments that restate the code
- Add comments only when the reason cannot be expressed as code
- Never add comments that reference this conversation or the changes being made

### Step 6: Order Deliberately

Apply as the final step after all other changes:

- **Critical configuration and variables** — at the top
- **Core purpose** — the most interesting or important part next, not boilerplate or helpers
- **Supporting details** — utilities and edge cases last
- **Cohesion groups** — in logical reading order

## Principles

1. **Never change logic** — only flatten, extract, rename, group, comment, and reorder
2. **Verify identical behavior** — mentally confirm nothing changes functionally
3. **No conversation references** — never add comments about the refactoring itself
4. **Why over what** — explain design decisions, not code mechanics

## Examples

### Flatten nesting

Bad:

```
process(order)
  if order exists
    if order.items not empty
      if order.status is pending
        total = calculateTotal(order.items)
        charge(order.customer, total)
        return order
      else
        throw 'already processed'
    else
      throw 'no items'
  else
    throw 'no order'
```

Good:

```
process(order)
  if not order          -> throw 'no order'
  if items empty        -> throw 'no items'
  if status not pending -> throw 'already processed'

  total = calculateTotal(order.items)
  charge(order.customer, total)
  return order
```

### Rename for clarity

Bad:

```
calc(d, r, t)
  v = d.filter(x => x.a > t)
  return v.reduce((s, x) => s + x.a * r, 0)
```

Good:

```
discountedTotal(orders, rate, minAmount)
  eligible = orders.filter(o => o.amount > minAmount)
  return eligible.reduce((sum, o) => sum + o.amount * rate, 0)
```

### Extract inline complexity

Bad — data structure and closure inline obscure the call:

```
schedule({
  task: 'sync',
  retries: 3,
  backoff: { initial: 100, max: 5000, factor: 2 },
  onFailure: (err, ctx) => {
    log(err)
    if ctx.attempt < 3
      ctx.retry()
    else
      alert(ctx.task, err)
  }
})
```

Good — named variable and function make the call scannable:

```
retryPolicy = { initial: 100, max: 5000, factor: 2 }

syncJob = {
  task: 'sync',
  retries: 3,
  backoff: retryPolicy,
  onFailure: retryOrAlert
}

schedule(syncJob)

retryOrAlert(err, ctx)
  log(err)
  if ctx.attempt < 3 -> ctx.retry()
  else               -> alert(ctx.task, err)
```

### Extract deeply nested object literals

Bad — nested JSON built inline inside a function call:

```
createClient(
  buildConfig({
    auth: {
      provider: 'oauth',
      credentials: {
        clientId: env.CLIENT_ID,
        clientSecret: env.CLIENT_SECRET,
        scopes: ['read', 'write', 'admin']
      },
      refresh: { enabled: true, interval: 3600 }
    },
    retry: { attempts: 3, backoff: { base: 100, max: 5000 } }
  })
)
```

Good — each concern extracted into a named variable:

```
scopes = ['read', 'write', 'admin']

credentials = {
  clientId: env.CLIENT_ID,
  clientSecret: env.CLIENT_SECRET,
  scopes: scopes
}

authConfig = {
  provider: 'oauth',
  credentials: credentials,
  refresh: { enabled: true, interval: 3600 }
}

retryPolicy = { attempts: 3, backoff: { base: 100, max: 5000 } }

config = buildConfig({ auth: authConfig, retry: retryPolicy })
createClient(config)
```

### Group by cohesion

Bad — dense wall of loosely related lines:

```
initApp()
  db = connectDB(config.db)
  cache = createCache(config.cache)
  logger = setupLogger(config.log)
  router = createRouter()
  router.use(authMiddleware)
  router.use(rateLimiter)
  router.mount('/users', userRoutes)
  router.mount('/orders', orderRoutes)
  server = createServer(router)
  server.onError(logger.error)
  server.listen(config.port)
  logger.info('started on ' + config.port)
```

Good — grouped by concern with blank lines between:

```
initApp()
  db = connectDB(config.db)
  cache = createCache(config.cache)
  logger = setupLogger(config.log)

  router = createRouter()
  router.use(authMiddleware)
  router.use(rateLimiter)
  router.mount('/users', userRoutes)
  router.mount('/orders', orderRoutes)

  server = createServer(router)
  server.onError(logger.error)
  server.listen(config.port)
  logger.info('started on ' + config.port)
```

### Comments

Bad — restating the code:

```
// set status to active
user.status = 'active'
```

Good — explaining a non-obvious reason:

```
// prefer reactivation over new account to retain history
user.status = 'active'
```

### Order deliberately

Bad — file level: config buried, helpers before purpose, related pieces scattered:

```
delay(ms) -> ...

class ProfileCache
  get(id) -> ...
  set(id, data) -> ...
  invalidate(id) -> ...

buildHeaders(token) -> ...

RETRIES = 3
BACKOFF = 100
BASE_URL = '/api/v2'

export fetchProfile(id, token) -> ...
export updateProfile(id, data, token) -> ...

formatProfile(raw) -> ...
```

Good — file level: config at top, then the interesting part, then supporting pieces grouped by what they support:

```
RETRIES = 3
BACKOFF = 100
BASE_URL = '/api/v2'

export fetchProfile(id, token) -> ...
export updateProfile(id, data, token) -> ...

class ProfileCache
  get(id) -> ...
  set(id, data) -> ...
  invalidate(id) -> ...

formatProfile(raw) -> ...
buildHeaders(token) -> ...
delay(ms) -> ...
```

Bad — class level: internals before the interface, construction mixed with behavior:

```
class OrderProcessor
  _validateItem(item) -> ...
  _applyDiscount(item, code) -> ...

  constructor(gateway, inventory)
    this.gateway = gateway
    this.inventory = inventory

  _reserveStock(items) -> ...

  submit(order) -> ...
  cancel(orderId) -> ...
```

Good — class level: construction, then public interface, then internals:

```
class OrderProcessor
  constructor(gateway, inventory)
    this.gateway = gateway
    this.inventory = inventory

  submit(order) -> ...
  cancel(orderId) -> ...

  _validateItem(item) -> ...
  _applyDiscount(item, code) -> ...
  _reserveStock(items) -> ...
```

Bad — function level: concerns scattered, reader can't tell what matters:

```
deployService(service, env)
  logDir = env.logDir or '/var/log'
  ensureDir(logDir)
  pidFile = logDir + '/' + service.name + '.pid'
  if fileExists(pidFile) -> throw 'already running'
  artifact = buildArtifact(service.source)
  checksum = hash(artifact)
  previous = getRunningChecksum(service.name)
  if checksum == previous -> return 'no changes'
  healthCheck = service.healthCheck or '/health'
  timeout = env.timeout or 30
  stopExisting(service.name)
  instance = startInstance(artifact, env)
  waitUntilHealthy(instance, healthCheck, timeout)
  writePid(pidFile, instance.pid)
  notifyTeam(service.name, checksum)
  return instance
```

Good — function level: config, then guard rails, then the interesting part (build, deploy, verify):

```
deployService(service, env)
  logDir = env.logDir or '/var/log'
  healthCheck = service.healthCheck or '/health'
  timeout = env.timeout or 30

  pidFile = logDir + '/' + service.name + '.pid'
  if fileExists(pidFile) -> throw 'already running'

  artifact = buildArtifact(service.source)
  checksum = hash(artifact)
  if checksum == getRunningChecksum(service.name) -> return 'no changes'

  stopExisting(service.name)
  instance = startInstance(artifact, env)
  waitUntilHealthy(instance, healthCheck, timeout)

  writePid(pidFile, instance.pid)
  notifyTeam(service.name, checksum)
  return instance
```
