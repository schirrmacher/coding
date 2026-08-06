---
name: shorten
description: Rewrite prose to cut filler, hedging, and pleasantries while keeping full sentences and every technical fact exact. Applies to a file (rewritten in place), pasted text, or prior conversation context.
triggers:
  - phrase: "/shorten"
  - phrase: "shorten this"
  - phrase: "make this shorter"
  - phrase: "tighten this text"
  - phrase: "cut the filler"
  - phrase: "condense this"
---

# Shorten — Filler-Free Rewrite

## Purpose

Compress the prose, not the meaning. Filler, hedging, and pleasantries carry no information; strip them and the text gets shorter, faster to read, and no less precise. The style is adapted from the `lite` intensity level of [Caveman](https://github.com/JuliusBrussee/caveman) (MIT): professional but tight, full sentences throughout, no caveman-speak.

This is a one-shot transformation of a target the user points at — not a persistent output mode. After the rewrite, keep answering normally.

## Target

Resolve in this order:

1. **File path(s) given** → rewrite in place with Edit or Write.
2. **Text pasted or quoted in the message** → return the shortened version in chat, nothing else.
3. **No target given** → shorten the most recent substantial prose in the conversation: the last summary, doc, plan, or explanation. If two candidates are equally plausible, ask which one rather than guessing.

## Cut

- Filler adverbs: just, really, basically, actually, simply, quite, very, essentially.
- Pleasantries: "Sure!", "Certainly", "Of course", "Happy to help", "Great question".
- Hedging: "I think", "it seems", "arguably", "might possibly", "in my opinion".
- Throat-clearing openers: "It's worth noting that…" → drop; "In order to…" → "To…"; "The reason X happens is because…" → "X happens because…".
- Restatement — a point already made once, repeated in the next paragraph as a summary.
- Self-reference to the process: "Let me look at…", "I'll now explain…", "As mentioned above".
- Decorative emoji in body text, and tables used for decoration rather than to hold data.
- Long verb phrases: "implement a solution for" → "fix", "make use of" → "use", "perform a check on" → "check", "is responsible for handling" → "handles".

## Keep

- Articles and complete grammatical sentences. This is the lite level — no fragments, no telegraphic style.
- Paragraph and heading structure. A three-section document stays a three-section document.
- Lists as lists. Do not fuse a list into a paragraph to save lines.
- Markdown frontmatter and links.
- Heading text byte-exact, emoji included. A heading is its own anchor; rewording or de-emojifying one breaks every inbound link to it.
- The source language. Never translate; compress the style, not the language.

## Never touch — byte-exact

Code blocks and inline code, shell commands, file paths, identifiers, API and function names, error strings, quotes and citations, numbers and units, legal and license text.

Never drop a negation — not, never, no, only, except. A flipped meaning costs far more than any word saved.

Never invent abbreviations (cfg, impl, req, fn). They tokenize the same as the full word — zero saving — and the reader still has to decode them.

## Do not compress

Leave these passages at full length and shorten the text around them:

- Security warnings.
- Irreversible-action confirmations.
- Ordered multi-step instructions where dropping connectives makes the order ambiguous.
- Any passage whose compressed form is open to a second reading.

## Process

1. Read the target whole before editing. Local rewrites miss the redundancy that spans sections.
2. Rewrite section by section, preserving structure.
3. Re-read the result against the original. Confirm no fact, constraint, negation, number, or unit was lost.
4. Report the before/after word count and one line naming anything deliberately left uncompressed.

Do not narrate the tool calls while working.

## Examples

Before:
> It's worth noting that the component will basically re-render because you're creating a new object reference on each render cycle. I'd recommend using useMemo here.

After:
> The component re-renders because you create a new object reference each render. Wrap it in `useMemo`.

Before:
> Sure! So the way that connection pooling works is that it essentially makes use of a set of already-open connections rather than performing the creation of a brand new connection for every single request that comes in.

After:
> Connection pooling reuses open connections instead of creating a new one per request.

Not compressed — a destructive operation:
> **Warning:** This deletes every row in the `users` table and cannot be undone. Verify a backup exists before running it.

The warning stays as written. Compressing it would trade a real safety margin for four words.

## Boundaries

`/shorten` changes the named target only. It does not change how you talk afterwards, and it does not rewrite code, tests, or config — prose only, including prose inside comments and docstrings when a file is the target.
