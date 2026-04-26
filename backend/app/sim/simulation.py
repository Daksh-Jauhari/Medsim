"""Tick-based simulation orchestrating patients, nurses, doctors."""
from __future__ import annotations

import random
from typing import Optional

import numpy as np

from ..schemas import AgentState, GridMap, SimRequest, SimResult, SimSnapshot, Zone
from .agents import (
    Doctor,
    Nurse,
    Patient,
    default_journey,
    sample_urgency,
)
from .grid import Grid
from .metrics import compute_metrics

SERVICE_TIMES: dict[str, int] = {
    # base service time in ticks per zone kind
    "triage": 15,
    "imaging": 40,
    "surgery": 90,
    "icu": 60,
    "er": 30,
    "corridor": 1,
    "entrance": 1,
    "other": 10,
}

URGENCY_SERVICE_MULT = {"critical": 0.7, "serious": 1.0, "stable": 1.2}


class Simulation:
    """Deterministic per-run simulation (seeded RNG)."""

    def __init__(self, request: SimRequest, seed: int = 42) -> None:
        self.request = request
        self.grid = Grid(request.grid)
        self.rng = random.Random(seed)
        self.tick_count: int = 0

        self.patients: dict[str, Patient] = {}
        self.nurses: list[Nurse] = []
        self.doctors: list[Doctor] = []
        self.departed_ids: set[str] = set()

        self.heatmap = np.zeros((self.grid.height, self.grid.width), dtype=np.float32)
        self.events: list[str] = []
        self.pending_events: list[str] = []

        # metrics aggregates
        self.zone_wait_totals: dict[str, float] = {}
        self.zone_wait_counts: dict[str, int] = {}
        self.zone_queue_max: dict[str, int] = {}
        self.journey_times: list[int] = []
        self.degraded_count: int = 0
        self.completed_count: int = 0
        self.spawned_count: int = 0

        self._available_kinds: set[str] = {z.kind for z in self.grid.zones}
        self._next_patient_id = 0

        self._spawn_staff()

    # --- public API ----------------------------------------------------

    def run(self) -> SimResult:
        total_ticks = max(1, int(self.request.ticks))
        snapshots: list[SimSnapshot] = []
        # Keep roughly 60 snapshots
        stride = max(1, total_ticks // 60)

        for _ in range(total_ticks):
            self.tick()
            if self.tick_count % stride == 0 or self.tick_count == total_ticks:
                snapshots.append(self._snapshot())

        metrics = compute_metrics(self)
        return SimResult(snapshots=snapshots, metrics=metrics)

    def tick(self) -> None:
        self.tick_count += 1
        self.pending_events = []

        # Maybe spawn a new patient
        if self.rng.random() < self.request.patient_spawn_rate:
            self._spawn_patient()

        # Step nurses & doctors
        for nurse in self.nurses:
            nurse.step(self)
            self._stamp_heatmap(nurse.x, nurse.y)

        for doc in self.doctors:
            doc.step(self)
            self._stamp_heatmap(doc.x, doc.y)

        # Step patients
        to_remove: list[str] = []
        # track zone occupancy for queue metric
        zone_counts: dict[str, int] = {}
        for pid, patient in self.patients.items():
            patient.step(self)
            self._stamp_heatmap(patient.x, patient.y)
            z = self.grid.zone_at(patient.x, patient.y)
            if z is not None and patient.status != "leaving":
                zone_counts[z.kind] = zone_counts.get(z.kind, 0) + 1
                if patient.status == "traveling":
                    self.zone_wait_totals[z.kind] = self.zone_wait_totals.get(z.kind, 0.0) + 0.1
                    self.zone_wait_counts[z.kind] = self.zone_wait_counts.get(z.kind, 0) + 1
            if pid in self.departed_ids:
                to_remove.append(pid)

        for kind, count in zone_counts.items():
            if count > self.zone_queue_max.get(kind, 0):
                self.zone_queue_max[kind] = count

        for pid in to_remove:
            p = self.patients.pop(pid, None)
            if p is not None:
                self.completed_count += 1
                if p.degraded:
                    self.degraded_count += 1
                if p.completed_tick is not None:
                    self.journey_times.append(p.completed_tick - p.spawn_tick)

        # Fade heatmap slightly so recent activity dominates
        self.heatmap *= 0.995

        # Move per-tick events into the rolling log
        if self.pending_events:
            self.events.extend(self.pending_events)
            # cap log length
            if len(self.events) > 500:
                self.events = self.events[-500:]

    # --- sim helpers ---------------------------------------------------

    def occupied(self, x: int, y: int, exclude: Optional[str] = None) -> bool:
        for p in self.patients.values():
            if p.id == exclude:
                continue
            if p.x == x and p.y == y:
                return True
        for n in self.nurses:
            if n.id == exclude:
                continue
            if n.x == x and n.y == y:
                return True
        for d in self.doctors:
            if d.id == exclude:
                continue
            if d.x == x and d.y == y:
                return True
        return False

    def mark_departed(self, patient_id: str) -> None:
        self.departed_ids.add(patient_id)

    def log(self, msg: str) -> None:
        self.pending_events.append(f"t={self.tick_count} {msg}")

    def pick_zone_for_kind(self, kind: str) -> Optional[Zone]:
        zs = self.grid.zones_of_kind(kind)
        if not zs:
            return None
        # prefer the least congested zone of that kind
        return min(zs, key=lambda z: self._zone_population(z.id))

    def _zone_population(self, zone_id: str) -> int:
        count = 0
        for p in self.patients.values():
            z = self.grid.zone_at(p.x, p.y)
            if z is not None and z.id == zone_id:
                count += 1
        return count

    def service_time_for(self, zone_kind: str, urgency: str) -> int:
        base = SERVICE_TIMES.get(zone_kind, 10)
        mult = URGENCY_SERVICE_MULT.get(urgency, 1.0)
        jitter = self.rng.uniform(0.85, 1.15)
        return max(1, int(base * mult * jitter))

    # --- spawn ---------------------------------------------------------

    def _spawn_staff(self) -> None:
        for i in range(self.request.nurses):
            pt = self._staff_spawn_point(i)
            self.nurses.append(Nurse(id=f"nurse_{i}", role="nurse", x=pt[0], y=pt[1]))

        surgery_zone = next((z for z in self.grid.zones if z.kind == "surgery"), None)
        er_zone = next((z for z in self.grid.zones if z.kind == "er"), None)
        icu_zone = next((z for z in self.grid.zones if z.kind == "icu"), None)
        home_options = [z for z in (surgery_zone, er_zone, icu_zone) if z is not None]

        for i in range(self.request.doctors):
            pt = self._staff_spawn_point(i + 100)
            home = home_options[i % len(home_options)] if home_options else None
            self.doctors.append(
                Doctor(id=f"doc_{i}", role="doctor", x=pt[0], y=pt[1],
                       home_zone_id=home.id if home else None)
            )

    def _staff_spawn_point(self, seed_offset: int) -> tuple[int, int]:
        # prefer a corridor, fall back to a walkable cell
        corridors = [z for z in self.grid.zones if z.kind == "corridor"]
        if corridors:
            z = corridors[seed_offset % len(corridors)]
            return self.grid.random_point_in_zone(z.id, self.rng)
        # any walkable cell
        for _ in range(50):
            x = self.rng.randrange(0, self.grid.width)
            y = self.rng.randrange(0, self.grid.height)
            if self.grid.is_walkable(x, y):
                return (x, y)
        return self.grid.spawn_points[0] if self.grid.spawn_points else (0, 0)

    def _spawn_patient(self) -> None:
        if not self.grid.spawn_points:
            return
        spawn = self.rng.choice(self.grid.spawn_points)
        spawn = self.grid.nearest_walkable(*spawn)
        pid = f"p_{self._next_patient_id}"
        self._next_patient_id += 1
        urgency = sample_urgency(self.rng)
        journey = default_journey(self._available_kinds, urgency)
        patient = Patient(
            id=pid,
            role="patient",
            x=spawn[0],
            y=spawn[1],
            status="traveling",
            urgency=urgency,
            journey=journey,
            spawn_tick=self.tick_count,
        )
        self.patients[pid] = patient
        self.spawned_count += 1
        self.log(f"Patient {pid} arrived ({urgency})")

    # --- snapshot / heatmap -------------------------------------------

    def _stamp_heatmap(self, x: int, y: int) -> None:
        if 0 <= x < self.grid.width and 0 <= y < self.grid.height:
            self.heatmap[y, x] += 1.0

    def _snapshot(self) -> SimSnapshot:
        agents: list[AgentState] = []
        for p in self.patients.values():
            agents.append(AgentState(id=p.id, role="patient", x=float(p.x), y=float(p.y),
                                     status=p.status, urgency=p.urgency))
        for n in self.nurses:
            agents.append(AgentState(id=n.id, role="nurse", x=float(n.x), y=float(n.y),
                                     status=n.status))
        for d in self.doctors:
            agents.append(AgentState(id=d.id, role="doctor", x=float(d.x), y=float(d.y),
                                     status=d.status))

        # Downsample heatmap only if huge; otherwise pass through.
        hm = self.heatmap
        if hm.size > 40 * 30 * 4:
            # average-pool 2x2
            h, w = hm.shape
            new_h, new_w = h // 2, w // 2
            hm = hm[: new_h * 2, : new_w * 2].reshape(new_h, 2, new_w, 2).mean(axis=(1, 3))
        heatmap_list = hm.astype(float).tolist()

        events = list(self.pending_events)
        return SimSnapshot(
            tick=self.tick_count,
            agents=agents,
            heatmap=heatmap_list,
            events=events,
        )


def run_simulation(request: SimRequest) -> SimResult:
    sim = Simulation(request)
    return sim.run()


def build_gridmap_stub() -> GridMap:  # pragma: no cover - dev helper
    """Used only in ad-hoc testing; API never calls this."""
    from ..vision.analyze_floor_plan import _fallback_grid
    return _fallback_grid()
