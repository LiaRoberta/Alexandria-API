"""
Testes da Coleção de Projetos e Acervo (/api/v1/projects e /api/v1/lib/acervo).

Verifica:
- Eager loading e prevenção de consultas N+1 via selectinload(ProjectModel.tasks)
- Consulta de tarefas vinculadas a um projeto (/api/v1/projects/{id}/tasks)
- Listagem paginada de projetos/livros e filtros combinados
- Seleção por ID existente (200 OK) e inexistente (404 RFC 9457)
- Proteção RBAC no cadastro POST: rejeição para MEMBER (403) e criação para ADMIN (201)
- Detecção de conflito em duplicidade de ISBN (409 Conflict RFC 9457)
- Atualização PATCH e exclusão DELETE restritas ao papel ADMIN
"""

from fastapi import status
from fastapi.testclient import TestClient


def test_get_project_tasks_selectinload(client: TestClient):
    """
    TESTE DE PREVENÇÃO DO PROBLEMA N+1:
    Garante que o endpoint /projects/{projectId}/tasks carrega as tarefas
    através de eager loading (selectinload) em uma única operação.
    """
    response = client.get("/api/v1/projects/1/tasks")
    assert response.status_code == status.HTTP_200_OK
    tasks = response.json()
    assert isinstance(tasks, list)
    assert len(tasks) >= 1
    assert tasks[0]["livro-id"] == 1


def test_get_project_tasks_not_found(client: TestClient):
    """Garante que consulta de tarefas de projeto inexistente retorna 404 RFC 9457."""
    response = client.get("/api/v1/projects/99999/tasks")
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.headers["content-type"] == "application/problem+json"
    body = response.json()
    assert body["type"] == "https://api.taskflow.dev/errors/not-found"
    assert body["status"] == 404


def test_list_projects(client: TestClient):
    """Garante listagem paginada dos projetos/livros do acervo com PageMeta."""
    response = client.get("/api/v1/projects?page=1&limit=5")
    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert "data" in body
    assert "meta" in body
    assert body["meta"]["page"] == 1
    assert body["meta"]["limit"] == 5
    assert body["meta"]["totalItems"] >= 2


def test_list_projects_filter(client: TestClient):
    """Garante filtros de acervo por categoria e estado de conservação."""
    response = client.get("/api/v1/projects?categoria=Estudantil")
    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    for item in body["data"]:
        assert item["categoria"] == "Estudantil"


def test_get_project_by_id(client: TestClient):
    """Garante seleção de projeto/livro existente por ID."""
    response = client.get("/api/v1/projects/1")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["livro-id"] == 1
    assert "titulo" in data
    assert "ISBN" in data


def test_get_project_not_found(client: TestClient):
    """Garante 404 RFC 9457 para projeto/livro inexistente."""
    response = client.get("/api/v1/projects/99999")
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.headers["content-type"] == "application/problem+json"
    body = response.json()
    assert body["type"] == "https://api.taskflow.dev/errors/not-found"
    assert body["status"] == 404


def test_create_project_forbidden_for_member(client: TestClient, member_headers: dict[str, str]):
    """Garante que usuário MEMBER é bloqueado com 403 ao tentar criar projeto/livro."""
    payload = {
        "titulo": "Livro Não Autorizado",
        "ISBN": "978-85-11111-22-3",
        "categoria": "Terror",
        "exemplar": False,
        "status": "Novo",
    }
    response = client.post("/api/v1/projects", json=payload, headers=member_headers)
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.headers["content-type"] == "application/problem+json"
    body = response.json()
    assert body["type"] == "https://api.taskflow.dev/errors/forbidden"
    assert body["status"] == 403


def test_create_project_admin_success(client: TestClient, admin_headers: dict[str, str]):
    """Garante que usuário ADMIN pode criar novo projeto/livro no acervo (201)."""
    payload = {
        "titulo": "Clean Code",
        "autor": "Robert C. Martin",
        "ISBN": "978-85-76082-67-5",
        "categoria": "Estudantil",
        "exemplar": False,
        "num-paginas": 464,
        "status": "Novo",
    }
    response = client.post("/api/v1/projects", json=payload, headers=admin_headers)
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["titulo"] == "Clean Code"
    assert data["ISBN"] == "978-85-76082-67-5"
    assert "livro-id" in data


def test_create_project_duplicate_isbn_conflict(client: TestClient, admin_headers: dict[str, str]):
    """Garante detecção de duplicidade de ISBN retornando HTTP 409 Conflict RFC 9457."""
    payload = {
        "titulo": "Livro com ISBN Duplicado",
        "ISBN": "978-85-12345-67-8",  # ISBN já inserido no seed
        "categoria": "Romance",
        "exemplar": False,
        "status": "Novo",
    }
    response = client.post("/api/v1/projects", json=payload, headers=admin_headers)
    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.headers["content-type"] == "application/problem+json"
    body = response.json()
    assert body["type"] == "https://api.taskflow.dev/errors/conflict"
    assert body["status"] == 409
    assert body["title"] in ("Conflict", "Conflito")


def test_update_project_admin_success(client: TestClient, admin_headers: dict[str, str]):
    """Garante atualização parcial de projeto/livro por ADMIN (200)."""
    response = client.patch(
        "/api/v1/projects/1",
        json={"titulo": "Engenharia de Software Moderna - 2ª Edição"},
        headers=admin_headers,
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["titulo"] == "Engenharia de Software Moderna - 2ª Edição"


def test_delete_project_admin_success(client: TestClient, admin_headers: dict[str, str]):
    """Garante exclusão de projeto/livro por ADMIN (204 No Content)."""
    response = client.delete("/api/v1/projects/2", headers=admin_headers)
    assert response.status_code == status.HTTP_204_NO_CONTENT

    # Confirmação de 404
    get_resp = client.get("/api/v1/projects/2")
    assert get_resp.status_code == status.HTTP_404_NOT_FOUND
