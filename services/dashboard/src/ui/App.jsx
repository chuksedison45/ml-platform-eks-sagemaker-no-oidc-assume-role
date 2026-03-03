import React, { useEffect, useMemo, useState } from "react";

const API_BASE = import.meta?.env?.VITE_API_BASE || "/api";

function badge(ok) {
  return {
    display: "inline-block",
    padding: "4px 10px",
    borderRadius: 999,
    fontSize: 12,
    border: "1px solid #ddd",
    background: ok ? "#eaffea" : "#ffecec",
  };
}

export default function App() {
  const [status, setStatus] = useState(null);
  const [err, setErr] = useState(null);
  const [loading, setLoading] = useState(true);
  const [payload, setPayload] = useState('{"userId": 42, "k": 5}');
  const [team, setTeam] = useState("recs");
  const [predictOut, setPredictOut] = useState(null);

  async function refresh() {
    setLoading(true);
    setErr(null);
    try {
      const r = await fetch(`${API_BASE}/status`);
      const j = await r.json();
      setStatus(j);
    } catch (e) {
      setErr(String(e));
    } finally {
      setLoading(false);
    }
  }

  async function sendTest() {
    setPredictOut(null);
    try {
      const r = await fetch(`${API_BASE}/predict/${team}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: payload,
      });
      const text = await r.text();
      try {
        setPredictOut(JSON.parse(text));
      } catch {
        setPredictOut(text);
      }
    } catch (e) {
      setPredictOut({ error: String(e) });
    }
  }

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 5000);
    return () => clearInterval(t);
  }, []);

  const rows = useMemo(() => {
    if (!status) return [];
    return [
      { team: "fraud", owner: "Fraud Detection Team", data: status.fraud },
      { team: "recs", owner: "Recommendations Team", data: status.recs },
      { team: "forecast", owner: "Forecasting Team", data: status.forecast },
    ];
  }, [status]);

  return (
    <div
      style={{
        fontFamily: "system-ui, -apple-system, Segoe UI, Roboto, sans-serif",
        padding: 24,
        maxWidth: 1100,
        margin: "0 auto",
      }}
    >
      <h1 style={{ margin: 0 }}>Internal ML Platform</h1>
      <p style={{ marginTop: 6, color: "#555" }}>
        Ops surface for multi-team SageMaker workloads running behind EKS services.
      </p>

      <div style={{ display: "flex", gap: 12, marginTop: 12 }}>
        <button
          onClick={refresh}
          style={{
            padding: "10px 14px",
            borderRadius: 12,
            border: "1px solid #ddd",
            background: "white",
          }}
        >
          Refresh
        </button>
        <div style={{ color: "#777", alignSelf: "center" }}>
          {loading ? "Polling…" : "Live (5s)"}
        </div>
        {err && <div style={{ color: "crimson", alignSelf: "center" }}>{err}</div>}
      </div>

      <div
        style={{
          marginTop: 18,
          border: "1px solid #eee",
          borderRadius: 16,
          overflow: "hidden",
        }}
      >
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ background: "#fafafa" }}>
              <th style={{ textAlign: "left", padding: 12 }}>Team</th>
              <th style={{ textAlign: "left", padding: 12 }}>Owner</th>
              <th style={{ textAlign: "left", padding: 12 }}>Status</th>
              <th style={{ textAlign: "left", padding: 12 }}>Service</th>
              <th style={{ textAlign: "left", padding: 12 }}>Version</th>
              <th style={{ textAlign: "left", padding: 12 }}>Error</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => {
              const ok = r?.data?.status === "ok";
              return (
                <tr key={r.team} style={{ borderTop: "1px solid #eee" }}>
                  <td style={{ padding: 12, fontWeight: 600 }}>{r.team}</td>
                  <td style={{ padding: 12 }}>{r.owner}</td>
                  <td style={{ padding: 12 }}>
                    <span style={badge(ok)}>{ok ? "Healthy" : "Down"}</span>
                  </td>
                  <td style={{ padding: 12 }}>{r?.data?.service || "-"}</td>
                  <td style={{ padding: 12 }}>{r?.data?.version || "-"}</td>
                  <td style={{ padding: 12, color: ok ? "#888" : "crimson" }}>
                    {r?.data?.error || "-"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div style={{ marginTop: 18, display: "grid", gridTemplateColumns: "1fr 1fr", gap: 18 }}>
        <div style={{ border: "1px solid #eee", borderRadius: 16, padding: 16 }}>
          <h2 style={{ marginTop: 0 }}>Test Request Interface</h2>
          <div style={{ display: "flex", gap: 10, marginBottom: 10 }}>
            <label style={{ alignSelf: "center" }}>Route:</label>
            <select
              value={team}
              onChange={(e) => setTeam(e.target.value)}
              style={{ padding: 8, borderRadius: 10 }}
            >
              <option value="fraud">fraud</option>
              <option value="recs">recs</option>
              <option value="forecast">forecast</option>
            </select>
            <button
              onClick={sendTest}
              style={{
                padding: "10px 14px",
                borderRadius: 12,
                border: "1px solid #ddd",
                background: "white",
              }}
            >
              Send
            </button>
          </div>
          <textarea
            value={payload}
            onChange={(e) => setPayload(e.target.value)}
            rows={10}
            style={{
              width: "100%",
              padding: 12,
              borderRadius: 12,
              border: "1px solid #ddd",
              fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
            }}
          />
        </div>

        <div style={{ border: "1px solid #eee", borderRadius: 16, padding: 16 }}>
          <h2 style={{ marginTop: 0 }}>Response</h2>
          <pre
            style={{
              background: "#fafafa",
              border: "1px solid #eee",
              borderRadius: 12,
              padding: 12,
              overflow: "auto",
              height: 300,
            }}
          >
            {predictOut ? JSON.stringify(predictOut, null, 2) : "No response yet."}
          </pre>
          <div style={{ color: "#777", fontSize: 12 }}>API base: {API_BASE}</div>
        </div>
      </div>
    </div>
  );
}
