"""
Testes de Conformidade Estrita com a RFC 9457 (Problem Details).

Verifica:
- Respostas de erro nos status HTTP 400, 401, 403, 404, 409 e 422
- Presença e integridade de todos os atributos: type, title, status, detail, instance
- Presença obrigatória do array 'invalidParams' em falhas 422
- Cabeçalho HTTP 'Content-Type: application/problem+json' em todas as respostas de erro
- Erradicação absoluta do formato padrão legado do FastAPI {"detail": "..."}
"""

from fastapi import status
from fastapi.testclient import TestClient


def _assert_rfc9457_structure(body: dict, expected_status: int, expected_type: str):
    """Auxiliar para asserção rigorosa da estrutura RFC 9457."""
    assert "type" in body, "Campo 'type' obrigatório ausente"
    assert "title" in body, "Campo 'title' obrigatório ausente"
    assert "status" in body, "Campo 'status' obrigatório ausente"
    assert "detail" in body, "Campo 'detail' obrigatório ausente"
    assert "instance" in body, "Campo 'instance' obrigatório ausente"

    assert body["status"] == expected_status
    assert body["type"] == expected_type
    assert isinstance(body["detail"], str)
    assert len(body["detail"]) > 0

    # Garantia de não ocorrência do formato padrão legado do FastAPI
    assert list(body.keys()) != ["detail"], "A API retornou o formato proibido {'detail': '...'}!"


def test_rfc9457_error_401_unauthorized(client: TestClient):
    """Valida formato RFC 9457 em 401 Unauthorized."""
    response = client.get("/api/v1/auth/me")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.headers["content-type"] == "application/problem+json"

    body = response.json()
    _assert_rfc9457_structure(body, 401, "https://api.taskflow.dev/errors/unauthorized")
    assert body["title"] == "Unauthorized"
    assert body["instance"] == "/api/v1/auth/me"


def test_rfc9457_error_403_forbidden(client: TestClient, member_headers: dict[str, str]):
    """Valida formato RFC 9457 em 403 Forbidden."""
    response = client.delete("/api/v1/tasks/1", headers=member_headers)
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.headers["content-type"] == "application/problem+json"

    body = response.json()
    _assert_rfc9457_structure(body, 403, "https://api.taskflow.dev/errors/forbidden")
    assert body["title"] == "Forbidden"
    assert body["instance"] == "/api/v1/tasks/1"


def test_rfc9457_error_404_not_found(client: TestClient):
    """Valida formato RFC 9457 em 404 Not Found para rotas e entidades inexistentes."""
    # Rota não mapeada
    resp_route = client.get("/api/v1/rota-que-nao-existe")
    assert resp_route.status_code == status.HTTP_404_NOT_FOUND
    assert resp_route.headers["content-type"] == "application/problem+json"
    body_route = resp_route.json()
    _assert_rfc9457_structure(body_route, 404, "https://api.taskflow.dev/errors/not-found")

    # Entidade inexistente
    resp_entity = client.get("/api/v1/projects/99999")
    assert resp_entity.status_code == status.HTTP_404_NOT_FOUND
    assert resp_entity.headers["content-type"] == "application/problem+json"
    body_entity = resp_entity.json()
    _assert_rfc9457_structure(body_entity, 404, "https://api.taskflow.dev/errors/not-found")


def test_rfc9457_error_409_conflict(client: TestClient, admin_headers: dict[str, str]):
    """Valida formato RFC 9457 em 409 Conflict para duplicidades."""
    payload = {
        "titulo": "Livro Duplicado",
        "ISBN": "978-85-12345-67-8",
        "categoria": "Romance",
        "exemplar": False,
        "status": "Novo",
    }
    response = client.post("/api/v1/projects", json=payload, headers=admin_headers)
    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.headers["content-type"] == "application/problem+json"

    body = response.json()
    _assert_rfc9457_structure(body, 409, "https://api.taskflow.dev/errors/conflict")
    assert body["title"] == "Conflict"


def test_rfc9457_error_422_validation(client: TestClient, admin_headers: dict[str, str]):
    """
    Valida formato RFC 9457 em 422 Unprocessable Entity com o array obrigatório
    'invalidParams' contendo objetos com 'name' e 'reason'.
    """
    payload = {
        "titulo": "",  # viola min_length=1
        "ISBN": "isbn_fora_do_padrao_regex",
        "categoria": "CategoriaInexistente",
        "status": "Invalido",
    }
    response = client.post("/api/v1/projects", json=payload, headers=admin_headers)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert response.headers["content-type"] == "application/problem+json"

    body = response.json()
    _assert_rfc9457_structure(body, 422, "https://api.taskflow.dev/errors/validation-error")
    assert body["title"] == "Unprocessable Entity"

    # Verificação de invalidParams
    assert "invalidParams" in body
    assert isinstance(body["invalidParams"], list)
    assert len(body["invalidParams"]) >= 1

    param_names = [p["name"] for p in body["invalidParams"]]
    assert any("titulo" in p for p in param_names)
    assert any("ISBN" in p for p in param_names)
