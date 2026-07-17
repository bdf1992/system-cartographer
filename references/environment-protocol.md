# Environment negotiation and concern escalation

## Contents

1. Separation of model and host
2. Negotiate before scanning
3. Capability vocabulary
4. Escalate an environmental signal
5. Portability rules

## 1. Separation of model and host

Never use a model name as a proxy for its environment. GPT, Grok, Claude, Gemini,
or a local model may run in a chat surface, an IDE agent, a CI worker, a shell, or a
custom harness. Describe these axes separately:

- **model** — provider and model identity, when declared;
- **host** — the surface orchestrating turns, tools, and approvals;
- **runtime** — Python/OS/process facts;
- **capabilities** — typed operations such as `filesystem.read`, `git.read`,
  `network.fetch`, `conversation.ask`, or `subagents.spawn`;
- **authority** — available, unavailable, restricted, or unknown;
- **roots** — explicit target, evidence, output, and configuration boundaries.

Unknown is a real value. Do not turn absence of evidence into unavailability.

## 2. Negotiate before scanning

Run `scripts/environment_probe.py --root <target> --out environment.json`, then ask
only the unresolved questions it emits. Treat detection as a proposal for the operator
to correct, not as truth. The probe is intentionally local and read-only: it never
tests network access, opens private session stores, or searches a home directory.

Resolve the minimum contract:

1. What is the target root?
2. Which other roots are legitimate evidence?
3. Which roots may receive output?
4. Which tool capabilities exist, and which are restricted?
5. Where does durable memory live, if anywhere?
6. Can the host ask the operator questions during a run?

This phase describes the observation apparatus. It does not reveal target evidence,
so it may precede blind belief elicitation without contaminating it.

Question 2 cannot be fully answered here — before a scan runs, "which other roots are
legitimate evidence" can only be guessed. The scan itself answers it properly: every
run automatically names, classifies, and peeks at path references the target's own
files point outside the declared root (`boundary_pointers` in `patterns.json`; detail
in `references/boundary-protocol.md`). Treat the Phase 0 answer to question 2 as
provisional and revisit it once `boundary_pointers` exists — that is the evidence-backed
version of the same question, not a separate concern.

## 3. Capability vocabulary

Use dotted, vendor-neutral identifiers. Prefer these common forms:

| Capability | Meaning |
|---|---|
| `filesystem.read` / `filesystem.write` | Read or create files within declared roots |
| `git.read` / `git.write` | Inspect or mutate version history |
| `network.fetch` | Retrieve public network resources |
| `conversation.ask` | Ask the operator a blocking question |
| `process.exec` | Run local commands |
| `subagents.spawn` | Delegate isolated work |
| `memory.read` / `memory.write` | Use a durable contextual store |
| `integration.<name>.read|write` | Reach a named external system |

Vendor-specific tool names belong in evidence, not in the capability ID.

## 4. Escalate an environmental signal

Do not immediately add every oddity to the permanent ontology. Move it through four
states:

1. **Signal** — record the observation and why no stable concern currently owns it.
2. **Question** — ask whether it changes what can be observed, reproduced, or handed
   off. If not, leave it as environment metadata.
3. **Provisional concern** — use `scripts/concern_registry.py propose` to create a typed
   descriptor with a question, required capabilities, outputs, and registration
   questions. Store it in the run's overlay registry, not in the skill.
4. **Registered concern** — after at least one real run produces distinct evidence and
   the operator confirms its boundary, validate the overlay and deliberately promote
   it to the maintained registry.

A concern earns registration when it has a distinct question, evidence source,
capability contract, and consequence for replication. Otherwise attach it as a field
to an existing concern. This prevents the registry from becoming an iron taxonomy.

## 5. Portability rules

- Keep the deterministic scan Python-standard-library only.
- Accept registry overlays rather than editing core code for a new concern.
- Never assume Claude paths, OpenAI tools, MCP, or Ollama endpoints.
- Never scan `$HOME`, private transcript stores, or all connected services by default.
- Translate host tools into capabilities; keep raw tool names as provenance.
- If Python is absent, preserve the same environment and concern JSON shapes and run
  the scan through the host's available file/search tools.
