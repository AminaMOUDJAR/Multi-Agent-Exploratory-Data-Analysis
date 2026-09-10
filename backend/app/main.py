"""FastAPI entrypoint.

POST /upload  → runs the full LangGraph pipeline, returns the JSON report
POST /ask     → LLM Q&A grounded in the stored report context
GET  /health  → status + capability flags
GET  /reports/{id} → fetch a previously generated report
"""
import os
import tempfile
import time
from datetime import datetime, timezone

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from .agents.insights import ASK_SYSTEM
from .agents.modeler import HAS_TORCH
from .config import LLM_ENABLED, LLM_MODEL, llm_client
from .graph import PIPELINE, eda_graph
from .schemas import AskRequest
from .store import get_report, save_report
from .utils import to_native

ALLOWED_EXT = {".csv", ".tsv", ".txt", ".xlsx", ".xls"}
MAX_UPLOAD_BYTES = 50 * 1024 * 1024

app = FastAPI(
    title="Multi-Agent EDA",
    version="1.0.0",
    description="LangGraph pipeline: load → clean → profile → model → visualize → insights",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "agents": PIPELINE,
        "llm_enabled": LLM_ENABLED,
        "llm_model": LLM_MODEL if LLM_ENABLED else None,
        "torch_available": HAS_TORCH,
    }


@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    name = file.filename or "upload"
    ext = os.path.splitext(name)[1].lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(415, f"Unsupported file type '{ext}'. Upload one of: {sorted(ALLOWED_EXT)}")
    data = await file.read()
    if not data:
        raise HTTPException(400, "Empty file.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "File too large (max 50 MB).")

    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        tmp.write(data)
        tmp_path = tmp.name

    t0 = time.time()
    try:
        final_state = eda_graph.invoke({"file_path": tmp_path, "file_name": name})
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(500, f"Pipeline failed: {exc}")
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    if final_state.get("df") is None:
        raise HTTPException(422, final_state.get("error") or "Could not parse the file into a table.")

    report = _build_report(final_state)
    report["report_id"] = save_report(report, final_state.get("context", ""))
    report["pipeline_seconds"] = round(time.time() - t0, 2)
    return report


def _build_report(state: dict) -> dict:
    prof = state.get("profile", {}) or {}
    modeling = state.get("modeling", {}) or {}
    modeling_public = {k: v for k, v in modeling.items() if not k.startswith("_")}
    report = {
        "report_id": None,  # filled by the caller
        "file_name": state.get("file_name"),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "agents": PIPELINE,
        "load_info": state.get("load_info"),
        "overview": prof.get("overview"),
        "cleaning": state.get("cleaning"),
        "columns": prof.get("columns", []),
        "correlation": modeling_public.get("correlation"),
        "clustering": modeling_public.get("clustering"),
        "anomalies": modeling_public.get("anomalies"),
        "autoencoder": modeling_public.get("autoencoder"),
        "charts": state.get("charts", []),
        "insights": state.get("insights"),
        "llm_enabled": LLM_ENABLED,
        "torch_available": HAS_TORCH,
    }
    return to_native(report)


@app.post("/ask")
def ask(req: AskRequest):
    entry = get_report(req.report_id)
    if entry is None:
        raise HTTPException(404, "Unknown report_id — re-upload the file.")
    client = llm_client()
    if client is None:
        raise HTTPException(400, "LLM is not configured. Set OPENAI_API_KEY in backend/.env to enable Q&A.")
    context = entry.get("context") or ""
    try:
        resp = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": ASK_SYSTEM},
                {"role": "user", "content": f"Dataset context (JSON):\n{context}\n\nQuestion: {req.question}"},
            ],
            temperature=0.2,
            max_tokens=600,
        )
        answer = (resp.choices[0].message.content or "").strip()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, f"LLM call failed: {exc}")
    if not answer:
        raise HTTPException(502, "LLM returned an empty answer.")
    return {"answer": answer, "model": LLM_MODEL, "source": "llm"}


@app.get("/reports/{report_id}")
def report(report_id: str):
    entry = get_report(report_id)
    if entry is None:
        raise HTTPException(404, "Unknown report_id.")
    return entry["report"]
