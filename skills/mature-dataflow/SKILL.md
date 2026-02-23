---
name: mature-dataflow
description: Evaluate the maturity of data flow through the application in recent changes. Use when reviewing how data moves between components, layers, and systems to ensure it is clean and traceable.
user-invocable: true
disable-model-invocation: true
allowed-tools: Read, Grep, Glob, Bash(git diff *), Bash(git log *)
argument-hint: [file-or-scope]
---

Evaluate the maturity of **data flow** through the application in recent changes.

If `$ARGUMENTS` is provided, scope the review to those files or directories. Otherwise, review all changes made in this session by inspecting the git diff against the base branch.

## Steps

1. **Gather context**: Read the changed files. Use `git diff` and `git log` to identify what was modified. Then trace the full path of data — from where it originates to where it is consumed or rendered.

2. **Trace data flow**: For each significant piece of data introduced or modified, map:
   - **Source**: Where does the data come from? (user input, API response, database, props, context, URL params, local state, environment)
   - **Transformations**: What happens to the data between source and destination? (parsing, mapping, filtering, enrichment, serialization)
   - **Destination**: Where does the data end up? (rendered in UI, sent to API, written to storage, passed as props, emitted as event)
   - **Intermediaries**: What components/functions/layers does it pass through?

3. **Audit against these criteria**:

   ### Flow clarity
   - Can you follow the data from source to destination without guessing?
   - Are there implicit handoffs where data appears in a component without a clear path of how it got there?
   - Is data passed through too many layers (prop drilling) when a more direct path exists?
   - Are there circular data flows or feedback loops that could cause infinite renders/updates?

   ### Transformation hygiene
   - Are transformations happening at the right layer? (e.g., not formatting dates in business logic, not parsing API responses in the UI)
   - Is the same data transformed multiple times in different places (redundant parsing, repeated normalization)?
   - Are transformations pure and predictable, or do they have hidden side effects?
   - Is data shape consistent throughout the flow, or does it silently change shape between layers?

   ### State management
   - Is state owned by the right component/layer? (as close to where it's used as possible)
   - Is there duplicated state — the same data stored in two places that could drift out of sync?
   - Are derived values computed from source state, or are they stored separately and manually synced?
   - Is async data (loading, error, success) modeled explicitly or handled ad-hoc?

   ### Side effects and boundaries
   - Are side effects (fetching, writing, subscribing) isolated and predictable?
   - Are effects properly cleaned up (unsubscribe, abort controllers, cleanup functions)?
   - Is data validated or sanitized when crossing trust boundaries (user input, external APIs)?
   - Are there race conditions where stale data could overwrite fresh data?

4. **Produce a report** with this structure:

   ### Data Flow Maturity Assessment

   **Status**: One of `Ready`, `Needs Work`, or `Not Ready`

   **Summary**: 1-2 sentences on the state of data flow.

   **Flow diagram**: A text-based diagram showing the primary data paths touched by the changes, e.g.:
   ```
   API response → useFetch hook → ParentComponent (state) → ChildComponent (props) → render
   ```

   **Issues** (if any): List each issue with:
   - File and line reference
   - The data flow affected (source → destination)
   - What the problem is
   - Severity: `blocking` (must fix) or `suggestion` (nice to have)

   **Recommendation**: Concrete next steps — either "data flow is clean" or a numbered list of fixes.

5. **If status is "Needs Work"**: Ask the user whether they want you to proceed with the fixes.
