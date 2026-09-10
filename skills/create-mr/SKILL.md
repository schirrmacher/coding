---
name: create-mr
description: Create one pull or merge request, or an approved chain of them, from selected changes using GitHub CLI or GitLab CLI when available. Use when asked to open, create, or split pull requests or merge requests.
---

# Create MR

Create reviewable pull requests on GitHub or merge requests on GitLab. Use the
`change-summary` skill for every title and description.

## Select the Changes

Determine what the user intends to submit from, in order:

1. Their explicit request and the current conversation
2. Workspace context that names the target branch or task
3. The working tree, staged diff, and commits ahead of the target branch

Inspect `git status`, relevant diffs, and `git log <target>..HEAD`. Respect an
explicit target branch. Otherwise use workspace context, the branch's configured
merge base, or the remote's default branch, in that order.

Proceed when the intended changes and target are clear. Ask a concise question
when materially different scopes remain plausible. Never include unrelated local
changes merely because they are present.

## Offer a Split

Treat changes as candidates for separate requests when they contain multiple
independent features, fixes, migrations, or review concerns. Present the proposed
parts in dependency order, with a short scope and target for each, then ask whether
to create the chain. Do not split until the user agrees.

If the user declines, create one request. If they agree, create a stacked chain:

- Part 1 targets the original target branch
- Each later part targets the preceding part's branch
- Each branch adds only its stated part on top of its target

Preserve unrelated work and published history. Do not discard changes or rewrite
published commits to manufacture a split. If the current work cannot be separated
safely, explain why and ask how the user wants to proceed.

## Prepare Each Part

For every part:

1. Confirm its branch contains only the intended changes relative to its target
2. Run the relevant checks before publishing
3. Commit any selected uncommitted changes in the repository's established style
4. Push the branch explicitly to the intended remote

Respect user-provided draft state, labels, reviewers, assignees, and issue links.
Do not add them by inference.

## Write the Title and Description

Invoke `change-summary` separately for each part. Give it only that request's diff:
the original target against Part 1, then the preceding branch against each later
part. Do not describe cumulative changes from earlier parts.

Use the generated heading as the request title. Use the generated `Purpose`, `What
changed`, and `Examples` sections as the description, then append:

```markdown
### Change chain

Part X of N
```

Every description must contain the marker, including `Part 1 of 1` for a single
request. Keep the title and description in a temporary file or otherwise pass them
without shell interpolation that could execute their contents.

## Choose the Hosting CLI

Detect the host from the selected Git remote, not from whichever executable happens
to be installed:

- For a GitHub remote, use `gh pr create`
- For a GitLab remote, use `glab mr create`

Check that the matching CLI exists and is authenticated. Pass the source branch,
target branch, title, and description explicitly so the command is non-interactive.
Consult that installed version's `--help` for its supported body-file option rather
than assuming flags shared by the other CLI.

If the matching CLI is absent or unauthenticated, do not install software or start
an authentication flow without a request. Preserve the prepared title and
description, explain the missing prerequisite, and give the user the next command.

## Create and Verify

Create requests in chain order. Before creating one, query open requests for the
same source branch so a retry cannot create a duplicate. After every creation,
verify its title, source, target, and `Part X of N` marker.

If creation fails after a possibly successful network request, query again before
retrying. If a chain stops partway through, leave successful requests intact and
report exactly which parts remain.

Summarize the complete submitted change in one crisp sentence. Return that sentence
followed by every request in chain order twice:

1. A Markdown list of clickable titles, including each request's `Part X of N`
   position and target branch
2. A `For Slack:` section containing a fenced `text` block that can be copied
   directly into Slack. Repeat the summary sentence as its first line, followed by
   a blank line and the request links.

Format each line in the Slack block as:

```text
<one-sentence summary>

• <URL|Part X of N: title> → `target-branch`
```
