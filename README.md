# Agentic-Demo-CSVIngestion

CSV ingestion pipeline with two implementations: **explicit graph** (fixed flow) and **single ReAct agent** (full autonomy over tools).

## Setup

Using the project’s `.venv`:

```bash
.venv/bin/pip install -r requirements.txt
```

## Config

- **Mandatory columns:** `config/mandatory_columns.yaml` (default: `customer_id`, `email`, `date`).
- **OpenAI:** The graph’s decide/fuzzy nodes and the agent both use an LLM. Set `OPENAI_API_KEY` in the environment (e.g. via a `.env` file). Copy `.env.example` to `.env` and add your key. Optional: set `OPENAI_MODEL` to override the default in `config/settings.yaml` (default model: `gpt-4o-mini`).
- **Agent loop:** In `config/settings.yaml`, `agent_recursion_limit` (default: 25) caps how many steps the ReAct agent can take per file (LLM → tools → LLM → …). Override with env `INGESTION_AGENT_RECURSION_LIMIT`.

## Run the graph (fixed flow)

```bash
# From project root; put CSVs in data/incoming/
PYTHONPATH=. .venv/bin/python run_graph.py
```

- Reads all `.csv` files in `data/incoming/`.
- Runs the graph once per file. On load error the graph short-circuits to decide; otherwise: load → validate → [fuzzy_match if needed] → decide (LLM) → move → append report.
- Writes `data/reports/ingestion_report_<timestamp>.csv` with columns: `path`, `decision`, `reasoning`.
- Files are **copied** into `data/accepted/`, `data/rejected/`, or `data/needs_review/` according to `decision`.
- Logs each node’s return value to the terminal and to `logs/ingestion.log` (see `src/logging_config.py`).

## Run the agent (ReAct, full autonomy)

```bash
PYTHONPATH=. .venv/bin/python run_agent.py
```

- Same input/output as the graph: reads `data/incoming/*.csv`, writes `data/reports/ingestion_report_agent_<timestamp>.csv`, and copies files into accepted/rejected/needs_review.
- The **agent** chooses which tools to call and in what order (load_csv, validate_columns, suggest_column_mapping, normalize_csv_columns, move_file_to_pile, append_report_entry) and stops when it has finished the task.

### Observability (Langfuse)

If `LANGFUSE_SECRET_KEY` and `LANGFUSE_PUBLIC_KEY` are set in the environment (e.g. in `.env`), each file run is traced in Langfuse. Optionally set `LANGFUSE_BASE_URL` (e.g. `https://cloud.langfuse.com`). In the Langfuse UI you get one trace per file with metadata `file_path`; LLM and tool spans appear inside each trace.

### Debug logging (agent)

To see tool calls and state changes, run with `--debug` (sets log level to DEBUG):

```bash
PYTHONPATH=. .venv/bin/python run_agent.py --debug
```

## Project layout

- `config/mandatory_columns.yaml` — mandatory column names.
- `config/settings.yaml` — app settings (e.g. `openai_model`). Override with `OPENAI_MODEL` env var.
- `src/config.py` — paths and config loading.
- `src/tools/` — shared tools (load, validate, normalize, move, report).
- `src/graph_agent/` — explicit graph: state, nodes, conditional edges, compiled graph.
- `src/agent/` — single ReAct agent: tools, state (messages + report_entries), agent + tools nodes.
- `src/logging_config.py` — logging to terminal and `logs/ingestion.log`; each graph step logs what it returns.
- `run_graph.py` — driver for the graph pipeline.
- `run_agent.py` — driver for the single-agent pipeline.
- `DESIGN.md` — design decisions and ReAct vs graph.

## Sample data

- `data/incoming/ok.csv` — has `customer_id`, `email`, `date` → **accepted**.
- `data/incoming/fuzzy_columns.csv` — has `cust_id` (fuzzy match to `customer_id`) → **needs_review**.
- `data/incoming/bad.csv` — missing mandatory columns, no fuzzy match → **rejected**.
