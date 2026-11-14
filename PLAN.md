# PLAN.md — Plano Técnico de Implementação: Alexandria v2 (SQLAlchemy 2.0 ORM & JWT/RBAC)

> **Status:** Concluído com 100% de Aprovação nos Testes  
> **Papel Ativo:** `[QA Engineer]` (Engenheiro de Qualidade)  
> **Contrato Base:** `Alexandria.Apidog.json`  
> **Constituição Técnica:** `STYLEGUIDE.md` & `AGENTS.md`

---

## 1. Visão Geral da Arquitetura & Mapeamento de Domínio

O objetivo deste plano é guiar a implementação da **Alexandria v2**, transformando o contrato formal de API de gerenciamento da biblioteca Alexandria (`Alexandria.Apidog.json`) em uma API assíncrona robusta em **FastAPI**, com persistência relacional **SQLAlchemy 2.0 Declarativo**, autenticação stateless **JWT (HS256)**, controle de acesso baseado em papéis (**RBAC: ADMIN e MEMBER**) e tratamento semântico de erros estritamente compatível com **RFC 9457 (Problem Details)**.

### Mapeamento de Entidades e Relacionamento 1:N
- **Autenticação & RBAC:** `UserModel` gerencia credenciais (`email`, `hashed_password`, `role`).
  - `ADMIN`: Funcionários/administradores com permissão total de escrita (CRUD no acervo, usuários e funcionários).
  - `MEMBER`: Leitores/usuários comuns com permissão de consulta e solicitação de empréstimos.
- **Domínio Principal (Alexandria):**
  - **Acervo (`LivroModel` / correspondência com `ProjectModel`):** Entidade pai com atributos como `ISBN`, `titulo`, `categoria`, `status`, `exemplar`, etc.
  - **Empréstimos (`EmprestimoModel` / correspondência com `TaskModel`):** Entidade dependente vinculada via chave estrangeira `ForeignKey("livros.id")`, além de vínculos com `UsuarioModel` e `FuncionarioModel`. Relacionamento `1:N` entre Livro e Empréstimos mapeado com `relationship(...)` e carregado com `selectinload` para erradicar o problema de queries N+1.
  - **Usuários Leitores (`UsuarioModel`):** Leitores cadastrados com limite de livros disponíveis.
  - **Funcionários (`FuncionarioModel`):** Colaboradores com matrícula e dados funcionais.

---

## 2. Checklist Sequencial e Granular de Implementação

### Fase 1: Estrutura de Diretórios e requirements.txt
- [x] 1.1 Criar a estrutura física de diretórios do projeto:
  - `src/api/`
  - `src/api/routers/`
  - `src/api/tests/`
- [x] 1.2 Criar os arquivos de pacote `__init__.py`:
  - `src/api/__init__.py`
  - `src/api/routers/__init__.py`
  - `src/api/tests/__init__.py`
- [x] 1.3 Criar o arquivo `src/api/requirements.txt` fixando dependências e versões estritas:
  - `fastapi>=0.110.0`
  - `uvicorn[standard]>=0.28.0`
  - `pydantic>=2.6.0`
  - `pydantic-settings>=2.2.0`
  - `sqlalchemy>=2.0.28`
  - `pyjwt>=2.8.0`
  - `pwdlib[bcrypt]>=0.2.0` ou `passlib[bcrypt]>=1.7.4`
  - `pytest>=8.0.0`
  - `httpx>=0.27.0`

---

### Fase 2: Extração de Schemas Pydantic v2 (Apidog + DTOs de Auth)
- [x] 2.1 Criar `src/api/schemas.py` com as definições de Enums tipados extraídos do contrato:
  - `CategoriaLivroEnum` (`Aventura`, `Terror`, `Romance`, `Fantasia`, `Ficção Científica`, `Suspense`, `Estudantil`)
  - `StatusLivroEnum` (`Novo`, `Conservado`, `Regular`, `Danificado`)
  - `StatusEmprestimoEnum` (`Emprestado`, `Devolvido`, `Vencido`)
  - `UserRoleEnum` (`ADMIN`, `MEMBER`)
- [x] 2.2 Definir os schemas base de infraestrutura e paginação:
  - `PageMeta`: `page` (int), `limit` (int), `totalItems` (int), `totalPages` (int), `hasNext` (bool).
  - `InvalidParam`: `name` (str), `reason` (str).
  - `ApiError`: `type` (str), `title` (str), `status` (int), `detail` (str), `instance` (str), `invalidParams` (list[InvalidParam] | None).
- [x] 2.3 Extrair os contratos de dados para Livros / Acervo (`schemas.py`):
  - `LivroBase`: atributos comuns com validações (`titulo` min 1 max 200, regex ISBN `^[0-9]{3}-[0-9]{2}-[0-9]{5}-[0-9]{2}-[0-9]{1}$`, categoria, status, num-paginas > 0, etc.).
  - `CreateLivro`: herda de `LivroBase`, omitindo `livro-id` e `qtd-emprestimos`.
  - `UpdateLivro`: campos parciais opcionais; não permite alteração de `livro-id`, `ISBN`, `dt-cadastro` e `exemplar`.
  - `LivroResponse`: inclui `livro-id`, `qtd-emprestimos`, `dt-cadastro` com `ConfigDict(populate_by_name=True, from_attributes=True)` e mapeamento com aliases kebab-case.
  - `LivroListResponse`: contém `data: list[LivroResponse]` e `meta: PageMeta`.
- [x] 2.4 Extrair os contratos de dados para Empréstimos (`schemas.py`):
  - `EmprestimoBase`: `livro-id` (int), `usuario-id` (int), `funcionario-id` (int), `status`, `dt-vencimento`.
  - `CreateEmprestimo`: excludes `emprestimo-id`, `status`, `dt-emprestimo`, `dt-devolucao`.
  - `UpdateEmprestimo`: permite atualizar `status` e `dt-devolucao`.
  - `EmprestimoResponse`: modelo de retorno completo com aliases e `from_attributes=True`.
  - `EmprestimoListResponse`: `data: list[EmprestimoResponse]` e `meta: PageMeta`.
- [x] 2.5 Extrair os contratos de Usuários e Funcionários (`schemas.py`):
  - `FuncionarioBase`, `CreateFuncionario`, `UpdateFuncionario`, `FuncionarioResponse`, `FuncionarioListResponse` (com validações de CPF e email).
  - `UsuarioBase`, `CreateUsuario`, `UpdateUsuario`, `UsuarioResponse`, `UsuarioListResponse` (com validações de CPF, CEP e limite-disp).
- [x] 2.6 Definir DTOs de Autenticação JWT e RBAC (`schemas.py`):
  - `LoginRequest`: `email` (EmailStr), `password` (str com minLength 6).
  - `TokenResponse`: `accessToken` (str), `tokenType` (str = "Bearer"), `expiresIn` (int).
  - `UserResponse`: `id` (int), `email` (EmailStr), `role` (UserRoleEnum), `createdAt` (datetime).
- [x] 2.7 Declarar aliases de compatibilidade de domínio (`ProjectCreate = CreateLivro`, `TaskCreate = CreateEmprestimo`, etc.) para conformidade integral com a especificação técnica do curso.

---

### Fase 3: Modelos ORM SQLAlchemy 2.0 e database.py com Seed
- [x] 3.1 Criar a base declarativa moderna em `src/api/models.py` utilizando `DeclarativeBase`, `Mapped`, `mapped_column`, `relationship` e `ForeignKey`.
- [x] 3.2 Implementar `UserModel` em `src/api/models.py`:
  - `id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)`
  - `email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)`
  - `hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)`
  - `role: Mapped[str] = mapped_column(String(20), default="MEMBER", nullable=False)`
  - `created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)`
- [x] 3.3 Implementar entidades do acervo e empréstimos com relacionamento 1:N:
  - `LivroModel` (tabela `livros`): colunas `id` (uint32), `isbn` (str), `titulo` (str), `autor` (str | None), `editora` (str | None), `publicacao` (int | None), `categoria` (str), `exemplar` (bool), `num_paginas` (int | None), `qtd_emprestimos` (int, default=0), `dt_cadastro` (datetime), `status` (str).
    - Relacionamento 1:N: `emprestimos: Mapped[list["EmprestimoModel"]] = relationship(back_populates="livro", cascade="all, delete-orphan")`
  - `UsuarioModel` (tabela `usuarios`): colunas `id`, `cpf`, `nome`, `email`, `telefone`, `cep`, `dt_nascimento`, `dt_cadastro`, `limite_disp`.
    - Relacionamento 1:N: `emprestimos: Mapped[list["EmprestimoModel"]] = relationship(back_populates="usuario")`
  - `FuncionarioModel` (tabela `funcionarios`): colunas `id`, `matricula`, `cpf`, `nome`, `email`, `telefone`, `dt_nascimento`, `dt_admissao`, `salario`.
    - Relacionamento 1:N: `emprestimos: Mapped[list["EmprestimoModel"]] = relationship(back_populates="funcionario")`
  - `EmprestimoModel` (tabela `emprestimos`): colunas `id`, `livro_id` (FK `livros.id`), `usuario_id` (FK `usuarios.id`), `funcionario_id` (FK `funcionarios.id`), `status`, `dt_emprestimo`, `dt_vencimento`, `dt_devolucao`.
    - Relacionamentos N:1: `livro`, `usuario` e `funcionario` com `back_populates`.
- [x] 3.4 Estabelecer aliases declarativos em `src/api/models.py` para garantia de compatibilidade com o STYLEGUIDE:
  - `ProjectModel = LivroModel`
  - `TaskModel = EmprestimoModel`
- [x] 3.5 Configurar `src/api/database.py`:
  - `engine = create_engine("sqlite:///./alexandria.db", connect_args={"check_same_thread": False})`
  - `SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)`
  - Dependência `get_db()` com gerenciamento de escopo e `db.close()`.
- [x] 3.6 Implementar rotina idempotente `init_db_and_seed(db: Session)` em `src/api/database.py`:
  - Criação automática de tabelas via `Base.metadata.create_all(bind=engine)`.
  - Criação de usuário `admin@fatec.sp.gov.br` com role `ADMIN` e senha segura hasheada (`admin123`).
  - Criação de usuário `aluno@fatec.sp.gov.br` com role `MEMBER` e senha segura hasheada (`aluno123`).
  - Carga inicial de livros no acervo (projetos), usuários leitores, funcionários e registros de empréstimo (tarefas vinculadas 1:N) de demonstração.

---

### Fase 4: Exceções RFC 9457 (400, 401, 403, 404, 422) e security.py (JWT + RBAC)
- [x] 4.1 Definir a hierarquia de exceções de domínio em `src/api/exceptions.py`:
  - `DomainBadRequestException` (HTTP 400)
  - `DomainUnauthorizedException` (HTTP 401)
  - `DomainForbiddenException` (HTTP 403)
  - `DomainNotFoundException` (HTTP 404)
  - `DomainConflictException` (HTTP 409)
  - `DomainValidationException` (HTTP 422)
- [x] 4.2 Construir formatadores RFC 9457 padronizados em `src/api/exceptions.py`:
  - Retorno com cabeçalho `Content-Type: application/problem+json` e formato `ApiError`.
  - Mapeamento estrito de URIs canônicas do STYLEGUIDE:
    - 400: `https://api.taskflow.dev/errors/bad-request`
    - 401: `https://api.taskflow.dev/errors/unauthorized`
    - 403: `https://api.taskflow.dev/errors/forbidden`
    - 404: `https://api.taskflow.dev/errors/not-found`
    - 422: `https://api.taskflow.dev/errors/validation-error`
- [x] 4.3 Implementar handlers globais do FastAPI em `src/api/exceptions.py`:
  - Handler para `RequestValidationError`: transforma erros do Pydantic na lista `invalidParams` (`{"name": "...", "reason": "..."}`) e responde com status 422.
  - Handler para `HTTPException` e `DomainException`: intercepta exceções e formata resposta sem usar o `{ "detail": "..." }` padrão.
- [x] 4.4 Implementar rotinas de criptografia de senhas em `src/api/security.py`:
  - `hash_password(plain_password: str) -> str`
  - `verify_password(plain_password: str, hashed_password: str) -> bool`
- [x] 4.5 Implementar geração e decodificação de JWT em `src/api/security.py`:
  - Parâmetros: `SECRET_KEY`, `ALGORITHM = "HS256"`, `ACCESS_TOKEN_EXPIRE_MINUTES = 60`.
  - `create_access_token(data: dict, expires_delta: timedelta | None = None) -> str` incluindo `sub`, `email`, `role`, `iat`, `exp`.
- [x] 4.6 Implementar dependências de autenticação e RBAC em `src/api/security.py`:
  - Esquema `HTTPBearer(auto_error=False)` para controle semântico de ausência de cabeçalho.
  - `get_current_user`: valida o token JWT; levanta `DomainUnauthorizedException` (401 RFC 9457) em caso de token ausente, malformado ou expirado.
  - `require_role(required_role: str)` / `require_roles`: factory de dependência que valida a role do usuário autenticado; levanta `DomainForbiddenException` (403 RFC 9457) caso a role seja insuficiente.

---

### Fase 5: Routers (auth, tasks, projects com selectinload) e main.py
- [x] 5.1 Implementar `src/api/routers/auth.py`:
  - `POST /api/v1/auth/login`: valida credenciais de email/senha, gera e retorna `TokenResponse` (200) ou 401 RFC 9457.
  - `GET /api/v1/auth/me`: protegido por `get_current_user`, retorna `UserResponse` (200).
- [x] 5.2 Implementar roteador do Acervo / Tarefas (`src/api/routers/tasks.py` / `acervo.py`):
  - `GET /api/v1/lib/acervo`: listagem paginada (`page`, `limit`) com filtros (`search`, `categoria`, `status`, `exemplar`, `titulo`) retornando `LivroListResponse`.
  - `GET /api/v1/lib/acervo/{livro-id}`: seleção por ID com 404 RFC 9457 se não encontrado.
  - `POST /api/v1/lib/acervo`: criação protegida por RBAC (`ADMIN`), valida duplicidade de ISBN (409) e campos (422), retornando status 201.
  - `PATCH /api/v1/lib/acervo/{livro-id}`: atualização parcial protegida por RBAC (`ADMIN`), status 200.
  - `DELETE /api/v1/lib/acervo/{livro-id}`: remoção protegida por RBAC (`ADMIN`), status 204.
- [x] 5.3 Implementar roteador de Empréstimos / Projetos (`src/api/routers/projects.py` / `emprestimos.py`) com prevenção N+1:
  - `GET /api/v1/lib/emprestimos`: listagem otimizada usando `select(EmprestimoModel).options(selectinload(EmprestimoModel.livro), selectinload(EmprestimoModel.usuario), selectinload(EmprestimoModel.funcionario))` evitando queries N+1.
  - `GET /api/v1/lib/emprestimos/{emprestimo-id}`: detalhe do empréstimo com eager loading e 404 RFC 9457.
  - `POST /api/v1/lib/emprestimos`: cadastro com validação de disponibilidade do exemplar, checagem do limite do usuário e transação explícita (`db.commit()`), status 201.
  - `PATCH /api/v1/lib/emprestimos/{emprestimo-Id}`: atualização de devolução/status e atualização atômica de contadores, status 200.
  - Endpoints aninhados `GET /api/v1/lib/acervo/{livro-id}/emprestimos` com `selectinload` para relacionar projetos/livros e suas tarefas/empréstimos.
- [x] 5.4 Implementar roteador de Usuários e Funcionários (`src/api/routers/users.py`):
  - Rotas completas para funcionários (`GET`, `GET/{id}`, `POST`, `PATCH`) protegidas por RBAC (`ADMIN`).
  - Rotas completas para usuários leitores (`GET`, `GET/{id}`, `POST`, `PATCH`).
- [x] 5.5 Implementar `src/api/main.py`:
  - Lifespan gerenciando inicialização e seed do banco (`init_db_and_seed`).
  - Instância do `FastAPI(title="Alexandria API v2", version="2.0.0")`.
  - Configuração de middlewares (CORS e validação JSON).
  - Registro de todos os exception handlers da RFC 9457.
  - Inclusão dos roteadores (`auth`, `tasks`/`acervo`, `projects`/`emprestimos`, `users`).

---

### Fase 6: Suíte Completa de Testes pytest
- [x] 6.1 Configurar fixtures e isolamento de banco em `src/api/tests/conftest.py`:
  - Criação de engine SQLite em memória/temporário (`sqlite:///:memory:`).
  - Override da dependência `get_db` do FastAPI direcionando para a sessão de teste isolada.
  - Fixtures de autenticação: `admin_token`, `member_token`, `expired_token`, `invalid_token`.
  - Fixture de `client: TestClient` para requisições HTTP locais.
- [x] 6.2 Implementar testes de autenticação e RBAC em `src/api/tests/test_auth.py`:
  - Teste de login com sucesso (200) e validação da estrutura do token JWT.
  - Teste de login com credenciais incorretas (401 RFC 9457).
  - Teste de `GET /api/v1/auth/me` com token válido (200).
  - Teste de acesso a rotas privadas sem header `Authorization` (401 RFC 9457).
  - Teste de acesso com token expirado e token corrompido (401 RFC 9457).
  - Teste de controle de acesso RBAC: usuário `MEMBER` tentando executar mutações administrativas (ex.: `POST` ou `DELETE` no acervo) recebendo status 403 Forbidden RFC 9457.
- [x] 6.3 Implementar testes de acervo/tarefas em `src/api/tests/test_tasks.py`:
  - Teste de listagem paginada e validação de `PageMeta` (`totalItems`, `totalPages`, `hasNext`).
  - Teste de filtros por categoria, status e busca textual.
  - Teste de criação de livro com validação de status 201 e persistência no banco.
  - Teste de consulta por ID existente (200) e inexistente (404 RFC 9457).
  - Teste de atualização parcial PATCH (200).
  - Teste de exclusão DELETE (204) e verificação de que nova consulta retorna 404.
- [x] 6.4 Implementar testes de projetos/empréstimos e integridade 1:N em `src/api/tests/test_projects.py`:
  - Teste de persistência do relacionamento 1:N entre Livro e Empréstimos.
  - Teste de consulta com eager loading (`selectinload`) comprovando ausência de problemas N+1.
  - Teste de criação de empréstimo vinculado a livro, usuário e funcionário válidos (201).
  - Teste de validação de FK inexistente ou exemplar indisponível gerando erro apropriado.
  - Teste de atualização de status e devolução de empréstimo (200).
- [x] 6.5 Implementar testes de conformidade com a RFC 9457 em `src/api/tests/test_errors.py`:
  - Validação estrita dos atributos do schema `ApiError` (`type`, `title`, `status`, `detail`, `instance`, `invalidParams`).
  - Teste de 400 Bad Request em requisições malformadas.
  - Teste de 401 Unauthorized em ausência/invalidação de token.
  - Teste de 403 Forbidden em violação de papel RBAC.
  - Teste de 404 Not Found para endpoints e IDs inexistentes.
  - Teste de 422 Unprocessable Entity com payload contendo campos inválidos, verificando o preenchimento do array `invalidParams`.
  - Asserção de que nenhuma rota retorna o formato padrão legado `{"detail": "..."}`.
- [x] 6.6 Executar e validar a suíte completa no terminal:
  - Comando: `pytest -v src/api/tests/`
  - Meta de aceitação: 100% dos testes aprovados (`PASSED`).
