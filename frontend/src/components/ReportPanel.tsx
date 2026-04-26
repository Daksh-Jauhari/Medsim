import type { BottleneckReport } from "../types";

interface Props {
  report: BottleneckReport;
  onRunAgain: () => void;
}

function formatInt(n: number): string {
  return n.toLocaleString("en-US");
}

export default function ReportPanel({ report, onRunAgain }: Props) {
  return (
    <div className="card">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <h2>3. Bottleneck report</h2>
        <button className="secondary" onClick={onRunAgain}>Run again</button>
      </div>
      <p className="report-summary">{report.summary}</p>

      {report.bottlenecks.length === 0 ? (
        <p className="loading">No significant bottlenecks detected.</p>
      ) : (
        report.bottlenecks.map((b, i) => (
          <div key={`${b.zone}-${i}`} className="bottleneck-card">
            <h3>{b.zone}</h3>
            <p><strong style={{ color: "var(--text)" }}>Issue:</strong> {b.description}</p>
            <p><strong style={{ color: "var(--text)" }}>Root cause:</strong> {b.root_cause}</p>
            <p><strong style={{ color: "var(--text)" }}>Fix:</strong> {b.fix}</p>
            <div className="meta">
              <span>
                <strong>{b.minutes_saved_per_patient}</strong> min saved / patient
              </span>
              <span>
                <strong>{formatInt(b.patients_per_day)}</strong> patients / day
              </span>
              <span>
                <strong>{formatInt(b.annual_minutes_saved)}</strong> min saved / year
              </span>
            </div>
          </div>
        ))
      )}
    </div>
  );
}
