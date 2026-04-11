---
name: commit-name
description: Generate a short, crisp commit message from the conversation context.
user-invocable: true
disable-model-invocation: true
allowed-tools:
---

From the conversation context, summarize what was done.

Write a commit message from the conversation context:

- Subject: one short line, max 50 characters, lowercase, imperative mood. No scope prefix. No period.
- Body: a minimal summary of what changed and why, wrapped at 72 characters. Use bullet points if multiple changes. Keep it brief — only include what is not obvious from the diff.

Output the subject, a blank line, then the body. Nothing else.
