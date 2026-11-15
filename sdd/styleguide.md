# STYLEGUIDE.md — Constituição Técnica (Projeto Alexandria: ORM & Auth Edition)

## 1. Stack Tecnológica e Versões Obrigatórias
- **Linguagem:** Python 3.12+ com anotações estáticas de tipo (`typing`, `UUID`, `datetime`, `Enum`, `Annotated`).
- **Framework Web:** FastAPI.
- **Validação e Serialização:** Pydantic v2 (`BaseModel`, `ConfigDict(populate_by_name=True, from_attributes=True)`, `Field`, `@field_validator`).
- **Persistência e ORM:** SQLAlchemy 2.0+ utilizando sintaxe declarativa moderna (`DeclarativeBase`, `Mapped`, `mapped_column`, `relationship`, `ForeignKey`) com banco SQLite (`sqlite:///./alexandria.db` em execução normal e banco isolado em memória/arquivo temporário nos testes).
- **Segurança, Autenticação e Autorização:** Autenticação Stateless via **JWT (`PyJWT`)** no padrão `Bearer Token` (`HTTPBearer`) e controle de acesso baseado em papéis (**RBAC**: ex. `ADMIN`, `BIBLIOTECARIO`, `LEITOR`).
- **Suíte de Testes:** `pytest` + `fastapi.testclient.TestClient`.

---

## 2. Arquitetura de Diretórios e Separação de Camadas
Todo o código da API deve respeitar rigorosamente a estrutura abaixo, refletindo as coleções do Apidog:

```text
src/api/
├── __init__.py
├── main.py          # Instância FastAPI, lifespan (init_db + seed), CORS, middleware JSON e rotas
├── schemas.py       # Contratos Pydantic v2 espelhando os Data Schemas do Apidog (com alias em kebab-case) + DTOs Auth
├── models.py        # Entidades ORM SQLAlchemy 2.0 (LivroModel, EmprestimoModel, FuncionarioModel, UsuarioModel)
├── database.py      # Engine SQLAlchemy, SessionLocal, get_db (Dependency Injection) e seed inicial
├── security.py      # Geração/validação de JWT, hash de senha e dependências RBAC (get_current_user, require_role)
├── exceptions.py    # Exceções de domínio e handlers globais no padrão RFC 9457 (400, 401, 403, 404, 409, 422)
├── requirements.txt # Dependências estritas do projeto (fastapi, uvicorn, pydantic, sqlalchemy, pyjwt, pytest, httpx)
├── routers/
│   ├── __init__.py
│   ├── auth.py            # Endpoints de autenticação
│   ├── livros.py          # Endpoints da coleção /api/v1/lib/acervo
│   ├── emprestimos.py     # Endpoints da coleção /api/v1/lib/emprestimos
│   ├── funcionarios.py    # Endpoints da coleção /api/v1/lib/users/funcionarios
│   └── usuarios.py        # Endpoints da coleção /api/v1/lib/users/usuarios (leitores)
└── tests/
    ├── __init__.py
    ├── conftest.py          # Override de get_db para banco SQLite isolado e fixtures JWT
    ├── test_auth.py         # Testes de segurança, login e RBAC
    ├── test_livros.py       # Testes de contrato e persistência do Acervo
    ├── test_emprestimos.py  # Testes de regras de negócio de Empréstimos e relacionamentos
    ├── test_funcionarios.py # Testes de operações CRUD de Funcionários (Equipe)
    ├── test_usuarios.py     # Testes de operações CRUD de Usuários (Leitores)
    └── test_errors.py       # Testes de conformidade RFC 9457 global
```

---

## 3. Regras Inegociáveis de Implementação

### 3.1. Tratamento de Erros Semântico (RFC 9457 / Problem Details)
- É **PROIBIDO** retornar erros no formato padrão do FastAPI (`{"detail": "..."}`).
- Qualquer erro HTTP (`400`, `401`, `403`, `404`, `409`, `422`) DEVE retornar um JSON compatível com o schema `ApiError`:
  - `type`: URI identificadora do erro (ex: `https://api.alexandria.dev/errors/not-found`).
  - `title`: Resumo curto e legível.
  - `status`: Código HTTP numérico.
  - `detail`: Explicação clara.
  - `instance`: Caminho da URI requisitada (`request.url.path`).
  - `invalidParams`: Lista de objetos `{"name": "<campo>", "reason": "<motivo>"}` obrigatória em falhas de validação.

### 3.2. Regras de ORM e Prevenção N+1
- Use exclusivamente **SQLAlchemy 2.0** (`select()`, `Session.scalars()`, `Mapped[...]`, `mapped_column(...)`).
- Nos Empréstimos (que conectam Livro, Usuário e Funcionário), configure os relacionamentos `ForeignKey` adequadamente.
- Ao consultar listas que envolvem relacionamentos (ex: listar empréstimos com dados do livro), utilize `selectinload` ou `joinedload` para **evitar o problema N+1**.
- Transações de escrita (`POST`, `PATCH`, `DELETE`) devem usar `db.commit()` e tratar falhas com `db.rollback()`.

### 3.3. Convenções de Nomenclatura Pydantic (Kebab-Case)
- O Apidog do projeto Alexandria usa estritamente `kebab-case` para as chaves JSON (ex: `livro-id`, `num-paginas`, `dt-cadastro`).
- No Python, os atributos do modelo Pydantic não podem conter hífens. Você **DEVE** mapeá-los usando `Field(alias="...")` ou configurar `alias_generator`.
- Exemplo: `livro_id: int = Field(alias="livro-id")`.
- A configuração `populate_by_name=True` no `ConfigDict` é obrigatória.