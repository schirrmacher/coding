CLAUDE_SKILLS_DIR := $(HOME)/.claude/skills
OPENCODE_SKILLS_DIR := $(HOME)/.config/opencode/skills
SKILL_DESTS := $(CLAUDE_SKILLS_DIR) $(OPENCODE_SKILLS_DIR)

REPO_SKILLS := $(shell find $(CURDIR)/skills -mindepth 1 -maxdepth 1 -type d)
SKILL_NAMES := $(notdir $(REPO_SKILLS))

# Output styles are Claude Code only; opencode has no equivalent
OUTPUT_STYLES_DIR := $(HOME)/.claude/output-styles
OUTPUT_STYLE_NAMES := $(notdir $(wildcard $(CURDIR)/output-styles/*.md))

# Symlinking a style only offers it; this key is what selects it in every project
CLAUDE_SETTINGS := $(HOME)/.claude/settings.json
DEFAULT_OUTPUT_STYLE := Plain

GITCONFIG_PATH := $(CURDIR)/git/gitconfig
NANORC_PATH := $(CURDIR)/nano/nanorc

all:
# Symlink every skill into each tool's skills dir
	@for dest in $(SKILL_DESTS); do \
		mkdir -p "$$dest"; \
		for name in $(SKILL_NAMES); do \
			rm -rf "$$dest/$$name"; \
			ln -s "$(CURDIR)/skills/$$name" "$$dest/$$name"; \
			echo "$$name → $$dest/$$name"; \
		done; \
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

# Shell: alias g=git in whichever rc files exist
	@for rc in $(HOME)/.bashrc $(HOME)/.zshrc; do \
		if [ -f "$$rc" ]; then \
			grep -qF "alias g=git" "$$rc" || echo "alias g=git" >> "$$rc"; \
			echo "alias g=git → $$rc"; \
		fi; \
	done

	@echo ""
	@if [ -n "$$ZSH_VERSION" ] || [ "$$SHELL" = "/bin/zsh" ]; then \
		echo "Run: source ~/.zshrc"; \
	elif [ -n "$$BASH_VERSION" ] || [ "$$SHELL" = "/bin/bash" ]; then \
		echo "Run: source ~/.bashrc"; \
	fi
