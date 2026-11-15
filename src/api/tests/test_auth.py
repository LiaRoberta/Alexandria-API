"""test_auth.py — Suíte de Testes de Autenticação e Segurança Stateless JWT.

Testa os fluxos de login com credenciais válidas e inválidas, emissão de tokens
JWT com claims RBAC e proteção de rotas com respostas padronizadas RFC 9457.
"""

from datetime import timedelta
import pytest
from fastapi.testclient import TestClient

from api.security import create_access_token


def test_login_admin_sucesso(client: TestClient):
    """Garante que o administrador consegue logar e receber token JWT válido."""
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "joao.souza@biblioteca.com", "password": "Admin@2026"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "accessToken" in data
    assert data["tokenType"] == "bearer"
    assert data["expiresIn"] == 3600
    assert data["user"]["id"] == 1
    assert data["user"]["email"] == "joao.souza@biblioteca.com"
    assert data["user"]["role"] == "ADMIN"


def test_login_bibliotecario_sucesso(client: TestClient):
    """Garante que o bibliotecário consegue logar e receber token com role BIBLIOTECARIO."""
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "ana.lima@biblioteca.com", "password": "Biblio@2026"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "accessToken" in data
    assert data["tokenType"] == "bearer"
    assert data["user"]["id"] == 2
    assert data["user"]["role"] == "BIBLIOTECARIO"


def test_login_senha_incorreta(client: TestClient):
    """Rejeita login com senha incorreta retornando HTTP 401 RFC 9457."""
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "joao.souza@biblioteca.com", "password": "SenhaErrada@2026"},
    )
    assert response.status_code == 401
    assert "application/problem+json" in response.headers["content-type"]
    body = response.json()
    assert body["status"] == 401
    assert body["type"] == "https://api.alexandria.dev/errors/unauthorized"
    assert body["title"] == "Não Autorizado"
    assert "Credenciais inválidas" in body["detail"]


def test_login_email_inexistente(client: TestClient):
    """Rejeita login com e-mail não cadastrado retornando HTTP 401 RFC 9457."""
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "fantasma@biblioteca.com", "password": "QualquerCoisa"},
    )
    assert response.status_code == 401
    assert "application/problem+json" in response.headers["content-type"]
    body = response.json()
    assert body["status"] == 401
    assert body["type"] == "https://api.alexandria.dev/errors/unauthorized"


def test_acesso_rota_protegida_sem_token(client: TestClient):
    """Bloqueia acesso a rotas autenticadas quando o cabeçalho Authorization está ausente."""
    response = client.get("/api/v1/lib/users/usuarios")
    assert response.status_code == 401
    assert "application/problem+json" in response.headers["content-type"]
    body = response.json()
    assert body["status"] == 401
    assert "Authorization" in body["detail"]


def test_acesso_rota_protegida_token_malformado(client: TestClient):
    """Bloqueia requisições contendo Bearer token corrompido ou malformado."""
    headers = {"Authorization": "Bearer token.completamente.invalido"}
    response = client.get("/api/v1/lib/users/usuarios", headers=headers)
    assert response.status_code == 401
    assert "application/problem+json" in response.headers["content-type"]
    body = response.json()
    assert body["status"] == 401
    assert "inválido ou malformado" in body["detail"]


def test_acesso_rota_protegida_token_expirado(client: TestClient):
    """Bloqueia requisições com tokens cuja data de expiração já foi ultrapassada."""
    expired_token = create_access_token(
        data={"sub": "1", "email": "joao.souza@biblioteca.com", "role": "ADMIN"},
        expires_delta=timedelta(minutes=-10),
    )
    headers = {"Authorization": f"Bearer {expired_token}"}
    response = client.get("/api/v1/lib/users/usuarios", headers=headers)
    assert response.status_code == 401
    assert "application/problem+json" in response.headers["content-type"]
    body = response.json()
    assert body["status"] == 401
    assert "expirado" in body["detail"]
