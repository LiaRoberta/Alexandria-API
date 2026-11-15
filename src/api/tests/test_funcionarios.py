"""test_funcionarios.py — Suíte de Testes da Coleção de Funcionários (/api/v1/lib/users/funcionarios).

Testa operações restritas exclusivamente ao perfil funcional ADMIN:
- Bloqueio estrito de Bibliotecário com HTTP 403 Forbidden em rotas de funcionários
- Consulta paginada e seleção por ID para ADMIN
- Cadastro de funcionário (201 Created) com hash de senha e Location
- Rejeição de duplicidade de CPF, E-mail e Matrícula (HTTP 409 Conflict)
- Validação de piso salarial mínimo de R$ 1.621,00 (HTTP 422 Problem Details)
- Atualização parcial de dados funcionais via PATCH (200 OK)
- Consulta de funcionário inexistente (HTTP 404 RFC 9457)
"""

import pytest
from fastapi.testclient import TestClient


def test_bibliotecario_bloqueado_listar_funcionarios_403(client: TestClient, biblio_headers: dict):
    """CRÍTICO DE RBAC: Bibliotecário tentando listar funcionários recebe HTTP 403 Forbidden."""
    response = client.get("/api/v1/lib/users/funcionarios", headers=biblio_headers)
    assert response.status_code == 403
    assert "application/problem+json" in response.headers["content-type"]
    body = response.json()
    assert body["status"] == 403
    assert body["type"] == "https://api.alexandria.dev/errors/forbidden"
    assert body["title"] == "Acesso Proibido"
    assert "BIBLIOTECARIO" in body["detail"]


def test_admin_listar_funcionarios_sucesso(client: TestClient, admin_headers: dict):
    """ADMIN lista funcionários cadastrados com sucesso retornando 200 OK e dados paginados."""
    response = client.get("/api/v1/lib/users/funcionarios", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert "meta" in data
    assert len(data["data"]) >= 2
    assert data["meta"]["totalItems"] >= 2


def test_admin_selecionar_funcionario_existente(client: TestClient, admin_headers: dict):
    """ADMIN consulta cadastro completo de funcionário existente por ID."""
    response = client.get("/api/v1/lib/users/funcionarios/1", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert (data.get("funcionario-id") or data.get("id")) == 1
    assert data["matricula"] == 20260
    assert data["CPF"] == "987.654.321-00"
    assert data["nome"] == "João Souza"


def test_admin_selecionar_funcionario_inexistente_404(client: TestClient, admin_headers: dict):
    """ADMIN consulta funcionário não cadastrado retornando 404 RFC 9457."""
    response = client.get("/api/v1/lib/users/funcionarios/9999", headers=admin_headers)
    assert response.status_code == 404
    assert "application/problem+json" in response.headers["content-type"]
    body = response.json()
    assert body["status"] == 404
    assert body["type"] == "https://api.alexandria.dev/errors/not-found"
    assert body["title"] == "Funcionário Não Encontrado"


def test_admin_cadastrar_funcionario_sucesso(client: TestClient, admin_headers: dict):
    """ADMIN cadastra novo membro da equipe com sucesso (HTTP 201 Created e Location)."""
    payload = {
        "matricula": 30550,
        "CPF": "555.444.333-22",
        "nome": "Carlos Drummond",
        "email": "carlos.drummond@biblioteca.com",
        "telefone": "(16)99111-2222",
        "dt-nascimento": "1988-10-31",
        "salario": 2800.00,
        "password": "SenhaForte@2026",
        "role": "BIBLIOTECARIO",
    }
    response = client.post("/api/v1/lib/users/funcionarios", json=payload, headers=admin_headers)
    assert response.status_code == 201
    assert "location" in response.headers
    data = response.json()
    assert (data.get("funcionario-id") or data.get("id")) is not None
    assert data["matricula"] == 30550
    assert data["email"] == payload["email"]


def test_admin_cadastrar_funcionario_conflito_cpf_409(client: TestClient, admin_headers: dict):
    """Rejeita tentativa de cadastro de funcionário com CPF duplicado (HTTP 409 Conflict)."""
    payload = {
        "matricula": 88888,
        "CPF": "987.654.321-00",  # CPF do João Souza (ID 1)
        "nome": "Outro João",
        "email": "outro.email@biblioteca.com",
        "dt-nascimento": "1990-01-01",
        "salario": 2000.00,
        "password": "OutraSenha@123",
    }
    response = client.post("/api/v1/lib/users/funcionarios", json=payload, headers=admin_headers)
    assert response.status_code == 409
    assert "application/problem+json" in response.headers["content-type"]
    body = response.json()
    assert body["status"] == 409
    assert body["title"] == "Conflito de CPF"


def test_admin_cadastrar_funcionario_conflito_email_409(client: TestClient, admin_headers: dict):
    """Rejeita tentativa de cadastro com e-mail institucional duplicado (HTTP 409 Conflict)."""
    payload = {
        "matricula": 77777,
        "CPF": "111.222.333-44",
        "nome": "Novo Bibliotecário",
        "email": "ana.lima@biblioteca.com",  # E-mail da Ana Lima (ID 2)
        "dt-nascimento": "1992-05-15",
        "salario": 2200.00,
        "password": "OutraSenha@123",
    }
    response = client.post("/api/v1/lib/users/funcionarios", json=payload, headers=admin_headers)
    assert response.status_code == 409
    assert "application/problem+json" in response.headers["content-type"]
    body = response.json()
    assert body["status"] == 409
    assert body["title"] == "Conflito de E-mail"


def test_admin_cadastrar_funcionario_conflito_matricula_409(client: TestClient, admin_headers: dict):
    """Rejeita tentativa de cadastro com matrícula duplicada (HTTP 409 Conflict)."""
    payload = {
        "matricula": 20260,  # Matrícula do João Souza (ID 1)
        "CPF": "444.555.666-77",
        "nome": "Outro Colaborador",
        "email": "colaborador.novo@biblioteca.com",
        "dt-nascimento": "1991-08-10",
        "salario": 2500.00,
        "password": "OutraSenha@123",
    }
    response = client.post("/api/v1/lib/users/funcionarios", json=payload, headers=admin_headers)
    assert response.status_code == 409
    assert "application/problem+json" in response.headers["content-type"]
    body = response.json()
    assert body["status"] == 409
    assert body["title"] == "Conflito de Matrícula"


def test_admin_cadastrar_funcionario_salario_invalido_422(client: TestClient, admin_headers: dict):
    """Rejeita cadastro de funcionário com remuneração inferior a R$ 1.621,00 (HTTP 422)."""
    payload = {
        "matricula": 99123,
        "CPF": "888.999.000-11",
        "nome": "Estagiário Abaixo do Piso",
        "email": "estagio@biblioteca.com",
        "dt-nascimento": "2002-04-12",
        "salario": 1200.00,  # Menor que 1621.0
        "password": "SenhaValida@2026",
    }
    response = client.post("/api/v1/lib/users/funcionarios", json=payload, headers=admin_headers)
    assert response.status_code == 422
    assert "application/problem+json" in response.headers["content-type"]
    body = response.json()
    assert body["status"] == 422
    assert "invalidParams" in body
    params = [p["name"] for p in body["invalidParams"]]
    assert "salario" in params


def test_admin_atualizar_funcionario_patch_sucesso(client: TestClient, admin_headers: dict):
    """ADMIN atualiza remuneração e telefone de colaborador com sucesso (HTTP 200 OK)."""
    patch_payload = {
        "salario": 3500.00,
        "telefone": "(16)99999-0000",
    }
    response = client.patch(
        "/api/v1/lib/users/funcionarios/2",
        json=patch_payload,
        headers=admin_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert (data.get("funcionario-id") or data.get("id")) == 2
    assert data["salario"] == 3500.00
    assert data["telefone"] == "(16)99999-0000"
    # Campos não modificados mantêm seus valores originais
    assert data["nome"] == "Ana Lima"
