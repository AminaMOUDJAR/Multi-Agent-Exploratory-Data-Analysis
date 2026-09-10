import { useEffect, useRef, useState } from "react";
import { askQuestion, getHealth, uploadFile } from "./api";
import Dashboard from "./components/Dashboard";

const AGENTS = ["loader", "cleaner", "profiler", "modeler", "visualizer", "insights"];

export default function App() {
  const [health, setHealth] = useState(null);
  const [report, setReport] = useState(null);
  const [busy, setBusy] = useState(false);
  const [stage, setStage] = useState(-1); // index into AGENTS, -1 = idle
  const [error, setError] = useState("");
  const [drag, setDrag] = useState(false);
  const [messages, setMessages] = useState([]);
  const [question, setQuestion] = useState("");
  const [askBusy, setAskBusy] = useState(false);
  const chatEndRef = useRef(null);
  const fileInputRef = useRef(null);
  const stageTimer = useRef(null);

  useEffect(() => {
    getHealth().then(setHealth).catch(() => setHealth(false));
  }, []);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => () => clearInterval(stageTimer.current), []);

  function pickFile(file) {
    if (!file) return;
    setError("");
    setReport(null);
    setBusy(true);
    setStage(0);
    setMessages([]);
    // rotate through pipeline steps while the backend runs
    stageTimer.current = setInterval(
      () => setStage((s) => (s < AGENTS.length - 1 ? s + 1 : s)),
      450
    );

    uploadFile(file)
      .then((r) => {
        clearInterval(stageTimer.current);
        setStage(AGENTS.length);
        setReport(r);
      })
      .catch((e) => {
        clearInterval(stageTimer.current);
        setStage(-1);
        setError(e.message || "Upload failed.");
      })
      .finally(() => setBusy(false));
  }

  async function sendQuestion(e) {
    e.preventDefault();
    const q = question.trim();
    if (!q || !report?.report_id || askBusy) return;
    setQuestion("");
    setMessages((m) => [...m, { role: "user", text: q }]);
    setAskBusy(true);
    try {
      const { answer } = await askQuestion(report.report_id, q);
      setMessages((m) => [...m, { role: "bot", text: answer }]);
    } catch (err) {
      setMessages((m) => [...m, { role: "bot", text: err.message || "Request failed.", error: true }]);
    } finally {
      setAskBusy(false);
    }
  }

  const llmOn = !!health?.llm_enabled;

  return (
    <div className="app">
      <header className="header">
        <div>
          <h1>📊 Multi-Agent EDA</h1>
          <div className="sub">
            LangGraph pipeline · FastAPI · React — upload a CSV/Excel and get a dashboard + insights
          </div>
        </div>
        <div className="badges">
          <span className="badge">
            <span className={`dot ${health ? "on" : health === false ? "err" : "off"}`} />
            {health ? "API online" : health === false ? "API offline" : "checking…"}
          </span>
          <span className="badge">
            LLM <b>{llmOn ? "on" : "off"}</b>
            {llmOn && health.llm_model ? ` · ${health.llm_model}` : ""}
          </span>
          <span className="badge">
            torch <b>{health?.torch_available ? "on" : "off"}</b>
          </span>
        </div>
      </header>

      <section className="panel">
        <div
          className={`dropzone${drag ? " drag" : ""}`}
          onClick={() => !busy && fileInputRef.current?.click()}
          onDragOver={(e) => {
            e.preventDefault();
            setDrag(true);
          }}
          onDragLeave={() => setDrag(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDrag(false);
            if (!busy) pickFile(e.dataTransfer.files[0]);
          }}
        >
          <div className="big">{busy ? "Running agent pipeline…" : "Drop a .csv / .xlsx file here, or click to browse"}</div>
          <div>
            The agents will clean, profile, model, chart, and summarize it — or try the bundled{" "}
            <b>sample_data/sales_sample.csv</b>
          </div>
          <input
            ref={fileInputRef}
            type="file"
            accept=".csv,.tsv,.txt,.xlsx,.xls"
            onChange={(e) => pickFile(e.target.files[0])}
          />
        </div>

        {(busy || stage >= 0) && (
          <div className="steps">
            {AGENTS.map((a, i) => (
              <span
                key={a}
                className={`step${busy && i === stage ? " active" : ""}${i < stage ? " done" : ""}`}
              >
                {i < stage ? "✓ " : ""}
                {a}
              </span>
            ))}
            {busy && <span className="spinner" />}
            {!busy && stage >= AGENTS.length && !error && (
              <span className="step done">✓ report ready</span>
            )}
          </div>
        )}

        {error && <div className="error-box">{error}</div>}
      </section>

      {report && <Dashboard report={report} />}

      {report && (
        <section className="panel">
          <h2>Ask the data</h2>
          <div className="chat-log">
            {messages.length === 0 && (
              <div className="hint">
                {llmOn
                  ? "Ask a follow-up question about this dataset — answers are grounded in the agent report."
                  : "Chat requires an LLM key in backend/.env (OPENAI_API_KEY)."}
              </div>
            )}
            {messages.map((m, i) => (
              <div key={i} className={`msg ${m.role}${m.error ? " err" : ""}`}>
                {m.text}
              </div>
            ))}
            {askBusy && (
              <div className="msg bot">
                <span className="spinner" /> thinking…
              </div>
            )}
            <div ref={chatEndRef} />
          </div>
          <form className="chat-input" onSubmit={sendQuestion}>
            <input
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder={llmOn ? "e.g. Which region has the highest average profit?" : "LLM key not configured"}
              disabled={!llmOn || askBusy}
            />
            <button className="button" type="submit" disabled={!llmOn || askBusy || !question.trim()}>
              Send
            </button>
          </form>
        </section>
      )}
    </div>
  );
}
