"""Claude vision: turn a floor-plan image into a GridMap JSON."""
from __future__ import annotations

import base64
import json
import re

from anthropic import Anthropic

from ..config import get_settings, require_api_key
from ..schemas import GridMap, Zone

# TODO: wire real prompt — tune with few-shot examples once we have sample plans.
SYSTEM_PROMPT = """You are a hospital floor-plan interpreter. Given an image of
a hospital floor plan, output ONLY a JSON object matching this schema (no prose,
no code fences):

{
  "width": int,                // grid columns, 20-60
  "height": int,               // grid rows, 15-45
  "cells": [[int, ...], ...],  // rows of height x width; 0=walkable, 1=wall, 2=doorway
  "zones": [
    {
      "id": "z1",
      "label": "Triage",
      "kind": "triage|imaging|surgery|icu|er|corridor|entrance|other",
      "polygon": [[x, y], ...]
    }
  ],
  "spawn_points": [[x, y], ...]  // typically entrance doorways
}

Rules:
- cells is height rows of width columns.
- Include at least one "entrance" zone with a spawn point.
- Coordinates are integer grid cells, origin top-left.
- Output only JSON, no explanations, no markdown fences.
"""

USER_TEXT = (
    "Analyze this hospital floor plan and return the GridMap JSON. "
    "Aim for roughly a 40x30 grid. Identify triage, imaging, surgery, ICU, "
    "ER, corridors, and entrances. Mark walls as 1, doorways as 2, walkable "
    "space as 0."
)


def _strip_code_fences(text: str) -> str:
    """Claude occasionally wraps JSON in ```json fences even when told not to."""
    fence = re.match(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", text, re.DOTALL)
    if fence:
        return fence.group(1)
    return text.strip()


def _fallback_grid() -> GridMap:
    """Minimal 40x30 layout used when parsing fails so the UI keeps flowing."""
    width, height = 40, 30
    cells: list[list[int]] = [
        [1 if (x == 0 or y == 0 or x == width - 1 or y == height - 1) else 0 for x in range(width)]
        for y in range(height)
    ]
    # doorway on the left edge
    cells[height // 2][0] = 2

    zones = [
        Zone(id="z_entrance", label="Entrance", kind="entrance",
             polygon=[(1, height // 2 - 2), (4, height // 2 - 2),
                      (4, height // 2 + 2), (1, height // 2 + 2)]),
        Zone(id="z_triage", label="Triage", kind="triage",
             polygon=[(6, 2), (14, 2), (14, 10), (6, 10)]),
        Zone(id="z_imaging", label="Imaging", kind="imaging",
             polygon=[(16, 2), (24, 2), (24, 10), (16, 10)]),
        Zone(id="z_surgery", label="Surgery", kind="surgery",
             polygon=[(26, 2), (38, 2), (38, 10), (26, 10)]),
        Zone(id="z_icu", label="ICU", kind="icu",
             polygon=[(6, 18), (14, 18), (14, 28), (6, 28)]),
        Zone(id="z_er", label="ER", kind="er",
             polygon=[(16, 18), (28, 18), (28, 28), (16, 28)]),
    ]
    spawn_points = [(1, height // 2)]
    return GridMap(width=width, height=height, cells=cells,
                   zones=zones, spawn_points=spawn_points)


def analyze(image_bytes: bytes, mime: str) -> GridMap:
    """Send the image to Claude and parse a GridMap out of the response."""
    require_api_key()
    settings = get_settings()
    client = Anthropic(api_key=settings.anthropic_api_key)

    b64 = base64.standard_b64encode(image_bytes).decode("ascii")

    response = client.messages.create(
        model=settings.claude_model,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": mime,
                            "data": b64,
                        },
                    },
                    {"type": "text", "text": USER_TEXT},
                ],
            }
        ],
    )

    if not response.content:
        raise ValueError("Claude returned no content for the floor plan analysis.")

    raw = response.content[0].text if hasattr(response.content[0], "text") else ""
    cleaned = _strip_code_fences(raw)

    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        # hackathon-friendly: don't bail the whole flow
        fb = _fallback_grid()
        fb_dict = fb.model_dump()
        fb_dict["_parse_error"] = f"{exc.msg} at pos {exc.pos}"
        return GridMap(**{k: v for k, v in fb_dict.items() if not k.startswith("_")})

    try:
        return GridMap(**payload)
    except Exception:
        return _fallback_grid()
