"""
Configurações Globais e Fixtures da Suíte de Testes (pytest).

Implementa:
- Banco de dados SQLite isolado em memória (:memory:) com StaticPool por sessão/função de teste
- Override seguro da dependência get_db do FastAPI
- Fixtures de clientes HTTP TestClient
- Fixtures para geração de tokens JWT: admin_headers, member_headers, expired_headers e invalid_headers
- Seed dos dados iniciais no banco de teste
"""

import sys
from datetime import timedelta
from typing import Generator
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from src.api.database import get_db, init_db_and_seed
from src.api.main import app
from src.api.models import Base
from src.api.security import create_access_token


# ==============================================================================
# CONFIGURAÇÃO DE BANCO DE TESTE ISOLADO EM MEMÓRIA
# ==============================================================================

TEST_DATABASE_URL = "sqlite:///:memory:"

engine_test = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine_test,
)


@pytest.fixture(scope="function")
def db_session() -> Generator[Session, None, None]:
    """
    Cria uma nova estrutura de banco de dados SQLite em memória para cada teste,
    populando com os dados iniciais do seed e descartando tudo ao final.
    """
    Base.metadata.create_all(bind=engine_test)
    session = TestingSessionLocal()

    # Executa o seed no banco isolado de teste
    init_db_and_seed(db=session)

    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine_test)


@pytest.fixture(scope="function")
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """
    Instancia o TestClient do FastAPI com a dependência get_db redirecionada
    para a sessão de banco de dados isolada do teste corrente.
    """
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


# ==============================================================================
# FIXTURES DE AUTENTICAÇÃO E TOKENS JWT
# ==============================================================================

@pytest.fixture
def admin_token() -> str:
    """Gera um token JWT válido com papel ADMIN."""
    return create_access_token(
        data={"sub": "1", "email": "admin@fatec.sp.gov.br", "role": "ADMIN"},
        expires_delta=timedelta(hours=1),
    )


@pytest.fixture
def admin_headers(admin_token: str) -> dict[str, str]:
    """Cabeçalho HTTP Authorization pronto para usuário ADMIN."""
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture
def member_token() -> str:
    """Gera um token JWT válido com papel MEMBER."""
    return create_access_token(
        data={"sub": "2", "email": "aluno@fatec.sp.gov.br", "role": "MEMBER"},
        expires_delta=timedelta(hours=1),
    )


@pytest.fixture
def member_headers(member_token: str) -> dict[str, str]:
    """Cabeçalho HTTP Authorization pronto para usuário MEMBER."""
    return {"Authorization": f"Bearer {member_token}"}


@pytest.fixture
def expired_token() -> str:
    """Gera um token JWT com data de expiração no passado."""
    return create_access_token(
        data={"sub": "1", "email": "admin@fatec.sp.gov.br", "role": "ADMIN"},
        expires_delta=timedelta(seconds=-60),
    )


@pytest.fixture
def expired_headers(expired_token: str) -> dict[str, str]:
    """Cabeçalho HTTP com token expirado para testes de rejeição 401."""
    return {"Authorization": f"Bearer {expired_token}"}


@pytest.fixture
def invalid_headers() -> dict[str, str]:
    """Cabeçalho HTTP com token malformado ou corrompido para testes 401."""
    return {"Authorization": "Bearer token_completamente_invalido_e_falso"}
