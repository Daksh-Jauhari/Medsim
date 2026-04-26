import type {
  BottleneckReport,
  GridMap,
  SimRequest,
  SimResult,
} from "../types";

const API_BASE: string =
  (import.meta.env.VITE_API_BASE as string | undefined) ??
  "http://localhost:8000";

async function handle<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      if (body && typeof body === "object" && "detail" in body) {
        detail = String((body as { detail: unknown }).detail);
      }
    } catch {
      // non-JSON error body
    }
    throw new Error(`API ${response.status}: ${detail}`);
  }
  return (await response.json()) as T;
}

export async function analyze(file: File): Promise<GridMap> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_BASE}/api/analyze`, {
    method: "POST",
    body: form,
  });
  return handle<GridMap>(res);
}

export async function simulate(request: SimRequest): Promise<SimResult> {
  const res = await fetch(`${API_BASE}/api/simulate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  return handle<SimResult>(res);
}

export async function generateReport(payload: {
  metrics: Record<string, unknown>;
  grid: GridMap;
}): Promise<BottleneckReport> {
  const res = await fetch(`${API_BASE}/api/report`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle<BottleneckReport>(res);
}

export const api = { analyze, simulate, generateReport };
