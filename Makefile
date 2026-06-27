CLAUDE_SKILLS_DIR := $(HOME)/.claude/skills
OPENCODE_SKILLS_DIR := $(HOME)/.config/opencode/skills
SKILL_DESTS := $(CLAUDE_SKILLS_DIR) $(OPENCODE_SKILLS_DIR)

REPO_SKILLS := $(shell find $(CURDIR)/skills -mindepth 1 -maxdepth 1 -type d)
SKILL_NAMES := $(notdir $(REPO_SKILLS))

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
