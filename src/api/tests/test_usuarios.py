"""test_usuarios.py — Suíte de Testes da Coleção de Leitores (/api/v1/lib/users/usuarios).

Testa fluxos operacionais e validações da gestão de leitores da biblioteca:
- Cadastro com sucesso (201 Created), Location header e limite inicial de 4 livros
- Conflito 409 ao tentar cadastrar CPF já existente
- Validações de schema 422 para CPF com formato inválido ou nome faltante
- Listagem paginada autenticada (qualquer funcionário)
- Atualização cadastral via PATCH (200 OK)
- Consulta por ID existente (200 OK) e inexistente (404 RFC 9457)
"""

import pytest
from fastapi.testclient import TestClient


def test_cadastrar_usuario_sucesso(client: TestClient, biblio_headers: dict):
    """Cadastra um novo leitor garantindo limite_disp inicial = 4 e Location header."""
    payload = {
        "CPF": "222.333.444-55",
        "nome": "Machado de Assis",
        "email": "machado@literatura.com",
        "telefone": "(16)98888-1234",
        "dt-nascimento": "1839-06-21",
        "CEP": "14010-000",
    }
    response = client.post("/api/v1/lib/users/usuarios", json=payload, headers=biblio_headers)
    assert response.status_code == 201
    assert "location" in response.headers
    data = response.json()
    assert (data.get("usuario-id") or data.get("id")) is not None
    assert data["CPF"] == payload["CPF"]
    assert data["nome"] == payload["nome"]
    assert (data.get("limite-disp") if "limite-disp" in data else data.get("limiteDisp")) == 4


def test_cadastrar_usuario_conflito_cpf_409(client: TestClient, biblio_headers: dict):
    """Rejeita cadastro de leitor com CPF já cadastrado (HTTP 409 Conflict)."""
    payload = {
        "CPF": "123.456.789-09",  # CPF da Maria Silva (ID 7) semeada
        "nome": "Maria Outra",
        "email": "outra.maria@email.com",
    }
    response = client.post("/api/v1/lib/users/usuarios", json=payload, headers=biblio_headers)
    assert response.status_code == 409
    assert "application/problem+json" in response.headers["content-type"]
    body = response.json()
    assert body["status"] == 409
    assert body["type"] == "https://api.alexandria.dev/errors/conflict"
    assert "já existe um leitor cadastrado" in body["detail"].lower()


def test_cadastrar_usuario_cpf_invalido_422(client: TestClient, biblio_headers: dict):
    """Rejeita cadastro com formato de CPF inválido retornando HTTP 422 Problem Details."""
    payload = {
        "CPF": "12345678900",  # Sem máscara de pontos e traço
        "nome": "Leitor Com CPF Invalido",
        "email": "leitor@email.com",
    }
    response = client.post("/api/v1/lib/users/usuarios", json=payload, headers=biblio_headers)
    assert response.status_code == 422
    assert "application/problem+json" in response.headers["content-type"]
    body = response.json()
    assert body["status"] == 422
    assert "invalidParams" in body
    params = [p["name"] for p in body["invalidParams"]]
    assert "CPF" in params


def test_cadastrar_usuario_nome_curto_422(client: TestClient, biblio_headers: dict):
    """Rejeita cadastro com nome menor que 3 caracteres (HTTP 422)."""
    payload = {
        "CPF": "777.888.999-00",
        "nome": "Ab",
        "email": "ab@email.com",
    }
    response = client.post("/api/v1/lib/users/usuarios", json=payload, headers=biblio_headers)
    assert response.status_code == 422
    assert "application/problem+json" in response.headers["content-type"]


def test_listar_usuarios_paginado(client: TestClient, biblio_headers: dict):
    """Listagem paginada de leitores acessível para qualquer funcionário autenticado."""
    response = client.get("/api/v1/lib/users/usuarios", headers=biblio_headers)
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert "meta" in data
    assert len(data["data"]) >= 1
    assert data["meta"]["page"] == 1


def test_selecionar_usuario_existente(client: TestClient, biblio_headers: dict):
    """Busca leitor existente por ID com sucesso (HTTP 200 OK)."""
    response = client.get("/api/v1/lib/users/usuarios/7", headers=biblio_headers)
    assert response.status_code == 200
    data = response.json()
    assert (data.get("usuario-id") or data.get("id")) == 7
    assert data["CPF"] == "123.456.789-09"
    assert data["nome"] == "Maria Silva"


def test_selecionar_usuario_inexistente_404(client: TestClient, biblio_headers: dict):
    """Retorna HTTP 404 Problem Details ao buscar leitor inexistente (ID 9999)."""
    response = client.get("/api/v1/lib/users/usuarios/9999", headers=biblio_headers)
    assert response.status_code == 404
    assert "application/problem+json" in response.headers["content-type"]
    body = response.json()
    assert body["status"] == 404
    assert body["type"] == "https://api.alexandria.dev/errors/not-found"
    assert body["title"] == "Usuário Não Encontrado"


def test_atualizar_usuario_patch_sucesso(client: TestClient, biblio_headers: dict):
    """Atualiza dados cadastrais e telefone do leitor via PATCH com sucesso."""
    patch_payload = {
        "telefone": "(16)99888-7766",
        "CEP": "14020-000",
    }
    response = client.patch(
        "/api/v1/lib/users/usuarios/7",
        json=patch_payload,
        headers=biblio_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert (data.get("usuario-id") or data.get("id")) == 7
    assert data["telefone"] == "(16)99888-7766"
    assert data["CEP"] == "14020-000"
    # Campos inalterados
    assert data["nome"] == "Maria Silva"
