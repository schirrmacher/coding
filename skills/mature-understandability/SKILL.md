---
name: mature-understandability
description: Evaluate the maturity of code readability and naming. Use when reviewing whether code is easy to follow, avoids unnecessary nesting, and uses clear names that convey intent.
user-invocable: true
disable-model-invocation: true
allowed-tools: Read, Grep, Glob
argument-hint: [file-or-scope]
---

Evaluate the maturity of **code understandability** — readability, naming, and structural clarity.

If `$ARGUMENTS` is provided, scope the review to those files or directories.

## Steps

1. **Gather context**: Read the files in scope. Read tests alongside source code to evaluate naming consistency across both.

2. **Scan for readability signals**: For each file or function, note:
   - How many levels of indentation does the deepest path have?
   - Can you understand what a function does without reading its body?
   - Can you understand what a test verifies without reading its assertions?

3. **Audit against these criteria**:

   ### Nesting and control flow
   - Are there deeply nested conditional, error-handling, or loop structures (3+ levels) that could be flattened?
   - Can guard clauses or early returns replace nested conditions?
   - Are there callback chains or continuation patterns that could be simplified with the language's preferred async idiom?
   - Are inline conditional expressions nested or overly complex when a plain conditional block would be clearer?

   ### Naming
   - Do function names describe what they do, not how they do it?
   - Do variable names reveal intent? (descriptive names, not single letters or abbreviations)
   - Are abbreviations avoided unless universally understood in the domain?
   - Are boolean variables and functions named as questions or predicates?
   - Are similar concepts named consistently across the codebase? (not mixing synonyms for the same thing)

   ### Test naming and clarity
   - Do test names describe the behavior being verified? (not just the method name)
   - Is it clear from the test name what scenario is covered? (input condition + expected outcome)
   - Are test names consistent in style across the suite?
   - Can someone reading only the test names understand the contract of the module?

   ### Structural clarity
   - Are functions short enough to read without scrolling?
   - Is related code grouped together, or are related operations scattered?
   - Are magic numbers and strings extracted into named constants?
   - Are complex expressions broken into named intermediate variables that explain the steps?

4. **Produce a report** with this structure:

   ### Understandability Maturity Assessment

   **Status**: One of `Ready`, `Needs Work`, or `Not Ready`

   **Summary**: 1-2 sentences on the state of readability and naming.

   **Issues** (if any): List each issue with:
   - File and line reference
   - The function, variable, or test affected
   - What the problem is and a concrete improvement
   - Severity: `blocking` (must fix) or `suggestion` (nice to have)

   **Recommendation**: Concrete next steps — either "code is clear" or a numbered list of fixes.

5. **Changes table**: End with a compact before/after summary:

   | Before | After |
   |---|---|
   | brief description of current state | what it should become |

6. **If status is "Needs Work"**: Ask the user whether they want you to proceed with the fixes.
