"""A* pathfinding on a Grid. 8-neighbor movement, octile heuristic."""
from __future__ import annotations

import heapq
import math

from .grid import Grid

SQRT2 = math.sqrt(2.0)

# (dx, dy, cost)
_NEIGHBORS: tuple[tuple[int, int, float], ...] = (
    (1, 0, 1.0),
    (-1, 0, 1.0),
    (0, 1, 1.0),
    (0, -1, 1.0),
    (1, 1, SQRT2),
    (1, -1, SQRT2),
    (-1, 1, SQRT2),
    (-1, -1, SQRT2),
)


def octile(a: tuple[int, int], b: tuple[int, int]) -> float:
    dx = abs(a[0] - b[0])
    dy = abs(a[1] - b[1])
    return (dx + dy) + (SQRT2 - 2.0) * min(dx, dy)


def astar(
    grid: Grid,
    start: tuple[int, int],
    goal: tuple[int, int],
    max_expansions: int = 8000,
) -> list[tuple[int, int]]:
    """Return a list of grid cells from start to goal (inclusive of goal,
    excluding start), or [] if no path found within max_expansions."""

    start = (int(start[0]), int(start[1]))
    goal = (int(goal[0]), int(goal[1]))

    if start == goal:
        return []
    if not grid.in_bounds(*goal):
        return []
    if not grid.is_walkable(*goal):
        goal = grid.nearest_walkable(*goal)
        if not grid.is_walkable(*goal):
            return []
    if not grid.is_walkable(*start):
        start = grid.nearest_walkable(*start)

    open_heap: list[tuple[float, int, tuple[int, int]]] = []
    counter = 0
    heapq.heappush(open_heap, (0.0, counter, start))
    came_from: dict[tuple[int, int], tuple[int, int]] = {}
    g_score: dict[tuple[int, int], float] = {start: 0.0}
    closed: set[tuple[int, int]] = set()

    expansions = 0
    while open_heap and expansions < max_expansions:
        _, _, current = heapq.heappop(open_heap)
        if current in closed:
            continue
        if current == goal:
            return _reconstruct(came_from, current)
        closed.add(current)
        expansions += 1

        cx, cy = current
        for dx, dy, cost in _NEIGHBORS:
            nx, ny = cx + dx, cy + dy
            if not grid.in_bounds(nx, ny):
                continue
            if not grid.is_walkable(nx, ny):
                continue
            # disallow diagonal squeeze through walls
            if dx != 0 and dy != 0:
                if not grid.is_walkable(cx + dx, cy) or not grid.is_walkable(cx, cy + dy):
                    continue
            neighbor = (nx, ny)
            if neighbor in closed:
                continue
            tentative = g_score[current] + cost
            if tentative < g_score.get(neighbor, float("inf")):
                came_from[neighbor] = current
                g_score[neighbor] = tentative
                f = tentative + octile(neighbor, goal)
                counter += 1
                heapq.heappush(open_heap, (f, counter, neighbor))

    return []


def _reconstruct(came_from: dict[tuple[int, int], tuple[int, int]],
                 current: tuple[int, int]) -> list[tuple[int, int]]:
    path: list[tuple[int, int]] = [current]
    while current in came_from:
        current = came_from[current]
        path.append(current)
    path.reverse()
    # drop the start cell so the agent steps onto the next cell
    return path[1:]
