import logging
import secrets
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import settings
from app.lifespan import lifespan
from app.routes.deps import OrbitronAPIException
from app.routes.health import router as health_router
from app.routes.auth import router as auth_router
from app.routes.snapshot import router as snapshot_router
from app.routes.jobs import router as jobs_router
from app.routes.scheduling import router as scheduling_router
from app.routes.events import router as events_router
from app.routes.simulation import router as simulation_router
from app.routes.transfers import router as transfers_router
from app.routes.security_checks import router as security_checks_router
from app.routes.evaluations import router as evaluations_router
from app.routes.operations import router as operations_router
from app.routes.ingestion import router as ingestion_router

logger = logging.getLogger("orbitron")

app = FastAPI(
    title="Orbitron Backend",
    version="1.0.0",
    description="Authoritative application service for satellite downlink scheduling and ground station sharing",
    lifespan=lifespan
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.orbitron_frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request ID middleware
@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    req_id = request.headers.get("X-Request-ID") or f"req-{secrets.token_hex(6)}"
    request.state.request_id = req_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = req_id
    return response

# Standardized Error Handlers
@app.exception_handler(OrbitronAPIException)
async def orbitron_exception_handler(request: Request, exc: OrbitronAPIException):
    req_id = getattr(request.state, "request_id", f"req-{secrets.token_hex(6)}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
                "request_id": req_id
            }
        }
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    req_id = getattr(request.state, "request_id", f"req-{secrets.token_hex(6)}")
    details = []
    for err in exc.errors():
        loc_parts = [str(p) for p in err.get("loc", []) if p != "body"]
        field_name = ".".join(loc_parts) or "body"
        details.append({
            "field": field_name,
            "message": err.get("msg", "Invalid value")
        })

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "The request could not be accepted due to semantic validation failures.",
                "details": details,
                "request_id": req_id
            }
        }
    )

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    req_id = getattr(request.state, "request_id", f"req-{secrets.token_hex(6)}")
    code_map = {
        400: "BAD_REQUEST",
        401: "UNAUTHENTICATED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        405: "METHOD_NOT_ALLOWED",
        409: "CONFLICT",
        422: "VALIDATION_ERROR",
        429: "RATE_LIMITED",
        503: "SERVICE_UNAVAILABLE"
    }
    code = code_map.get(exc.status_code, "HTTP_ERROR")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": code,
                "message": str(exc.detail),
                "details": [],
                "request_id": req_id
            }
        }
    )

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    req_id = getattr(request.state, "request_id", f"req-{secrets.token_hex(6)}")
    logger.error(f"Unhandled server error [req_id={req_id}]: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An internal error occurred. Please contact network administrator.",
                "details": [],
                "request_id": req_id
            }
        }
    )

# Register routers under /api/v1
api_v1_prefix = "/api/v1"
app.include_router(health_router, prefix=api_v1_prefix)
app.include_router(auth_router, prefix=api_v1_prefix)
app.include_router(snapshot_router, prefix=api_v1_prefix)
app.include_router(jobs_router, prefix=api_v1_prefix)
app.include_router(scheduling_router, prefix=api_v1_prefix)
app.include_router(events_router, prefix=api_v1_prefix)
app.include_router(simulation_router, prefix=api_v1_prefix)
app.include_router(transfers_router, prefix=api_v1_prefix)
app.include_router(security_checks_router, prefix=api_v1_prefix)
app.include_router(evaluations_router, prefix=api_v1_prefix)
app.include_router(operations_router, prefix=api_v1_prefix)
app.include_router(ingestion_router, prefix=api_v1_prefix)

# Also expose health at root /health for convenience
app.include_router(health_router)
