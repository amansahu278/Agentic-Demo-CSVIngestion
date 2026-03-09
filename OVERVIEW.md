# CSV Ingestion Pipeline — Overview

This document explains the overall idea, the tools, and the two pipeline implementations (explicit graph and ReAct agent). For setup and run instructions, see [README](README.md).

---

## Overall idea

**Problem:** Ingest CSVs from a folder; for each file, decide whether it is **accepted**, **rejected**, or **needs human review** based on mandatory columns.

- **Input:** All `.csv` files in `data/incoming/`.
- **Output:** (1) Files copied into `data/accepted/`, `data/rejected/`, or `data/needs_review/`; (2) a report CSV with one row per file (path, decision, reasoning; the agent run also includes usage stats).
- **Outcomes:**
  - **accepted** — All mandatory columns present and no fuzzy mapping was used.
  - **needs_review** — Fuzzy/suggested column mapping was used (e.g. `cust_id` → `customer_id`); a human should verify.
  - **rejected** — Missing mandatory columns and no reasonable mapping.
- **Config:** Mandatory column names in `config/mandatory_columns.yaml`; app settings (e.g. OpenAI model, agent recursion limit) in `config/settings.yaml` and environment variables.

---

## Tools (shared and per implementation)

The pipeline needs a fixed set of **capabilities**. The implementations share the same logic; only **orchestration** (who calls what and when) differs.

| Capability | Description | Implementation |
|------------|-------------|----------------|
| **Load CSV** | Read a CSV and return column names and row count. | [src/tools/load.py](src/tools/load.py); used by both pipelines. |
| **Validate columns** | Check that all mandatory columns (from config) are present. | [src/tools/validate.py](src/tools/validate.py). |
| **Suggest column mapping** | When columns are missing, use an LLM to suggest mappings (e.g. `cust_id` → `customer_id`). Used for fuzzy cases that go to needs_review. | Graph: dedicated node; Agent: LangChain tool that calls an LLM. |
| **Normalize CSV columns** | (Optional) Rename columns in the file using a mapping (e.g. after a suggested mapping). | [src/tools/normalize.py](src/tools/normalize.py). |
| **Move file to pile** | Copy the file into `accepted/`, `rejected/`, or `needs_review/`. | [src/tools/move.py](src/tools/move.py). |
| **Report** | Append a row (path, decision, reasoning) to the run’s report. | Graph: explicit “append report” step; Agent: tool `append_report_entry`; both write via [src/tools/report.py](src/tools/report.py). |

**Functionality lives in shared tools; orchestration** (order and when to call) differs between the two methods.

---

## Two methods: high-level and architecture

### Method 1 — Explicit graph (fixed flow)

- **Idea:** A fixed pipeline: load → validate → (optionally fuzzy_match) → decide (LLM) → move → append report. The **graph** defines the order and branching; the LLM is used only in the “decide” node.
- **Entrypoint:** [run_graph.py](run_graph.py); graph and nodes in [src/graph_agent/](src/graph_agent/).
- **Architecture:**  
  `START → load → validate → [if missing columns: fuzzy_match] → decide (LLM) → move → append_report → END`
- **Features:** Same input/output as the agent; no tool choice—every file goes through the same steps; easy to reason about and test.

### Method 2 — ReAct agent (tool-calling agent)

- **Idea:** One agent (LLM) that sees the file path and **chooses** which tools to call and in what order (load_csv, validate_columns, suggest_column_mapping, move_file_to_pile, append_report_entry) until it finishes. Flow is **agent → tools → agent → …** until the agent stops.
- **Entrypoint:** [run_agent.py](run_agent.py); graph and tools in [src/agent/](src/agent/).
- **Architecture:**  
  `START → agent (LLM) → [if tool_calls: tools node] → agent → … → END (when no tool_calls)`
- **Features:** Same input/output and report; optional **--debug** (log level DEBUG for tool calls and state); optional **Langfuse** tracing (env); **usage in report** (llm_calls, tool_calls, token counts per file); **agent_recursion_limit** in settings (max steps per file).

---

## Architecture diagrams

Plain text flow (arrows show direction). These are sometimes called ASCII or text diagrams.

**Explicit graph** — fixed sequence with one conditional branch:

```
        START
          |
          v
        load
          |
          v
        validate
          |
  +-+--+-+-+-+-+-+-+
  |                |
  v                v
  fuzzy   (all present)
    \          /
     v        v
    decide (LLM)
         |
         v
        move
          |
          v
        +-+-+
        |   |
        v   v
      append_report
          |
          v
          END
```

**ReAct agent** — agent and tools form a loop until the agent is done:

```
  START
    |
    v
  agent (LLM)
    |
    +---> tool_calls? ---> tools ---+
    |                               |
    +<------ (loop back) -----------+
    |
    v  (done: no tool_calls)
  END
```

---

## Side-by-side summary

| Aspect | Explicit graph | ReAct agent |
|--------|----------------|-------------|
| Flow control | Graph (fixed sequence + conditionals) | LLM (chooses tools and order) |
| LLM role | Decider only (accept/reject/needs_review + reasoning) | Orchestrator + decider |
| Entrypoint | run_graph.py | run_agent.py |
| Code location | src/graph_agent/ | src/agent/ |
| Report columns | path, decision, reasoning | path, decision, reasoning, llm_calls, tool_calls, tokens |
| Extra features | — | --debug, Langfuse, recursion_limit |

---

To run and configure, see [README](README.md).
