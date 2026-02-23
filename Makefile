SKILLS_DIR := $(HOME)/.claude/skills
REPO_SKILLS := $(shell find $(CURDIR)/skills -mindepth 1 -maxdepth 1 -type d)
SKILL_NAMES := $(notdir $(REPO_SKILLS))
GITCONFIG_PATH := $(CURDIR)/git/gitconfig

all:
	@mkdir -p $(SKILLS_DIR)
	@for name in $(SKILL_NAMES); do \
		rm -f "$(SKILLS_DIR)/$$name"; \
		ln -s "$(CURDIR)/skills/$$name" "$(SKILLS_DIR)/$$name"; \
		echo "$$name → $(SKILLS_DIR)/$$name"; \
	done
	@rm -f "$(HOME)/.gitignore"
	@ln -s "$(CURDIR)/git/gitignore" "$(HOME)/.gitignore"
	@echo ".gitignore → $(HOME)/.gitignore"
	@git config --global --get-all include.path | grep -qF "$(GITCONFIG_PATH)" \
		|| git config --global --add include.path "$(GITCONFIG_PATH)"
	@echo ".gitconfig includes $(GITCONFIG_PATH)"
