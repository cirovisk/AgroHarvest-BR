import os
import logging
import traceback
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from dotenv import load_dotenv

# Garante que as variáveis de ambiente locais do .env sejam carregadas
load_dotenv()

from api.routers import culturas, municipios, producao, insumos, clima, analytics, zarc

# Lê limite de rate limit de forma dinâmica, com fallback seguro para 30
rate_limit_val = os.getenv("API_LIMIT_PER_MINUTE", "30").strip()
limiter = Limiter(key_func=get_remote_address, default_limits=[f"{rate_limit_val} per minute"])

app = FastAPI(
    title="AgroHarvest API",
    description="API somente-leitura para dados agropecuários do projeto AgroHarvest BR.",
    version="1.0.0"
)

# Configura CORS para permitir integração perfeita com Metabase ou outras aplicações frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    import uuid
    error_id = str(uuid.uuid4())
    logging.error(f"FATAL ERROR [{error_id}]: {request.url}\n{traceback.format_exc()}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "message": "Ocorreu um erro interno no servidor.",
            "error_id": error_id
        }
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
