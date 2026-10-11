.DEFAULT_GOAL := all

REPO_SKILLS := $(shell find $(CURDIR)/skills -mindepth 1 -maxdepth 1 -type d)
SKILL_NAMES := $(notdir $(REPO_SKILLS))

CLAUDE_SKILLS_DIR := $(HOME)/.claude/skills
# .agents is shared by Codex and OpenCode; Claude keeps its own links.
AGENTS_SKILLS_DIR := $(HOME)/.agents/skills
SHARED_SKILL_DIRS := $(CLAUDE_SKILLS_DIR) $(AGENTS_SKILLS_DIR)

OPENCODE_SKILLS_DIR := $(HOME)/.config/opencode/skills
OPENCODE_COMMANDS_DIR := $(HOME)/.config/opencode/commands
OPENCODE_COMMAND_MARKER := <!-- Installed as an OpenCode command by the skills Makefile. -->
GITCONFIG_PATH := $(CURDIR)/git/gitconfig
NANORC_PATH := $(CURDIR)/nano/nanorc
SANDBOX_DIR := $(CURDIR)/sandbox

.PHONY: all install install-skills install-opencode-commands \
        install-git install-nano \
        install-shell install-sandbox

# Installation touches shared user settings; keep the listed order under make -j.
.NOTPARALLEL: all install

all: install-skills install-opencode-commands \
     install-git install-nano \
     install-shell install-sandbox
	@echo ""
	@if [ -n "$$ZSH_VERSION" ] || [ "$$SHELL" = "/bin/zsh" ]; then \
		echo "Run: source ~/.zshrc"; \
	elif [ -n "$$BASH_VERSION" ] || [ "$$SHELL" = "/bin/bash" ]; then \
		echo "Run: source ~/.bashrc"; \
	fi

install: all
	@echo "install complete (aliases and wrappers apply to new shells)"

install-skills:
	@for skill_dir in $(SHARED_SKILL_DIRS); do \
		mkdir -p "$$skill_dir"; \
		for name in $(SKILL_NAMES); do \
			rm -rf "$$skill_dir/$$name"; \
			ln -s "$(CURDIR)/skills/$$name" "$$skill_dir/$$name"; \
			echo "$$name → $$skill_dir/$$name"; \
		done; \
	done

# OpenCode uses the Agents directory; remove duplicate links from older installs.
	@for name in $(SKILL_NAMES); do \
		legacy_skill="$(OPENCODE_SKILLS_DIR)/$$name"; \
		[ -L "$$legacy_skill" ] || continue; \
		rm -f "$$legacy_skill"; \
		echo "removed duplicate $$legacy_skill"; \
	done

# Command copies make skills visible in OpenCode's default slash autocomplete.
install-opencode-commands:
	@mkdir -p "$(OPENCODE_COMMANDS_DIR)"
	@set -e; for name in $(SKILL_NAMES); do \
		skill_file="$(CURDIR)/skills/$$name/SKILL.md"; \
		command_file="$(OPENCODE_COMMANDS_DIR)/$$name.md"; \
		if [ -e "$$command_file" ] && [ ! -L "$$command_file" ] \
			&& ! grep -qF '$(OPENCODE_COMMAND_MARKER)' "$$command_file"; then \
			echo "$$command_file exists and is not managed by this installer; skipping"; \
			continue; \
		fi; \
		cp "$$skill_file" "$$command_file.tmp"; \
		printf '\n%s\n' '$(OPENCODE_COMMAND_MARKER)' >> "$$command_file.tmp"; \
		mv "$$command_file.tmp" "$$command_file"; \
		echo "$$name → $$command_file"; \
	done

install-git:
	@rm -f "$(HOME)/.gitignore"
	@ln -s "$(CURDIR)/git/gitignore" "$(HOME)/.gitignore"
	@echo ".gitignore → $(HOME)/.gitignore"
	@git config --global --get-all include.path | grep -qF "$(GITCONFIG_PATH)" \
		|| git config --global --add include.path "$(GITCONFIG_PATH)"
	@echo ".gitconfig includes $(GITCONFIG_PATH)"

install-nano:
	@rm -f "$(HOME)/.nanorc"
	@ln -s "$(NANORC_PATH)" "$(HOME)/.nanorc"
	@echo ".nanorc → $(HOME)/.nanorc"

# Keep OpenCode from scanning duplicate Claude links.
install-shell:
	@for shell_rc in $(HOME)/.bashrc $(HOME)/.zshrc; do \
		[ -f "$$shell_rc" ] || continue; \
		grep -qF "alias g=git" "$$shell_rc" || echo "alias g=git" >> "$$shell_rc"; \
		echo "alias g=git → $$shell_rc"; \
		grep -qF "export OPENCODE_DISABLE_CLAUDE_CODE_SKILLS=1" "$$shell_rc" \
			|| echo "export OPENCODE_DISABLE_CLAUDE_CODE_SKILLS=1" >> "$$shell_rc"; \
		echo "OPENCODE_DISABLE_CLAUDE_CODE_SKILLS=1 → $$shell_rc"; \
	done

install-sandbox:
	@$(SANDBOX_DIR)/bin/sandbox_wrappers

.PHONY: install-apps

install-apps:
	@python3 $(SANDBOX_DIR)/lib/install_apps.py
	@$(MAKE) install-sandbox
