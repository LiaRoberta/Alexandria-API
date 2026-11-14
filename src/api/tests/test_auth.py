"""
Testes de Autenticação JWT e Perfil do Usuário (/api/v1/auth).

Verifica:
- Login com credenciais válidas (200 OK) e formato do token
- Rejeição de login com senha incorreta ou e-mail inexistente (401 RFC 9457)
- Rejeição de login com payload inválido (422 RFC 9457 com invalidParams)
- Consulta do perfil em /api/v1/auth/me com tokens ADMIN e MEMBER (200 OK)
- Bloqueio de acesso sem token, com token expirado ou malformado (401 RFC 9457)
"""

from fastapi import status
from fastapi.testclient import TestClient


def test_login_success(client: TestClient):
    """Garante que credenciais válidas autenticam e retornam o accessToken no padrão Bearer."""
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@fatec.sp.gov.br", "password": "admin123"},
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "accessToken" in data
    assert data["tokenType"] == "Bearer"
    assert data["expiresIn"] == 3600


def test_login_member_success(client: TestClient):
    """Garante que usuário com role MEMBER também autentica com sucesso."""
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "aluno@fatec.sp.gov.br", "password": "aluno123"},
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "accessToken" in data
    assert data["tokenType"] == "Bearer"


def test_login_invalid_password(client: TestClient):
    """Garante que senha incorreta retorna HTTP 401 no formato RFC 9457."""
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@fatec.sp.gov.br", "password": "senha_errada"},
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.headers["content-type"] == "application/problem+json"
    body = response.json()
    assert body["type"] == "https://api.taskflow.dev/errors/unauthorized"
    assert body["title"] == "Unauthorized"
    assert body["status"] == 401
    assert "Credenciais inválidas" in body["detail"]


def test_login_nonexistent_user(client: TestClient):
    """Garante que e-mail não cadastrado retorna HTTP 401 no formato RFC 9457."""
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "inexistente@fatec.sp.gov.br", "password": "qualquer_senha"},
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.headers["content-type"] == "application/problem+json"
    body = response.json()
    assert body["type"] == "https://api.taskflow.dev/errors/unauthorized"
    assert body["status"] == 401


def test_login_validation_error(client: TestClient):
    """Garante que envio de dados inválidos (ex.: senha curta) retorna HTTP 422 com invalidParams."""
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "formato-invalido", "password": "123"},
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert response.headers["content-type"] == "application/problem+json"
    body = response.json()
    assert body["type"] == "https://api.taskflow.dev/errors/validation-error"
    assert body["status"] == 422
    assert isinstance(body["invalidParams"], list)
    assert len(body["invalidParams"]) > 0


def test_get_me_admin_success(client: TestClient, admin_headers: dict[str, str]):
    """Garante consulta do perfil autenticado de usuário ADMIN em /api/v1/auth/me."""
    response = client.get("/api/v1/auth/me", headers=admin_headers)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["email"] == "admin@fatec.sp.gov.br"
    assert data["role"] == "ADMIN"
    assert "id" in data
    assert "createdAt" in data


def test_get_me_member_success(client: TestClient, member_headers: dict[str, str]):
    """Garante consulta do perfil autenticado de usuário MEMBER em /api/v1/auth/me."""
    response = client.get("/api/v1/auth/me", headers=member_headers)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["email"] == "aluno@fatec.sp.gov.br"
    assert data["role"] == "MEMBER"


def test_get_me_missing_token(client: TestClient):
    """Garante que rota privada sem header Authorization retorna 401 RFC 9457."""
    response = client.get("/api/v1/auth/me")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.headers["content-type"] == "application/problem+json"
    body = response.json()
    assert body["type"] == "https://api.taskflow.dev/errors/unauthorized"
    assert body["status"] == 401


def test_get_me_expired_token(client: TestClient, expired_headers: dict[str, str]):
    """Garante que token expirado retorna 401 RFC 9457 com detalhe explicativo."""
    response = client.get("/api/v1/auth/me", headers=expired_headers)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.headers["content-type"] == "application/problem+json"
    body = response.json()
    assert body["type"] == "https://api.taskflow.dev/errors/unauthorized"
    assert body["status"] == 401
    assert "expirou" in body["detail"]


def test_get_me_invalid_token(client: TestClient, invalid_headers: dict[str, str]):
    """Garante que token inválido/corrompido retorna 401 RFC 9457."""
    response = client.get("/api/v1/auth/me", headers=invalid_headers)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.headers["content-type"] == "application/problem+json"
    body = response.json()
    assert body["type"] == "https://api.taskflow.dev/errors/unauthorized"
    assert body["status"] == 401
    assert "inválido" in body["detail"]
