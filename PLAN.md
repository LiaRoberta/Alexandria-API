# PLAN.md — Plano de Implementação Técnica da Alexandria API

**Metodologia:** Spec-Driven Development (SDD)  
**Fonte da Verdade do Contrato:** [`Alexandria.Apidog.json`](Alexandria.Apidog.json)  
**Especificação de Negócio, ORM e Segurança:** [`sdd/spec.md`](sdd/spec.md)  
**Constituição Técnica e Padrões:** [`sdd/styleguide.md`](sdd/styleguide.md)  
**Persona Responsável:** `[Tech Lead]` (Planejamento) / `[Backend Coder]` (Fases 1–5) / `[QA Engineer]` (Fase 6)  
**Status do Projeto:** 🟡 Planejamento Arquitetural Aprovado — Pronto para Execução Granular  

---

## Visão Geral da Arquitetura e Diretrizes

1. **Schema-First:** Toda tipagem em Pydantic v2 deriva estritamente de `Alexandria.Apidog.json`, com chaves JSON em `kebab-case` mapeadas via `Field(alias="...")` e `ConfigDict(populate_by_name=True, from_attributes=True)`.
2. **SQLAlchemy 2.0:** Persistência relacional moderna com `Mapped[...]`, `mapped_column(...)`, integridade referencial via `ForeignKey`, relacionamentos com `selectinload` para prevenção N+1 e IDs numéricos autoincrementais (`Integer PK`).
3. **Autenticação Stateless JWT & RBAC:** Criptografia de senha com `pwd_context` (bcrypt), emissão de tokens JWT (algoritmo `HS256`), dependência `get_current_user` e autorização por papéis `require_roles(["ADMIN", ...])`.
4. **Tratamento de Erros Semântico (RFC 9457):** Todas as falhas HTTP (`400`, `401`, `403`, `404`, `409`, `422`) devem responder rigorosamente no schema `ApiError` (`type`, `title`, `status`, `detail`, `instance`, `invalidParams`) com o header `application/problem+json`.
5. **Governança SDD:** Nenhuma linha de código em `src/api/` deve ser criada sem o correspondente item marcado como `[x]` neste plano e sob autorização expressa do usuário.

---

## 📋 Checklist Sequencial de Execução

### Fase 1: Estrutura de Diretórios e Dependências
- [x] **1.1. Inicialização da Estrutura de Diretórios:**
  - Criar `src/api/` e `src/api/routers/`
  - Criar `src/api/tests/`
  - Criar arquivos `__init__.py` nos diretórios `src/api/`, `src/api/routers/` e `src/api/tests/`
- [x] **1.2. Definição do `src/api/requirements.txt`:**
  - `fastapi>=0.115.0`
  - `uvicorn[standard]>=0.32.0`
  - `pydantic>=2.9.0`
  - `pydantic-settings>=2.5.0`
  - `sqlalchemy>=2.0.35`
  - `pyjwt[crypto]>=2.9.0`
  - `passlib[bcrypt]>=1.7.4`
  - `python-multipart>=0.0.12`
  - `pytest>=8.3.0`
  - `httpx>=0.27.0`

---

### Fase 2: Extração de Schemas Pydantic v2 (Apidog + DTOs de Auth)
*Arquivo de destino:* `src/api/schemas.py`

- [x] **2.1. Configurações Base e Enums de Domínio:**
  - Criar classe base com `ConfigDict(populate_by_name=True, from_attributes=True)`
  - `CategoriaLivro(str, Enum)`: `"Aventura"`, `"Terror"`, `"Romance"`, `"Fantasia"`, `"Ficção Científica"`, `"Suspense"`, `"Estudantil"`
  - `StatusLivro(str, Enum)`: `"Novo"`, `"Conservado"`, `"Regular"`, `"Danificado"`
  - `StatusEmprestimo(str, Enum)`: `"Emprestado"`, `"Devolvido"`, `"Vencido"`
  - `FuncionarioRole(str, Enum)`: `"ADMIN"`, `"BIBLIOTECARIO"`
- [x] **2.2. DTOs de Autenticação e Segurança (JWT/RBAC):**
  - `LoginRequestDTO`: `email` (str, formato email), `password` (str, min_length 6)
  - `AuthResponse`: `id` (int), `nome` (str), `email` (str), `role` (`FuncionarioRole`)
  - `TokenResponseDTO`: `accessToken` (str, alias `accessToken`), `tokenType` (str, alias `tokenType`, default `"bearer"`), `expiresIn` (int, alias `expiresIn`), `user` (`AuthResponse`)
- [x] **2.3. Schemas de Erro Padronizados (RFC 9457 — Problem Details):**
  - `InvalidParam`: `name` (str), `reason` (str)
  - `ApiError`: `type` (str), `title` (str), `status` (int), `detail` (str), `instance` (str), `invalidParams` (Optional[list[InvalidParam]])
- [x] **2.4. Schemas de Paginação:**
  - `PageMeta`: `page` (int), `limit` (int), `totalItems` (int, alias `totalItems`), `totalPages` (int, alias `totalPages`), `hasNext` (bool, alias `hasNext`)
- [x] **2.5. Schemas de Acervo (Livros):**
  - `Livro`: `livro_id` (int, alias `livro-id`), `ISBN` (str, regex), `titulo` (str, min 1, max 200), `autor` (Optional[str]), `num_paginas` (Optional[int], alias `num-paginas`), `editora` (Optional[str]), `publicacao` (Optional[int]), `categoria` (`CategoriaLivro`), `qtd_emprestimos` (int, alias `qtd-emprestimos`), `dt_cadastro` (datetime, alias `dt-cadastro`), `status` (`StatusLivro`), `exemplar` (bool)
  - `CreateLivroDTO`: omitir `livro-id` e `qtd-emprestimos`
  - `UpdateLivroDTO`: campos opcionais para atualização (omitir `livro-id`, `ISBN`, `dt-cadastro`, `exemplar`)
  - `LivroListResponse`: envelope `{ "data": list[Livro], "meta": PageMeta }`
- [x] **2.6. Schemas de Usuários (Leitores):**
  - `Usuario`: `usuario_id` (int, alias `usuario-id`), `CPF` (str, regex), `nome` (str, min 3, max 120), `email` (str, formato email), `telefone` (Optional[str]), `dt_nascimento` (Optional[date], alias `dt-nascimento`), `CEP` (Optional[str]), `limite_disp` (int, alias `limite-disp`), `dt_cadastro` (datetime, alias `dt-cadastro`)
  - `CreateUsuarioDTO`: omitir `usuario-id`, `limite-disp`, `dt-cadastro`
  - `UpdateUsuarioDTO`: campos editáveis (`nome`, `email`, `telefone`, `CEP`, `dt-nascimento`, `limite-disp`)
  - `UsuarioListResponse`: envelope `{ "data": list[Usuario], "meta": PageMeta }`
- [x] **2.7. Schemas de Funcionários (Equipe Administrativa):**
  - `Funcionario`: `funcionario_id` (int, alias `funcionario-id`), `matricula` (int), `CPF` (str, regex), `nome` (str, min 3, max 120), `email` (str, formato email), `telefone` (Optional[str]), `dt_nascimento` (date, alias `dt-nascimento`), `dt_admissao` (datetime, alias `dt-admissao`), `salario` (float, minimum 1621.0)
  - `CreateFuncionarioDTO`: omitir `funcionario-id`; incluir `password` temporária para geração de hash de acesso
  - `UpdateFuncionarioDTO`: campos editáveis (`nome`, `email`, `telefone`, `salario`)
  - `FuncionarioListResponse`: envelope `{ "data": list[Funcionario], "meta": PageMeta }`
- [x] **2.8. Schemas de Empréstimos:**
  - `Emprestimo`: `emprestimo_id` (int, alias `emprestimo-id`), `livro_id` (int, alias `livro-id`), `usuario_id` (int, alias `usuario-id`), `funcionario_id` (int, alias `funcionario-id`), `status` (`StatusEmprestimo`), `dt_emprestimo` (datetime, alias `dt-emprestimo`), `dt_vencimento` (datetime, alias `dt-vencimento`), `dt_devolucao` (Optional[datetime], alias `dt-devolucao`)
  - `CreateEmprestimoDTO`: `livro_id` (int, alias `livro-id`), `usuario_id` (int, alias `usuario-id`), `funcionario_id` (int, alias `funcionario-id`), `dt_vencimento` (datetime, alias `dt-vencimento`)
  - `UpdateEmprestimoDTO`: `status` (`StatusEmprestimo`), `dt_devolucao` (Optional[datetime], alias `dt-devolucao`)
  - `EmprestimoListResponse`: envelope `{ "data": list[Emprestimo], "meta": PageMeta }`

---

### Fase 3: Modelos ORM SQLAlchemy 2.0 e Banco de Dados com Seed
*Arquivos de destino:* `src/api/models.py` e `src/api/database.py`

- [x] **3.1. Modelagem Declarativa em `src/api/models.py`:**
  - Criar `Base(DeclarativeBase)`
  - `FuncionarioModel` (tabela `funcionarios`):
    - `id`: `Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)`
    - `matricula`: `Mapped[int] = mapped_column(Integer, unique=True, nullable=False)`
    - `cpf`: `Mapped[str] = mapped_column(String(14), unique=True, nullable=False)`
    - `nome`: `Mapped[str] = mapped_column(String(120), nullable=False)`
    - `email`: `Mapped[str] = mapped_column(String(120), unique=True, nullable=False)`
    - `telefone`: `Mapped[Optional[str]] = mapped_column(String(20), nullable=True)`
    - `dt_nascimento`: `Mapped[date] = mapped_column(Date, nullable=False)`
    - `dt_admissao`: `Mapped[datetime] = mapped_column(DateTime, nullable=False)`
    - `salario`: `Mapped[float] = mapped_column(Float, nullable=False)`
    - `password_hash`: `Mapped[str] = mapped_column(String(255), nullable=False)`
    - `role`: `Mapped[str] = mapped_column(String(20), default="BIBLIOTECARIO", nullable=False)`
    - `emprestimos: Mapped[list["EmprestimoModel"]] = relationship(back_populates="funcionario")`
  - `UsuarioModel` (tabela `usuarios`):
    - `id`: `Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)`
    - `cpf`: `Mapped[str] = mapped_column(String(14), unique=True, nullable=False)`
    - `nome`: `Mapped[str] = mapped_column(String(120), nullable=False)`
    - `email`: `Mapped[str] = mapped_column(String(120), nullable=False)`
    - `telefone`: `Mapped[Optional[str]] = mapped_column(String(20), nullable=True)`
    - `dt_nascimento`: `Mapped[Optional[date]] = mapped_column(Date, nullable=True)`
    - `cep`: `Mapped[Optional[str]] = mapped_column(String(10), nullable=True)`
    - `limite_disp`: `Mapped[int] = mapped_column(Integer, default=4, nullable=False)`
    - `dt_cadastro`: `Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)`
    - `emprestimos: Mapped[list["EmprestimoModel"]] = relationship(back_populates="usuario")`
  - `LivroModel` (tabela `livros`):
    - `id`: `Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)`
    - `isbn`: `Mapped[str] = mapped_column(String(20), unique=True, nullable=False)`
    - `titulo`: `Mapped[str] = mapped_column(String(200), nullable=False)`
    - `autor`: `Mapped[Optional[str]] = mapped_column(String(100), nullable=True)`
    - `num_paginas`: `Mapped[Optional[int]] = mapped_column(Integer, nullable=True)`
    - `editora`: `Mapped[Optional[str]] = mapped_column(String(100), nullable=True)`
    - `publicacao`: `Mapped[Optional[int]] = mapped_column(Integer, nullable=True)`
    - `categoria`: `Mapped[str] = mapped_column(String(50), nullable=False)`
    - `qtd_emprestimos`: `Mapped[int] = mapped_column(Integer, default=0, nullable=False)`
    - `dt_cadastro`: `Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)`
    - `status`: `Mapped[str] = mapped_column(String(30), default="Novo", nullable=False)`
    - `exemplar`: `Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)`
    - `emprestimos: Mapped[list["EmprestimoModel"]] = relationship(back_populates="livro")`
  - `EmprestimoModel` (tabela `emprestimos`):
    - `id`: `Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)`
    - `livro_id`: `Mapped[int] = mapped_column(ForeignKey("livros.id"), nullable=False)`
    - `usuario_id`: `Mapped[int] = mapped_column(ForeignKey("usuarios.id"), nullable=False)`
    - `funcionario_id`: `Mapped[int] = mapped_column(ForeignKey("funcionarios.id"), nullable=False)`
    - `status`: `Mapped[str] = mapped_column(String(30), default="Emprestado", nullable=False)`
    - `dt_emprestimo`: `Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)`
    - `dt_vencimento`: `Mapped[datetime] = mapped_column(DateTime, nullable=False)`
    - `dt_devolucao`: `Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)`
    - `livro: Mapped["LivroModel"] = relationship(back_populates="emprestimos")`
    - `usuario: Mapped["UsuarioModel"] = relationship(back_populates="emprestimos")`
    - `funcionario: Mapped["FuncionarioModel"] = relationship(back_populates="emprestimos")`
- [x] **3.2. Gerenciador de Banco de Dados em `src/api/database.py`:**
  - Configuração da engine SQLite (`sqlite:///./alexandria.db`) com `connect_args={"check_same_thread": False}`
  - Criação do `sessionmaker(autocommit=False, autoflush=False, bind=engine)`
  - Dependência FastAPI `get_db()` para injeção de sessão com `yield` e fechamento automático
  - Função `init_db()` idempotente:
    - `Base.metadata.create_all(bind=engine)`
    - Seed Funcionario ID 1: `"João Souza"`, `CPF: "987.654.321-00"`, `email: "joao.souza@biblioteca.com"`, hash de `"Admin@2026"`, role `"ADMIN"`, matricula `20260`
    - Seed Funcionario ID 2: `"Ana Lima"`, `CPF: "321.654.987-11"`, `email: "ana.lima@biblioteca.com"`, hash de `"Biblio@2026"`, role `"BIBLIOTECARIO"`, matricula `20261`
    - Seed Livro ID 1: `"O Hobbit"`, `ISBN: "978-85-12345-67-8"`, `categoria: "Fantasia"`
    - Seed Usuario ID 7: `"Maria Silva"`, `CPF: "123.456.789-09"`, `email: "maria.silva@email.com"`, `limite_disp: 3`
    - Regra estrita: O identificador `9999` NUNCA deve ser inserido em nenhuma tabela (reservado para testes 404).

---

### Fase 4: Exceções RFC 9457 e Segurança JWT/RBAC
*Arquivos de destino:* `src/api/exceptions.py` e `src/api/security.py`

- [x] **4.1. Camada de Exceções RFC 9457 em `src/api/exceptions.py`:**
  - Classe base `AlexandriaException(Exception)` com `status_code`, `title`, `detail`, `type_uri`, `invalid_params`
  - `NotFoundException(AlexandriaException)` -> HTTP 404
  - `ConflictException(AlexandriaException)` -> HTTP 409 (ISBN, CPF ou livros em empréstimo/exemplar)
  - `ValidationException(AlexandriaException)` -> HTTP 422 com lista `invalidParams`
  - `UnauthorizedException(AlexandriaException)` -> HTTP 401
  - `ForbiddenException(AlexandriaException)` -> HTTP 403 (acesso exclusivo ADMIN)
  - `BadRequestException(AlexandriaException)` -> HTTP 400
  - Handlers globais registrados para FastAPI:
    - Handler para `AlexandriaException`
    - Handler para `RequestValidationError` do FastAPI (transformando erros de validação Pydantic no formato RFC 9457 com `invalidParams`)
    - Handler para `HTTPException` nativo
    - Todos retornando JSONResponse com `media_type="application/problem+json"`
- [x] **4.2. Segurança, Criptografia e RBAC em `src/api/security.py`:**
  - Instância de hashing `CryptContext(schemes=["bcrypt"], deprecated="auto")`
  - Funções `verify_password(plain, hashed)` e `hash_password(plain)`
  - Configurações JWT: `SECRET_KEY`, `ALGORITHM = "HS256"`, `ACCESS_TOKEN_EXPIRE_MINUTES = 60`
  - Função `create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str`
  - Dependência `get_current_user(token: Annotated[str, Depends(HTTPBearer())], db: Session) -> FuncionarioModel`:
    - Validação de decodificação JWT
    - Lançamento de `UnauthorizedException` (401 RFC 9457) se token inválido, expirado ou usuário inexistente
  - Fábrica de dependência `require_roles(allowed_roles: list[str])`:
    - Retorna `ForbiddenException` (403 RFC 9457) se `current_user.role` não constar em `allowed_roles`

---

### Fase 5: Implementação dos Routers HTTP e `main.py`
*Arquivos de destino:* `src/api/routers/*.py` e `src/api/main.py`

- [ ] **5.1. Router de Autenticação (`src/api/routers/auth.py`):**
  - `POST /api/v1/auth/login`:
    - Busca funcionário por `email`
    - Valida senha com `verify_password` (lança `UnauthorizedException` se inválida)
    - Gera token JWT contendo `sub` (id), `email` e `role`
    - Retorna `TokenResponseDTO` (status 200 OK)
- [ ] **5.2. Router de Acervo (`src/api/routers/livros.py`):**
  - Prefixo `/api/v1/lib/acervo`, tags `["livros"]`
  - `GET /`: Consulta paginada pública (suporta query params `page`, `limit`, `search`, `categoria`, `status`, `exemplar`, `titulo`)
  - `GET /{livro-id}`: Consulta por ID (retorna 404 se inexistente)
  - `POST /`: Autenticado (qualquer funcionário); valida unicidade de `ISBN` (lança 409 se duplicado); retorna 201 Created
  - `PATCH /{livro-id}`: Autenticado; atualiza campos parciais; retorna 200 OK
  - `DELETE /{livro-id}`: **Exclusivo `ADMIN`** via `Depends(require_roles(["ADMIN"]))`; lança 403 se Bibliotecário; retorna 204 No Content
- [ ] **5.3. Router de Empréstimos (`src/api/routers/emprestimos.py`):**
  - Prefixo `/api/v1/lib/emprestimos`, tags `["emprestimos"]`
  - Autenticação obrigatória em todas as operações
  - `GET /`: Listagem paginada com `selectinload` em `livro`, `usuario` e `funcionario`
  - `GET /{emprestimo-id}`: Seleção por ID (retorna 404 se inexistente)
  - `POST /`: Criação de empréstimo com validações críticas de negócio:
    - Valida existência de `livro_id` e `usuario_id` (lança 422 se inexistentes)
    - Conflito 409: Rejeita se o livro tiver `exemplar == True`
    - Conflito 409: Rejeita se o livro estiver com status `"Emprestado"`
    - Conflito 409: Rejeita se o usuário estiver com `limite_disp <= 0`
    - Ao criar: subtrai 1 de `usuario.limite_disp` e soma 1 em `livro.qtd_emprestimos`
    - Retorna 201 Created
  - `PATCH /{emprestimo-id}`: Atualização de status:
    - Se status alterado para `"Devolvido"`, preenche `dt_devolucao = datetime.utcnow()` e restaura `usuario.limite_disp += 1`
    - Retorna 200 OK
  - `DELETE /{emprestimo-id}`: Remoção com liberação e retorno 204 No Content
- [ ] **5.4. Router de Usuários/Leitores (`src/api/routers/usuarios.py`):**
  - Prefixo `/api/v1/lib/users/usuarios`, tags `["usuarios"]`
  - Autenticação obrigatória (qualquer funcionário)
  - `GET /`: Listagem paginada
  - `GET /{usuario-id}`: Seleção por ID (retorna 404 se inexistente)
  - `POST /`: Cadastro de leitor; valida unicidade de `CPF` (lança 409 se duplicado); inicializa `limite_disp = 4`; retorna 201 Created
  - `PATCH /{usuario-id}`: Atualização cadastral; retorna 200 OK
  - `DELETE /{usuario-id}`: Exclusão com retorno 204 No Content
- [ ] **5.5. Router de Funcionários (`src/api/routers/funcionarios.py`):**
  - Prefixo `/api/v1/lib/users/funcionarios`, tags `["funcionarios"]`
  - **Acesso exclusivo `ADMIN`** em todos os endpoints (`Depends(require_roles(["ADMIN"]))`)
  - `GET /`: Listagem de funcionários (bloqueia Bibliotecário com 403)
  - `GET /{funcionario-id}`: Seleção de funcionário por ID
  - `POST /`: Cadastro RESTful (`POST /api/v1/lib/users/funcionarios`); valida unicidade de `CPF` e `email` (lança 409 se duplicado); gera `password_hash`; retorna 201 Created com header `Location`
  - `PATCH /{funcionario-id}`: Atualização de dados funcionais e salariais (mínimo 1621.0)
  - `DELETE /{funcionario-id}`: Exclusão de funcionário; retorna 204 No Content
- [ ] **5.6. Ponto de Entrada Principal (`src/api/main.py`):**
  - Instância FastAPI com lifespan assíncrono para execução do `init_db()`
  - Configuração de middleware CORS (origens liberadas para desenvolvimento)
  - Registro de handlers globais RFC 9457 de `src/api/exceptions.py`
  - Inclusão dos 5 routers com prefixos corretos

---

### Fase 6: Suíte Completa de Testes de Contrato, ORM e RBAC
*Arquivos de destino:* `src/api/tests/*.py`

- [ ] **6.1. Fixtures e Isolamento em `src/api/tests/conftest.py`:**
  - Criação de engine SQLite isolada (`sqlite:///:memory:` ou arquivo temporário por sessão de teste)
  - Fixture `db_session` com rollback/recreation por teste
  - Override de dependência `app.dependency_overrides[get_db] = override_get_db`
  - Fixture `client(TestClient)`
  - Fixture de seed inicial para os testes (Admin ID 1, Bibliotecário ID 2, Livro ID 1, Usuário ID 7)
  - Fixtures auxiliares de autenticação: `admin_headers` (Bearer token JWT de ADMIN) e `biblio_headers` (Bearer token JWT de BIBLIOTECARIO)
- [ ] **6.2. Testes de Autenticação e RBAC (`src/api/tests/test_auth.py`):**
  - Teste de login bem-sucedido com ADMIN (`Admin@2026`) gerando token JWT válido
  - Teste de login com senha incorreta retornando HTTP 401 RFC 9457
  - Teste de login com e-mail inexistente retornando HTTP 401 RFC 9457
  - Teste de rota protegida sem header Authorization retornando HTTP 401 RFC 9457
  - Teste de rota protegida com token malformado ou expirado retornando HTTP 401 RFC 9457
- [ ] **6.3. Testes do Acervo de Livros (`src/api/tests/test_livros.py`):**
  - Teste de listagem pública `GET /api/v1/lib/acervo` sem token retornando HTTP 200
  - Teste de criação de livro autenticado retornando HTTP 201 Created
  - Teste de conflito 409 ao tentar cadastrar livro com ISBN já existente
  - Teste de consulta por ID existente (HTTP 200) e ID 9999 (HTTP 404 RFC 9457)
  - Teste de atualização parcial `PATCH` (HTTP 200)
  - **Teste Crítico de RBAC:** Tentativa de `DELETE` por Bibliotecário retornando estritamente HTTP 403 Forbidden
  - **Teste de Sucesso:** `DELETE` executado por ADMIN retornando HTTP 204 No Content e verificando exclusão
- [ ] **6.4. Testes de Regras de Negócio de Empréstimos (`src/api/tests/test_emprestimos.py`):**
  - Teste de criação de empréstimo bem-sucedido (201 Created) verificando decremento de `limite_disp` do usuário e incremento de `qtd_emprestimos` do livro
  - Teste de conflito 409 ao tentar emprestar livro marcado com `exemplar = True`
  - Teste de conflito 409 ao tentar emprestar livro já atualmente emprestado
  - Teste de conflito 409 quando o usuário atingiu limite de livros (`limite_disp == 0`)
  - Teste de devolução via `PATCH`: status `"Devolvido"` preenche `dt_devolucao` e restaura `limite_disp` do leitor (+1)
  - Teste de `DELETE` do empréstimo retornando HTTP 204 No Content
  - Teste de busca por empréstimo com ID 9999 retornando HTTP 404 RFC 9457
- [ ] **6.5. Testes de Gestão de Funcionários (`src/api/tests/test_funcionarios.py`):**
  - **Teste Crítico de RBAC:** Bibliotecário tentando acessar `GET /api/v1/lib/users/funcionarios` recebe HTTP 403 Forbidden
  - ADMIN acessando a lista de funcionários recebe HTTP 200 OK
  - ADMIN cadastrando funcionário via `POST /api/v1/lib/users/funcionarios` com sucesso (201 Created)
  - Teste de conflito 409 em tentativa de duplicidade de CPF ou e-mail de funcionário
  - Validação de salário mínimo (tentativa com valor < 1621.0 retorna HTTP 422 RFC 9457)
  - ADMIN executando `DELETE` de funcionário retornando HTTP 204 No Content
- [ ] **6.6. Testes de Gestão de Usuários/Leitores (`src/api/tests/test_usuarios.py`):**
  - Criação de leitor com sucesso (201 Created) com `limite_disp` padrão inicializado em 4
  - Conflito 409 ao tentar cadastrar leitor com CPF duplicado
  - Validação 422 ao tentar cadastrar leitor sem nome ou com CPF em formato incorreto
  - Atualização cadastral via `PATCH` (200 OK)
  - Consulta de leitor inexistente retornando 404 RFC 9457
  - Exclusão via `DELETE` retornando 204 No Content
- [ ] **6.7. Testes de Conformidade Global RFC 9457 (`src/api/tests/test_errors.py`):**
  - Validação de schema de erro em 400 (parâmetros de query inválidos)
  - Validação de schema de erro em 401 (ausência de token)
  - Validação de schema de erro em 403 (falta de permissão de role)
  - Validação de schema de erro em 404 (recursos inexistentes)
  - Validação de schema de erro em 409 (conflitos de chave única e regras de acervo)
  - Validação de schema de erro em 422 (body malformado ou campos obrigatórios faltantes, com lista `invalidParams`)
  - Garantia de que o cabeçalho `Content-Type` de erro é estritamente `application/problem+json` em 100% dos casos
- [ ] **6.8. Execução e Homologação Final:**
  - Execução de `pytest -v` no terminal garantindo 100% de testes aprovados sem falhas
