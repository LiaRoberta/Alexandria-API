"""main.py — Ponto de Entrada Principal da Alexandria API.

Configura a instância FastAPI com ciclo de vida (lifespan) para inicialização
e seed idempotente do banco de dados, middleware CORS, handlers de erro RFC 9457
e inclusão de todas as rotas da aplicação.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware

from database import init_db
from exceptions import register_exception_handlers
from routers import auth, emprestimos, funcionarios, livros, usuarios


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Gerencia a inicialização da base de dados e seed no ciclo de vida da aplicação."""
    # Inicializa as tabelas e insere os registros fundamentais idempotentemente
    init_db()
    yield


app = FastAPI(
    title="Alexandria API",
    description=(
        "API RESTful para gerenciamento ágil do acervo de uma biblioteca, controle "
        "de leitores, funcionários e empréstimos com ORM SQLAlchemy 2.0 e "
        "Autenticação Stateless JWT/RBAC."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# -----------------------------------------------------------------------------
# Configuração de CORS (Cross-Origin Resource Sharing)
# -----------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------------------------------------------------------
# Registro dos Handlers Globais RFC 9457 (Problem Details)
# -----------------------------------------------------------------------------
register_exception_handlers(app)

# -----------------------------------------------------------------------------
# Inclusão dos Routers da API
# -----------------------------------------------------------------------------
app.include_router(auth.router)
app.include_router(livros.router)
app.include_router(emprestimos.router)
app.include_router(usuarios.router)
app.include_router(funcionarios.router)


@app.get(
    "/",
    status_code=status.HTTP_200_OK,
    summary="Health Check & Informações da API",
    tags=["root"],
)
def root_info() -> dict[str, str]:
    """Retorna o status operacional e links para a documentação interativa."""
    return {
        "name": "Alexandria API",
        "version": "1.0.0",
        "status": "online",
        "docs": "/docs",
        "openapi": "/openapi.json",
    }
