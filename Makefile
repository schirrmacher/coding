SKILLS_DIR := $(HOME)/.claude/skills
REPO_SKILLS := $(shell find $(CURDIR)/skills -mindepth 1 -maxdepth 1 -type d)
SKILL_NAMES := $(notdir $(REPO_SKILLS))

all:
	@mkdir -p $(SKILLS_DIR)
	@for name in $(SKILL_NAMES); do \
		rm -f "$(SKILLS_DIR)/$$name"; \
		ln -s "$(CURDIR)/skills/$$name" "$(SKILLS_DIR)/$$name"; \
		echo "$$name → $(SKILLS_DIR)/$$name"; \
	done
