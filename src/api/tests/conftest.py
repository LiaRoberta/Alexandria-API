"""conftest.py — Fixtures de Teste, Isolamento de Banco SQLite e Tokens JWT.

Configura ambiente isolado em memória (sqlite:///:memory: com StaticPool) para
cada função de teste, sobrescreve a dependência get_db do FastAPI, e disponibiliza
fixtures de cliente HTTP e headers de autorização para perfis ADMIN e BIBLIOTECARIO.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from api.database import get_db, init_db
from api.main import app
from api.models import Base
from api.security import create_access_token


@pytest.fixture(scope="function")
def test_engine():
    """Cria uma engine SQLite em memória isolada com tabelas e seed inicial."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    init_db(target_engine=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture(scope="function")
def db_session(test_engine) -> Session:
    """Fornece uma sessão SQLAlchemy vinculada ao banco em memória do teste."""
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="function")
def client(test_engine) -> TestClient:
    """Instancia TestClient sobrescrevendo get_db com o banco isolado."""
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

    def override_get_db():
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def admin_headers() -> dict[str, str]:
    """Retorna cabeçalho Authorization com Bearer token de Administrador (ID 1)."""
    token = create_access_token(
        data={
            "sub": "1",
            "email": "joao.souza@biblioteca.com",
            "role": "ADMIN",
            "nome": "João Souza",
        }
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="function")
def biblio_headers() -> dict[str, str]:
    """Retorna cabeçalho Authorization com Bearer token de Bibliotecário (ID 2)."""
    token = create_access_token(
        data={
            "sub": "2",
            "email": "ana.lima@biblioteca.com",
            "role": "BIBLIOTECARIO",
            "nome": "Ana Lima",
        }
    )
    return {"Authorization": f"Bearer {token}"}
