---
name: deep-copy
description: Analyze a source project's core data structures and embed the minimal structure into the current project. Accepts a local path or a git URL.
user-invocable: true
disable-model-invocation: true
allowed-tools: Read, Grep, Glob, Bash(git clone *), Bash(mktemp *), Bash(rm -rf *), Edit, Write
argument-hint: <path-or-url> [target-scope]
---

Analyze a source project and embed its core data structures into the current project.

`$ARGUMENTS` must include a source (local path or git URL). An optional second argument scopes where to embed in the current project.

## Steps

1. **Resolve source**:
   - If the argument is a URL, clone it into a temp directory (`mktemp -d`).
   - If it's a local path, use it directly.

2. **Explore the source project**:
   - Identify the language, framework, and project layout.
   - Identify naming schemes: casing (camelCase, snake_case, PascalCase), prefixes/suffixes (I-prefix for interfaces, -DTO suffixes, etc.), file naming patterns.
   - Find all core data structures: types, interfaces, models, schemas, enums, constants, config shapes.

3. **Extract the minimal structure**:
   - For each core data structure, capture: name, fields/properties, relationships to other structures.
   - Strip implementation details — keep only the shape, not the logic.
   - Note any patterns: inheritance hierarchies, composition, generics, discriminated unions.

4. **Analyze the current project**:
   - Read existing data structures in scope.
   - Identify naming conventions (casing, prefixes, suffixes), type system, module layout, and import style.

5. **Embed**:
   - Translate source naming schemes to the current project's conventions (e.g. `user_id` → `userId`, `IUser` → `User`).
   - Merge with existing structures — extend rather than duplicate.
   - Place new types in the appropriate module/file following the project's layout.
   - Add necessary imports.

6. **Report**:

   ### Deep Copy Summary

   **Source**: path or URL

   **Structures copied**:
   | Source structure | Embedded as | Location |
   |---|---|---|
   | `SourceType` | `AdaptedType` | `path/to/file` |

   **Adaptations made**: List any renaming, restructuring, or simplification applied.

   **Skipped**: Structures intentionally left out and why.

7. Clean up temp directory if one was created.
