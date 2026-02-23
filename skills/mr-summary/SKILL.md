---
name: mr-summary
description: Generate a concise merge request summary from the conversation context. Focuses on features and APIs, not implementation details.
user-invocable: true
disable-model-invocation: true
allowed-tools: Read, Grep, Glob
---

From the conversation context, create a merge request summary.

## Format

```
## <title: max 60 chars, imperative mood>

<1-2 sentences: what problem this solves and why>

### What changed

- <bullet per feature or API change, user-facing language>

### Examples

<2-3 short code snippets showing usage of the new/changed APIs or features. No internals.>
```

## Rules

- Title describes the outcome, not the work done.
- Skip implementation details — no file lists, no refactoring notes, no internal method names.
- Examples should be copy-pasteable and show the public interface.
- Keep the entire summary under 30 lines.
- Output the summary inside a single markdown code block (```markdown) so the user can copy it directly.
