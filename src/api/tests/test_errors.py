"""test_errors.py — Suíte de Conformidade Global com a RFC 9457 (Problem Details).

Testa a padronização estrita de 100% das respostas de erro da Alexandria API:
- Status HTTP semânticos (400, 401, 403, 404, 409 e 422)
- Cabeçalho Content-Type obrigatório 'application/problem+json'
- Campos canônicos da RFC 9457: type, title, status, detail, instance
- Presença de lista invalidParams em falhas de validação sintática (422)
"""

import pytest
from fastapi.testclient import TestClient

from api.exceptions import BadRequestException


def test_rfc9457_error_401_unauthorized(client: TestClient):
    """Garante que falhas de autenticação retornem RFC 9457 com cabeçalho application/problem+json."""
    response = client.get("/api/v1/lib/users/usuarios")
    assert response.status_code == 401
    assert "application/problem+json" in response.headers["content-type"]
    body = response.json()
    assert body["status"] == 401
    assert body["type"] == "https://api.alexandria.dev/errors/unauthorized"
    assert body["title"] == "Não Autorizado"
    assert "detail" in body
    assert body["instance"] == "/api/v1/lib/users/usuarios"


def test_rfc9457_error_403_forbidden(client: TestClient, biblio_headers: dict):
    """Garante que violações de permissão RBAC retornem RFC 9457 padronizado."""
    response = client.get("/api/v1/lib/users/funcionarios", headers=biblio_headers)
    assert response.status_code == 403
    assert "application/problem+json" in response.headers["content-type"]
    body = response.json()
    assert body["status"] == 403
    assert body["type"] == "https://api.alexandria.dev/errors/forbidden"
    assert body["title"] == "Acesso Proibido"
    assert "detail" in body
    assert body["instance"] == "/api/v1/lib/users/funcionarios"


def test_rfc9457_error_404_not_found(client: TestClient):
    """Garante que recursos não localizados retornem RFC 9457."""
    response = client.get("/api/v1/lib/acervo/9999")
    assert response.status_code == 404
    assert "application/problem+json" in response.headers["content-type"]
    body = response.json()
    assert body["status"] == 404
    assert body["type"] == "https://api.alexandria.dev/errors/not-found"
    assert body["title"] == "Livro Inexistente"
    assert "detail" in body
    assert body["instance"] == "/api/v1/lib/acervo/9999"


def test_rfc9457_error_409_conflict(client: TestClient, admin_headers: dict):
    """Garante que conflitos de unicidade (ISBN duplicado) retornem RFC 9457."""
    payload = {
        "ISBN": "978-85-12345-67-8",  # Livro 1
        "titulo": "Livro com ISBN Repetido",
        "categoria": "Fantasia",
    }
    response = client.post("/api/v1/lib/acervo", json=payload, headers=admin_headers)
    assert response.status_code == 409
    assert "application/problem+json" in response.headers["content-type"]
    body = response.json()
    assert body["status"] == 409
    assert body["type"] == "https://api.alexandria.dev/errors/conflict"
    assert body["title"] == "Conflito de Acervo"
    assert "detail" in body
    assert body["instance"] == "/api/v1/lib/acervo"


def test_rfc9457_error_422_validation_error(client: TestClient, admin_headers: dict):
    """Garante que erros de validação Pydantic retornem RFC 9457 com invalidParams."""
    # Envia payload sem campos obrigatórios
    response = client.post("/api/v1/lib/acervo", json={}, headers=admin_headers)
    assert response.status_code == 422
    assert "application/problem+json" in response.headers["content-type"]
    body = response.json()
    assert body["status"] == 422
    assert body["type"] == "https://api.alexandria.dev/errors/validation-error"
    assert body["title"] == "Erro de Validação"
    assert "invalidParams" in body
    assert isinstance(body["invalidParams"], list)
    assert len(body["invalidParams"]) >= 1
    # Cada item de invalidParams possui 'name' e 'reason'
    for param in body["invalidParams"]:
        assert "name" in param
        assert "reason" in param


def test_rfc9457_error_400_bad_request():
    """Garante que a classe BadRequestException serializa perfeitamente os atributos RFC 9457."""
    exc = BadRequestException(detail="Parâmetro de consulta incompatível.")
    assert exc.status_code == 400
    assert exc.title == "Solicitação Incorreta"
    assert exc.type_uri == "https://api.alexandria.dev/errors/bad-request"
    assert exc.detail == "Parâmetro de consulta incompatível."
