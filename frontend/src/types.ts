// Mirrors backend/app/schemas.py

export type ZoneKind =
  | "triage"
  | "imaging"
  | "surgery"
  | "icu"
  | "er"
  | "corridor"
  | "entrance"
  | "other";

export interface Zone {
  id: string;
  label: string;
  kind: ZoneKind;
  polygon: [number, number][];
}

export interface GridMap {
  width: number;
  height: number;
  cells: number[][]; // 0 walkable, 1 wall, 2 doorway
  zones: Zone[];
  spawn_points: [number, number][];
}

export interface AgentState {
  id: string;
  role: string; // "patient" | "nurse" | "doctor" | "equipment"
  x: number;
  y: number;
  status: string;
  urgency?: string | null;
}

export interface SimSnapshot {
  tick: number;
  agents: AgentState[];
  heatmap: number[][];
  events: string[];
}

export interface SimRequest {
  grid: GridMap;
  ticks: number;
  patient_spawn_rate: number;
  nurses: number;
  doctors: number;
}

export interface SimResult {
  snapshots: SimSnapshot[];
  metrics: Record<string, unknown>;
}

export interface Bottleneck {
  zone: string;
  description: string;
  root_cause: string;
  fix: string;
  minutes_saved_per_patient: number;
  patients_per_day: number;
  annual_minutes_saved: number;
}

export interface BottleneckReport {
  summary: string;
  bottlenecks: Bottleneck[];
}
