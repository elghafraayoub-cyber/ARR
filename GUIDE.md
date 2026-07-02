# GUIDE — Running the Soil Health KG Builder, Start to Finish

This walks through everything from a clean checkout to a finished knowledge
graph you can open in a browser, plus what to do when something goes wrong.

---

## 0. What you need before you start

- Python 3.10+
- A **vLLM** server already running, serving a model, with **tool-calling
  enabled** (see step 2 — this is the single most common setup mistake)
- Your soil-health papers as PDF or `.txt` files

---

## 1. Install

```bash
cd soil_kg_agentic
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e .
```

This installs: `openai` (client for the OpenAI-compatible vLLM API),
`pymupdf` (PDF text extraction), `pydantic` (schema validation), `networkx`
+ `pyvis` (graph storage/visualization), `sentence-transformers` (entity
dedup), `python-dotenv`, `json-repair`.

Sanity check:
```bash
python -c "import kg_building.agents.orchestrator; print('OK')"
```

---

## 2. Start vLLM with tool-calling enabled

The Worker and Critic agents rely on native OpenAI-style function calling.
If vLLM isn't started with tool-calling support, the server silently ignores
the `tools` parameter and the agents will never call anything — the run
won't crash, it'll just produce an empty graph.

```bash
vllm serve /path/to/your/model \
  --enable-auto-tool-choice \
  --tool-call-parser hermes \
  --port 8000
```

`--tool-call-parser` depends on your model family (e.g. `hermes` for
Hermes/Qwen-style models, `llama3_json` for Llama 3.1/3.2, `mistral` for
Mistral). Check `vllm serve --help` or vLLM's tool-calling docs for the
parser matching your specific model — using the wrong one produces malformed
tool calls that fail silently in the agent loop.

**Verify it's actually working** before running the full pipeline:
```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "/path/to/your/model",
    "messages": [{"role": "user", "content": "What is 2+2? Use the add tool."}],
    "tools": [{"type": "function", "function": {"name": "add", "description": "adds two numbers", "parameters": {"type": "object", "properties": {"a": {"type": "number"}, "b": {"type": "number"}}, "required": ["a", "b"]}}}]
  }'
```
If the response contains a `tool_calls` field, you're good. If it just
answers "4" in plain text, tool-calling isn't wired up correctly yet.

---

## 3. Configure

```bash
cp .env.example .env
```

Edit `.env`:
```bash
PROVIDER=vllm
MODEL=/path/to/your/model          # must match what you passed to `vllm serve`
VLLM_BASE_URL=http://localhost:8000/v1
CONTEXT_WINDOW=8192                 # set to your model's actual context length
```

Getting `CONTEXT_WINDOW` right matters: the client auto-caps output tokens
based on this value, and if it's set higher than the model actually supports,
you'll get truncated/malformed JSON from the model instead of a clean error.

---

## 4. Add papers

```bash
cp your_paper1.pdf data/papers/
cp your_paper2.pdf data/papers/
```

PDF and `.txt` are both supported. Scanned/image-only PDFs won't extract
text — if `data/papers/` only has scans, OCR them first (not handled by this
pipeline).

---

## 5. Run

```bash
python run.py --provider vllm --model /path/to/your/model --visualize --eval
```

Or rely on `.env` and just run `python run.py --visualize --eval`.

**What happens, in order, per paper:**
1. Paper is chunked (section-aware — Abstract/Methods/Results/etc.)
2. **Planner** makes one call, decides task order, logs its reasoning
3. **Worker** drains the task queue — one tool-calling loop per task,
   extracting entities/findings, possibly queuing its own follow-up tasks
4. **Critic** reviews the resulting graph, either approves or queues
   targeted repair tasks
5. If repairs were queued, back to step 3 (up to `MAX_CRITIC_ROUNDS`, default 3)
6. Graph is saved after every round (safe to Ctrl-C and resume-ish — see
   Troubleshooting)

Watch the console. You should see lines like:
```
[planner] Methods and Results carry the causal claims — prioritize those.
[worker/t_0002] step 1 -> calling: get_study_context
[worker/t_0002] step 2 -> calling: add_entity, add_entity
[critic] reviewing graph (round 1)
[critic/critic_round_1] step 2 tool=request_repair -> Queued repair task t_0000_cr.
```
If you don't see any `-> calling:` lines at all, tool-calling isn't working
— go back to step 2.

---

## 6. Look at the results

```
data/output/soil_kg.json          # the graph: entities, findings, study contexts
data/output/soil_kg.html          # interactive viewer (from --visualize)
data/output/run_*.log             # full debug log
data/output/traces/*.jsonl        # per-agent trace (see README's Debugging section)
```

Open `soil_kg.html` in a browser — nodes are entities (colored by type),
edges are findings (hover for relation type, magnitude, p-value, conditions,
and the evidence quote).

The `--eval` flag prints a quick quality summary:
```json
{
  "entities": 42,
  "findings": 31,
  "condition_coverage": 0.87,
  "findings_with_quote": 31,
  "flagged_findings": 2
}
```
`condition_coverage` close to 1.0 means findings are getting proper
conditions attached (the whole point of the reified-finding design).
`flagged_findings` > 0 means the critic left notes worth a manual look —
check those findings' `flags` field in `soil_kg.json`.

---

## 7. If something looks wrong

Read the README's **Debugging** section for the full walkthrough, but the
short version:
```bash
# find which task produced a specific finding/entity
grep '"find_017"' data/output/traces/your_paper.pdf.jsonl

# replay that task's full reasoning
python -m kg_building.utils.replay_trace data/output/traces/your_paper.pdf.jsonl --task t_0003 --full
```

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Graph is empty, no `-> calling:` lines in console | Tool-calling not enabled on vLLM | Re-check step 2, verify with the `curl` test |
| `ERROR: unknown tool` in trace | `--tool-call-parser` mismatch for your model | Try a different parser value |
| JSON parse errors / truncated output | `CONTEXT_WINDOW` set too high for the actual model | Lower it to the model's real context length |
| "No papers found" | Nothing in `data/papers/`, or wrong `--papers` path | Check the path; PDF/.txt only |
| Worker loops hit `max_steps` without finishing | Task is too broad, or model is looping on a tool | Check the trace for that task; consider lowering `max_steps` in `worker.run_task` or splitting large chunks (`CHUNK_TARGET` in `chunker.py`) |
| Low `condition_coverage` in eval | Study context extraction came back mostly empty | Check the `STUDY_CONTEXT` task's trace — the methods/site chunks may not have been detected; inspect `section_hint` in the chunk manifest |
| Re-running adds duplicate findings | Findings aren't deduplicated across runs (only entities are) | Delete `soil_kg.json` before a clean re-run, or treat re-runs as additive/cumulative on purpose |

---

## Re-running / adding more papers later

`run.py` loads `soil_kg.json` if it already exists and merges new papers
into it — entities get deduplicated against what's already there. Findings
are NOT deduplicated across runs, so if you're re-running the *same* paper
(e.g. after a prompt tweak), delete `data/output/soil_kg.json` first for a
clean result.
