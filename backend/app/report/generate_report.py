"""Use Claude to turn sim metrics into a bottleneck report."""
from __future__ import annotations

import json
import re

from anthropic import Anthropic

from ..config import get_settings, require_api_key
from ..schemas import Bottleneck, BottleneckReport, GridMap

# TODO: wire real prompt — tune with stakeholder vocabulary once we settle on tone.
SYSTEM_PROMPT = """You are a hospital operations analyst. Given simulation
metrics and a zone layout, identify the top 1-4 bottlenecks and propose fixes.

Return ONLY JSON in this schema (no prose, no code fences):

{
  "summary": "<2-3 sentence executive summary>",
  "bottlenecks": [
    {
      "zone": "<zone label>",
      "description": "<what is going wrong>",
      "root_cause": "<why>",
      "fix": "<concrete actionable intervention>",
      "minutes_saved_per_patient": <float>,
      "patients_per_day": <int>,
      "annual_minutes_saved": <int>    // roughly minutes_saved_per_patient * patients_per_day * 365
    }
  ]
}

Be realistic with numbers: minutes_saved_per_patient typically 2-25, patients_per_day
typically 20-400 depending on zone. Compute annual_minutes_saved yourself.
"""


def _strip_code_fences(text: str) -> str:
    fence = re.match(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", text, re.DOTALL)
    if fence:
        return fence.group(1)
    return text.strip()


def _fallback_report(metrics: dict) -> BottleneckReport:
    """If Claude fails or returns garbage, derive a crude report from metrics."""
    waits = metrics.get("avg_wait_per_zone", {})
    if not waits:
        return BottleneckReport(
            summary="No bottlenecks detected in this short run.",
            bottlenecks=[],
        )
    worst = max(waits.items(), key=lambda kv: kv[1])
    kind, wait = worst
    minutes_saved = round(max(2.0, float(wait) * 0.6), 1)
    patients = 80
    return BottleneckReport(
        summary=f"{kind.title()} appears to be the primary bottleneck with "
                f"an average wait of {wait} minutes during the simulated window.",
        bottlenecks=[
            Bottleneck(
                zone=kind.title(),
                description=f"Patients accumulate in {kind} while staff are "
                            f"occupied elsewhere.",
                root_cause="Staff allocation is not matched to arrival rate.",
                fix=f"Add a dedicated triage nurse to {kind} during peak hours "
                    f"and pre-position the next patient when service time runs long.",
                minutes_saved_per_patient=minutes_saved,
                patients_per_day=patients,
                annual_minutes_saved=int(minutes_saved * patients * 365),
            )
        ],
    )


def generate(metrics: dict, grid: GridMap) -> BottleneckReport:
    """Call Claude with metrics + layout, parse a BottleneckReport, or fall back."""
    require_api_key()
    settings = get_settings()
    client = Anthropic(api_key=settings.anthropic_api_key)

    # Keep the prompt payload tight — drop the heatmap itself.
    layout_summary = {
        "width": grid.width,
        "height": grid.height,
        "zones": [{"id": z.id, "label": z.label, "kind": z.kind} for z in grid.zones],
    }

    user_text = (
        "Simulation metrics:\n"
        + json.dumps(metrics, indent=2)
        + "\n\nZone layout:\n"
        + json.dumps(layout_summary, indent=2)
        + "\n\nReturn the BottleneckReport JSON now."
    )

    try:
        response = client.messages.create(
            model=settings.claude_model,
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_text}],
        )
        raw = response.content[0].text if response.content else ""
        cleaned = _strip_code_fences(raw)
        data = json.loads(cleaned)
        return BottleneckReport(**data)
    except Exception:
        return _fallback_report(metrics)
