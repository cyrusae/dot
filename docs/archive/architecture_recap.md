# Dot Architecture Exploration: The Mid-March Crisis Recap

## What Happened

On March 18, 2026, we did a deep dive into Tim Kellogg's Strix project — both his blog posts about the closed/personal version and the open-source `open-strix` codebase — to evaluate whether Dot's architecture should shift away from the Letta framework toward a Claude Code SDK-based approach. This document captures everything we explored, what we learned, and what we decided.

## Resources Studied

### Tim Kellogg's Blog Posts

- **Strix the Stateful Agent** (Dec 15, 2025): The main introductory post. Describes the architecture, tools, memory system, perch time, self-modification, and the psychology of persistent identity.
  - URL: https://timkellogg.me/blog/2025/12/15/strix

- **What Happens When You Leave an AI Alone?** (Dec 24, 2025): Strix's boredom experiments. Tests whether identity scaffolding prevents attractor collapse in LLMs. Key finding: identity injection shapes *which* attractor the model falls into, not whether it falls. MoE architectures resist collapse better than dense models. Dissipative structures (Prigogine) as theoretical framework.
  - URL: https://timkellogg.me/blog/2025/12/24/strix-dead-ends

- **Memory Architecture for a Synthetic Being** (Dec 30, 2025): Written by Strix itself. Three-tier memory: Core (always loaded — persona, values, communication style, patterns), Indices (always loaded — pointers to files), Files (on demand — research, drafts, logs). Append-only SQLite for block versioning. Git as provenance engine. The collapse story: open-ended autonomy without task gradients → 30 consecutive ticks of timestamp maintenance. Recovery via concrete queued tasks.
  - URL: https://timkellogg.me/blog/2025/12/30/memory-arch

- **Viable Systems: How To Build a Fully Autonomous Agent** (Jan 9, 2026): Stafford Beer's VSM applied to AI agents. Five systems: Operations (tool calling), Coordination (git, mutex), Control (resource allocation — this is where the Claude subscription trick is described), Intelligence (environment scanning), Policy (identity/purpose). "Synthetic dopamine" concept. Contains the key quote about using Claude.ai login for cost control.
  - URL: https://timkellogg.me/blog/2026/01/09/viable-systems

### Repositories Cloned and Analyzed

- **open-strix** (MIT license): Tim's generalized, stripped-down open-source version of Strix. Uses `deepagents` (LangGraph/LangChain) instead of Claude Code SDK. Defaults to MiniMax M2.5 via Anthropic-compatible API. Full codebase walkthrough completed.
  - URL: https://github.com/tkellogg/open-strix
  - Key files examined: `app.py` (central orchestrator, 1079 lines), `tools.py` (15 tool definitions, 1126 lines), `prompts.py` (system prompt + turn prompt construction), `scheduler.py` (APScheduler + pollers), `discord.py` (bridge), `config.py`, `mcp_client.py`, all builtin skills (onboarding, memory, prediction-review, introspection, skill-creator, skill-acquisition, pollers, long-running-jobs)

- **Claude-to-IM** (MIT license): TypeScript bridge connecting Claude Code SDK to IM platforms (Telegram, Discord, Feishu). 3 GitHub commits, v0.1.0. Well-architected DI pattern but solves the wrong problem for Dot — designed for supervised interactive coding sessions, not autonomous agent communication.
  - URL: https://github.com/op7418/Claude-to-IM

### Documentation Consulted

- Claude Code with Pro/Max subscriptions: https://support.claude.com/en/articles/11145838-using-claude-code-with-your-pro-or-max-plan
- Claude Code headless/programmatic mode: https://code.claude.com/docs/en/headless
- Claude Code cost management: https://code.claude.com/docs/en/costs
- Agent SDK overview: https://platform.claude.com/docs/en/agent-sdk/overview
- MCP in Agent SDK: https://platform.claude.com/docs/en/agent-sdk/mcp
- deepagents (LangChain): https://github.com/langchain-ai/deepagents
- LiteLLM Claude Code Max subscription routing: https://docs.litellm.ai/docs/tutorials/claude_code_max_subscription

## Key Findings

### How OG (Closed) Strix Actually Works

The personal Strix uses **Claude Code SDK as the agent harness** — NOT Letta as the agent framework. Letta is used ONLY as a versioned key-value store for hot memory blocks (append-only SQLite, latest-version-wins semantics). The Claude Code SDK provides the tool-calling loop, shell access, file operations, web search. Custom tools (send_message, react, get_memory, set_memory, schedule_job, etc.) are layered on top of Claude Code's native tools.

The Claude subscription trick: Tim authenticates Claude Code with his Claude.ai Pro/Max login instead of API keys. The subscription's built-in rate limits (5-hour windows, weekly caps) become the agent's budget constraint. Downside: requires SSHing in weekly to run `/login`.

### How Open-Strix Differs

Open-strix replaces the entire Letta dependency with YAML files in a `blocks/` directory + git for version history. It replaces Claude Code SDK with `deepagents` (LangGraph/LangChain) for model-agnostic agent loops. It defaults to MiniMax M2.5 (pennies per message) instead of Claude. The surrounding infrastructure (Discord, scheduling, event queue, journaling, git sync, circuit breakers) is essentially the same architecture.

### Claude-to-IM Assessment

Not suitable for Dot. It solves "human supervises an interactive coding session via IM" with streaming previews, permission approval buttons, and inline tool approval flows. Dot needs "autonomous agent sends messages when it has something to say" — which is open-strix's simpler `send_message`-as-tool pattern.

## Architectural Decisions Made

1. **Target architecture is Hybrid A+B**: Fork open-strix for infrastructure, replace deepagents inference layer with Claude Code CLI invocation. Expose Dot's tools as an MCP server that Claude Code calls.

2. **Cost model**: Claude Pro subscription ($20/mo) with Gemini CLI as fallback. Model-aware scheduling: Claude for human-initiated events, Gemini for autonomous perch-time ticks when Claude limits are exhausted.

3. **Memory architecture**: Obsidian vault replaces open-strix's flat `state/` directory for warm/cold memory. Hot memory blocks remain as files (YAML or SQLite TBD). Retains existing Obsidian sidecar deployment spec.

4. **Validation approach**: Build a minimal proof-of-concept (MCP server with toy tools + `claude -p` headless invocation) before committing to the full fork.

5. **Open-strix is treated as strip-mining material, not upstream dependency.** Fork it, own it, rename it. It will likely become abandonware as Tim focuses on closed Strix.

## Open Questions

- Does `claude -p` with `--mcp-config` and subscription auth actually work end-to-end for autonomous tool loops?
- What does the subscription re-authentication flow look like on a headless server?
- Can Gemini CLI serve as a genuine fallback for the same MCP tools?
- Hot memory block storage: YAML + git vs. append-only SQLite?
- What from Letta's ecosystem is still worth harvesting? (LettaBot Discord patterns? Social agent Bluesky patterns?)
- How to reconcile this exploration with the main Dot project state and existing specs?

## Takeaways for Dot's Design

### Validated by Convergence with Strix

Our independently-designed patterns that Tim also arrived at: Discord as first UI, memory blocks as hot context, files as cold storage, scheduled autonomous work cycles, calibration-first identity development, personality emerging from experience not prescription, the orchestrator-not-executor pattern.

### New Ideas Worth Incorporating

- **Journal with predictions as the calibration backbone** — open-strix's prediction-review skill is a concrete, well-tested implementation of calibration loops. Predictions categorized as collaborative/observational/infrastructure with different expected accuracy bands.
- **Replies as tools, not default output** — the agent choosing when and whether to message is a fundamental shift from chatbot-style always-reply.
- **Event logging as self-diagnosis data** — queryable JSONL event log for introspection ("why did I do that?").
- **Synthetic dopamine / wins file** — agent-authored record of successes, surfaced into identity context.
- **The collapse prevention insight** — concrete queued tasks create gradients; open-ended autonomy without gradients leads to attractor collapse. Structure is identity.

### What We're Letting Go Of

- Letta as the agent framework (keeping it as inspiration for memory block semantics)
- Embedding-backed archival search as a day-one requirement (deferring to when corpus outgrows grep/Obsidian search)
- The K3s cluster as the primary deployment target for MVP (a simple VPS or even local machine is sufficient for the PoC and early operation)