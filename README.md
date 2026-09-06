# Dotfiles

Personal dotfiles and Claude Code skills. Run `make` to install.

```sh
make
```

Symlinks skills, output styles, and gitignore, includes gitconfig. `user.email` stays local.
Skills land in `~/.claude/skills` and `~/.agents/skills` (Codex and OpenCode). The installer keeps
OpenCode from scanning the duplicate Claude links. Managed OpenCode command copies also land in
`~/.config/opencode/commands`, making every skill visible in the default `/` autocomplete.
OpenCode has no output styles, so `make` adds the same style file to its `instructions` list.
Restart OpenCode after running `make` so it reloads the links.

## Output Styles

Symlinked into `~/.claude/output-styles/`. `make` also sets `outputStyle` in
`~/.claude/settings.json` to `DEFAULT_OUTPUT_STYLE` (currently `Plain`), which
applies in every project. `/output-style` overrides it for one project only.

| Style | What it does |
|---|---|
| `Plain` | States what changed and why in project vocabulary. One fact per sentence, no filler, no unverifiable adjectives, no LLM sentence patterns. |

## Claude Code Skills

| Skill | What it reviews |
|---|---|
| `/mature-dataflow` | Data flow between components, layers, and systems |
| `/mature-interfaces` | Types, API contracts, and module boundaries |
| `/mature-logic` | Separation of concerns, correctness, edge cases |
| `/mature-performance` | Efficiency, resource management, scalability |
| `/mature-testing` | Public API coverage, behavior-driven tests, naming |
| `/deepcopy` | Port a reference codebase into this project, tests-first |
| `/deepspec` | Implement a specification (RFC/standard) into this project, conformance-first |
| `/commit-name` | Generate a short commit message from current changes |
| `/mr-summary` | Generate a concise merge request summary with examples |
| `/handover` | Create a handover doc for another agent to pick up work |
| `/shorten` | Compress a file, pasted text, or prior context — drops what the reader can derive. Levels: `tight` (nothing lost), default, `core` |

## Git

Aliases, core settings, and a global gitignore. Set your email per machine:

```sh
git config --global user.email "you@company.com"
```
