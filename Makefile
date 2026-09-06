CLAUDE_SKILLS_DIR := $(HOME)/.claude/skills
OPENCODE_SKILLS_DIR := $(HOME)/.config/opencode/skills
OPENCODE_COMMANDS_DIR := $(HOME)/.config/opencode/commands
OPENCODE_COMMAND_MARKER := <!-- Installed as an OpenCode command by the skills Makefile. -->
# Codex reads ~/.agents/skills as well as ~/.codex/skills; .agents is the shared root
AGENTS_SKILLS_DIR := $(HOME)/.agents/skills
SHARED_SKILL_DIRS := $(CLAUDE_SKILLS_DIR) $(AGENTS_SKILLS_DIR)

REPO_SKILLS := $(shell find $(CURDIR)/skills -mindepth 1 -maxdepth 1 -type d)
SKILL_NAMES := $(notdir $(REPO_SKILLS))

# Output styles are Claude Code only; opencode has no equivalent
OUTPUT_STYLES_DIR := $(HOME)/.claude/output-styles
OUTPUT_STYLE_NAMES := $(notdir $(wildcard $(CURDIR)/output-styles/*.md))

# Symlinking a style only offers it; this key is what selects it in every project
CLAUDE_SETTINGS := $(HOME)/.claude/settings.json
DEFAULT_OUTPUT_STYLE := Plain
DEFAULT_STYLE_FILE := plain.md

# opencode has no output styles, so the same file is loaded via its instructions key
OPENCODE_CONFIG := $(HOME)/.config/opencode/opencode.jsonc

GITCONFIG_PATH := $(CURDIR)/git/gitconfig
NANORC_PATH := $(CURDIR)/nano/nanorc

all:
# Symlink every skill into each tool's skills dir
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

# Symlink every output style into Claude Code's output-styles dir
	@mkdir -p "$(OUTPUT_STYLES_DIR)"
	@for name in $(OUTPUT_STYLE_NAMES); do \
		rm -rf "$(OUTPUT_STYLES_DIR)/$$name"; \
		ln -s "$(CURDIR)/output-styles/$$name" "$(OUTPUT_STYLES_DIR)/$$name"; \
		echo "$$name → $(OUTPUT_STYLES_DIR)/$$name"; \
	done

# Select the default style globally; /output-style only ever sets it per project
	@if command -v jq >/dev/null 2>&1; then \
		[ -s "$(CLAUDE_SETTINGS)" ] || echo '{}' > "$(CLAUDE_SETTINGS)"; \
		jq --arg style "$(DEFAULT_OUTPUT_STYLE)" '.outputStyle = $$style' \
			"$(CLAUDE_SETTINGS)" > "$(CLAUDE_SETTINGS).tmp" \
			&& mv "$(CLAUDE_SETTINGS).tmp" "$(CLAUDE_SETTINGS)"; \
		echo "outputStyle=$(DEFAULT_OUTPUT_STYLE) → $(CLAUDE_SETTINGS)"; \
	else \
		echo "jq not found; set \"outputStyle\": \"$(DEFAULT_OUTPUT_STYLE)\" in $(CLAUDE_SETTINGS) by hand"; \
	fi

# Load the default style as an instruction because OpenCode has no output styles.
# Leave JSONC with comments untouched because jq would discard them.
	@opencode_style="$(CURDIR)/output-styles/$(DEFAULT_STYLE_FILE)"; \
	if ! command -v jq >/dev/null 2>&1; then \
		echo "jq not found; add $$opencode_style to \"instructions\" in $(OPENCODE_CONFIG) by hand"; \
	elif [ -s "$(OPENCODE_CONFIG)" ] && ! jq empty "$(OPENCODE_CONFIG)" >/dev/null 2>&1; then \
		echo "$(OPENCODE_CONFIG) is not plain JSON; add $$opencode_style to \"instructions\" by hand"; \
	else \
		mkdir -p "$$(dirname "$(OPENCODE_CONFIG)")"; \
		[ -s "$(OPENCODE_CONFIG)" ] || echo '{}' > "$(OPENCODE_CONFIG)"; \
		jq --arg p "$$opencode_style" '.instructions = (((.instructions // []) - [$$p]) + [$$p])' \
			"$(OPENCODE_CONFIG)" > "$(OPENCODE_CONFIG).tmp" \
			&& mv "$(OPENCODE_CONFIG).tmp" "$(OPENCODE_CONFIG)"; \
		echo "instructions += $(DEFAULT_STYLE_FILE) → $(OPENCODE_CONFIG)"; \
	fi

# Git: global gitignore, plus include our shared gitconfig
	@rm -f "$(HOME)/.gitignore"
	@ln -s "$(CURDIR)/git/gitignore" "$(HOME)/.gitignore"
	@echo ".gitignore → $(HOME)/.gitignore"
	@git config --global --get-all include.path | grep -qF "$(GITCONFIG_PATH)" \
		|| git config --global --add include.path "$(GITCONFIG_PATH)"
	@echo ".gitconfig includes $(GITCONFIG_PATH)"

# Nano: 80-column wrap
	@rm -f "$(HOME)/.nanorc"
	@ln -s "$(NANORC_PATH)" "$(HOME)/.nanorc"
	@echo ".nanorc → $(HOME)/.nanorc"

# Shell: alias g=git and keep OpenCode from scanning the duplicate Claude links
	@for shell_rc in $(HOME)/.bashrc $(HOME)/.zshrc; do \
		[ -f "$$shell_rc" ] || continue; \
		grep -qF "alias g=git" "$$shell_rc" || echo "alias g=git" >> "$$shell_rc"; \
		echo "alias g=git → $$shell_rc"; \
		grep -qF "export OPENCODE_DISABLE_CLAUDE_CODE_SKILLS=1" "$$shell_rc" \
			|| echo "export OPENCODE_DISABLE_CLAUDE_CODE_SKILLS=1" >> "$$shell_rc"; \
		echo "OPENCODE_DISABLE_CLAUDE_CODE_SKILLS=1 → $$shell_rc"; \
	done

	@echo ""
	@if [ -n "$$ZSH_VERSION" ] || [ "$$SHELL" = "/bin/zsh" ]; then \
		echo "Run: source ~/.zshrc"; \
	elif [ -n "$$BASH_VERSION" ] || [ "$$SHELL" = "/bin/bash" ]; then \
		echo "Run: source ~/.bashrc"; \
	fi
