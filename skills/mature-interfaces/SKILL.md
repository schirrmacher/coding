---
name: mature-interfaces
description: Evaluate the maturity of data structures, APIs, and interfaces in recent changes. Use when reviewing whether types, contracts, and boundaries between modules are production-ready.
user-invocable: true
disable-model-invocation: true
allowed-tools: Read, Grep, Glob, Bash(git diff *), Bash(git log *)
argument-hint: [file-or-scope]
---

Evaluate the maturity of **data structures, APIs, and interfaces** in recent changes.

If `$ARGUMENTS` is provided, scope the review to those files or directories. Otherwise, review all changes made in this session by inspecting the git diff against the base branch.

## Steps

1. **Gather context**: Read the changed files. Use `git diff` and `git log` to identify what was modified. Then trace outward — find all types, interfaces, and data structures that the changes touch or depend on.

2. **Map the interface surface**: For each changed file, identify:
   - Type definitions and interfaces it exports or consumes
   - Props types, function signatures, return types
   - API contracts (request/response shapes, route params, query params)
   - Shared data structures (config objects, state shapes, domain models)

3. **Audit against these criteria**:

   ### Type integrity
   - Are types precise or are they overly permissive (`any`, `unknown`, loose unions)?
   - Do generic types have proper constraints?
   - Are optional fields genuinely optional or are they masking required data?
   - Are there type assertions (`as`) that bypass the type system instead of fixing the real issue?

   ### Interface contracts
   - Do the changed interfaces align with how they are actually used across the codebase?
   - Are there breaking changes to existing interfaces without updating all consumers?
   - Are new interfaces consistent with naming and shape conventions already in use?
   - Do function signatures match what callers actually pass?

   ### Data structure design
   - Are data structures normalized or is there redundant/denormalized data that could drift?
   - Are enums, constants, or union types used where stringly-typed values appear?
   - Is the shape of shared objects stable or likely to cause churn downstream?
   - Are there implicit contracts (magic strings, assumed field presence) that should be explicit types?

   ### API boundaries
   - Are request/response types shared between client and server where applicable?
   - Are API payloads validated at the boundary (zod, io-ts, or equivalent)?
   - Is versioning or backward compatibility considered for external-facing APIs?
   - Do error responses have a consistent shape?

4. **Produce a report** with this structure:

   ### Interface Maturity Assessment

   **Status**: One of `Ready`, `Needs Work`, or `Not Ready`

   **Summary**: 1-2 sentences on the state of interfaces and data structures.

   **Interface map**: Brief list of the key types/interfaces touched and their relationships.

   **Issues** (if any): List each issue with:
   - File and line reference
   - The interface/type affected
   - What the problem is
   - Severity: `blocking` (must fix) or `suggestion` (nice to have)

   **Recommendation**: Concrete next steps — either "interfaces are solid" or a numbered list of fixes.

5. **If status is "Needs Work"**: Ask the user whether they want you to proceed with the fixes.
