import { useEffect, useMemo, useRef } from "react";
import type { GridMap, SimSnapshot, ZoneKind } from "../types";

interface Props {
  grid: GridMap;
  snapshot: SimSnapshot | null;
  showHeatmap: boolean;
}

const ZONE_TINT: Record<ZoneKind, string> = {
  triage: "rgba(226, 92, 92, 0.18)",
  imaging: "rgba(63, 143, 255, 0.18)",
  surgery: "rgba(240, 180, 41, 0.18)",
  icu: "rgba(155, 89, 182, 0.20)",
  er: "rgba(231, 76, 60, 0.22)",
  corridor: "rgba(255, 255, 255, 0.04)",
  entrance: "rgba(78, 203, 113, 0.20)",
  other: "rgba(255, 255, 255, 0.05)",
};

const WALL = "#243041";
const WALKABLE = "#0f1720";
const DOORWAY = "#2b4466";

const ROLE_COLOR: Record<string, string> = {
  patient: "#e25c5c",
  nurse: "#4ecb71",
  doctor: "#f0b429",
  equipment: "#8493ab",
};

// Simple blue -> orange -> red heat color scale
function heatColor(t: number): [number, number, number] {
  const x = Math.max(0, Math.min(1, t));
  if (x < 0.5) {
    const k = x / 0.5;
    const r = Math.round(40 + k * 215);
    const g = Math.round(80 + k * 100);
    const b = Math.round(200 - k * 200);
    return [r, g, b];
  }
  const k = (x - 0.5) / 0.5;
  const r = 255;
  const g = Math.round(180 - k * 180);
  const b = 0;
  return [r, g, b];
}

// TODO: upgrade to three.js with elevated 2.5D blocks
function drawFrame(
  canvas: HTMLCanvasElement,
  grid: GridMap,
  snapshot: SimSnapshot | null,
  cell: number,
  showHeatmap: boolean
) {
  const ctx = canvas.getContext("2d");
  if (!ctx) return;

  ctx.fillStyle = WALKABLE;
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  // Cells
  for (let y = 0; y < grid.height; y++) {
    for (let x = 0; x < grid.width; x++) {
      const v = grid.cells[y]?.[x] ?? 1;
      if (v === 1) {
        ctx.fillStyle = WALL;
        ctx.fillRect(x * cell, y * cell, cell, cell);
      } else if (v === 2) {
        ctx.fillStyle = DOORWAY;
        ctx.fillRect(x * cell, y * cell, cell, cell);
      }
    }
  }

  // Zone tints
  for (const zone of grid.zones) {
    if (zone.polygon.length < 3) continue;
    ctx.fillStyle = ZONE_TINT[zone.kind] ?? ZONE_TINT.other;
    ctx.beginPath();
    const [sx, sy] = zone.polygon[0];
    ctx.moveTo(sx * cell, sy * cell);
    for (let i = 1; i < zone.polygon.length; i++) {
      const [px, py] = zone.polygon[i];
      ctx.lineTo(px * cell, py * cell);
    }
    ctx.closePath();
    ctx.fill();
  }

  // Zone labels
  ctx.fillStyle = "rgba(223, 230, 242, 0.75)";
  ctx.font = `${Math.max(10, Math.floor(cell * 1.2))}px system-ui, sans-serif`;
  ctx.textBaseline = "top";
  for (const zone of grid.zones) {
    if (!zone.polygon.length) continue;
    const xs = zone.polygon.map((p) => p[0]);
    const ys = zone.polygon.map((p) => p[1]);
    const cx = (Math.min(...xs) + Math.max(...xs)) / 2;
    const cy = Math.min(...ys);
    ctx.fillText(zone.label, cx * cell - 20, cy * cell + 2);
  }

  // Heatmap overlay
  if (showHeatmap && snapshot?.heatmap?.length) {
    const heatH = snapshot.heatmap.length;
    const heatW = snapshot.heatmap[0]?.length ?? 0;
    const sx = (grid.width * cell) / heatW;
    const sy = (grid.height * cell) / heatH;
    let max = 0;
    for (let y = 0; y < heatH; y++) {
      for (let x = 0; x < heatW; x++) {
        const v = snapshot.heatmap[y][x];
        if (v > max) max = v;
      }
    }
    if (max > 0) {
      for (let y = 0; y < heatH; y++) {
        for (let x = 0; x < heatW; x++) {
          const v = snapshot.heatmap[y][x];
          if (v <= 0) continue;
          const t = Math.min(1, v / max);
          if (t < 0.08) continue;
          const [r, g, b] = heatColor(t);
          ctx.fillStyle = `rgba(${r}, ${g}, ${b}, ${0.35 * t})`;
          ctx.fillRect(x * sx, y * sy, sx, sy);
        }
      }
    }
  }

  // Agents
  if (snapshot) {
    for (const a of snapshot.agents) {
      const color = ROLE_COLOR[a.role] ?? "#dfe6f2";
      const radius = Math.max(2, cell * 0.35);
      ctx.fillStyle = color;
      ctx.beginPath();
      ctx.arc(
        a.x * cell + cell / 2,
        a.y * cell + cell / 2,
        radius,
        0,
        Math.PI * 2
      );
      ctx.fill();
      if (a.role === "patient" && a.urgency === "critical") {
        ctx.strokeStyle = "#fff";
        ctx.lineWidth = 1;
        ctx.stroke();
      }
    }
  }
}

export default function SimCanvas({ grid, snapshot, showHeatmap }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  const cell = useMemo(() => {
    const targetW = 720;
    const targetH = 520;
    return Math.max(4, Math.floor(Math.min(targetW / grid.width, targetH / grid.height)));
  }, [grid.width, grid.height]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    canvas.width = grid.width * cell;
    canvas.height = grid.height * cell;
    drawFrame(canvas, grid, snapshot, cell, showHeatmap);
  }, [grid, snapshot, cell, showHeatmap]);

  return (
    <div className="sim-canvas-wrap">
      <canvas ref={canvasRef} />
    </div>
  );
}
