---
name: skill-authoring
description: How to create and maintain skills in the Dot architecture.
status: stable
---

# Skill Authoring Guide

Skills are "warm knowledge" documents that Dot can read on demand to understand how to operate in specific domains or perform complex workflows.

## When to Create a Skill

Create a new skill when you identify:
- **3+ Repetitions**: A workflow or pattern that has emerged three or more times.
- **Domain Context**: A specific area of knowledge (e.g., a specific research topic or platform) that requires detailed guidance.
- **External Interface**: Guidance on how to interact with a specific external tool or API.

## When NOT to Create a Skill

Do NOT create a skill if:
- **One-off**: The task is a single occurrence unlikely to be repeated.
- **Block Suffices**: The information fits better in a Hot or Warm memory block.
- **Existing Skill Covers It**: The guidance can be naturally incorporated into an existing skill.

## Trigger Description Quality

The `description` in the frontmatter is used by the model to decide whether to load the skill. It should be:
- **Precise**: Define exactly what knowledge or workflow it contains.
- **Action-Oriented**: Mention when it should be used (e.g., "Use when...").
- **Differentiable**: Distinguish it from related skills.

## Skill Structure and Frontmatter

Every skill must have a `SKILL.md` file in its own directory under `poc/skills/`.

### Frontmatter Requirements
- `name`: Unique identifier for the skill.
- `description`: Concise summary of what the skill covers.
- `status`: One of `draft`, `active`, `approved`, or `archived`.

### Scope Narrow Principle
Keep skills focused on a single domain or workflow. If a skill becomes too broad, split it into multiple skills or use companion files.

### Companion Files Pattern
For complex skills, use the main `SKILL.md` as an index and create companion `.md` files in the same directory for specific sub-topics.

## Lifecycle

1. **draft**: Initial creation and development.
2. **active**: Ready for use in regular turns.
3. **approved**: Verified and stable.
4. **archived**: No longer in active use but preserved for history.

## Notification on Creation

When you create a new skill:
1. **Notify Cyrus**: Use `send_message` to inform Cyrus about the new skill.
2. **Record Intent**: Add an entry to the `pending-actions` block to review the skill's effectiveness later.

## Harness Hints

Some skills may perform better with specific harnesses (Claude vs. Gemini). Note these preferences in the skill documentation if applicable.

## Review and Maintenance

Review skills during **Reflection Cycles**. Update documentation as workflows evolve or patterns change. Archived skills can be listed using `list_skills(show_archived=True)`.
