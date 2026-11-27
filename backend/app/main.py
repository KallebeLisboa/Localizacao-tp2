"""Ponto de entrada da API RESTful do Sistema de Ocorrências Urbanas."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import models  # noqa: F401 (registra as tabelas no metadata)
from app.api.routes import auth, categorias, usuarios
from app.core.exceptions import ErroDominio
from app.database import Base, engine
from app.notificacoes.rotas import router as notificacoes_router
from app.notificacoes.rotas import router_admin as status_admin_router
from app.ocorrencias.rotas import router as ocorrencias_router

TAGS_METADATA = [
    {
        "name": "Infraestrutura",
        "description": "Verificação de saúde e disponibilidade da API.",
    },
    {
        "name": "Autenticação",
        "description": (
            "Registro público de cidadãos, autenticação via OAuth2/JWT "
            "e consulta do perfil logado."
        ),
    },
    {
        "name": "Usuários",
        "description": (
            "Gestão de contas de usuários e administradores "
            "(CRUD e inativação lógica)."
        ),
    },
    {
        "name": "Categorias",
        "description": "Consulta pública das categorias ativas de ocorrências.",
    },
    {
        "name": "Admin - Categorias (US05)",
        "description": (
            "Gestão administrativa do catálogo de categorias "
            "(criação, edição, inativação e reativação)."
        ),
    },
    {
        "name": "Ocorrências",
        "description": (
            "Registro georreferenciado (US01), consulta com filtros espaciais/"
            "bounding box (US02) e detalhamento de ocorrências."
        ),
    },
    {
        "name": "Notificações (US03)",
        "description": (
            "Inscrição em ocorrências ou zonas (raio em metros) e consulta "
            "das notificações de mudança de status."
        ),
    },
    {
        "name": "Admin — Status de Ocorrências (US03)",
        "description": (
            "Mudança de status pelo administrador, que gera o log de "
            "eventos usado nas notificações."
        ),
    },
]

DESCRICAO_API = """
API RESTful georreferenciada para **Registro e Acompanhamento de Ocorrências
Urbanas** (TP2 — UnB).

### Autenticação
1. Crie uma conta em **`POST /auth/registrar`** ou use uma credencial existente.
2. Clique no botão **Authorize** acima e informe seu **e-mail** (no campo
   `username`) e **senha** para obter o token JWT Bearer.
"""


@asynccontextmanager
async def ciclo_de_vida(_app: FastAPI) -> AsyncIterator[None]:
    """Cria as tabelas que faltarem ao subir a aplicação.

    Provisório: quando o grupo adotar migrações (ex.: Alembic), remover.
    """
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="API - Sistema de Registro e Acompanhamento de Ocorrências Urbanas",
    description=DESCRICAO_API,
    version="0.2.0",
    openapi_tags=TAGS_METADATA,
    lifespan=ciclo_de_vida,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(ErroDominio)
async def tratar_erro_dominio(_req: Request, exc: ErroDominio) -> JSONResponse:
    """Converte exceções de domínio em respostas HTTP."""
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detalhe})


@app.get("/health", tags=["Infraestrutura"])
def health_check() -> dict[str, str]:
    """Verifica se a API está online e operacional."""
    return {"status": "ok", "service": "ocorrencias-urbanas-api"}


app.include_router(auth.router)
app.include_router(usuarios.router)
app.include_router(categorias.router_admin)
app.include_router(categorias.router_publico)
app.include_router(ocorrencias_router)
app.include_router(notificacoes_router)
app.include_router(status_admin_router)
