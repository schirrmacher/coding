---
name: weird
description: Rewrite wording that obscures its point through strange word choices, slang, forced metaphors, awkward idioms, or an unsuitable register. Use when text sounds weird, unnatural, overly clever, vague, or hard to understand and the user wants clearer phrasing without changing the intended meaning.
---

# Weird

Rewrite oddly formulated prose so its point is immediate.

## Target

Resolve the target in this order:

1. Use the file or passage the user names.
2. Otherwise, use text pasted or quoted in the request.
3. If the user only says that something "sounds weird," use the most recent substantial prose in the conversation.
4. Ask for the target when more than one candidate is plausible.

Edit a named file in place. Return a rewritten passage directly in chat.

## Method

1. Infer the sentence's intended point from its surrounding context.
2. Find wording that makes that point harder to recover:
   - slang or an internet expression that does not suit the audience;
   - a rare, invented, or surprising word where a familiar one is more exact;
   - a forced metaphor, joke, or idiom that the reader must decode;
   - vague language that gestures at the point instead of stating it;
   - an abrupt shift in tone or level of formality;
   - awkward syntax caused by choosing a striking formulation over a clear one.
3. Replace the formulation with direct, familiar, specific language.
4. Read the result in context. Preserve the claim, emphasis, and source language.
5. If the original has two plausible meanings, do not guess. State the ambiguity and ask what the author means.

Prefer the smallest rewrite that makes the point clear. Repair the affected phrase or sentence before rewriting a whole paragraph.

## Preserve

- Technical terms, project vocabulary, and proper names used correctly.
- Deliberate voice when readers can understand it without extra decoding.
- Facts, qualifications, negations, examples, and logical relationships.
- Markdown structure, links, code, commands, paths, identifiers, quoted text, and citations.

Do not shorten merely for brevity, flatten all personality, change the author's position, or add an explanation the source does not support.

## Output

Give the rewritten text without a preamble. Add a short note only when meaning remains ambiguous or a potentially deliberate expression needs the user's decision.

For file edits, report the file changed and summarize the unclear formulations replaced.

## Examples

> Let's yeet the old compatibility layer once clients catch up.

becomes:

> Remove the old compatibility layer once clients have upgraded.

> The parser spelunks the response for a usable identifier.

becomes:

> The parser searches the response for a usable identifier.

> The proposal is kind of giving temporary fix energy.

is ambiguous. Ask which weakness makes the proposal seem temporary instead of inventing one.
