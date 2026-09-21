from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.maps import router as maps_router
from app.api.plans import router
from app.core.config import Settings
from app.core.errors import ControlledError
from app.core.logging import configure_logging
from app.core.middleware import RequestSizeLimit
from app.schemas.api import HealthResponse
from app.services.runs import RunService


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    configure_logging()
    service = RunService(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        await service.close()

    app = FastAPI(title="TripPilot", version="0.1.0", lifespan=lifespan)
    app.state.runs = service
    app.include_router(router)
    app.include_router(maps_router)
    app.state.settings = settings
    app.add_middleware(RequestSizeLimit)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    @app.exception_handler(ControlledError)
    async def controlled_error_handler(request: Request, exc: ControlledError) -> JSONResponse:
        status = {"NOT_FOUND": 404, "CONFLICT": 409, "CAPACITY": 503}.get(exc.error.code, 422)
        return JSONResponse(status_code=status, content={"error": exc.error.model_dump()})

    @app.exception_handler(RequestValidationError)
    async def invalid_input_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422, content={"error": ControlledError("INVALID_INPUT").error.model_dump()}
        )

    @app.get("/health", response_model=HealthResponse)
    async def health() -> dict:
        return {
            "status": "ok",
            "service": "TripPilot",
            "version": "0.1.0",
            "mode": "live" if settings.model_ready else "fixture",
            "providers": {
                "qwen": settings.model_ready,
                "amap": settings.amap_ready,
                "rail": settings.rail_provider or "mock",
            },
            "provider_status": {
                "qwen": {"state": "PENDING" if settings.model_ready else "UNCONFIGURED"},
                "amap": {"state": "PENDING" if settings.amap_ready else "MOCK"},
                "rail": {"state": "PENDING"},
            },
        }

    return app


app = create_app()
