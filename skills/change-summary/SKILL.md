---
name: change-summary
description: Generate a concise change summary from the conversation context. Focuses on features and APIs, not implementation details. Produces a copy-pasteable markdown summary.
triggers:
  - phrase: "/change-summary"
  - phrase: "change summary"
  - phrase: "summarize changes"
  - phrase: "merge request summary"
  - phrase: "PR description"
---

# Change Summary — Change Description Generator

## Purpose

Generate a change summary that communicates **what changed and why** in user-facing language. Focus on features and APIs, skip implementation details.

Also produce a crisp 3-5 point summary at the top that captures the purpose of the change — what problem it solves, what it enables, and why it matters.

## When to Use

1. **Manual invocation** — user types `/change-summary` before opening a merge request
2. **Post-feature** — user asks to "summarize changes" or "write a PR description"
3. **Proactive** — user says "I need a summary for this branch"

## What It Produces

A markdown summary wrapped in a 4-backtick code block so inner 3-backtick fences for each example render correctly when pasted:

`````
````markdown
## <title: max 60 chars, imperative mood>

### Purpose

- <3-5 crisp bullets: what problem this solves, what it enables, why it matters>

### What changed

- <bullet per feature or API change, user-facing language>

### Examples

```<lang>
<example 1: short snippet showing usage of the new/changed API>
```

```<lang>
<example 2: another snippet, different scenario>
```
````
`````

Each inner example MUST be wrapped in its own triple-backtick fence with a language tag (e.g. `http`, `json`, `bash`, `ts`, `py`). Do not paste raw snippets without fences — they will not render as code.

## Workflow

### Step 1: Analyze Context

- Review the conversation to identify features implemented and problems solved
- Check git log and diffs to understand the full scope of changes
- Identify public API changes, new endpoints, or user-facing behavior

### Step 2: Draft Summary

- Write a title that describes the outcome, max 60 characters, imperative mood
- Write 3-5 crisp purpose bullets capturing problem, enablement, and motivation
- List each feature or API change as a bullet in user-facing language
- Write 2-3 code snippets showing usage of new or changed interfaces

### Step 3: Format Output

- Wrap the entire summary in a 4-backtick fence tagged `markdown` (` ````markdown `)
- Wrap each example snippet in its own 3-backtick fence with the appropriate language tag (`http`, `json`, `bash`, `ts`, `py`, etc.)
- Never leave example code as bare text — every snippet must be inside a fenced block
- Verify the summary is under 30 lines
- Ensure examples are copy-pasteable and show the public interface

## Principles

1. **Outcome over work** — title describes what the user gets, not what was done
2. **No internals** — no file lists, no refactoring notes, no internal method names
3. **Copy-pasteable examples** — show the public interface, not implementation
4. **Brevity** — entire summary under 30 lines
5. **User-facing language** — write for the reviewer, not the author

## Examples

**Input**: "Summarize the auth feature I just built"

**Output**:

`````markdown
````markdown
## Add JWT authentication with refresh token rotation

### Purpose

- API clients need secure access to protected endpoints
- Server-side sessions do not scale across multiple instances
- Stateless tokens eliminate shared session storage
- Refresh rotation limits exposure window of compromised tokens

### What changed

- New `/auth/login` and `/auth/refresh` endpoints
- Bearer token middleware for protected routes
- Automatic token rotation on refresh

### Examples

```http
POST /auth/login
{ "email": "a@b.com", "password": "..." }
```

```json
{ "access_token": "...", "refresh_token": "..." }
```

```http
GET /api/profile
Authorization: Bearer <access_token>
```
````
`````

**Input**: "PR description for the pagination changes"

**Output**:

`````markdown
````markdown
## Add cursor-based pagination to list endpoints

### Purpose

- Offset pagination degrades on large datasets due to row skipping
- Cursor-based pagination maintains constant query performance
- Clients need a stable, predictable way to page through results
- Sensible defaults (25) and limits (100) prevent accidental overload

### What changed

- All list endpoints accept `cursor` and `limit` query params
- Responses include `next_cursor` for fetching the next page
- Default limit set to 25, max 100

### Examples

```http
GET /api/users?limit=10
```

```json
{ "data": [...], "next_cursor": "abc123" }
```

```http
GET /api/users?limit=10&cursor=abc123
```

```json
{ "data": [...], "next_cursor": "def456" }
```
````
`````
