import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "./api/client";
import FloorPlanUploader from "./components/FloorPlanUploader";
import ReportPanel from "./components/ReportPanel";
import SimCanvas from "./components/SimCanvas";
import SimControls from "./components/SimControls";
import type { BottleneckReport, GridMap, SimResult, SimSnapshot } from "./types";

type Step = "upload" | "simulate" | "report";

const BASE_TICK_MS = 100; // 10 frames/sec at 1x

export default function App() {
  const [step, setStep] = useState<Step>("upload");
  const [grid, setGrid] = useState<GridMap | null>(null);
  const [simResult, setSimResult] = useState<SimResult | null>(null);
  const [report, setReport] = useState<BottleneckReport | null>(null);

  const [simLoading, setSimLoading] = useState(false);
  const [reportLoading, setReportLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Playback state
  const [frameIdx, setFrameIdx] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const [showHeatmap, setShowHeatmap] = useState(true);
  const playTimer = useRef<number | null>(null);

  const snapshots: SimSnapshot[] = simResult?.snapshots ?? [];

  // Stitch events from all snapshots up through the current frame.
  const visibleEvents = useMemo(() => {
    if (!snapshots.length) return [] as string[];
    const all: string[] = [];
    for (let i = 0; i <= Math.min(frameIdx, snapshots.length - 1); i++) {
      for (const e of snapshots[i].events ?? []) all.push(e);
    }
    return all.slice(-60);
  }, [snapshots, frameIdx]);

  useEffect(() => {
    if (!playing || snapshots.length === 0) return;
    const interval = Math.max(25, BASE_TICK_MS / speed);
    playTimer.current = window.setInterval(() => {
      setFrameIdx((prev) => {
        const next = prev + 1;
        if (next >= snapshots.length) {
          setPlaying(false);
          return snapshots.length - 1;
        }
        return next;
      });
    }, interval);
    return () => {
      if (playTimer.current !== null) {
        window.clearInterval(playTimer.current);
        playTimer.current = null;
      }
    };
  }, [playing, speed, snapshots.length]);

  const onAnalyzed = async (g: GridMap) => {
    setGrid(g);
    setError(null);
    setStep("simulate");
    await runSimulation(g);
  };

  const runSimulation = async (g: GridMap) => {
    setSimLoading(true);
    setError(null);
    try {
      const res = await api.simulate({
        grid: g,
        ticks: 600,
        patient_spawn_rate: 0.05,
        nurses: 4,
        doctors: 2,
      });
      setSimResult(res);
      setFrameIdx(0);
      setPlaying(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSimLoading(false);
    }
  };

  const buildReport = async () => {
    if (!grid || !simResult) return;
    setReportLoading(true);
    setError(null);
    try {
      const r = await api.generateReport({
        metrics: simResult.metrics,
        grid,
      });
      setReport(r);
      setStep("report");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setReportLoading(false);
    }
  };

  const resetAll = () => {
    setStep("upload");
    setGrid(null);
    setSimResult(null);
    setReport(null);
    setFrameIdx(0);
    setPlaying(false);
    setError(null);
  };

  const currentSnapshot = snapshots[Math.min(frameIdx, snapshots.length - 1)] ?? null;

  return (
    <div className="app">
      <header className="app-header">
        <h1>MedSim</h1>
        <div className="step-progress">
          <div className={`step ${step === "upload" ? "active" : grid ? "done" : ""}`}>
            1. Upload
          </div>
          <div className={`step ${step === "simulate" ? "active" : simResult ? "done" : ""}`}>
            2. Simulate
          </div>
          <div className={`step ${step === "report" ? "active" : report ? "done" : ""}`}>
            3. Report
          </div>
        </div>
      </header>

      <main>
        {error && <div className="error">{error}</div>}

        {step === "upload" && <FloorPlanUploader onAnalyzed={onAnalyzed} />}

        {step === "simulate" && grid && (
          <div className="card">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <h2>2. Simulate</h2>
              <div style={{ display: "flex", gap: 8 }}>
                <button
                  className="secondary"
                  onClick={() => runSimulation(grid)}
                  disabled={simLoading}
                >
                  {simLoading ? "Running..." : "Re-run simulation"}
                </button>
                <button onClick={buildReport} disabled={!simResult || reportLoading}>
                  {reportLoading ? "Generating..." : "Generate report"}
                </button>
              </div>
            </div>

            {simLoading && !simResult && (
              <p className="loading">Running simulation on the server...</p>
            )}

            {simResult && (
              <div className="sim-layout" style={{ marginTop: 16 }}>
                <SimCanvas
                  grid={grid}
                  snapshot={currentSnapshot}
                  showHeatmap={showHeatmap}
                />
                <div className="sim-side">
                  <SimControls
                    playing={playing}
                    speed={speed}
                    currentIndex={frameIdx}
                    totalSnapshots={snapshots.length}
                    currentTick={currentSnapshot?.tick ?? 0}
                    showHeatmap={showHeatmap}
                    onPlayPause={() => setPlaying((p) => !p)}
                    onStep={() =>
                      setFrameIdx((i) => Math.min(snapshots.length - 1, i + 1))
                    }
                    onReset={() => {
                      setFrameIdx(0);
                      setPlaying(false);
                    }}
                    onSpeedChange={setSpeed}
                    onHeatmapToggle={setShowHeatmap}
                  />
                  <div className="card" style={{ padding: 12 }}>
                    <h2 style={{ fontSize: 13 }}>Events</h2>
                    <div className="events-log">
                      {visibleEvents.length ? (
                        visibleEvents.map((e, i) => <div key={i}>{e}</div>)
                      ) : (
                        <div>No events yet.</div>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {step === "report" && report && (
          <ReportPanel report={report} onRunAgain={resetAll} />
        )}
      </main>
    </div>
  );
}
