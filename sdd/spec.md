# SPEC.md — Especificação de Negócio, ORM e Autenticação (Projeto Alexandria API)

## 1. Visão Geral e Fonte da Verdade do Contrato
Este projeto implementa a **Alexandria API**, uma API RESTful para o gerenciamento ágil do acervo de uma biblioteca, controle de leitores, funcionários e processos de empréstimo. O sistema possui **persistência relacional via ORM (SQLAlchemy 2.0)** e **controle de acesso Stateless via JWT e RBAC**.
O contrato base de rotas, parâmetros, cabeçalhos e JSON Schemas das entidades de domínio está estritamente definido no arquivo `Alexandria.Apidog.json`.

---

## 2. Prioridade Arquitetural: Extração de Tipos (Schema-First)
O sistema DEVE extrair e consolidar todas as tipagens estáticas (modelos Pydantic v2 em `src/api/schemas.py`) a partir dos `Data Schemas` do Apidog e dos requisitos de Autenticação **antes** de implementar os modelos ORM ou rotas HTTP. Devido ao uso de chaves em `kebab-case` no JSON (ex: `livro-id`), todos os schemas devem utilizar `Field(alias="...")` e `ConfigDict(populate_by_name=True)`.

1. **Enums de Domínio e Segurança:**
   - `CategoriaLivro`: `"Aventura"`, `"Terror"`, `"Romance"`, `"Fantasia"`, `"Ficção Científica"`, `"Suspense"`, `"Estudantil"`
   - `StatusLivro`: `"Novo"`, `"Conservado"`, `"Regular"`, `"Danificado"`
   - `StatusEmprestimo`: `"Emprestado"`, `"Devolvido"`, `"Vencido"`
   - `FuncionarioRole`: `"ADMIN"`, `"BIBLIOTECARIO"`
2. **Modelos de Autenticação (Auth):**
   - `LoginRequestDTO`: `email` (str, formato email), `password` (str, min 6 caracteres).
   - `AuthResponse`: `id` (int), `nome` (str), `email` (str), `role` (`FuncionarioRole`).
   - `TokenResponseDTO`: `accessToken` (str JWT), `tokenType` (str, default `"bearer"`), `expiresIn` (int), `user` (`AuthResponse`).
3. **Modelos de Acervo (Livros):**
   - `Livro`: `livro_id` (int, alias `livro-id`), `ISBN` (str, regex), `titulo` (str, 1-200), `autor` (str), `num_paginas` (int, alias `num-paginas`), `editora` (str), `publicacao` (int), `categoria` (`CategoriaLivro`), `qtd_emprestimos` (int, default 0, alias `qtd-emprestimos`), `dt_cadastro` (datetime, alias `dt-cadastro`), `status` (`StatusLivro`), `exemplar` (bool).
   - `CreateLivroDTO`: Omitir `livro-id` e `qtd-emprestimos`.
   - `UpdateLivroDTO`: Campos opcionais (não pode atualizar `ISBN`, `livro-id`, `dt-cadastro`, `exemplar`).
   - `LivroListResponse` & `Meta`: envelope `{ "data": [...], "meta": { "page", "limit", "totalItems", "totalPages", "hasNext" } }`.
4. **Modelos de Usuários (Leitores):**
   - `Usuario`: `usuario_id` (int, alias `usuario-id`), `CPF` (str, regex `000.000.000-00`), `nome` (str), `email` (str), `telefone` (str, regex `(00)00000-0000`), `dt_nascimento` (date, alias `dt-nascimento`), `CEP` (str), `limite_disp` (int 0-4, alias `limite-disp`), `dt_cadastro` (datetime, alias `dt-cadastro`).
   - `CreateUsuarioDTO`: Omitir `usuario-id`, `limite-disp`, `dt-cadastro`.
5. **Modelos de Funcionários (Equipe):**
   - `Funcionario`: `funcionario_id` (int, alias `funcionario-id`), `matricula` (int), `CPF` (str), `nome` (str), `email` (str), `telefone` (str), `dt_nascimento` (date, alias `dt-nascimento`), `dt_admissao` (datetime, alias `dt-admissao`), `salario` (float, min 1621).
6. **Modelos de Empréstimos:**
   - `Emprestimo`: `emprestimo_id` (int, alias `emprestimo-id`), `livro_id` (int, alias `livro-id`), `usuario_id` (int, alias `usuario-id`), `funcionario_id` (int, alias `funcionario-id`), `status` (`StatusEmprestimo`), `dt_emprestimo` (datetime, alias `dt-emprestimo`), `dt_vencimento` (datetime, alias `dt-vencimento`), `dt_devolucao` (datetime nullable, alias `dt-devolucao`).
7. **Modelos de Erro (RFC 9457):**
   - `InvalidParam`: `name` (str), `reason` (str).
   - `ApiError`: `type` (URI str, ex: `https://api.alexandria.dev/errors/validation-error`), `title` (str), `status` (int), `detail` (str), `instance` (str), `invalidParams` (lista opcional).

---

## 3. Mapeamento Objeto-Relacional — ORM (SQLAlchemy 2.0)
A camada de persistência (`src/api/models.py`) mapeia as 4 entidades para o SQLite usando IDs numéricos autoincrementais (Integer PK):

1. **Tabela `funcionarios` (`FuncionarioModel`):**
   - Campos de domínio: `id` (Integer PK), `matricula`, `cpf`, `nome`, `email` (Unique), `telefone`, `dt_nascimento`, `dt_admissao`, `salario`.
   - **Campos de Auth (Ocultos no Contrato):** `password_hash` (String(255)), `role` (String(20): `"ADMIN"` ou `"BIBLIOTECARIO"`).
2. **Tabela `usuarios` (`UsuarioModel`):**
   - Campos: `id` (Integer PK), `cpf` (Unique), `nome`, `email`, `telefone`, `dt_nascimento`, `cep`, `limite_disp` (Integer, default 4), `dt_cadastro`.
   - Relacionamento: `emprestimos: Mapped[list["EmprestimoModel"]] = relationship(back_populates="usuario")`.
3. **Tabela `livros` (`LivroModel`):**
   - Campos: `id` (Integer PK), `isbn` (Unique), `titulo`, `autor`, `num_paginas`, `editora`, `publicacao`, `categoria`, `qtd_emprestimos` (Integer, default 0), `dt_cadastro`, `status`, `exemplar` (Boolean).
   - Relacionamento: `emprestimos: Mapped[list["EmprestimoModel"]] = relationship(back_populates="livro")`.
4. **Tabela `emprestimos` (`EmprestimoModel`):**
   - Campos: `id` (Integer PK), `livro_id` (`ForeignKey("livros.id")`), `usuario_id` (`ForeignKey("usuarios.id")`), `funcionario_id` (`ForeignKey("funcionarios.id")`), `status`, `dt_emprestimo`, `dt_vencimento`, `dt_devolucao`.
   - Prevenção N+1: Nas consultas, use `joinedload` ou `selectinload` para os relacionamentos `livro`, `usuario` e `funcionario`.

---

## 4. Autenticação JWT, Autorização RBAC e Regras dos Endpoints

### 4.1. Coleção Autenticação (`/api/v1/auth`)
- **`POST /api/v1/auth/login`**:
  - Valida `email` e `password` contra a tabela `funcionarios`.
  - Retorna `200 OK` com JWT (`HS256`, expiração padrão) contendo `sub` (funcionario-id), `email` e `role`.
  - Retorna `401 Unauthorized` (`ApiError`) para credenciais inválidas.

### 4.2. Matriz de Controle de Acesso (RBAC) nas Rotas de Domínio
| Coleção / Endpoint | Permissão Exigida | Comportamento de Segurança |
| :--- | :--- | :--- |
| `GET /api/v1/lib/acervo` | Público (Livre) | Permite consulta ao acervo por qualquer pessoa. |
| `POST /api/v1/lib/acervo`, `PATCH /api/v1/lib/acervo/{id}` | Autenticado (qualquer role) | Exige cabeçalho `Authorization: Bearer <token>`. Retorna 401 se falhar. |
| **`DELETE /api/v1/lib/acervo/{id}`** | **Exclusivo `ADMIN`** | Retorna `403 Forbidden` (`ApiError`) se o funcionário for apenas `BIBLIOTECARIO`. |
| `GET / POST / PATCH / DELETE /api/v1/lib/emprestimos` | Autenticado (qualquer role) | Apenas funcionários gerenciam empréstimos. |
| `GET / POST / PATCH / DELETE /api/v1/lib/users/usuarios` | Autenticado (qualquer role) | Apenas funcionários gerenciam os leitores. |
| `GET / POST / PATCH / DELETE /api/v1/lib/users/funcionarios`| **Exclusivo `ADMIN`** | Apenas um Admin pode listar, cadastrar ou gerenciar outros funcionários da equipe. Retorna `403 Forbidden` para bibliotecários. |

### 4.3. Regras de Negócio e Conflitos (HTTP 409 / 422)
- **Criação de Empréstimo (`POST /api/v1/lib/emprestimos`)**:
  - Retorna `422 Unprocessable Entity` se o `livro-id` ou `usuario-id` não existirem no banco.
  - Retorna `409 Conflict` se o livro solicitado possuir a flag `exemplar = true` (não sai da biblioteca) ou se estiver com outro empréstimo ativo.
  - Regra: Ao aprovar, **subtrai 1** do `limite_disp` do Usuário e **soma 1** no `qtd_emprestimos` do Livro.
- **Devolução (`PATCH /api/v1/lib/emprestimos/{id}`)**:
  - Ao alterar o status para `"Devolvido"`, a `dt-devolucao` deve ser registrada e o `limite_disp` do Usuário deve ser **restaurado (+1)**.
- **Unicidade (`409 Conflict`)**:
  - `POST` em Livros não pode ter `ISBN` duplicado.
  - `POST` em Usuários não pode ter `CPF` duplicado.
  - `POST` em Funcionários não pode ter `CPF` ou `email` duplicados.

### 4.4. Seed Inicial do Banco de Dados
A função `init_db()` deve inserir de forma idempotente para testabilidade:
1. **Funcionários Base:**
   - **ID 1 (Mock Apidog):** `nome: "João Souza"`, `CPF: "987.654.321-00"`, `email: "joao.souza@biblioteca.com"`, `password: "Admin@2026"`, `role: "ADMIN"`, `matricula: 20260`.
   - **ID 2 (Mock Apidog):** `nome: "Ana Lima"`, `CPF: "321.654.987-11"`, `email: "ana.lima@biblioteca.com"`, `password: "Biblio@2026"`, `role: "BIBLIOTECARIO"`, `matricula: 20261`.
2. **Livro Base:**
   - **ID 1 (Mock Apidog):** `ISBN: "978-85-12345-67-8"`, `titulo: "O Hobbit"`, `categoria: "Fantasia"`.
3. **Usuário Base:**
   - **ID 7 (Mock Apidog):** `CPF: "123.456.789-09"`, `nome: "Maria Silva"`, `email: "maria.silva@email.com"`, `limite_disp: 3`.
4. **Id de Expectation 404:** O ID `9999` NUNCA deve existir em nenhuma tabela (reservado para testes de `404 Not Found`).