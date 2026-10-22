---
name: chunk
description: Split current unstaged changes into balanced, dependency-ordered commits, with passing builds and tests at every step. Use when asked to chunk working-tree changes into multiple commits, optionally with a requested count.
---

# Chunk

Split changes into a commit sequence. Use the `commit` skill for every commit.

## Purpose

Turn the current unstaged working tree into a sequence of coherent commits that
build and pass tests independently. Each commit builds on the preceding ones.
Aim for roughly equal implementation and review effort without breaking dependencies.

## When to Use

- User types `/chunk [n]`
- User asks to split uncommitted changes into multiple commits

Honor a supplied positive integer `n`. When omitted, choose a sensible count after
reviewing all changes. If the count is invalid or cannot produce meaningful,
passing commits, explain the constraint and ask for an adjusted count.

## Workflow

### Step 1: Inventory All Changes

Inspect `git status`, the complete unstaged diff, and non-ignored untracked files.
Read the changed code and its surrounding interfaces before grouping anything.
Include deletions, renames, binary changes, and file modes in the inventory.

If changes are already staged, ask how to handle them before modifying the index.
Record the starting commit and preserve a recoverable snapshot of the original
changes, including untracked contents, outside the working tree before staging.
If there are no changes, report that and stop.

Read project instructions and build/test configuration. Establish baseline build
and test health on the starting commit in an isolated checkout. Identify the
project's required checks and relevant tests for the affected behavior. If the
baseline fails or required validation cannot run, explain the blocker and stop.
If no applicable tests exist, report that limitation rather than claiming they pass.

### Step 2: Identify Dependencies and Safe Additions

Map which changes require others: types before consumers, implementations with
their tests, and configuration or generated artifacts with the code they enable.

Check which new files can land before their consumers. An unreferenced file is
not automatically inert: source globs, module discovery, test collection, plugin
registration, and build scripts may activate it immediately. Include any required
dependencies in the same commit or an earlier one.

### Step 3: Balance and Order the Commits

Group changes by coherent purpose, then order prerequisites before consumers.
Keep behavior changes with their tests. Split changes within a file when useful;
whole files are not mandatory commit boundaries.

Balance implementation and review effort rather than matching line counts.
Dependency correctness and passing checks take priority over equal size. Do not
invent transitional code, empty commits, or unrelated fixes to force a count.

Present the complete sequence before committing. For each part, show its purpose,
files or hunks, dependencies on earlier parts, and validation commands. Proceed
without an additional approval step unless the user requested one.

### Step 4: Validate and Commit Each Part

For each part in order:

1. Stage only its intended files or hunks and inspect the staged diff.
2. Materialize the exact staged tree in an isolated checkout or temporary directory
   and run the required build and test checks there. Exclude later unstaged and
   untracked changes; testing the full working tree can hide missing dependencies.
3. If checks fail, revise the grouping or order and retest before committing.
   If blocked, stop and report the failure without discarding changes.
4. Invoke the `commit` skill with only this part staged. Let it detect the repo's
   message style and hand off to `commit-name`; do not bypass it with a separate
   message-writing or committing workflow.
5. Verify the resulting commit contains exactly the validated tree. If hooks
   changed its contents, validate the resulting commit before continuing.

Preserve the original working-tree contents while staging partial changes. Keep
completed commits and remaining work intact if execution stops; do not automatically
reset, amend, or rewrite earlier commits to repair the sequence.

### Step 5: Verify and Report

Confirm the intended number of commits was created and their combined diff matches
the original snapshot, including untracked additions and file modes. Check that
the final file contents are unchanged and no intended changes remain uncommitted.

Report commit hashes and subjects in order, with build/test results for each.
If interrupted, identify completed parts, remaining changes, and the blocker.
Remove only temporary artifacts created by this workflow after verification;
retain the recovery snapshot when work remains unresolved. Do not push.

## Principles

1. **Inspect before splitting.** Understand the complete change before choosing boundaries.
2. **Dependencies before balance.** Equal size never justifies a broken intermediate commit.
3. **Test the commit itself.** Later working-tree changes must not make a part appear valid.
4. **Preserve the result.** Rearrange existing changes without changing their final contents.
5. **Use commit.** Commit messages and creation belong to the existing commit workflow.
