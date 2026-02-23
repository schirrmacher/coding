---
name: mature-performance
description: Evaluate the maturity of performance characteristics in recent changes. Use when reviewing whether code is efficient, avoids unnecessary work, and scales appropriately.
user-invocable: true
disable-model-invocation: true
allowed-tools: Read, Grep, Glob
argument-hint: [file-or-scope]
---

Evaluate the maturity of **performance characteristics** in recent changes.

If `$ARGUMENTS` is provided, scope the review to those files or directories.

## Steps

1. **Gather context**: Read the files in scope. Identify hot paths, loops, data processing pipelines, and rendering logic.

2. **Map performance-sensitive areas**: For each file or function, identify:
   - What is the expected input size or call frequency?
   - What is the algorithmic complexity?
   - What work is repeated or redundant?
   - What resources are allocated and when are they released?

3. **Audit against these criteria**:

   ### Unnecessary work
   - Are there redundant computations that could be cached or memoized?
   - Are expensive operations happening inside loops when they could be hoisted out?
   - Are large data sets copied, filtered, or transformed multiple times when one pass would suffice?
   - Are there unnecessary re-renders, re-fetches, or re-computations triggered by unstable references?

   ### Algorithmic efficiency
   - Are there O(n²) or worse patterns where O(n) or O(n log n) alternatives exist? (nested loops, repeated lookups in arrays instead of sets/maps)
   - Are data structures chosen appropriately? (array vs map/set for lookups, sorted structures for range queries)
   - Are there unbounded operations — loops, recursion, or accumulations without limits?

   ### Resource management
   - Are allocations proportional to input size, or are there hidden memory blowups? (string concatenation in loops, accumulating closures, growing buffers)
   - Are resources released promptly? (connections, file handles, subscriptions, timers)
   - Are there potential memory leaks from retained references, event listeners, or caches that grow without eviction?

   ### Concurrency and I/O
   - Are independent async operations parallelized where possible, or unnecessarily sequential?
   - Are there N+1 query patterns — fetching related data one item at a time instead of in batch?
   - Is there appropriate debouncing, throttling, or batching for high-frequency operations?
   - Are there blocking operations on the main thread or event loop?

4. **Produce a report** with this structure:

   ### Performance Maturity Assessment

   **Status**: One of `Ready`, `Needs Work`, or `Not Ready`

   **Summary**: 1-2 sentences on the state of performance.

   **Hot spots**: List the performance-sensitive areas identified and their estimated impact (high/medium/low).

   **Issues** (if any): List each issue with:
   - File and line reference
   - The operation or pattern affected
   - What the problem is and the expected impact
   - Severity: `blocking` (must fix) or `suggestion` (nice to have)

   **Recommendation**: Concrete next steps — either "performance is solid" or a numbered list of fixes.

5. **If status is "Needs Work"**: Ask the user whether they want you to proceed with the fixes.
