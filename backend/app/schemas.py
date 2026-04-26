"""Pydantic schemas shared by API, simulation, and Claude IO."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

ZoneKind = Literal[
    "triage",
    "imaging",
    "surgery",
    "icu",
    "er",
    "corridor",
    "entrance",
    "other",
]

CellValue = int  # 0 walkable, 1 wall, 2 doorway


class Zone(BaseModel):
    id: str
    label: str
    kind: ZoneKind
    polygon: list[tuple[int, int]] = Field(default_factory=list)


class GridMap(BaseModel):
    width: int
    height: int
    # cells[y][x] layout: 0=walkable, 1=wall, 2=doorway
    cells: list[list[CellValue]]
    zones: list[Zone] = Field(default_factory=list)
    spawn_points: list[tuple[int, int]] = Field(default_factory=list)


class AgentState(BaseModel):
    id: str
    role: str  # "patient" | "nurse" | "doctor" | "equipment"
    x: float
    y: float
    status: str
    urgency: Optional[str] = None


class SimSnapshot(BaseModel):
    tick: int
    agents: list[AgentState]
    heatmap: list[list[float]]
    events: list[str] = Field(default_factory=list)


class SimRequest(BaseModel):
    grid: GridMap
    ticks: int = 600
    patient_spawn_rate: float = 0.05
    nurses: int = 4
    doctors: int = 2


class SimResult(BaseModel):
    snapshots: list[SimSnapshot]
    metrics: dict


class Bottleneck(BaseModel):
    zone: str
    description: str
    root_cause: str
    fix: str
    minutes_saved_per_patient: float
    patients_per_day: int
    annual_minutes_saved: int


class BottleneckReport(BaseModel):
    summary: str
    bottlenecks: list[Bottleneck] = Field(default_factory=list)


class ReportRequest(BaseModel):
    metrics: dict
    grid: GridMap
