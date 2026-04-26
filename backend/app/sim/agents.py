"""Agent classes for the simulation."""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

from .pathfinding import astar

if TYPE_CHECKING:
    from .simulation import Simulation


@dataclass
class Agent:
    id: str
    role: str
    x: int
    y: int
    status: str = "idle"
    path: list[tuple[int, int]] = field(default_factory=list)
    goal: Optional[tuple[int, int]] = None

    # --- helpers -------------------------------------------------------

    def set_goal(self, sim: "Simulation", goal: tuple[int, int]) -> None:
        self.goal = goal
        self.path = astar(sim.grid, (self.x, self.y), goal)

    def advance(self, sim: "Simulation", speed: int = 1) -> None:
        """Walk up to `speed` cells along the current path."""
        for _ in range(speed):
            if not self.path:
                return
            nx, ny = self.path.pop(0)
            # Avoid piling directly on another agent's cell (simple crowd)
            if sim.occupied(nx, ny, exclude=self.id):
                # yield a tick, replan if blocked repeatedly
                self.path.insert(0, (nx, ny))
                self._stuck_ticks = getattr(self, "_stuck_ticks", 0) + 1
                if self._stuck_ticks > 3 and self.goal is not None:
                    self._stuck_ticks = 0
                    self.path = astar(sim.grid, (self.x, self.y), self.goal)
                return
            self.x, self.y = nx, ny
            self._stuck_ticks = 0

    def at_goal(self) -> bool:
        if self.goal is None:
            return False
        return (self.x, self.y) == self.goal and not self.path

    def step(self, sim: "Simulation") -> None:  # pragma: no cover - overridden
        if self.path:
            self.advance(sim)


# --------------------------------------------------------------------- #
# Patient
# --------------------------------------------------------------------- #


URGENCY_SPEEDS = {"critical": 2, "serious": 1, "stable": 1}
URGENCY_WEIGHTS = [("stable", 0.55), ("serious", 0.30), ("critical", 0.15)]


@dataclass
class Patient(Agent):
    urgency: str = "stable"
    journey: list[str] = field(default_factory=list)  # zone kinds in order
    journey_index: int = 0
    wait_time: float = 0.0
    degraded: bool = False
    spawn_tick: int = 0
    completed_tick: Optional[int] = None
    service_until_tick: Optional[int] = None
    current_zone_kind: Optional[str] = None

    def step(self, sim: "Simulation") -> None:
        # Finished the whole journey -> leave through nearest entrance.
        if self.journey_index >= len(self.journey):
            if self.completed_tick is None:
                self.completed_tick = sim.tick_count
                sim.log(f"Patient {self.id} completed journey "
                        f"in {self.completed_tick - self.spawn_tick} ticks")
            # walk out to the exit (any spawn point)
            if not self.path and sim.grid.spawn_points:
                exit_pt = sim.grid.spawn_points[0]
                self.set_goal(sim, exit_pt)
                self.status = "leaving"
            self.advance(sim, speed=URGENCY_SPEEDS[self.urgency])
            if (self.x, self.y) in sim.grid.spawn_points and not self.path:
                sim.mark_departed(self.id)
            return

        target_kind = self.journey[self.journey_index]

        # If currently being serviced at an equipment, wait out the timer.
        if self.status == "in_service" and self.service_until_tick is not None:
            self.wait_time += 0
            if sim.tick_count >= self.service_until_tick:
                sim.log(f"Patient {self.id} done at {target_kind}")
                self.status = "traveling"
                self.service_until_tick = None
                self.journey_index += 1
                self.path = []
                self.goal = None
            return

        # If no goal yet, aim for a zone of the target kind.
        if self.goal is None or (not self.path and self.status == "traveling"):
            zone = sim.pick_zone_for_kind(target_kind)
            if zone is None:
                # skip stage
                self.journey_index += 1
                return
            self.current_zone_kind = target_kind
            destination = sim.grid.random_point_in_zone(zone.id, sim.rng)
            self.set_goal(sim, destination)
            if not self.path and (self.x, self.y) != destination:
                # unreachable; skip
                self.journey_index += 1
                return

        # Travel.
        self.status = "traveling"
        self.advance(sim, speed=URGENCY_SPEEDS[self.urgency])

        # Arrived at target zone cell?
        if not self.path:
            # Request service at this stage
            service_ticks = sim.service_time_for(target_kind, self.urgency)
            self.service_until_tick = sim.tick_count + service_ticks
            self.status = "in_service"
            sim.log(f"Patient {self.id} arrived at {target_kind} "
                    f"(wait {self.wait_time:.1f})")
            self.wait_time = 0.0
        else:
            self.wait_time += 0.1  # fractional minute per tick while moving

        # Critical patients degrade fast if they dawdle.
        if self.urgency == "critical" and self.wait_time > 30.0 and not self.degraded:
            self.degraded = True
            sim.log(f"Patient {self.id} condition degraded at {target_kind}")


# --------------------------------------------------------------------- #
# Nurse
# --------------------------------------------------------------------- #


@dataclass
class Nurse(Agent):
    fatigue: float = 0.0
    patrol_zone_kinds: list[str] = field(default_factory=lambda: ["triage", "er", "icu"])

    def step(self, sim: "Simulation") -> None:
        # Speed drops with fatigue.
        speed = 1 if self.fatigue < 0.5 else 1  # still 1 tile/tick; diagonal cost handles diffs
        if not self.path or self.at_goal():
            kind = sim.rng.choice(self.patrol_zone_kinds)
            zone = sim.pick_zone_for_kind(kind)
            if zone is not None:
                dest = sim.grid.random_point_in_zone(zone.id, sim.rng)
                self.set_goal(sim, dest)
                self.status = f"patrolling {kind}"
        self.advance(sim, speed=speed)
        self.fatigue = min(1.0, self.fatigue + 0.0005)


# --------------------------------------------------------------------- #
# Doctor
# --------------------------------------------------------------------- #


@dataclass
class Doctor(Agent):
    home_zone_id: Optional[str] = None

    def step(self, sim: "Simulation") -> None:
        if not self.path or self.at_goal():
            # 70% time at home zone, 30% wander to ER/surgery
            if self.home_zone_id and sim.rng.random() < 0.7:
                dest = sim.grid.random_point_in_zone(self.home_zone_id, sim.rng)
            else:
                kind = sim.rng.choice(["er", "surgery", "icu"])
                zone = sim.pick_zone_for_kind(kind)
                dest = sim.grid.random_point_in_zone(zone.id, sim.rng) if zone else None
            if dest is not None:
                self.set_goal(sim, dest)
                self.status = "rounding"
        self.advance(sim, speed=1)


# --------------------------------------------------------------------- #
# Equipment (static pieces with queues — not currently used as path actors)
# --------------------------------------------------------------------- #


@dataclass
class Equipment(Agent):
    queue: list[str] = field(default_factory=list)
    busy_until_tick: int = 0

    def step(self, sim: "Simulation") -> None:
        # Static; simulation.py uses equipment only for queue modelling.
        return


# --------------------------------------------------------------------- #
# Factory helpers
# --------------------------------------------------------------------- #


def sample_urgency(rng: random.Random) -> str:
    r = rng.random()
    cumulative = 0.0
    for kind, weight in URGENCY_WEIGHTS:
        cumulative += weight
        if r <= cumulative:
            return kind
    return "stable"


def default_journey(available_kinds: set[str], urgency: str) -> list[str]:
    """Pick a patient journey filtered to zone kinds that exist on this map."""
    if urgency == "critical":
        order = ["triage", "er", "imaging", "surgery", "icu"]
    elif urgency == "serious":
        order = ["triage", "imaging", "er"]
    else:
        order = ["triage", "imaging"]
    return [k for k in order if k in available_kinds]
