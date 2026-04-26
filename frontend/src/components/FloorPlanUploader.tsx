import { useCallback, useRef, useState } from "react";
import { api } from "../api/client";
import type { GridMap } from "../types";

interface Props {
  onAnalyzed: (grid: GridMap) => void;
}

export default function FloorPlanUploader({ onAnalyzed }: Props) {
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFile = useCallback((f: File | null) => {
    setError(null);
    setFile(f);
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewUrl(f ? URL.createObjectURL(f) : null);
  }, [previewUrl]);

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragActive(false);
      const f = e.dataTransfer.files?.[0];
      if (f) handleFile(f);
    },
    [handleFile]
  );

  const analyze = async () => {
    if (!file) return;
    setLoading(true);
    setError(null);
    try {
      const grid = await api.analyze(file);
      onAnalyzed(grid);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="card">
      <h2>1. Upload floor plan</h2>
      <div
        className={`drop-zone ${dragActive ? "drag" : ""}`}
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setDragActive(true);
        }}
        onDragLeave={() => setDragActive(false)}
        onDrop={onDrop}
      >
        {file ? (
          <div>{file.name} ({Math.round(file.size / 1024)} KB)</div>
        ) : (
          <div>Drop an image here, or click to browse</div>
        )}
        <input
          ref={inputRef}
          type="file"
          accept="image/*"
          style={{ display: "none" }}
          onChange={(e) => handleFile(e.target.files?.[0] ?? null)}
        />
      </div>

      {previewUrl && (
        <div className="preview">
          <img src={previewUrl} alt="Floor plan preview" />
          <div>
            <p style={{ color: "var(--muted)", margin: "0 0 12px" }}>
              Claude will identify zones and produce a walkable grid.
            </p>
            <button onClick={analyze} disabled={loading || !file}>
              {loading ? "Analyzing..." : "Analyze"}
            </button>
          </div>
        </div>
      )}

      {error && <div className="error" style={{ marginTop: 12 }}>{error}</div>}
    </div>
  );
}
