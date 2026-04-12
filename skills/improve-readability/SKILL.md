---
name: improve-readability
description: Flatten nested code, reorder by importance, extract inline complexity, and clarify names. Reduces deep indentation, puts main logic first, moves complex inline structures and closures into named variables, and renames unclear identifiers.
user-invocable: true
disable-model-invocation: true
allowed-tools: Read, Grep, Glob, Edit
argument-hint: <file|code-target>
---

Improve the **readability** of the code specified by `$ARGUMENTS`.

## What to change

1. **Flatten nesting** — guard clauses and early exits first, main logic at one indent level.
2. **Extract inline complexity** — move complex inline data structures and closures into named variables or functions.
3. **Rename for clarity** — names must be understandable in their surrounding context.
4. **Group by cohesion** — cluster related lines together, separate groups with blank lines. Add a short comment above a group only if its purpose is not obvious from the code.
5. **Comment only the why** — only when the reason cannot be expressed as code. Never add comments that reference this conversation or the changes being made.
6. **Order deliberately** — apply as the final step after all other changes. Arrange code by what the reader needs to understand first:
   - Critical configuration and variables at the top.
   - The most interesting or important part next — the core purpose, not boilerplate or helpers.
   - Supporting details, utilities, and edge cases last.
   - Cohesion groups in logical reading order.

Do **not** change logic beyond flattening, extracting, renaming, grouping, commenting, and reordering. Verify identical behavior mentally.

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

## Output

| Before | After |
|---|---|
| brief description of how the code was | what changed |
