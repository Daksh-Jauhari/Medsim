"""Grid wrapper around a numpy cell array plus zone lookup."""
from __future__ import annotations

import random
from typing import Optional

import numpy as np

from ..schemas import GridMap, Zone


def _point_in_polygon(x: int, y: int, polygon: list[tuple[int, int]]) -> bool:
    """Standard ray-cast point-in-polygon. Polygon is a list of (x, y) ints."""
    n = len(polygon)
    if n < 3:
        return False
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        intersects = ((yi > y) != (yj > y)) and (
            x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-9) + xi
        )
        if intersects:
            inside = not inside
        j = i
    return inside


class Grid:
    """Walkability + zone queries for the simulation."""

    def __init__(self, gridmap: GridMap) -> None:
        self.width = gridmap.width
        self.height = gridmap.height
        self.zones: list[Zone] = gridmap.zones
        self.spawn_points: list[tuple[int, int]] = [tuple(p) for p in gridmap.spawn_points]

        cells = np.array(gridmap.cells, dtype=np.int16)
        if cells.shape != (self.height, self.width):
            # defensively reshape / pad with walls
            fixed = np.ones((self.height, self.width), dtype=np.int16)
            h = min(cells.shape[0], self.height)
            w = min(cells.shape[1], self.width)
            fixed[:h, :w] = cells[:h, :w]
            cells = fixed
        self.cells = cells

        # Precompute zone masks (bool array per zone id).
        self._zone_mask: dict[str, np.ndarray] = {}
        self._zone_cells: dict[str, list[tuple[int, int]]] = {}
        for z in self.zones:
            mask = np.zeros((self.height, self.width), dtype=bool)
            coords: list[tuple[int, int]] = []
            if z.polygon:
                # bounding box prune for speed
                xs = [p[0] for p in z.polygon]
                ys = [p[1] for p in z.polygon]
                x0, x1 = max(0, min(xs)), min(self.width - 1, max(xs))
                y0, y1 = max(0, min(ys)), min(self.height - 1, max(ys))
                for y in range(y0, y1 + 1):
                    for x in range(x0, x1 + 1):
                        if _point_in_polygon(x, y, z.polygon):
                            mask[y, x] = True
                            if self.is_walkable(x, y):
                                coords.append((x, y))
            self._zone_mask[z.id] = mask
            self._zone_cells[z.id] = coords

        if not self.spawn_points:
            # fallback: first entrance zone center, else any walkable cell
            entrance = next((z for z in self.zones if z.kind == "entrance"), None)
            if entrance and self._zone_cells.get(entrance.id):
                self.spawn_points = [self._zone_cells[entrance.id][0]]
            else:
                ys, xs = np.where(self.cells != 1)
                if len(xs):
                    self.spawn_points = [(int(xs[0]), int(ys[0]))]
                else:
                    self.spawn_points = [(0, 0)]

    # --- basic queries -------------------------------------------------

    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def is_walkable(self, x: int, y: int) -> bool:
        if not self.in_bounds(x, y):
            return False
        return int(self.cells[y, x]) != 1  # walls block; doorways pass

    def zone_at(self, x: int, y: int) -> Optional[Zone]:
        if not self.in_bounds(x, y):
            return None
        for z in self.zones:
            if self._zone_mask[z.id][y, x]:
                return z
        return None

    def zones_of_kind(self, kind: str) -> list[Zone]:
        return [z for z in self.zones if z.kind == kind]

    def zone_by_id(self, zone_id: str) -> Optional[Zone]:
        return next((z for z in self.zones if z.id == zone_id), None)

    def zone_center(self, zone_id: str) -> tuple[int, int]:
        coords = self._zone_cells.get(zone_id, [])
        if not coords:
            z = self.zone_by_id(zone_id)
            if z and z.polygon:
                xs = [p[0] for p in z.polygon]
                ys = [p[1] for p in z.polygon]
                return (sum(xs) // len(xs), sum(ys) // len(ys))
            return (self.width // 2, self.height // 2)
        cx = sum(c[0] for c in coords) // len(coords)
        cy = sum(c[1] for c in coords) // len(coords)
        # snap to a walkable cell within the zone
        best = min(coords, key=lambda p: (p[0] - cx) ** 2 + (p[1] - cy) ** 2)
        return best

    def random_point_in_zone(self, zone_id: str, rng: Optional[random.Random] = None) -> tuple[int, int]:
        rng = rng or random
        coords = self._zone_cells.get(zone_id, [])
        if not coords:
            return self.zone_center(zone_id)
        return rng.choice(coords)

    def nearest_walkable(self, x: int, y: int) -> tuple[int, int]:
        """Return the closest walkable cell by BFS (small radius)."""
        if self.is_walkable(x, y):
            return (x, y)
        seen = {(x, y)}
        frontier: list[tuple[int, int]] = [(x, y)]
        for _ in range(64):  # bounded search
            nxt: list[tuple[int, int]] = []
            for cx, cy in frontier:
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nx, ny = cx + dx, cy + dy
                    if (nx, ny) in seen or not self.in_bounds(nx, ny):
                        continue
                    seen.add((nx, ny))
                    if self.is_walkable(nx, ny):
                        return (nx, ny)
                    nxt.append((nx, ny))
            frontier = nxt
            if not frontier:
                break
        return (x, y)
