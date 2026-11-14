"""
Testes da Coleção de Tarefas e Empréstimos (/api/v1/tasks e /api/v1/lib/emprestimos).

Verifica:
- Listagem paginada e cálculo correto dos metadados PageMeta
- Filtragem por status e busca textual
- Consulta por ID existente (200 OK) e inexistente (404 RFC 9457)
- Criação de tarefa/empréstimo exigindo autenticação (401 sem token, 201 com token)
- Atualização parcial PATCH exigindo autenticação (401 sem token, 200 com token)
- Controle de acesso RBAC no DELETE: bloqueio de MEMBER (403 Forbidden RFC 9457)
- Exclusão permitida para ADMIN (204 No Content) e verificação de remoção (404)
"""

from datetime import datetime, timedelta
from fastapi import status
from fastapi.testclient import TestClient


def test_list_tasks(client: TestClient):
    """Garante listagem paginada de tarefas/empréstimos com estrutura PageMeta."""
    response = client.get("/api/v1/tasks?page=1&limit=5")
    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert "data" in body
    assert "meta" in body
    meta = body["meta"]
    assert meta["page"] == 1
    assert meta["limit"] == 5
    assert meta["totalItems"] >= 1
    assert isinstance(meta["hasNext"], bool)


def test_list_tasks_filter_status(client: TestClient):
    """Garante filtragem de tarefas pelo campo status."""
    response = client.get("/api/v1/tasks?status=Emprestado")
    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    for item in body["data"]:
        assert item["status"] == "Emprestado"


def test_get_task_by_id_success(client: TestClient):
    """Garante seleção correta de empréstimo/tarefa por ID existente."""
    response = client.get("/api/v1/tasks/1")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["livro-id"] >= 1
    assert data["status"] in ("Emprestado", "Devolvido", "Vencido")


def test_get_task_not_found(client: TestClient):
    """Garante que busca por tarefa inexistente retorna HTTP 404 no padrão RFC 9457."""
    response = client.get("/api/v1/tasks/99999")
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.headers["content-type"] == "application/problem+json"
    body = response.json()
    assert body["type"] == "https://api.taskflow.dev/errors/not-found"
    assert body["status"] == 404
    assert body["instance"] == "/api/v1/tasks/99999"


def test_create_task_unauthenticated(client: TestClient):
    """Garante que tentativa de criação sem header Authorization retorna 401 RFC 9457."""
    payload = {
        "livro-id": 1,
        "usuario-id": 1,
        "funcionario-id": 1,
        "dt-vencimento": (datetime.utcnow() + timedelta(days=14)).isoformat(),
    }
    response = client.post("/api/v1/tasks", json=payload)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.headers["content-type"] == "application/problem+json"
    body = response.json()
    assert body["type"] == "https://api.taskflow.dev/errors/unauthorized"
    assert body["status"] == 401


def test_create_task_authenticated(client: TestClient, member_headers: dict[str, str]):
    """Garante que usuário autenticado (mesmo MEMBER) pode registrar tarefa/empréstimo (201)."""
    payload = {
        "livro-id": 1,
        "usuario-id": 1,
        "funcionario-id": 1,
        "dt-vencimento": (datetime.utcnow() + timedelta(days=14)).isoformat(),
    }
    response = client.post("/api/v1/tasks", json=payload, headers=member_headers)
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["livro-id"] == 1
    assert data["status"] == "Emprestado"
    assert "emprestimo-id" in data


def test_update_task_unauthenticated(client: TestClient):
    """Garante que tentativa de PATCH sem autenticação retorna 401 RFC 9457."""
    response = client.patch(
        "/api/v1/tasks/1",
        json={"status": "Devolvido"},
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.headers["content-type"] == "application/problem+json"


def test_update_task_authenticated(client: TestClient, member_headers: dict[str, str]):
    """Garante que usuário autenticado pode atualizar o status da tarefa/empréstimo (200)."""
    response = client.patch(
        "/api/v1/tasks/1",
        json={"status": "Devolvido"},
        headers=member_headers,
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["status"] == "Devolvido"
    assert data["dt-devolucao"] is not None


def test_delete_task_unauthenticated(client: TestClient):
    """Garante que exclusão sem autenticação é rejeitada com 401 RFC 9457."""
    response = client.delete("/api/v1/tasks/1")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.headers["content-type"] == "application/problem+json"


def test_delete_task_forbidden_for_member(client: TestClient, member_headers: dict[str, str]):
    """
    TESTE CRÍTICO DE RBAC:
    Garante que usuário comum (MEMBER) tentando executar DELETE recebe estritamente
    HTTP 403 Forbidden no formato RFC 9457 (tipo: https://api.taskflow.dev/errors/forbidden).
    """
    response = client.delete("/api/v1/tasks/1", headers=member_headers)
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.headers["content-type"] == "application/problem+json"
    body = response.json()
    assert body["type"] == "https://api.taskflow.dev/errors/forbidden"
    assert body["title"] == "Forbidden"
    assert body["status"] == 403
    assert "Acesso negado" in body["detail"]


def test_delete_task_admin_success(client: TestClient, admin_headers: dict[str, str]):
    """Garante que usuário com role ADMIN pode excluir a tarefa (204 No Content)."""
    response = client.delete("/api/v1/tasks/1", headers=admin_headers)
    assert response.status_code == status.HTTP_204_NO_CONTENT

    # Confirmação de que o registro foi removido definitivamente
    get_resp = client.get("/api/v1/tasks/1")
    assert get_resp.status_code == status.HTTP_404_NOT_FOUND
    assert get_resp.headers["content-type"] == "application/problem+json"
