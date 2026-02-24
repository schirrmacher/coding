---
name: mature-logic
description: Evaluate the maturity of logic, separation of concerns, and edge case handling. Use when reviewing whether business logic is well-structured, properly isolated, and handles all cases.
user-invocable: true
disable-model-invocation: true
allowed-tools: Read, Grep, Glob
argument-hint: [file-or-scope]
---

Evaluate the maturity of **logic, separation of concerns, and edge case handling**.

If `$ARGUMENTS` is provided, scope the review to those files or directories.

## Steps

1. **Gather context**: Read the files in scope. Read surrounding code to understand what each function/component is responsible for.

2. **Map responsibilities**: For each file or function, identify:
   - What is its single responsibility? Can you state it in one sentence?
   - What decisions (branching logic) does it make?
   - What are the possible inputs and their ranges?
   - What are the possible outputs and outcomes?

3. **Audit against these criteria**:

   ### Separation of concerns
   - Does each function/component/module have a single, clear responsibility?
   - Is business logic mixed into UI components, or properly extracted?
   - Is presentation logic mixed into data-handling layers?
   - Are there god-functions that do too many things and should be decomposed?
   - Are concerns split across files that should be colocated, or colocated when they should be separate?

   ### Logic correctness
   - Are conditionals correct? Check for inverted conditions, missing `else` branches, wrong operators (`&&` vs `||`).
   - Are comparisons correct? Check for off-by-one errors, `<` vs `<=`, `===` vs `==`.
   - Is boolean logic simplified or unnecessarily nested?
   - Are early returns used effectively, or are there deeply nested if/else trees?
   - Are there implicit assumptions about input values that are not validated?

   ### Edge cases
   - What happens with empty/null/undefined inputs?
   - What happens with boundary values (0, -1, MAX_INT, empty string, empty array)?
   - What happens with unexpected types if the language allows it?
   - What happens when an async operation fails, times out, or returns unexpected data?
   - What happens on first render, on rapid re-renders, on unmount?
   - Are there race conditions in async logic?

   ### Error handling
   - Are errors caught at the right level — not too early (swallowing useful info) and not too late (crashing the app)?
   - Are error messages actionable or generic?
   - Is the happy path clearly distinguishable from error paths?
   - Are there silent failures where errors are caught but nothing meaningful happens?

4. **Produce a report** with this structure:

   ### Logic Maturity Assessment

   **Status**: One of `Ready`, `Needs Work`, or `Not Ready`

   **Summary**: 1-2 sentences on the state of logic and separation of concerns.

   **Responsibility map**: Brief list of each function/component and its identified responsibility.

   **Issues** (if any): List each issue with:
   - File and line reference
   - The function/component affected
   - What the problem is (with a concrete example of the failing case if an edge case)
   - Severity: `blocking` (must fix) or `suggestion` (nice to have)

   **Recommendation**: Concrete next steps — either "logic is solid" or a numbered list of fixes.

5. **Changes table**: End with a compact before/after summary:

   | Before | After |
   |---|---|
   | brief description of current state | what it should become |

6. **If status is "Needs Work"**: Ask the user whether they want you to proceed with the fixes.
