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
2. **Reorder by importance** — public API and core logic first, helpers and constants after.
3. **Extract inline complexity** — move complex inline data structures and closures into named variables or functions.
4. **Rename for clarity** — names must be understandable in their surrounding context.
5. **Group by cohesion** — cluster related lines together, separate groups with blank lines, order groups by logical coherence. Add a short comment above a group only if its purpose is not obvious from the code.
6. **Comment only the why** — only when the reason cannot be expressed as code. Never add comments that reference this conversation or the changes being made.

Do **not** change logic beyond flattening, reordering, extracting, renaming, grouping, and commenting. Verify identical behavior mentally.

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

### Reorder by importance

Bad — reader must scroll past helpers to find the purpose:

```
RETRIES = 3

delay(ms) -> ...
buildHeaders(token) -> ...

export fetchProfile(id, token) -> ...
```

Good — purpose first, mechanism after:

```
export fetchProfile(id, token) -> ...

RETRIES = 3

delay(ms) -> ...
buildHeaders(token) -> ...
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

## Output

| Before | After |
|---|---|
| brief description of how the code was | what changed |
