# Dotfiles

Personal dotfiles and Claude Code skills. Run `make` to install.

```sh
make
```

Symlinks skills and gitignore, includes gitconfig. `user.email` stays local.

## Claude Code Skills

| Skill | What it reviews |
|---|---|
| `/mature-dataflow` | Data flow between components, layers, and systems |
| `/mature-interfaces` | Types, API contracts, and module boundaries |
| `/mature-logic` | Separation of concerns, correctness, edge cases |
| `/mature-performance` | Efficiency, resource management, scalability |
| `/mature-testing` | Public API coverage, behavior-driven tests, naming |
| `/deep-copy` | Extract core data structures from a project and embed them |
| `/commit-name` | Generate a short commit message from current changes |
| `/mr-summary` | Generate a concise merge request summary with examples |
| `/handover` | Create a handover doc for another agent to pick up work |

## Git

Aliases, core settings, and a global gitignore. Set your email per machine:

```sh
git config --global user.email "you@company.com"
```
