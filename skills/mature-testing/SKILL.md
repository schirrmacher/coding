---
name: mature-testing
description: Evaluate the maturity of tests. Use when reviewing whether public APIs and outer interfaces are properly tested through behavior, not implementation details.
user-invocable: true
disable-model-invocation: true
allowed-tools: Read, Grep, Glob
argument-hint: [file-or-scope]
---

Evaluate the maturity of **tests** with a focus on public API and outer interface coverage.

If `$ARGUMENTS` is provided, scope the review to those files or directories.

## Principles

- Tests should describe **what** the system does, not **how** it does it.
- Test the public contract — inputs, outputs, side effects, errors.
- Avoid coupling tests to internal structure — refactoring internals should not break tests.
- Test names should read as behavior specifications, not method names.

## Steps

1. **Gather context**: Read the source files in scope. Identify every public API surface — exported functions, class methods, endpoints, event handlers, component props.

2. **Find existing tests**: Locate test files covering the code in scope. Map which public interfaces have tests and which do not.

3. **Audit against these criteria**:

   ### Coverage of public interfaces
   - Is every exported function, endpoint, or public method tested?
   - Are the main success paths covered?
   - Are error and rejection paths covered?
   - Are edge cases at the boundary tested? (empty input, null, max values, unauthorized)

   ### Test quality
   - Do test names describe behavior? (`"returns empty list when no items match"` not `"test getItems"`)
   - Does each test assert one clear outcome?
   - Are tests independent — no shared mutable state, no required ordering?
   - Do tests use realistic inputs, not trivial placeholders?

   ### Abstraction from internals
   - Do tests call the public API, or do they reach into private methods and internal state?
   - Are mocks limited to external dependencies (network, database, clock), not internal collaborators?
   - Would renaming an internal variable or extracting a helper break any test?
   - Do tests assert on return values and observable effects, not on how the result was computed?

   ### Naming and structure
   - Is it clear from the test file what module or interface is being tested?
   - Are tests grouped by behavior or use case, not by method name?
   - Can someone unfamiliar with the code read the tests and understand the contract?

4. **Produce a report** with this structure:

   ### Testing Maturity Assessment

   **Status**: One of `Ready`, `Needs Work`, or `Not Ready`

   **Summary**: 1-2 sentences on the state of testing.

   **Coverage map**: List each public interface and whether it is tested, partially tested, or untested.

   **Issues** (if any): List each issue with:
   - File and line reference
   - The interface or behavior affected
   - What the problem is
   - Severity: `blocking` (must fix) or `suggestion` (nice to have)

   **Recommendation**: Concrete next steps — either "tests are solid" or a numbered list of fixes.

5. **If status is "Needs Work"**: Ask the user whether they want you to proceed with the fixes.
