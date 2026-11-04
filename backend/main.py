"""Local application API. Run: python -m uvicorn backend.main:app --reload."""
import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from time import perf_counter

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware

from backend.schemas import HealthResponse, PredictionResponse, Tower
from speedmap import config

logger = logging.getLogger("uvicorn.error")


def create_app(mode: str | None = None, predictor=None) -> FastAPI:
    selected_mode = mode or os.getenv("SPEEDMAP_MODE", "demo")
    if selected_mode not in {"demo", "model"}:
        raise ValueError("SPEEDMAP_MODE must be 'demo' or 'model'.")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.predictor = predictor
        if app.state.predictor is None:
            try:
                if selected_mode == "demo":
                    from backend.demo import DemoPredictor

                    app.state.predictor = DemoPredictor()
                else:
                    from speedmap.inference.predictor import Predictor

                    app.state.predictor = Predictor(
                        os.getenv("SPEEDMAP_MODEL_NAME", "hybrid"),
                        os.getenv("SPEEDMAP_MODEL_RUN") or None,
                    )
            except Exception:
                logger.exception("Predictor unavailable; API will return 503. Mode=%s", selected_mode)
        yield
        app.state.predictor = None

    app = FastAPI(title="Hanoi Signal API", version="0.2.0", lifespan=lifespan)
    origins = os.getenv("SPEEDMAP_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[origin.strip() for origin in origins.split(",") if origin.strip()],
        allow_methods=["GET"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def log_request(request: Request, call_next):
        started = perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        finally:
            logger.info(json.dumps({
                "event": "request", "time": datetime.now(timezone.utc).isoformat(), "path": request.url.path,
                "method": request.method, "status": status,
                "duration_ms": round((perf_counter() - started) * 1000, 2),
                "lat": request.query_params.get("lat"), "lon": request.query_params.get("lon"),
                "mode": selected_mode,
            }))

    def get_predictor():
        service = app.state.predictor
        if service is None:
            raise HTTPException(503, "Prediction service unavailable. Check the backend logs and model setup.")
        return service

    @app.get("/api/health", response_model=HealthResponse)
    def health():
        service = app.state.predictor
        return {
            "status": "ok" if service is not None else "unavailable",
            "ready": service is not None,
            "mode": selected_mode,
            "model_loaded": selected_mode == "model" and service is not None,
            "model_version": getattr(service, "version", None),
            "tower_count": len(service.tower_list()) if service is not None else 0,
        }

    @app.get("/api/boundary")
    def boundary():
        return json.loads(config.HANOI_BOUNDARY_FILE.read_text(encoding="utf-8"))

    @app.get("/api/towers", response_model=list[Tower])
    def towers():
        return get_predictor().tower_list()

    @app.get("/api/predict", response_model=PredictionResponse)
    def predict(
        lat: float = Query(..., ge=-90, le=90, allow_inf_nan=False),
        lon: float = Query(..., ge=-180, le=180, allow_inf_nan=False),
    ):
        if not config.inside_hanoi(lat, lon):
            raise HTTPException(422, "This point is outside Hanoi. Choose a location inside the city boundary.")
        try:
            result = PredictionResponse.model_validate(get_predictor().predict(lat, lon))
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception("Prediction failed")
            raise HTTPException(503, "Could not estimate this location. Try again or check the backend logs.") from exc
        logger.info(json.dumps({
            "event": "prediction", "lat": lat, "lon": lon,
            "download_mbps": result.download_mbps, "model_version": result.model_version,
        }))
        return result

    return app


app = create_app()
