# Platform Architecture — Design Proposal v0.2

> **Status:** Proposal — everything here is subject to change.
> **v0.1** was the initial MVP: a single-purpose chat UI on a Pi with a local llama runtime.
> **v0.2** is the vision for what Potato OS becomes next: an agentic platform.

## Vision

Potato OS evolves from a single-purpose chat UI into a local AI operating system — autonomous agents running on Raspberry Pi hardware, powered by shared inference, kept alive by a self-healing supervisor.

The core bet: AI agents need a home. Not a cloud subscription that disappears when the company pivots. Not a laptop that sleeps when you close the lid. A dedicated, always-on, local device that runs your agents 24/7 — in a closet, on a shelf, on your desk. A Pi in a closet is the primary deployment target.

Everything flows from three principles:
- **Local-first** — every cloud-dependent AI device has died (Humane, Limitless, Bee). Local inference is survival insurance.
- **Agents, not chat** — chat is a demo. The real product is autonomous background agents doing work while you sleep.
- **Shared inference is the scarce resource** — on constrained hardware, the model is the bottleneck. The entire architecture is designed around using it sparingly and sharing it fairly.

## Proposed Stack

```
┌──────────────────────────────────────────────────────┐
│                      Potato OS                       │
│                                                      │
│  Mother (supervisor / FDIR daemon)                   │
│  ├── Prime directive: preserve and restore inference │
│  ├── FDIR loop: Detect → Isolate → Recover           │
│  ├── Deterministic mode (default)                    │
│  └── Agentic mode (reasons via Inferno)              │
│                                                      │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐               │
│  │  Chat   │  │  RIG A  │  │  RIG B  │               │
│  │ (demo)  │  │ (no UI) │  │(has UI) │               │
│  └────┬────┘  └────┬────┘  └────┬────┘               │
│       │            │            │                    │
│  ┌────▼────────────▼────────────▼────┐               │
│  │            Inferno                │               │
│  │    (inference orchestrator)       │               │
│  │    local or remote, multi-model,  │               │
│  │    scheduler, network-transparent │               │
│  └───────────────────────────────────┘               │
│                                                      │
│  Dashboard (optional web UI)                         │
│  └── just a window into the system                   │
└──────────────────────────────────────────────────────┘
```

---

## Mother — The Supervisor

Mother is the system's always-on supervisor — a compiled, self-contained, small and efficient daemon that implements a NASA-style FDIR (Fault Detection, Isolation, and Recovery) loop. In CS terms: a supervisor in the Erlang/OTP lineage, purpose-built for a single-board computer running in a closet with no human nearby.

Mother has one prime directive and follows it absolutely.

She will wake subsystems before they're needed. She will reallocate resources without asking. She will bring Inferno back from the dead at 3 AM on a Tuesday. Inference is the priority. All other concerns are secondary.

**Mother ships with Inferno, not with Potato.** She knows nothing about RIGs, the dashboard, or the Potato daemon. She is Inferno's guardian and works standalone — on a Pi running Potato, on a desktop GPU server with no Potato anywhere near it, on any device that runs Inferno. This is a hard architectural boundary.

### Prime Directive

Preserve and restore inference capability. At minimum: one model loaded, Inferno responding to health checks, clients able to make inference requests. Mother does whatever it takes to maintain this.

### FDIR Loop

```
    ┌──────────┐
    │  Detect  │  Is Inferno responding to health checks?
    └────┬─────┘  Is a model loaded and ready?
         │        Can a test inference request complete?
         │
    ┌────▼─────┐
    │  Isolate │  What failed? Process crash? Model corruption?
    └────┬─────┘  Disk full? OOM kill? Network interface down?
         │        GPU/NPU hang? Memory leak?
         │
    ┌────▼─────┐
    │  Recover │  Restart Inferno process
    └────┬─────┘  Redownload corrupted model
         │        Clean disk to free space
         │        Kill runaway processes
         │        Reconfigure and retry
         │
    ┌────▼─────┐
    │  Verify  │  Did the fix work?
    └────┬─────┘  Run the same health checks from Detect.
         │        If yes → return to monitoring.
         │        If no → escalate (try next recovery strategy,
         └──────→   or in the worst case, reboot)
```

### Two Proposed Modes

**Deterministic (default)** — a fixed recovery playbook. Ordered list of recovery strategies, tried in sequence. Predictable, auditable, no surprises. Think systemd restart policies with smarter ordering and dependency awareness. Every action is logged. No intelligence required — this mode works even if Inferno is completely dead.

Example playbook:
1. Health check fails → restart Inferno process
2. Still failing → check disk space, clean temp files if needed, retry
3. Still failing → check if model file exists and is valid, redownload if corrupted
4. Still failing → kill all non-essential processes, reclaim memory, retry
5. Still failing → full system reboot
6. Still failing → enter degraded mode, log error, wait for human

**Agentic** — Mother uses Inferno itself to reason about what's wrong and takes corrective action. She reads system logs, inspects process states, analyzes error patterns, and generates targeted fixes. When Inferno is dead, she falls back to deterministic mode to bring it back — then she has her brain again.

This mode is more powerful but less predictable. It's opt-in, not default. The deterministic playbook is the safety net that's always there.

### What Mother Is Not

- Not a RIG manager — she doesn't know what RIGs are
- Not a network manager — she doesn't manage communications
- Not part of Potato — she ships with Inferno
- Not a general-purpose supervisor — she has exactly one job

---

## Inferno — The Inference Orchestrator

Not just "llama-server with a name." Inferno is a standalone inference service designed to be network-transparent from day one. It's the shared resource that every RIG consumes, and managing it well is the key to running multiple agents on constrained hardware.

### Proposed Capabilities

- **Model management** — load, unload, swap between models, advertise available models to the network
- **Scheduler** — queue and prioritize inference requests from multiple concurrent RIGs. On a Pi with one model loaded, requests are serialized — the scheduler decides who goes next
- **Network-transparent** — runs on the same Pi or on a separate device on the LAN (later internet). The API is the same either way
- **Multi-client** — multiple Potato OS instances can share one Inferno. A beefy desktop running Inferno can serve inference to a fleet of lightweight Pis
- **Service discovery** — advertises itself and available models to the network so Potatoes can find it automatically

### Deployment Scenarios

```
Scenario 1: Self-contained Pi
┌──────────────┐
│  Potato OS   │
│  ┌────────┐  │
│  │Inferno │  │  Inferno runs locally with a small model.
│  │Qwen 3B │  │  Mother guards it on the same device.
│  └────────┘  │  Simple, self-sufficient, no network needed.
└──────────────┘

Scenario 2: Distributed
┌──────────────┐         ┌──────────────┐
│  Potato OS   │         │   Inferno    │
│  (Pi 4 2GB)  │────────▶│  (Desktop)   │
│  no local    │   LAN   │  GPT-OSS 120B│  Potato has no local inference.
│  inferno     │         │  Qwen 30B    │  All Model Steps go to the remote
└──────────────┘         └──────────────┘  Inferno over the network.
                                           Mother guards Inferno on the desktop.

Scenario 3: Hybrid
┌──────────────┐         ┌──────────────┐
│  Potato OS   │         │   Inferno    │
│  ┌────────┐  │         │  (remote)    │
│  │Inferno │  │────────▶│  big models  │  Local Inferno for fast, simple
│  │(local) │  │   WAN   │              │  inference. Remote Inferno for
│  │small   │  │         │              │  heavy reasoning. Potato routes
│  └────────┘  │         └──────────────┘  Model Steps to the right one.
│  local=fast  │
│  remote=smart│
└──────────────┘
```

### Design Principle

Even when Inferno runs locally, RIGs talk to it through the same API as if it were remote. Local → remote becomes a configuration change, not an architecture change. A RIG developed on a laptop against a local Inferno deploys to a Pi talking to a remote Inferno with zero code changes.

---

## Potato — The OS Daemon

Potato is the operating system layer. It manages RIGs, maintains communications, serves the dashboard, and connects to Inferno (local or remote). It's the thing that makes a Pi into an agent platform rather than just a computer with an LLM on it.

### What Potato Manages

- **RIG lifecycle** — loads RIG manifests, starts RIG processes, monitors their health, restarts crashed RIGs. RIGs marked as critical get restarted automatically. Non-critical RIGs can be started/stopped on demand.
- **Communications** — network connectivity, device discovery (mDNS), interagent protocol for Potato-to-Potato communication.
- **Dashboard** — the optional web UI for monitoring and configuration. Serves static assets, proxies to RIG web panels, shows system status.
- **Inferno connection** — manages the connection to one or more Inferno instances (local, remote, or both). Routes Model Steps from RIGs to the appropriate Inferno.

### What Potato Is Not

- Not the inference engine — that's Inferno
- Not the inference guardian — that's Mother
- Not a RIG itself — Potato is the platform that runs RIGs

systemd supervises Potato itself. If the Potato daemon crashes, systemd restarts it. Potato doesn't need an AI supervisor — it's the orchestrator, and a simple restart is enough to recover.

---

## RIGs — The Apps

A **RIG** is an **application framework for AI agents**: a versioned runtime with strict interfaces, an explicit workflow loop, and persistent operational memory so agent work is repeatable, debuggable, and safe to evolve.

RIGs are a universal format — not Potato-specific. A RIG can run on Potato, on a laptop, on a server, in CI. Potato is just a particularly good runtime for them because it has Inferno, always-on hardware, and lifecycle management built in.

We assume RIGs will be developed by agentic development — agents building, testing, and evolving RIGs — as a first-class workflow. The framework is designed for that from day one.

### The Mental Model

- **Agent** = the model (brains) + harness (hands)
- **OS/environment** = the job site (files, network, APIs)
- **RIG** = the machine the agent operates

The agent *could* improvise a one-off solution each time, but a RIG is pre-built and hardened: faster, more reliable, and reusable across runs. Like an excavator vs digging with your hands.

### Why RIGs Exist

Most agent frameworks give the model tools and say "figure it out." This works for demos but fails in production because:
- The model takes different paths each time (non-reproducible)
- Failures are silent (the model just tries something else)
- There's no memory between runs (cold start every time)
- Every action requires an inference call (expensive on constrained hardware)

RIGs solve all four problems.

### The Five Layers

**1. Contract Layer — strict inputs and outputs**

Every step in a RIG has typed JSON schemas for its inputs and outputs. No free-form prose driving tools. When the model prepares input for a tool, it must output schema-validated JSON. If it doesn't match, the step fails loudly with a schema error instead of silently producing garbage.

This makes behavior predictable and failures explicit. You can look at a failed run and see exactly which step broke and why — the schema violation tells you.

**2. Orchestration Layer — the workflow protocol**

Work runs as an explicit workflow of two step types:

**Model Steps (MS)** — invoke the model for intelligence. Brainstorm ideas, make decisions, rank options, judge quality, generate plans. These are the expensive steps that hit Inferno.

**Tool Steps (TS)** — run deterministic code. Query a database, check DNS, run tests, edit files, call an API, parse a response. These are fast, free, and predictable. Same inputs always produce the same outputs.

**The design principle: use Tool Steps for as much as possible. Model Steps only when you genuinely need intelligence.**

A typical workflow: `MS (brainstorm) → TS (check reality) → TS (filter results) → TS (format data) → MS (rank and decide) → TS (apply the decision)`. Two Inferno calls instead of twenty. On a Pi sharing Inferno between multiple RIGs, this is the difference between "works" and "doesn't work."

Each step returns a standard JSON envelope:
```json
{
  "step_id": "check_availability",
  "type": "TS",
  "result": { "available": ["example.com", "example.io"] },
  "next": { "mode": "model", "step_id": "rank_domains" }
}
```

Steps chain explicitly — a Tool Step can chain directly to another Tool Step, or request a Model Step when it needs intelligence. The workflow graph is deterministic and inspectable.

**Lifecycle:** `start()` → initialize state. `step()` → run the next MS or TS. `get_state()` → inspect progress. `finish()` → finalize outputs and notes.

**3. Capability Layer — tools behind stable interfaces**

Tools are exposed through stable protocol interfaces instead of ad-hoc shell glue. This keeps capabilities modular, swappable, testable, and versionable. Different harnesses can use the same RIG, and different RIGs can use the same tools.

**4. State and Learning Layer — persistent operational notes**

Agents are stateless. They forget everything between runs. A RIG solves this with persistent operational notes:

- **Cold start (first run):** slow, like a human using a new machine for the first time. The agent discovers the real path through trial and error — tool ordering, retries, environment quirks, permission gotchas, machine-specific constraints.
- **Run notes:** the RIG stores those discoveries as structured operational notes. Not chat transcripts — structured, queryable knowledge about what worked and what didn't.
- **Warm start (later runs):** a new agent loads those notes and starts experienced, skipping the mistakes. The RIG learns across runs even though the agent is stateless.
- **Reality still wins:** notes are acceleration hints. Live tool outputs and checks are always the source of truth each run. Stale notes get overridden by fresh observations.

This is particularly powerful for Potato: a proven RIG deployed to a new Pi carries its operational notes with it. First run on new hardware might discover Pi-specific quirks and add those to the notes. Every subsequent run benefits.

**5. Observability and Governance Layer — debuggable by default**

Every run emits structured logs so you can answer:
- What tools ran, with what inputs, and what they returned
- What changed (diffs, artifacts, side effects)
- What the model decided and why (key decision points with reasoning)
- Where time was spent (which steps were slow, which Model Steps were expensive)

Failures surface as contract/schema violations rather than silent behavior changes. When a RIG breaks, you can trace the exact step, see the exact input that violated the schema, and understand why.

### Versioning and Evolution

A RIG lives in a git repo with two branches:
- **`main`** — maintainer upstream. Updates and improvements come from here.
- **`for_agent`** — agent/user working branch. The agent can change anything: tools, code, schemas, `rig.md`, config.

Updates arrive by merging `main` into `for_agent`. Customizations that prove generally useful can be promoted upstream via PR. Rollback is `git checkout main`.

### The Manifest: `rig.md`

Every RIG has a `rig.md` that serves as both manifest and documentation:
1. **Workflow overview** — one paragraph explaining what the RIG does
2. **Step catalog** — table of all steps with types, schemas, and chaining
3. **Flow graph** — visual representation of the workflow
4. **Schemas** — links to JSON schemas for each step's inputs and outputs

This file is readable by humans and parseable by agents. It's the contract between the RIG and anything that runs it.

---

## Dashboard — The Window

The web UI is not the system — it's a window into it. Everything works without it. A Pi in a closet running RIGs headlessly is the primary use case. The dashboard is for when a human wants to check in.

### What the Dashboard Shows

- **System status** — hardware metrics (CPU, memory, temperature, storage), network status, uptime
- **Inferno status** — loaded models, health, queue depth, connected clients, active Model Steps
- **Mother status** — current FDIR state, last recovery action, mode (deterministic/agentic)
- **RIG status** — all running RIGs, their current step, progress, last output, health
- **RIG panels** — mount/unmount individual RIG web panels for RIGs that have a UI (most won't)
- **Configuration** — settings, model management, RIG management, interagent protocol peers

### Design Principle

The shell knows RIG **metadata** (name, icon, status, current step) but never reaches into RIG internals. RIGs push status updates through a defined protocol. This is the Chrome tab architecture pattern — the browser manages tabs using only metadata, never page content.

---

## Interagent Protocol (Future)

The protocol layer for Potato-to-Potato communication. Potatoes discover each other, delegate work, share Inferno instances, and potentially transact.

### Two Proposed Modes

**Trusted hierarchy** — for your own devices on your own network. One Potato delegates scoped authority to another: "run these RIG steps using your Inferno, here are the inputs, return the results." Trust is established by network membership and shared keys. This is how a fleet of Pis on a home network would cooperate.

**Open market** — for broader, less-trusted networks. Potatoes advertise available Inferno capacity and capabilities. Other Potatoes can bid on work, negotiate terms, and execute RIG steps for payment. Trust is established through reputation and crypto-backed settlement.

### Building Blocks Under Evaluation

- **Transport:** mDNS/DNS-SD for LAN discovery, HTTP/WebSocket for messaging
- **Identity:** UCAN-style capability delegation for scoped authority
- **Negotiation:** Contract Net / bidding model for open market
- **Settlement:** Crypto-backed escrow and payment (future extension point, not v1)

### Connection to the Architecture

The interagent protocol connects naturally to the rest of the stack:
- **Inferno** is already network-transparent — one Potato using another's Inferno is literally the first delegation use case
- **RIG step envelopes** (typed JSON in, typed JSON out) are a natural wire format for delegated work
- **Mother** on each device independently guards its own Inferno — the protocol doesn't change her job

---

## The Supervision Chain

Each layer supervises the one below it with the appropriate level of intelligence:

```
systemd (PID 1)
│
│   "Is the process alive?"
│   Dumb, reliable. Restart loop. Been doing this since 2010.
│
├── Inferno + Mother
│   │
│   │   Mother: "Is inference healthy?"
│   │   Smart. FDIR loop. Diagnoses problems.
│   │   Deterministic playbook or agentic reasoning.
│   │   Compiled, self-contained, ships with Inferno.
│   │
│   └── llama-server / inference runtime
│       Models, KV cache, request queue
│
└── Potato daemon
    │
    │   "Are RIGs running? Are comms up?"
    │   Moderate intelligence. Restarts crashed RIGs.
    │   Manages network and discovery.
    │   Python/FastAPI, supervised by systemd.
    │
    ├── RIG: chat (demo)
    ├── RIG: weather-briefing (headless)
    ├── RIG: home-monitor (has web panel)
    └── Dashboard (web UI)
```

Why this layering works:
- systemd is always there, always works, never confused. It's the bedrock.
- Mother is specialized — she only understands inference, but she understands it deeply. She can survive Potato crashing.
- Potato is the generalist — it manages everything else. If it crashes, systemd restarts it and RIGs resume.
- Each layer can fail independently without taking down the layers above it. A crashed RIG doesn't kill Potato. A crashed Potato doesn't kill Inferno. A crashed Inferno gets restored by Mother.

---

## Patterns to Steal

Proven patterns from existing systems that directly apply to this architecture.

| Pattern | Source | What to steal |
|---------|--------|---------------|
| LLM syscall abstraction + scheduler | AIOS (COLM 2025) | RIGs don't talk to the model directly — Model Steps are dispatched and scheduled by the platform |
| Sidecar supervisor with behavioral memory | VIGIL (arxiv:2512.07094) | Mother watches system health, builds a persistent model with decay, emits targeted fixes — not just restart |
| Hub-and-spoke with message queue | llama-deploy | Control plane routes Model Steps, message queue decouples RIGs from inference execution |
| P2P distributed inference | LocalAI / exo | Automatic node discovery, inference across network devices, no master-worker hierarchy |
| 4-tier self-healing | OpenClaw | systemd restart → watchdog health check → AI diagnosis + repair → human escalation |
| Dual-model (fast + smart) | Max Headbox | Small model for quick Tool Step guidance, bigger model for complex Model Steps — manage latency on constrained hardware |
| Plan-Execute-Verify loop | Autonomic Computing (arxiv:2407.14402) | Safe remediation with rollback — detect, reason, act, verify the fix worked |
| Agent OS kernel with sandbox isolation | OpenFang | Agents as OS-level processes, sandboxed execution, typed message channels, single-binary deployment |
| Localhost OpenAI-compatible API | Jan.ai / LM Studio / Ollama | Standard interface for all RIGs to consume inference — the `/v1/chat/completions` contract |
| Command deny-list + human escalation | Rampart | Safety guardrails for agentic mode — deny dangerous commands, escalate to human for high-risk actions |

### What Nobody Does Yet

No existing project combines all five of these on Pi-class hardware:

1. OS-level multi-agent orchestration with structured workflows
2. Owned/shared inference engine with scheduling
3. Network-transparent inference (local or remote)
4. Self-healing AI supervisor
5. Runs on a Raspberry Pi

That's the gap.

---

## Where We Are Today

| Component | v0.1 (current MVP) | v0.2 (this proposal) |
|-----------|--------------------|-----------------------|
| Mother | Doesn't exist. systemd restarts the service | Compiled FDIR supervisor, ships with Inferno |
| Inferno | llama-server subprocess, managed by runtime_state.py | Standalone orchestrator, multi-model, multi-client, network-discoverable |
| RIGs | Chat hardwired into shell (partially extracted in #144) | Universal agent app framework with MS/TS workflows, persistent notes, strict contracts |
| Potato | FastAPI monolith serving chat + API + status | OS daemon managing RIG lifecycles, comms, dashboard |
| Dashboard | Shell + chat monolith | Thin shell showing RIG/Inferno/Mother status, mounting RIG panels |
| Interagent | Doesn't exist | Potato-to-Potato delegation, discovery, and negotiation protocol |

---

## Open Questions

These are intentionally unresolved — the proposal needs input before they're decided.

- **RIG process model** — each RIG as a separate Python process? How do they communicate with Potato? Unix sockets for local, HTTP for network-crossing?
- **Inferno API** — is OpenAI-compatible `/v1/chat/completions` the right interface, or does Inferno need its own protocol with scheduling, priority, and model selection?
- **Mother's deterministic playbook** — what are the exact recovery steps and their ordering?
- **RIG-to-Inferno contract** — how does a Model Step express what it needs? Capability requests ("I need vision") vs model requests ("I need Qwen 3B") vs resource requests ("I need 64k context")?
- **Interagent protocol shape** — thin Potato-specific protocol, layered hierarchy + market, or existing ecosystem adaptation?
- **Security model** — how does remote Inferno authenticate clients? How does agentic Mother scope her access? How are RIG permissions declared and enforced?
- **Build sequencing** — what do we build first?
