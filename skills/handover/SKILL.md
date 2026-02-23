---
name: handover
description: Create a handover document summarizing context, progress, and next steps so another agent can pick up the work. Use when switching context, pausing work, or handing off to someone else.
user-invocable: true
disable-model-invocation: true
allowed-tools: Read, Grep, Glob, Write
argument-hint: <topic>
---

Create a **handover document** for the given topic.

`$ARGUMENTS` is required and used as the topic name. If the user provides a long or verbose argument, shorten it to a concise kebab-case slug (1-3 words) that captures the topic for use in the filename. For example: `auth-refactor`, `api-caching`, `checkout-bug`.

## Steps

1. **Gather context**: Read the relevant files, understand the current state of the work, and identify what has been done and what remains.

2. **Write the handover file** to `handover-$ARGUMENTS.md` in the project root with this structure:

   ```
   # Handover: <topic>

   ## Goal
   One sentence describing the objective.

   ## Context
   Key files, modules, or systems involved. List paths.

   ## What was done
   Numbered list of completed work.

   ## Current state
   Where things stand right now. What works, what doesn't.

   ## What remains
   Numbered list of open tasks, in priority order.

   ## Decisions made
   Key choices and their reasoning, so the next agent doesn't revisit them.

   ## Gotchas
   Anything surprising, non-obvious, or easy to get wrong.
   ```

3. Keep it factual and concise. No filler. Every line should help the next agent move faster.
