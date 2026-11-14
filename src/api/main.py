"""
Ponto de Entrada Principal da Alexandria API v2.

Configura:
- Ciclo de vida (lifespan) com inicialização e seed idempotente do banco SQLite
- Instância FastAPI com documentação OpenAPI/Swagger personalizada
- Middleware de CORS
- Registro integral dos Exception Handlers padronizados RFC 9457
- Inclusão dos roteadores: auth, tasks, projects (com selectinload) e users
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from src.api.database import init_db_and_seed
from src.api.exceptions import register_exception_handlers
from src.api.routers import auth, projects, tasks, users


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Gerenciador de ciclo de vida da aplicação.
    Executa a criação das tabelas e a carga inicial (seed) antes de aceitar requisições.
    """
    init_db_and_seed()
    yield


app = FastAPI(
    title="Alexandria API v2",
    description=(
        "API de gerenciamento ágil de tarefas e acervo da biblioteca Alexandria na FATEC. "
        "Desenvolvida com FastAPI, persistência relacional SQLAlchemy 2.0 Declarativo, "
        "autenticação stateless JWT HS256, controle de acesso RBAC e tratamento semântico "
        "de erros estritamente compatível com a RFC 9457 (Problem Details)."
    ),
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configuração de CORS (Cross-Origin Resource Sharing)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registro obrigatório dos handlers globais de conformidade com a RFC 9457
register_exception_handlers(app)

# Inclusão dos roteadores da aplicação
app.include_router(auth.router)
app.include_router(tasks.router)
app.include_router(projects.router)
app.include_router(users.router)


@app.get("/", include_in_schema=False)
def root_redirect():
    """Redireciona a raiz para a documentação interativa Swagger UI."""
    return RedirectResponse(url="/docs")


@app.get(
    "/health",
    tags=["Infraestrutura"],
    summary="Verificação de integridade operacional",
)
def health_check():
    """Endpoint de checagem do status operacional da API."""
    return {
        "status": "healthy",
        "version": "2.0.0",
        "database": "sqlite",
        "standard": "RFC 9457 Problem Details",
    }
