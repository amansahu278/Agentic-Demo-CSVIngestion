# Agentic-Demo-CSVIngestion

CSV ingestion pipeline with **explicit graph** (tools + LangGraph flow) first; ReAct agent to be added later.

## Setup

Using the project’s `.venv`:

```bash
.venv/bin/pip install -r requirements.txt
```

## Config

- **Mandatory columns:** `config/mandatory_columns.yaml` (default: `customer_id`, `email`, `date`).
- **OpenAI (decide node):** The decide node uses an LLM. Set `OPENAI_API_KEY` in the environment (e.g. via a `.env` file). Copy `.env.example` to `.env` and add your key. Optional: set `OPENAI_MODEL` to override the default in `config/settings.yaml` (default model: `gpt-4o-mini`).

## Run the graph (process folder)

```bash
# From project root; put CSVs in data/incoming/
PYTHONPATH=. .venv/bin/python run_graph.py
```

- Reads all `.csv` files in `data/incoming/`.
- Runs the graph once per file. On load error the graph short-circuits to decide; otherwise: load → validate → [fuzzy_match if needed] → decide (LLM) → move → append report.
- Writes `data/reports/ingestion_report_<timestamp>.csv` with columns: `path`, `decision`, `reasoning`.
- Files are **copied** into `data/accepted/`, `data/rejected/`, or `data/needs_review/` according to `decision`.
- Logs each node’s return value to the terminal and to `logs/ingestion.log` (see `src/logging_config.py`).

## Project layout

- `config/mandatory_columns.yaml` — mandatory column names.
- `config/settings.yaml` — app settings (e.g. `openai_model`). Override with `OPENAI_MODEL` env var.
- `src/config.py` — paths and config loading.
- `src/tools/` — shared tools (load, validate, normalize, move, report).
- `src/graph_agent/` — explicit graph: state, nodes, conditional edges, compiled graph.
- `src/logging_config.py` — logging to terminal and `logs/ingestion.log`; each graph step logs what it returns.
- `run_graph.py` — driver: list CSVs in `data/incoming/`, invoke graph per file, write report CSV.
- `DESIGN.md` — design decisions and ReAct vs graph.

## Sample data

- `data/incoming/ok.csv` — has `customer_id`, `email`, `date` → **accepted**.
- `data/incoming/fuzzy_columns.csv` — has `cust_id` (fuzzy match to `customer_id`) → **needs_review**.
- `data/incoming/bad.csv` — missing mandatory columns, no fuzzy match → **rejected**.
