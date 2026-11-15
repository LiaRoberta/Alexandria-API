"""test_livros.py — Suíte de Testes da Coleção de Acervo (/api/v1/lib/acervo).

Testa operações públicas e autenticadas do catálogo de livros: listagem paginada,
criação com unicidade de ISBN, busca por ID, atualização parcial PATCH,
regras semânticas de erro RFC 9457 (404, 409) e exclusividade de exclusão
para perfil ADMIN (RBAC 403 Forbidden para Bibliotecário vs 204 para Admin).
"""

import pytest
from fastapi.testclient import TestClient


def test_listar_livros_publico(client: TestClient):
    """Garante que a listagem do acervo é pública e não exige token JWT."""
    response = client.get("/api/v1/lib/acervo")
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert "meta" in data
    assert len(data["data"]) >= 1
    assert data["meta"]["page"] == 1
    assert data["meta"]["totalItems"] >= 1


def test_listar_livros_com_filtros(client: TestClient):
    """Testa filtros de busca por categoria, status, exemplar e texto de busca."""
    # Filtro por texto
    response = client.get("/api/v1/lib/acervo?search=Hobbit")
    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) == 1
    assert data["data"][0]["titulo"] == "O Hobbit"

    # Filtro por categoria existente
    response = client.get("/api/v1/lib/acervo?categoria=Fantasia")
    assert response.status_code == 200
    assert len(response.json()["data"]) >= 1

    # Filtro por categoria inexistente
    response = client.get("/api/v1/lib/acervo?categoria=Terror")
    assert response.status_code == 200
    assert len(response.json()["data"]) == 0


def test_selecionar_livro_existente(client: TestClient):
    """Garante que um livro existente (ID 1) pode ser consultado com sucesso."""
    response = client.get("/api/v1/lib/acervo/1")
    assert response.status_code == 200
    livro = response.json()
    assert livro.get("livro-id") == 1 or livro.get("id") == 1
    assert livro["titulo"] == "O Hobbit"
    assert livro["ISBN"] == "978-85-12345-67-8"
    assert "categoria" in livro
    assert "status" in livro


def test_selecionar_livro_inexistente_404(client: TestClient):
    """Retorna HTTP 404 Problem Details ao consultar livro não cadastrado (ID 9999)."""
    response = client.get("/api/v1/lib/acervo/9999")
    assert response.status_code == 404
    assert "application/problem+json" in response.headers["content-type"]
    body = response.json()
    assert body["status"] == 404
    assert body["type"] == "https://api.alexandria.dev/errors/not-found"
    assert body["title"] == "Livro Inexistente"


def test_adicionar_livro_sucesso(client: TestClient, admin_headers: dict):
    """Cadastra um novo livro com perfil autenticado retornando 201 Created e Location."""
    payload = {
        "ISBN": "978-85-32511-01-0",
        "titulo": "Harry Potter e a Pedra Filosofal",
        "autor": "J. K. Rowling",
        "numPaginas": 264,
        "editora": "Rocco",
        "publicacao": 1997,
        "categoria": "Fantasia",
        "status": "Novo",
        "exemplar": False,
    }
    response = client.post("/api/v1/lib/acervo", json=payload, headers=admin_headers)
    assert response.status_code == 201
    assert "location" in response.headers
    data = response.json()
    assert (data.get("livro-id") or data.get("id")) is not None
    assert data["titulo"] == payload["titulo"]
    assert data["ISBN"] == payload["ISBN"]
    assert (data.get("qtd-emprestimos") if "qtd-emprestimos" in data else data.get("qtdEmprestimos", 0)) == 0


def test_adicionar_livro_conflito_isbn_409(client: TestClient, biblio_headers: dict):
    """Rejeita cadastro de livro com ISBN já cadastrado com HTTP 409 RFC 9457."""
    payload = {
        "ISBN": "978-85-12345-67-8",  # ISBN do livro ID 1 já existente
        "titulo": "Outro Livro com mesmo ISBN",
        "autor": "Outro Autor",
        "numPaginas": 150,
        "editora": "Outra Editora",
        "publicacao": 2020,
        "categoria": "Ficção Científica",
        "status": "Novo",
        "exemplar": False,
    }
    response = client.post("/api/v1/lib/acervo", json=payload, headers=biblio_headers)
    assert response.status_code == 409
    assert "application/problem+json" in response.headers["content-type"]
    body = response.json()
    assert body["status"] == 409
    assert body["type"] == "https://api.alexandria.dev/errors/conflict"
    assert "já existe uma obra cadastrada" in body["detail"].lower()


def test_atualizar_livro_patch_sucesso(client: TestClient, biblio_headers: dict):
    """Atualiza seletivamente propriedades do livro retornando HTTP 200 OK."""
    patch_payload = {
        "status": "Danificado",
        "exemplar": True,
    }
    response = client.patch("/api/v1/lib/acervo/1", json=patch_payload, headers=biblio_headers)
    assert response.status_code == 200
    livro = response.json()
    assert (livro.get("livro-id") or livro.get("id")) == 1
    assert livro["status"] == "Danificado"
    assert livro["exemplar"] is True
    # Campos inalterados permanecem iguais
    assert livro["titulo"] == "O Hobbit"


def test_atualizar_livro_inexistente_404(client: TestClient, admin_headers: dict):
    """Rejeita atualização de livro com ID inexistente retornando HTTP 404 Problem Details."""
    response = client.patch(
        "/api/v1/lib/acervo/9999",
        json={"status": "Conservado"},
        headers=admin_headers,
    )
    assert response.status_code == 404
    assert "application/problem+json" in response.headers["content-type"]
    body = response.json()
    assert body["status"] == 404
    assert body["type"] == "https://api.alexandria.dev/errors/not-found"


def test_remover_livro_bibliotecario_proibido_403(client: TestClient, biblio_headers: dict):
    """CRÍTICO DE RBAC: Bibliotecário não tem permissão para remover livros (HTTP 403 Forbidden)."""
    response = client.delete("/api/v1/lib/acervo/1", headers=biblio_headers)
    assert response.status_code == 403
    assert "application/problem+json" in response.headers["content-type"]
    body = response.json()
    assert body["status"] == 403
    assert body["type"] == "https://api.alexandria.dev/errors/forbidden"
    assert body["title"] == "Acesso Proibido"
    assert "BIBLIOTECARIO" in body["detail"]


def test_remover_livro_admin_sucesso(client: TestClient, admin_headers: dict):
    """Administrador exclui livro com sucesso (HTTP 204 No Content)."""
    # 1. Deleta o livro 1 com perfil ADMIN
    response = client.delete("/api/v1/lib/acervo/1", headers=admin_headers)
    assert response.status_code == 204

    # 2. Confirma que o livro realmente não existe mais
    check_response = client.get("/api/v1/lib/acervo/1")
    assert check_response.status_code == 404
