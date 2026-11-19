---
name: similar
description: Review recent changes against surrounding code and comments for consistent placement, ordering, and style. Use when asked whether additions fit the existing code or to challenge their surrounding context. Adjust new changes only; report issues in existing code without editing it.
---

# Similar

Make recent changes fit their surroundings. Challenge both the additions and the local conventions instead of assuming either is correct.

## Target

Use an explicit target when provided. Otherwise, review the changes made in the current task. If that context is unavailable, inspect staged and unstaged changes, including relevant untracked source files. Ask for a target if none can be identified.

Distinguish new changes from existing code before editing. A named file narrows the review; it does not make all its contents editable. When the boundary is unclear, report suggested adjustments rather than rewriting existing code.

## Review

Read the enclosing function, class, or section and comparable nearby examples, not just the diff. Follow explicit project conventions; use the closest comparable code to resolve choices they leave open.

- **Placement and order:** Do additions belong beside related code? Check declaration order, imports, configuration entries, and test grouping against local conventions. Before moving executable code, check dependencies, initialization, side effects, and error paths; visual consistency must not change behavior.
- **Style:** Compare naming, formatting, control flow, abstraction level, helper usage, and error handling. Prefer established patterns over introducing a different way to do the same thing.
- **Comments:** Check new comments for accuracy, tone, placement, and useful intent beyond restating the code. Check whether additions invalidate surrounding comments or separate a comment from the code it describes. Preserve warnings, contracts, and provenance.
- **Surrounding assumptions:** Does the nearby code still make sense with the additions? Identify contradictions, duplicated work, and conventions that are themselves defective. Do not copy a defect merely for consistency; explain the justified deviation.

## Adjust and Verify

Make the smallest behavior-preserving adjustments to new changes. Report problems in existing code or comments with their locations and suggested fixes; leave those lines untouched. Avoid unrelated cleanup or new abstractions introduced solely for uniformity.

If correctness requires a behavior change or an edit to existing code, report the issue and the needed correction instead of silently broadening this review.

Re-read the result in context. Run relevant formatting checks without rewriting unrelated code, and use focused tests when an adjustment could affect execution. Leave already consistent changes alone.

## Output

Briefly summarize adjustments, unresolved findings with locations, and verification performed. If no adjustment is needed, say that the reviewed changes fit their surroundings. Distinguish checks actually run from conclusions based on inspection.
