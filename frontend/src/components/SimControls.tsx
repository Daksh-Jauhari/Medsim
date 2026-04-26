interface Props {
  playing: boolean;
  speed: number;
  currentIndex: number;
  totalSnapshots: number;
  currentTick: number;
  showHeatmap: boolean;
  onPlayPause: () => void;
  onStep: () => void;
  onReset: () => void;
  onSpeedChange: (speed: number) => void;
  onHeatmapToggle: (on: boolean) => void;
}

export default function SimControls({
  playing,
  speed,
  currentIndex,
  totalSnapshots,
  currentTick,
  showHeatmap,
  onPlayPause,
  onStep,
  onReset,
  onSpeedChange,
  onHeatmapToggle,
}: Props) {
  return (
    <div className="card">
      <h2>Controls</h2>
      <div className="controls">
        <button onClick={onPlayPause}>{playing ? "Pause" : "Play"}</button>
        <button className="secondary" onClick={onStep}>Step</button>
        <button className="secondary" onClick={onReset}>Reset</button>
      </div>
      <div className="controls" style={{ marginTop: 12 }}>
        <label>Speed</label>
        {[1, 2, 4].map((s) => (
          <button
            key={s}
            className={s === speed ? "" : "secondary"}
            onClick={() => onSpeedChange(s)}
          >
            {s}x
          </button>
        ))}
      </div>
      <div className="controls" style={{ marginTop: 12 }}>
        <label>
          <input
            type="checkbox"
            checked={showHeatmap}
            onChange={(e) => onHeatmapToggle(e.target.checked)}
          />{" "}
          Heatmap
        </label>
      </div>
      <div className="tick-counter" style={{ marginTop: 12 }}>
        Frame {currentIndex + 1} / {totalSnapshots} &middot; tick {currentTick}
      </div>
      <div className="legend" style={{ marginTop: 12 }}>
        <span><span className="swatch" style={{ background: "#e25c5c" }} /> patient</span>
        <span><span className="swatch" style={{ background: "#4ecb71" }} /> nurse</span>
        <span><span className="swatch" style={{ background: "#f0b429" }} /> doctor</span>
      </div>
    </div>
  );
}
