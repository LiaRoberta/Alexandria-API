"""test_emprestimos.py — Suíte de Testes da Coleção de Empréstimos (/api/v1/lib/emprestimos).

Testa regras críticas de negócio e integridade transacional ACID:
- Criação com decremento de limite do leitor e incremento de empréstimos do livro
- Conflito 409 para livro exemplar de consulta local
- Conflito 409 para livro já emprestado simultaneamente
- Conflito 409 para leitor com cota esgotada (limite_disp == 0)
- Devolução via PATCH com preenchimento de dt_devolucao e restauração da cota
- Remoção DELETE com liberação e retorno 204 No Content
- Consulta por ID inexistente retornando 404 RFC 9457
"""

from datetime import datetime, timedelta
import pytest
from fastapi.testclient import TestClient


def test_criar_emprestimo_sucesso(client: TestClient, biblio_headers: dict):
    """Cria empréstimo com sucesso (201 Created), verifica cota do leitor e contador do livro."""
    dt_vencimento = (datetime.utcnow() + timedelta(days=14)).isoformat()
    payload = {
        "livro-id": 1,
        "usuario-id": 7,
        "dt-vencimento": dt_vencimento,
    }

    # 1. Realiza empréstimo
    response = client.post("/api/v1/lib/emprestimos", json=payload, headers=biblio_headers)
    assert response.status_code == 201
    assert "location" in response.headers
    data = response.json()
    emp_id = data.get("emprestimo-id") or data.get("id")
    assert emp_id is not None
    assert (data.get("livro-id") or data.get("livro_id")) == 1
    assert (data.get("usuario-id") or data.get("usuario_id")) == 7
    assert data["status"] == "Emprestado"

    # 2. Verifica se limite_disp do usuário decrementou (era 3 no seed, agora 2)
    user_res = client.get("/api/v1/lib/users/usuarios/7", headers=biblio_headers)
    assert user_res.status_code == 200
    user_data = user_res.json()
    assert (user_data.get("limite-disp") if "limite-disp" in user_data else user_data.get("limiteDisp")) == 2

    # 3. Verifica se qtd_emprestimos do livro incrementou (era 0, agora 1)
    book_res = client.get("/api/v1/lib/acervo/1")
    assert book_res.status_code == 200
    book_data = book_res.json()
    assert (book_data.get("qtd-emprestimos") if "qtd-emprestimos" in book_data else book_data.get("qtdEmprestimos")) == 1


def test_emprestimo_conflito_livro_exemplar_409(client: TestClient, admin_headers: dict):
    """Rejeita empréstimo de livro marcado como exemplar de consulta local (HTTP 409)."""
    # 1. Marca livro 1 como exemplar
    client.patch("/api/v1/lib/acervo/1", json={"exemplar": True}, headers=admin_headers)

    # 2. Tenta realizar empréstimo
    dt_vencimento = (datetime.utcnow() + timedelta(days=7)).isoformat()
    payload = {
        "livro-id": 1,
        "usuario-id": 7,
        "dt-vencimento": dt_vencimento,
    }
    response = client.post("/api/v1/lib/emprestimos", json=payload, headers=admin_headers)
    assert response.status_code == 409
    assert "application/problem+json" in response.headers["content-type"]
    body = response.json()
    assert body["status"] == 409
    assert body["type"] == "https://api.alexandria.dev/errors/conflict"
    assert "consulta local exclusiva" in body["detail"].lower()


def test_emprestimo_conflito_livro_ja_emprestado_409(client: TestClient, biblio_headers: dict):
    """Rejeita tentativa de emprestar obra que já possui empréstimo ativo em andamento (HTTP 409)."""
    dt_vencimento = (datetime.utcnow() + timedelta(days=14)).isoformat()
    payload = {
        "livro-id": 1,
        "usuario-id": 7,
        "dt-vencimento": dt_vencimento,
    }

    # 1. Primeiro empréstimo com sucesso
    r1 = client.post("/api/v1/lib/emprestimos", json=payload, headers=biblio_headers)
    assert r1.status_code == 201

    # 2. Segundo empréstimo para o mesmo livro sem devolução
    r2 = client.post("/api/v1/lib/emprestimos", json=payload, headers=biblio_headers)
    assert r2.status_code == 409
    assert "application/problem+json" in r2.headers["content-type"]
    body = r2.json()
    assert body["status"] == 409
    assert "empréstimo ativo" in body["detail"].lower()


def test_emprestimo_conflito_limite_zerado_409(client: TestClient, biblio_headers: dict):
    """Rejeita empréstimo quando o leitor atinge limite_disp == 0 (HTTP 409)."""
    # 1. Zera o limite disponível do leitor 7
    client.patch("/api/v1/lib/users/usuarios/7", json={"limite-disp": 0}, headers=biblio_headers)

    # 2. Tenta realizar empréstimo
    dt_vencimento = (datetime.utcnow() + timedelta(days=14)).isoformat()
    payload = {
        "livro-id": 1,
        "usuario-id": 7,
        "dt-vencimento": dt_vencimento,
    }
    response = client.post("/api/v1/lib/emprestimos", json=payload, headers=biblio_headers)
    assert response.status_code == 409
    assert "application/problem+json" in response.headers["content-type"]
    body = response.json()
    assert body["status"] == 409
    assert "limite máximo" in body["detail"].lower()


def test_devolucao_emprestimo_patch_sucesso(client: TestClient, biblio_headers: dict):
    """Devolução restaura a cota do leitor (+1) e preenche dt_devolucao (HTTP 200 OK)."""
    dt_vencimento = (datetime.utcnow() + timedelta(days=14)).isoformat()
    create_res = client.post(
        "/api/v1/lib/emprestimos",
        json={"livro-id": 1, "usuario-id": 7, "dt-vencimento": dt_vencimento},
        headers=biblio_headers,
    )
    assert create_res.status_code == 201
    emp_id = create_res.json().get("emprestimo-id") or create_res.json().get("id")

    # Atualiza status para Devolvido
    patch_res = client.patch(
        f"/api/v1/lib/emprestimos/{emp_id}",
        json={"status": "Devolvido"},
        headers=biblio_headers,
    )
    assert patch_res.status_code == 200
    patch_data = patch_res.json()
    assert patch_data["status"] == "Devolvido"
    assert (patch_data.get("dt-devolucao") or patch_data.get("dtDevolucao")) is not None

    # Verifica se cota do leitor foi restaurada de volta para 3
    user_res = client.get("/api/v1/lib/users/usuarios/7", headers=biblio_headers)
    assert (user_res.json().get("limite-disp") if "limite-disp" in user_res.json() else user_res.json().get("limiteDisp")) == 3


def test_remover_emprestimo_delete_sucesso(client: TestClient, admin_headers: dict):
    """Exclui registro de empréstimo retornando HTTP 204 No Content e restaurando cota se ativo."""
    dt_vencimento = (datetime.utcnow() + timedelta(days=14)).isoformat()
    create_res = client.post(
        "/api/v1/lib/emprestimos",
        json={"livro-id": 1, "usuario-id": 7, "dt-vencimento": dt_vencimento},
        headers=admin_headers,
    )
    assert create_res.status_code == 201
    emp_id = create_res.json().get("emprestimo-id") or create_res.json().get("id")

    # Exclui empréstimo
    del_res = client.delete(f"/api/v1/lib/emprestimos/{emp_id}", headers=admin_headers)
    assert del_res.status_code == 204

    # Confirma que consulta retorna 404
    check_res = client.get(f"/api/v1/lib/emprestimos/{emp_id}", headers=admin_headers)
    assert check_res.status_code == 404


def test_selecionar_emprestimo_inexistente_404(client: TestClient, biblio_headers: dict):
    """Retorna HTTP 404 Problem Details ao buscar empréstimo inexistente (ID 9999)."""
    response = client.get("/api/v1/lib/emprestimos/9999", headers=biblio_headers)
    assert response.status_code == 404
    assert "application/problem+json" in response.headers["content-type"]
    body = response.json()
    assert body["status"] == 404
    assert body["type"] == "https://api.alexandria.dev/errors/not-found"
    assert body["title"] == "Empréstimo Inexistente"


def test_listar_emprestimos_paginado(client: TestClient, biblio_headers: dict):
    """Consulta listagem de empréstimos autenticada com meta de paginação."""
    response = client.get("/api/v1/lib/emprestimos?page=1&limit=10", headers=biblio_headers)
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert "meta" in data
    assert data["meta"]["page"] == 1
