import logging
import os
import time
import traceback
import uuid

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

# Ensure local .env environment variables are loaded
load_dotenv()

from logging_config import configure_logging

configure_logging()
log = logging.getLogger(__name__)

from api.routers import analytics, clima, culturas, insumos, municipios, producao, zarc

# Read the rate-limit value dynamically, with a safe fallback to 30
rate_limit_val = os.getenv("API_LIMIT_PER_MINUTE", "30").strip()
limiter = Limiter(key_func=get_remote_address, default_limits=[f"{rate_limit_val} per minute"])

app = FastAPI(
    title="AgroHarvest API",
    description="API somente-leitura para dados agropecuários do projeto AgroHarvest BR.",
    version="1.0.0",
)

# ALLOWED_ORIGINS: comma-separated list, for example: "http://localhost:3000,https://mydomain.com"
# When unset, use wildcard WITHOUT credentials (safe for public read-only APIs).
_raw_origins = os.getenv("ALLOWED_ORIGINS", "").strip()
if _raw_origins:
    _origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]
    _allow_credentials = True  # origins específicas permitem credentials
else:
    _origins = ["*"]  # wildcard: sem credentials (obrigatório pelo spec CORS)
    _allow_credentials = False

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=_allow_credentials,
    allow_methods=["GET", "OPTIONS"],  # API somente-leitura
    allow_headers=["Authorization", "Content-Type"],
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)


@app.middleware("http")
async def access_log_middleware(request: Request, call_next):
    started = time.monotonic()
    response = await call_next(request)
    duration = time.monotonic() - started
    log.info(
        "API request completed",
        extra={
            "event": "api_request",
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "duration_seconds": round(duration, 4),
        },
    )
    return response


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    error_id = str(uuid.uuid4())
    log.error(
        f"FATAL ERROR [{error_id}]: {request.url}\n{traceback.format_exc()}",
        extra={"event": "api_error", "error_id": error_id, "method": request.method, "path": request.url.path},
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "message": "Ocorreu um erro interno no servidor.",
            "error_id": error_id,
        },
    )


app.include_router(culturas.router)
app.include_router(municipios.router)
app.include_router(producao.router)
app.include_router(insumos.router)
app.include_router(clima.router)
app.include_router(analytics.router)
app.include_router(zarc.router)


@app.get("/")
def health_check():
    return {"status": "ok", "message": "AgroHarvest API rodando!"}
