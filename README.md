# Multi-Agent EDA

A multi-agent system that ingests CSV/Excel files, cleans and profiles the data, runs
statistical + ML analysis, builds a Plotly dashboard, and synthesizes insights with an LLM.

**Stack:** LangGraph (agent orchestration) · FastAPI (backend) · React + Vite + Plotly (frontend)
· pandas/scikit-learn (EDA + ML) · optional PyTorch (autoencoder anomaly detection) · any OpenAI-compatible LLM (defaults to Groq).

## Architecture

```
 CSV / Excel
     │
     ▼
┌──────────────────────────────────────────────────────────────┐
│                    FastAPI Backend                            │
│  ┌─────────┐  ┌─────────┐  ┌──────────┐  ┌──────────┐        │
│  │ Loader  │→ │ Cleaner │→ │ Profiler │→ │ Modeler  │        │
│  │ (pandas)│  │(dedup,  │  │(schema,  │  │(correl., │        │
│  │         │  │ impute) │  │ describe)│  │ KMeans,  │        │
│  └─────────┘  └─────────┘  └──────────┘  │ IsoForest│        │
│                                          │ +torch AE│        │
│                                          └────┬─────┘        │
│   LangGraph StateGraph (each box = one agent) │              │
│                                          ┌────▼─────┐        │
│                                          │Visualizer│        │
│                                          │(Plotly    │        │
│                                          │ specs)    │        │
│                                          └────┬─────┘        │
│                                          ┌────▼─────┐        │
│                                          │ Insights │        │
│                                          │ (LLM or  │        │
│                                          │ template)│        │
│                                          └──────────┘        │
└──────────────────────────────────────────────────────────────┘
     │  profile / charts / insights          ▲
     ▼                                       │ /ask (LLM Q&A)
┌──────────────────────────┐                │
│  React frontend           │────────────────┘
│  Upload → Dashboard → Chat│
└──────────────────────────┘
```

CSV/Excel → FastAPI `/upload`
   └─ LangGraph StateGraph pipeline (shared `EDAState` dict):
      1. **Loader** – pandas reads csv/xlsx
      2. **Cleaner** – dedupe + median/mode imputation, cleaning report
      3. **Profiler** – schema, dtypes, missingness, describe()
      4. **Modeler** – sklearn: correlation matrix, top pairs, KMeans clusters,
         Isolation Forest anomalies; optional PyTorch autoencoder
         (only runs if torch is installed)
      5. **Visualizer** – Plotly figure specs (histograms, bar, correlation heatmap)
      6. **Insights** – LLM narrative (OpenAI-compatible), template fallback if no key
   → React frontend: upload → profile tables → dashboard grid → insights → `/ask` chat

## Quickstart

```bash
# 1. Backend
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env          # optional: add OPENAI_API_KEY for LLM insights
uvicorn app.main:app --reload --port 8000

# 2. Frontend (new terminal)
cd frontend
npm install
npm run dev                   # http://localhost:5173
```

On Windows you can also just double-click **`start_backend.bat`** and **`start_frontend.bat`**.

Upload any `.csv` / `.xlsx` file in the UI. The agent pipeline runs end-to-end and
renders the dashboard + insights. Without an `OPENAI_API_KEY`, insights fall back to
rule-based templates and Q&A is disabled.

## LLM configuration (backend/.env)

```
OPENAI_API_KEY=sk-...
OPENAI_BASE_URL=https://api.groq.com/openai/v1   # any OpenAI-compatible endpoint
LLM_MODEL=openai/gpt-oss-20b
```

Works with OpenAI, Groq, Together, Ollama (`http://localhost:11434/v1`), LM Studio, etc.

## API

| Method | Endpoint | Description |
|---|---|---|
| POST | `/upload` | multipart file upload → runs full agent pipeline, returns report |
| POST | `/ask` | `{report_id, question}` → LLM answer grounded in the report |
| GET  | `/health` | health check + capability flags |
| GET  | `/reports/{report_id}` | fetch a previously generated report |

Interactive docs: http://localhost:8000/docs

## Design choices that keep it simple and quota-friendly

- **Linear LangGraph pipeline** — each agent is one pure function over shared state; trivial to extend into loops/human-in-the-loop later.
- **LLM is optional** — every LLM call has a deterministic fallback, so the app works end-to-end with zero API spend; the chat tab is the only thing that strictly needs a key.
- **PyTorch is a soft dependency** — the autoencoder anomaly detector is wrapped in try/except, so no heavy install unless you want it.
- **Charts are Plotly specs produced by the backend** and rendered by the frontend, so the LLM can later modify/regenerate dashboard specs without touching React.
- **JSON-safe output** — numpy scalars / NaN are converted server-side so strict JSON parsers never choke.

## Project layout

```
backend/
  app/
    agents/       # loader, cleaner, profiler, modeler, visualizer, insights
    config.py     # env config + OpenAI-compatible client
    graph.py      # LangGraph StateGraph wiring
    state.py      # shared EDAState TypedDict
    store.py      # in-memory report store
    main.py       # FastAPI endpoints
    utils.py      # JSON-safety helpers
  requirements.txt
  .env            # LLM keys (not committed)
frontend/
  src/
    App.jsx               # upload → pipeline progress → chat
    components/Dashboard.jsx  # overview stats, tabs, column table, insights
    components/Chart.jsx      # Plotly renderer with ResizeObserver
  src/api.js       # backend client
sample_data/       # generated demo dataset
scripts/           # data generator
```

## Using Google Antigravity

Open this repo folder in Antigravity and let its agents extend the project, e.g.:

> "Add a LangGraph ReAct agent that answers follow-up questions by generating and
> executing pandas code against the uploaded dataframe instead of relying on the
> static profile context."
