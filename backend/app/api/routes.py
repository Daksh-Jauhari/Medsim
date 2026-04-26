"""FastAPI routes: /api/analyze, /api/simulate, /api/report."""
from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, UploadFile

from ..report.generate_report import generate as generate_report
from ..schemas import BottleneckReport, GridMap, ReportRequest, SimRequest, SimResult
from ..sim.simulation import run_simulation
from ..vision.analyze_floor_plan import analyze as analyze_image

router = APIRouter()


@router.post("/analyze", response_model=GridMap)
async def analyze_endpoint(file: UploadFile = File(...)) -> GridMap:
    if file.content_type is None or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Upload must be an image file.")
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file upload.")
    try:
        return analyze_image(data, file.content_type)
    except RuntimeError as exc:
        # Missing API key, etc.
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Vision analysis failed: {exc}") from exc


@router.post("/simulate", response_model=SimResult)
async def simulate_endpoint(request: SimRequest) -> SimResult:
    try:
        return run_simulation(request)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Simulation failed: {exc}") from exc


@router.post("/report", response_model=BottleneckReport)
async def report_endpoint(payload: ReportRequest) -> BottleneckReport:
    try:
        return generate_report(payload.metrics, payload.grid)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Report generation failed: {exc}") from exc
