---
name: deepcomment
description: Audit comments with no comments as the default. Delete noise, retain only useful non-obvious information or required content, and match surviving comments to surrounding style. Edits in place; defaults to the current unstaged changes.
triggers:
  - phrase: "/deepcomment"
  - phrase: "review the comments"
  - phrase: "audit the comments"
  - phrase: "challenge the comments"
  - phrase: "clean up the comments"
  - phrase: "are these comments useful"
---

# Deep Comment

**No comments by default.** Keep a comment only when removing it would lose useful, non-obvious information needed to understand, use, or safely change the code. An entirely comment-free result is valid.

## Target

Resolve in this order:

1. **File / class / function given** → challenge the comments there, edit in place.
2. **Code pasted or quoted in the message** → return the cleaned version in chat, nothing else.
3. **No target** → the comments in the current unstaged changes (`git diff`).

Edit in place and make every deletion reviewable via `git diff`. For a wholly untracked file with no committed baseline, show the result and confirm before overwriting unless already authorized.

## Usefulness Test

For each comment, ask: **What useful information would the reader lose without this?** If there is no concrete answer, delete it.

- Delete restatements, obvious explanations, decorative dividers, obsolete notes, dead commented-out code, and commentary about the conversation or current edit.
- Reasons, warnings, contracts, and references earn no automatic exemption. Keep them only when they convey a relevant constraint, decision, caller obligation, or source the reader needs and cannot readily derive from the code. Judge API documentation from the caller's view, not from knowledge of the implementation.
- Preserve required documentation, legal notices, and functional tool directives. These may have obligations or effects beyond helping a reader; retain required wording and syntax.
- Do not turn redundant “what” into speculative “why.” Rewrite only when the rationale is supported by the code, existing documentation, or supplied context. Never invent intent to justify keeping a comment.
- Check apparent contradictions before editing. Correct or remove a demonstrably stale comment; if it may expose a code defect or a still-valid constraint, report the uncertainty rather than erasing the evidence.
- Tighten useful comments to the shortest wording that preserves the necessary information, including qualifications and references. There is no comment-to-code length ratio.

## Context and Style

Read the enclosing function, class, or section and nearby comparable code before editing. Apply style consistency only after a comment passes the usefulness test.

Follow explicit project conventions. For choices they leave open, match nearby useful comments' tone, syntax, capitalization, punctuation, placement, and formatting. Keep each comment attached to the code it describes and check that its scope and claims still fit.

Do not copy clutter or defective conventions for consistency. Nearby comments are not a reason to add comments to otherwise clear code. Inspect surroundings outside the selected target read-only; report issues there with locations instead of expanding the edit.

## Apply and Report

Review inline comments, block comments, docstrings, doc-comments, and file/module headers. Decide whether to delete, tighten, correct, or retain each one using the test above. Keep the audit focused on comments; suggest code improvements separately rather than introducing renames, extractions, or unrelated refactoring.

Re-read the result in context. Ensure edits preserve code behavior and directive placement. Use relevant checks if comments affect tooling or generated documentation.

Except for pasted-code targets, close with a compact report: the target, what was deleted or changed, which comments remain and why, and any unresolved findings with locations. Distinguish checks run from inspection. Do not manufacture comments to fill a report category.

## Examples

**Delete an obvious restatement.**

```
// increment the counter
counter++
```

→

```
counter++
```

**Delete instead of inventing rationale.** Nothing here establishes why three attempts were chosen; do not invent a gateway failure explanation.

```
// retry three times
for (let i = 0; i < 3; i++) { ... }
```

→

```
for (let i = 0; i < 3; i++) { ... }
```

**Delete an explanation of a standard operation.** Explaining set membership adds no project-specific information here.

```
// Use a Set for O(1) membership checks.
const seen = new Set()
```

→

```
const seen = new Set()
```

**Keep a verified constraint.** If migration documentation confirms this ordering requirement, removing the comment would hide a corruption risk:

```
// Must run after migrate(): reads columns it adds.
// Reordering silently corrupts existing rows.
backfill(db)
```

**Preserve a functional directive.** In a type test, this comment makes the expected diagnostic part of the test:

```ts
// @ts-expect-error -- null is not a valid user ID
loadUser(null)
```

**Match surrounding style after establishing usefulness.** Nearby useful comments use sentence-case line comments above the affected statement. Given a documented provider limit, tighten and align this comment:

```
/* IMPORTANT: we have to cap batches at 100 because the provider rejects larger requests!!! */
sendBatch(items)
```

→

```
// The provider rejects batches over 100 items.
sendBatch(items)
```

Leave nearby comments outside the target unchanged.
