# Soil Health Knowledge Graph — Agentic Builder

> **New to this project?** See [`GUIDE.md`](GUIDE.md) for a full start-to-finish
> walkthrough (install → vLLM setup → run → read results → troubleshooting).

Reads soil-health research papers (PDF/TXT) and builds a **causal knowledge graph**
using three cooperating LLM agents — a **Planner**, a tool-using **Worker**, and a
**Critic** — instead of a fixed sequence of extraction passes.

## Why this is different from a "3-pass pipeline"

The earlier design in this project ran fixed code: Pass A (entities), Pass A
(study context), Pass B (findings per chunk), Pass C (validate/dedup/repair) —
always in that order, always the same number of LLM calls per chunk. That's
multiple LLM calls, but it isn't agentic: the *code* decides what happens next,
never the model.

This version gives the decision-making to the agents themselves:

| Agent | Decides | Via |
|---|---|---|
| **Planner** | The order of work for this specific paper (which chunks matter most, whether study-context needs a wider net) | One structured-output call producing a task queue |
| **Worker** | What to actually look at and extract for a task — including whether to jump to a *different* chunk mid-task if it needs more context, whether an entity already exists, whether a finding needs a follow-up task queued | A ReAct tool-calling loop (`read_chunk`, `search_entities`, `add_entity`, `add_finding`, `get_study_context`, `request_followup_task`, `finish_task`) |
| **Critic** | Whether the graph is good enough, or which specific gaps are worth fixing (missing conditions, broken causal chains, unverified quotes) | A second tool-calling loop over the graph (`list_findings_missing_conditions`, `list_broken_chains`, `verify_quote`, `request_repair`, `approve`) |

The **orchestrator** just runs: `Plan → drain task queue via Worker → Critic
review → (if repairs queued) drain again → Critic review → ...` up to
`MAX_CRITIC_ROUNDS`. That's the only fixed part — a budget, not a script. Every
task the Worker executes, every repair the Critic queues, and every "I need to
look at another chunk" decision comes from the model via tool calls.

```
            ┌───────────┐
            │  Planner  │  one call → task queue (ordered, but not exhaustive)
            └─────┬─────┘
                   ▼
     ┌────────────────────────────┐
     │   Worker (tool loop)       │◄────────────┐  can enqueue its own
     │ read_chunk / search /      │             │  follow-up tasks
     │ add_entity / add_finding   │─────────────┘
     └──────────────┬─────────────┘
                     ▼
            ┌─────────────────┐
            │  Critic (tool    │──► approve → done
            │  loop over graph)│──► request_repair → back to Worker
            └─────────────────┘        (up to MAX_CRITIC_ROUNDS)
```

## Data model

Findings are **reified nodes**, not bare edges — conditions, effect magnitude,
p-value, and evidence quote all live on the finding itself, so causal claims
stay queryable and comparable across papers. See `src/extraction/types.py`.

## Setup

```bash
pip install -e .
cp .env.example .env        # set MODEL to your served model path/name
```

**If you're running vLLM**, tool-calling must be enabled on the server for the
agent loop to work:

```bash
vllm serve /path/to/model \
  --enable-auto-tool-choice \
  --tool-call-parser hermes   # or the parser matching your model family
```

Check vLLM's docs for the right `--tool-call-parser` for your specific model —
this varies by model family (Hermes/Qwen-style, Llama 3.1, Mistral, etc.).
Without this flag the server will ignore the `tools` parameter and the agents
won't be able to call anything.

## Run

```bash
cp your_paper.pdf data/papers/
python run.py --provider vllm --model /models/Gem4 --visualize --eval
```

Watch the console (or `data/output/run_*.log`) — you'll see the Planner's
reasoning, each Worker task and the tools it calls, and the Critic's repair
requests. That transcript is the actual audit trail of the agents' decisions.

## Output

- `data/output/soil_kg.json` — entities, findings, study contexts
- `data/output/soil_kg.html` — interactive PyVis viewer (`--visualize`)
- Quality check (`--eval`): condition coverage, quote presence, flagged findings

## Debugging — seeing exactly what each agent saw and did

There are three layers, from quick glance to full replay:

**1. Console (live, human-skimmable)**
```
16:42:03 INFO src.agents.planner: [planner] Methods and Results carry the causal claims — prioritize those.
16:42:05 INFO src.llm.client: [worker/t_0002] step 1 -> calling: get_study_context
16:42:05 INFO src.llm.client: [worker/t_0002] step 1 tool=get_study_context -> {"geographic_region": "North Florida", ...}
16:42:07 INFO src.llm.client: [worker/t_0002] step 2 -> calling: add_entity, add_entity
16:42:07 INFO src.llm.client: [worker/t_0002] step 2 tool=add_entity -> OK id=mgmt_001 new=True
16:42:11 INFO src.agents.critic: [critic] reviewing graph (round 1)
16:42:12 INFO src.llm.client: [critic/critic_round_1] step 1 tool=list_broken_chains -> [{"finding_id": "find_003", ...}]
16:42:13 INFO src.llm.client: [critic/critic_round_1] step 2 tool=request_repair -> Queued repair task t_0000_cr.
```
Run with `--log-level DEBUG` to also see the **full prompt text** sent to each
agent and the raw model output, not just the tool-call summary line.

**2. File log** — `data/output/run_*.log` always has DEBUG-level detail
regardless of console `--log-level`, so you can `grep` it after the fact.

**3. Agent trace (JSONL, full fidelity)** — `data/output/traces/<paper>.jsonl`.
One line per event: `agent_start`, `assistant_turn` (model's reasoning +
requested tool calls), `tool_call` (args + result), `agent_end`. This is the
one to use when you need to know *exactly* why a finding looks wrong.

Read it with the built-in viewer instead of raw `cat`:
```bash
# everything, in order
python -m src.utils.replay_trace data/output/traces/soil1.txt.jsonl

# just one task (e.g. the chunk that produced a bad finding)
python -m src.utils.replay_trace data/output/traces/soil1.txt.jsonl --task t_0003

# just the critic's reasoning across all its rounds
python -m src.utils.replay_trace data/output/traces/soil1.txt.jsonl --agent critic

# don't truncate long prompt/result text
python -m src.utils.replay_trace data/output/traces/soil1.txt.jsonl --task t_0003 --full
```

**Typical debugging flow:** open `soil_kg.json`, find a finding that looks
wrong, note its `paper_source`. Its `id` won't tell you the task — instead
grep the trace for the entity/finding id to find which task added it:
```bash
grep '"find_017"' data/output/traces/soil1.txt.jsonl
```
That line's `task_id` is what you replay with `--task` to see the worker's
full reasoning, which chunk(s) it read, and why it made that call. If a
finding was added by a critic-queued repair, its `task_id` will end in
`_cr` (critic-originated) — check the corresponding `critic_round_N` trace
to see what gap the critic thought it was fixing.



- `MAX_CRITIC_ROUNDS` (.env) — hard ceiling on plan→work→critique cycles per paper
- `max_steps` in `worker.run_task` / `critic.review` — tool-call budget per task
- `prompts` live inline in `src/agents/{planner,worker,critic}.py` — edit the
  `_SYSTEM` strings directly to change agent behavior/rules

## What's intentionally not (yet) here

- No cross-paper concept-linking layer (each entity is its own concept for now)
- No retrieval/Q&A layer on top of the graph — this builds the graph only
- Eval is a lightweight sanity check, not a full precision/recall harness
