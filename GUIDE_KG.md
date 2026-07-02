# GUIDE_KG — Running the Soil KG Builder as a Local Web App

This covers the **frontend + backend** (FastAPI + SQLite + React) that wraps the
same extraction engine the CLI uses. If you just want the CLI, see `GUIDE.md` —
that keeps working unchanged; this is an additional way to use the same pipeline
with a browser UI, run history, and a graph explorer instead of one-off JSON files.

---

## 0. What you need before you start

- Everything `GUIDE.md` requires: Python 3.10+, a vLLM or Ollama server reachable
  over HTTP with tool-calling enabled (see `GUIDE.md` step 2 if you haven't set
  this up yet)
- **Node.js 18+** (only needed to build/run the frontend — the backend itself is
  pure Python)
- Your papers as `.pdf`, `.txt`, or `.md` — you can drop them in `data/papers/`
  ahead of time, or upload them through the browser once it's running

---

## 1. Install

```bash
cd soil_kg_agentic
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[backend]"
```

The `[backend]` extra adds `fastapi`, `uvicorn`, `sqlmodel`, and `python-multipart`
on top of the CLI's existing dependencies (openai, pymupdf, networkx,
sentence-transformers, etc.).

Sanity check:
```bash
python -c "import backend.main; print('OK')"
```

---

## 2. Configure

Same `.env` as the CLI — copy it if you haven't already:
```bash
cp .env.example .env
```

Edit `.env` with your provider/model/endpoints (see `GUIDE.md` step 3 for the full
field reference: `PROVIDER`, `MODEL`, `VLLM_BASE_URL`, `OLLAMA_BASE_URL`,
`CONTEXT_WINDOW`, `MAX_CRITIC_ROUNDS`). You can also change provider/model/max
critic rounds later from the browser's **Upload & Config** tab — that updates the
backend's running config directly, no restart needed.

---

## 3. Run it

You have two options: a **dev** setup (hot-reload on both sides, two terminals)
or a **built** setup (one process, one port — closer to how you'd actually use
this day to day).

### Option A — Development (hot reload)

**Terminal 1 — backend:**
```bash
uvicorn backend.main:app --reload --port 8010
```

**Terminal 2 — frontend:**
```bash
cd frontend
npm install       # first time only
npm run dev
```

Open the URL Vite prints (usually `http://localhost:5173`). The dev server proxies
all `/api/*` requests to the backend on port 8010 (see `frontend/vite.config.ts`),
so both sides can be edited and hot-reload independently.

### Option B — Built (one process, one port)

```bash
cd frontend
npm install       # first time only
npm run build     # produces frontend/dist
cd ..
uvicorn backend.main:app --port 8010
```

Open `http://localhost:8010` — the backend serves the built frontend as static
files at `/` and the API at `/api/*` from the same process. Rebuild
(`npm run build`) any time you change frontend code; the backend doesn't need a
restart to pick up a new build.

---

## 4. Use it

1. **Upload & Config tab** — drag a paper in (or pick one already in
   `data/papers/` from the dropdown), set provider/model/max critic rounds,
   click **Start Run**.
2. **Run Monitor tab** — polls every 1.5s: status badge, round counter,
   entity/finding counts, and a live-tailed log of agent tool calls (the
   "what's it doing right now" view). Counts jump once per checkpoint (each
   extraction round and each critic round), not per individual entity — see the
   note below on live updates.
3. **Graph Explorer tab** — once a run is `done`, an interactive force-directed
   graph of entities (colored by type) and findings (as directed edges). Click a
   node or edge for its full detail: description, evidence quote, conditions,
   confidence.
4. **Run History tab** — every run you've started, with entity/finding counts,
   orphan rate, condition coverage, and a button back into Monitor (if still
   running) or Graph Explorer (if done).

**Note on "live":** the Run Monitor's counts and log update in near-real-time
while a run is in progress. The Graph Explorer canvas itself is a snapshot
fetched once when you open that tab — it does not currently auto-refresh while
a run is still going. Switch away and back (or reload) to see a newer snapshot.

---

## 5. Where things live

```
data/papers/                        input papers (CLI and web UI share this dir)
data/output/app.db                  SQLite — run history, entities, findings (read-side only)
data/output/runs/<run_id>/soil_kg.json    that run's actual KG (same format the CLI produces)
data/output/runs/<run_id>/traces/*.jsonl  that run's agent trace (same format the CLI produces)
```

Each run started from the browser gets its **own** `soil_kg.json` and trace
directory — runs don't share or accumulate into one global file the way repeated
CLI runs against the same `--kg` path do. `app.db` is a rebuildable projection of
whatever's in each run's `soil_kg.json`, not a second source of truth — if you
ever need to reset it, just delete `data/output/app.db` and re-sync (or start
fresh runs; it recreates itself automatically on next backend startup).

---

## 6. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `Connection error.` in Run Monitor | vLLM/Ollama server unreachable from the backend's machine | Check `VLLM_BASE_URL`/`OLLAMA_BASE_URL` in the Config tab or `.env`; confirm the server is actually up (see `GUIDE.md` step 2's `curl` test) |
| "Set a model name before starting" won't go away | `MODEL` empty in config | Fill in the Model field in Upload & Config — it's required, same as `--model` on the CLI |
| Uploaded paper doesn't appear in the dropdown | Unsupported file type | Only `.pdf`, `.txt`, `.md` are accepted |
| Graph Explorer shows a mostly-disconnected graph | This is a real signal, not a bug | See `GUIDE.md`'s "Low `condition_coverage`" troubleshooting row, and the Run History tab's orphan-rate/condition-coverage columns — the critic is designed to catch and repair exactly this |
| Port already in use | Something else on 8010 (or 5173 for the Vite dev server) | Pass a different `--port` to uvicorn, or stop whatever's already bound |
| Frontend shows stale data after a code change | Old build | Re-run `npm run build` (Option B) or make sure the Vite dev server (Option A) is still running |

The CLI (`python run.py ...`) and this web app read/write in the same formats and
share the same `kg_building/` engine — nothing here changes how `run.py` behaves.
