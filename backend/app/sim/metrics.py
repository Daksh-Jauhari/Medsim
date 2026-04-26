"""Post-run metric computation."""
from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from .simulation import Simulation


def compute_metrics(sim: "Simulation") -> dict:
    """Return a JSON-serialisable metrics dict summarising the run."""
    avg_wait_per_zone: dict[str, float] = {}
    for kind, total in sim.zone_wait_totals.items():
        count = sim.zone_wait_counts.get(kind, 0)
        avg_wait_per_zone[kind] = round(total / count, 2) if count else 0.0

    hm = sim.heatmap
    if hm.size == 0:
        p95 = 0.0
        hotspots: list[dict] = []
    else:
        p95 = float(np.percentile(hm, 95))
        # Top 5 hotspots by value
        flat = hm.flatten()
        idxs = np.argsort(flat)[-5:][::-1]
        hotspots = []
        for idx in idxs:
            y, x = int(idx // hm.shape[1]), int(idx % hm.shape[1])
            value = float(flat[idx])
            zone = sim.grid.zone_at(x, y)
            hotspots.append(
                {
                    "x": x,
                    "y": y,
                    "intensity": round(value, 2),
                    "zone": zone.label if zone else None,
                    "kind": zone.kind if zone else None,
                }
            )

    journey_stats: dict[str, float] = {}
    if sim.journey_times:
        arr = np.array(sim.journey_times, dtype=float)
        journey_stats = {
            "avg_ticks": round(float(arr.mean()), 2),
            "p50_ticks": round(float(np.percentile(arr, 50)), 2),
            "p90_ticks": round(float(np.percentile(arr, 90)), 2),
            "count": int(arr.size),
        }
    else:
        journey_stats = {"avg_ticks": 0.0, "p50_ticks": 0.0, "p90_ticks": 0.0, "count": 0}

    return {
        "ticks_run": sim.tick_count,
        "spawned": sim.spawned_count,
        "completed": sim.completed_count,
        "degraded": sim.degraded_count,
        "avg_wait_per_zone": avg_wait_per_zone,
        "max_queue_per_zone": dict(sim.zone_queue_max),
        "heatmap_p95": round(p95, 2),
        "hotspots": hotspots,
        "journey": journey_stats,
        "zones": [
            {"id": z.id, "label": z.label, "kind": z.kind}
            for z in sim.grid.zones
        ],
    }
