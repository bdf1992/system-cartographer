# Host environment mappings

Treat these as discovery hints, never universal paths. Confirm visibility and authority
before reading anything outside the target root.

| Host family | Likely local evidence | Questions to resolve |
|---|---|---|
| ChatGPT Work / Codex | workspace files, `AGENTS.md`, `.agents/`, `.codex/`, attached or materialized files, exposed apps/tools | Which workspace roots are writable? Are prior conversations or connected apps actually exposed to this run? |
| Claude Code | repo `CLAUDE.md`, `.claude/agents/`, `.claude/skills/`, `.claude/commands/`, settings and declared MCP config | Are project transcripts authorized evidence? Which home-level files are in scope? |
| Ollama or local harness | harness config, model manifest, prompt templates, tool router, local state/store paths | Is Ollama only inference, or also the host? Which wrapper owns tools, memory, and approval? |
| Grok / xAI API harness | application source, xAI request configuration, tool definitions, orchestration state | Which application—not the model—owns memory, tools, and evidence? |
| Generic API/CI worker | container/workspace, environment contract, workflow files, logs and artifacts | Is the run ephemeral? Which artifacts survive and where may output be written? |

Do not infer capability from product branding. For example, an Ollama model behind an
agent framework may have rich tools, while the same model behind a bare completion API
has none. Record the framework as host, Ollama as provider/runtime, and each tool as a
capability with separate authority.

Use the environment descriptor and a run-local registry overlay for additional host
detail; do not make a host's private paths part of the maintained core.
