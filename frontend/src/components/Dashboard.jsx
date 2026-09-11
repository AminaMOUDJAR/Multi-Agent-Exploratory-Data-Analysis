import { useMemo, useState } from "react";
import Chart from "./Chart";

/* markdown rendering without a markdown dep. handles what the llm actually
   emits in practice: ## headings, - bullets, **bold**, *italic*, `code`.
   everything gets html-escaped first so a chatty model can't inject markup. */
function renderMarkdown(text) {
  const esc = (s) =>
    s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

  const inline = (s) =>
    esc(s)
      .replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>")
      .replace(/(^|\W)\*([^*\n]+)\*(?=\W|$)/g, "$1<i>$2</i>")
      .replace(/`([^`]+)`/g, '<code style="background:rgba(255,255,255,.08);padding:1px 5px;border-radius:4px;font-family:inherit">$1</code>');

  const html = [];
  let inList = false;
  for (const raw of text.split("\n")) {
    const line = raw.trimEnd();
    const bullet = line.match(/^\s*[-*•]\s+(.*)$/);
    const heading = line.match(/^(#{1,4})\s+(.*)$/);
    if (bullet) {
      if (!inList) {
        html.push("<ul style='margin:6px 0;padding-left:22px'>");
        inList = true;
      }
      html.push(`<li>${inline(bullet[1])}</li>`);
    } else {
      if (inList) {
        html.push("</ul>");
        inList = false;
      }
      if (heading) {
        const level = Math.min(heading[1].length + 1, 5);
        html.push(`<h${level}>${inline(heading[2])}</h${level}>`);
      } else if (line.trim()) {
        html.push(`<p style='margin:6px 0'>${inline(line)}</p>`);
      }
    }
  }
  if (inList) html.push("</ul>");
  return html.join("");
}

function fmt(n) {
  if (n === null || n === undefined) return "—";
  if (typeof n !== "number") return String(n);
  if (Number.isInteger(n)) return n.toLocaleString();
  if (Math.abs(n) >= 1000) return n.toLocaleString(undefined, { maximumFractionDigits: 0 });
  if (Math.abs(n) >= 10) return n.toFixed(1);
  return n.toFixed(2);
}

function Stat({ label, value, suffix }) {
  return (
    <div className="stat">
      <div className="label">{label}</div>
      <div className="value">
        {value} {suffix && <small>{suffix}</small>}
      </div>
    </div>
  );
}

function ColumnTable({ columns }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Feature</th>
            <th>Role</th>
            <th>Data Type</th>
            <th>Missing (Null)</th>
            <th>Cardinality</th>
            <th>Summary Statistics</th>
          </tr>
        </thead>
        <tbody>
          {columns.map((c) => {
            // one "notes" cell per role: stats for numeric, top values for
            // cats, the range for dates, raw samples for ids
            let summary = "—";
            if (c.stats) {
              const s = c.stats;
              summary = `mean ${fmt(s.mean)} · min ${fmt(s.min)} · median ${fmt(s.median)} · max ${fmt(s.max)}`;
            } else if (c.top_values) {
              summary = c.top_values.map((t) => `${t.value} (${t.count})`).join(", ");
            } else if (c.range) {
              summary = `${c.range[0]} → ${c.range[1]}`;
            } else if (c.sample) {
              summary = c.sample.join(", ");
            }
            return (
              <tr key={c.name}>
                <td><b>{c.name}</b></td>
                <td><span className={`pill ${c.role}`}>{c.role}</span></td>
                <td style={{ color: "var(--muted)" }}>{c.dtype}</td>
                <td style={{ color: c.missing_before ? "var(--warn)" : undefined }}>
                  {c.missing_before}
                  {c.missing > 0 && <small> → {c.missing} residual</small>}
                </td>
                <td>{c.unique}</td>
                <td style={{ color: "var(--muted)", maxWidth: 380, overflow: "hidden", textOverflow: "ellipsis" }}>
                  {summary}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

const TABS = ["Plots", "Variables", "Lab notes"];

export default function Dashboard({ report }) {
  const [tab, setTab] = useState("Plots");
  const ov = report.overview || {};

  const cleaning = report.cleaning || {};
  const insights = report.insights || {};
  const nImputed = useMemo(
    () => (cleaning.imputations || []).reduce((s, i) => s + (i.missing || 0), 0),
    [cleaning]
  );

  return (
    <>
      <div className="panel">
        <h2>
          Exploratory Data Analysis — {report.file_name}
          <small style={{ color: "var(--muted)", textTransform: "none", fontWeight: 400 }}>
            {" "}
            · execution latency: {report.pipeline_seconds}s
          </small>
        </h2>
        <div className="stats">
          <Stat label="Observations (Rows)" value={fmt(ov.rows)} />
          <Stat label="Features (Columns)" value={fmt(ov.columns)} />
          <Stat label="Completeness" value={fmt(ov.completeness_pct)} suffix="%" />
          <Stat label="Duplicates Removed" value={fmt(cleaning.duplicates_removed ?? 0)} />
          <Stat label="Imputed Values" value={fmt(nImputed)} />
          <Stat label="Anomalies Detected" value={report.anomalies ? fmt(report.anomalies.count) : "—"} />
          <Stat label="Clusters Identified" value={report.clustering ? fmt(report.clustering.k) : "—"} />
          <Stat label="Memory Usage" value={fmt(ov.memory_mb)} suffix="MB" />
        </div>
      </div>

      <div className="tabs">
        {TABS.map((t) => (
          <button key={t} className={`tab${tab === t ? " active" : ""}`} onClick={() => setTab(t)}>
            {t}
          </button>
        ))}
      </div>

      {tab === "Plots" && (
        <>
          {report.charts?.length ? (
            <div className="grid">
              {report.charts.map((ch) => (
                <Chart key={ch.id} title={ch.title} figure={ch.figure} wide={ch.wide} />
              ))}
            </div>
          ) : (
            <div className="panel">no plots came out of this one, sorry.</div>
          )}
        </>
      )}

      {tab === "Variables" && (
        <div className="panel">
          <h2>Feature Schema & Profiling</h2>
          <ColumnTable columns={report.columns || []} />
          {cleaning.imputations?.length > 0 && (
            <p className="hint">
              prep work: purged {cleaning.duplicates_removed} duplicate rows, backfilled {nImputed}{" "}
              empty cells
              {cleaning.date_converted?.length
                ? `, and talked ${cleaning.date_converted.join(", ")} into being real dates`
                : ""}
              .
            </p>
          )}
        </div>
      )}

      {tab === "Lab notes" && insights.text && (
        <div className="panel">
          <h2>
            Lab notes
            <span className={`source-tag ${insights.source === "llm" ? "llm" : "template"}`}>
              {insights.source === "llm" ? `written by ${insights.model}` : "copied from the rulebook"}
            </span>
          </h2>
          <div
            className="insights-md"
            dangerouslySetInnerHTML={{ __html: renderMarkdown(insights.text) }}
          />
        </div>
      )}
    </>
  );
}
