# 📋 Folha de Cola de Prompts: Aula Prática SDD + ORM + Autenticação + Oficina P2

Use esta folha de referência rápida durante a aula para executar os prompts no **Google Antigravity** (tanto na demonstração integrada de **SDD + ORM + Auth** quanto na **Auditoria da Especificação da P2** dos grupos).

---

## 🔎 PARTE 1: Prompt para os Grupos Auditarem a Especificação da P2 (Apidog)

> **Como usar com os alunos:** Cada grupo (2 a 4 membros) exporta o arquivo `.Apidog.json` (ou OpenAPI `.json`) do seu projeto da P2 para a pasta de trabalho e executa o prompt abaixo para descobrir falhas antes de entregar o link no Teams!

### Prompt 0 — Auditoria da Entrega de 30% da P2 (`[Spec Auditor]`)
```text
Atuando como [Spec Auditor], inspecione o arquivo de especificação do Apidog do nosso projeto e avalie rigorosamente se ele cumpre os 5 critérios da entrega da P2 (peso 30%):

1. README / Documentação Inicial: Existe descrição clara do propósito da API e identificação da equipe (2 a 4 integrantes)?
2. Entidades e CRUD: Existem pelo menos 2 entidades de domínio com todas as 5 operações do CRUD (GET lista, POST criação, GET por id, PUT/PATCH atualização e DELETE remoção) e Status Codes semânticos?
3. Schemas Desacoplados (DRY): Os payloads de Request e Response estão referenciando componentes da seção Data Schemas ($ref) ou foram criados inline dentro das rotas?
4. Riqueza dos Schemas: Verifique atributo por atributo nos Data Schemas se possuem description, format (uuid, date-time, email, etc.), limites (minLength, maxLength, minimum, maximum), obrigatoriedade (required), enum, example e regras de Mock (@guid, @ctitle, etc.).

Gere uma tabela de diagnóstico com a nota estimada de 0 a 10 e uma lista exata do que precisamos corrigir no Apidog antes de gerar o link do Compartilhamento Rápido.
```

---

## 🏗️ PARTE 2: Construindo a API com ORM (Aula 09) e Auth JWT/RBAC (Aula 08) via SDD

> **Pré-condição:** Arquivos `STYLEGUIDE.md`, `AGENTS.md`, `SPEC.md` e `Alexandria.Apidog.json` presentes na raiz do workspace.

### Prompt 1 — Planejamento Arquitetural (`[Tech Lead]`)
```text
Atuando como [Tech Lead], leia o @SPEC.md, o @"Alexandria.Apidog.json" e nosso @STYLEGUIDE.md. Crie (ou atualize) o arquivo PLAN.md contendo um checklist sequencial e granular das tarefas técnicas necessárias para implementar a Alexandria API com SQLAlchemy 2.0 ORM e Autenticação JWT/RBAC.

Não escreva código Python ainda! Apenas detalhe as 6 fases:
- Fase 1: Estrutura de diretórios e requirements.txt
- Fase 2: Extração de schemas Pydantic v2 com kebab-case alias (Apidog + DTOs de Auth)
- Fase 3: Modelos ORM SQLAlchemy 2.0 (FuncionarioModel, UsuarioModel, LivroModel, EmprestimoModel) e database.py com seed
- Fase 4: Exceções RFC 9457 (400, 401, 403, 404, 409, 422) e security.py (JWT + RBAC)
- Fase 5: Routers (auth, livros, emprestimos, funcionarios, usuarios) e main.py
- Fase 6: Suíte completa de testes pytest (test_auth, test_livros, test_emprestimos, test_funcionarios, test_usuarios, test_errors)
```

---

### Prompt 2 — Execução das Fases 1 e 2: Estrutura + Tipagens Pydantic v2 (`[Backend Coder]`)
```text
Atuando como [Backend Coder], execute a Fase 1 e a Fase 2 descritas no @PLAN.md (criação da estrutura de pastas, src/api/requirements.txt e extração completa dos modelos Pydantic v2 em src/api/schemas.py, garantindo os alias_generator/Field alias para as chaves em kebab-case, incluindo os schemas do Apidog e os DTOs de autenticação AuthResponse, LoginRequestDTO e TokenResponseDTO).

Siga estritamente o @STYLEGUIDE.md e o @SPEC.md. Marque os itens concluídos como [x] no @PLAN.md e pare para nossa revisão.
```

---

### Prompt 3 — Execução da Fase 3: Mapeamento ORM SQLAlchemy 2.0 + Seed (`[Backend Coder]`)
```text
Os contratos em schemas.py foram revisados e aprovados! Agora, atuando como [Backend Coder], execute a Fase 3 do @PLAN.md:
1. Implemente src/api/models.py usando SQLAlchemy 2.0 (Mapped, mapped_column, relationship, ForeignKey) para FuncionarioModel, UsuarioModel, LivroModel e EmprestimoModel.
2. Implemente src/api/database.py com a engine SQLite, get_db() e a função de seed inicial de forma idempotente, garantindo a criação dos mocks baseados na doc do Apidog e dos funcionários ADMIN e BIBLIOTECARIO.

Marque a Fase 3 como [x] no @PLAN.md e aguarde nossa revisão.
```

---

### Prompt 4 — Execução da Fase 4: Segurança JWT/RBAC e Erros RFC 9457 (`[Backend Coder]`)
```text
Modelos ORM e banco revisados! Atuando como [Backend Coder], execute a Fase 4 do @PLAN.md:
1. Implemente src/api/exceptions.py garantindo respostas RFC 9457 (Problem Details) para 400, 401, 403, 404, 409 e 422.
2. Implemente src/api/security.py com geração/validação de JWT (HS256) e as dependências FastAPI get_current_user (retornando 401 RFC 9457 se ausente/inválido) e require_roles (retornando 403 RFC 9457 se o papel do usuário não tiver permissão, separando acesso de ADMIN e BIBLIOTECARIO).

Atualize o @PLAN.md ao concluir e pare para revisão.
```

---

### Prompt 5 — Execução da Fase 5: Routers HTTP e `main.py` (`[Backend Coder]`)
```text
Camada de segurança e exceções aprovadas! Atuando como [Backend Coder], execute a Fase 5 do @PLAN.md implementando:
1. src/api/routers/auth.py (POST /api/v1/auth/login)
2. src/api/routers/livros.py (/api/v1/lib/acervo), permitindo GET público e exigindo permissão no DELETE.
3. src/api/routers/usuarios.py e src/api/routers/funcionarios.py (sendo funcionarios de acesso exclusivo ADMIN).
4. src/api/routers/emprestimos.py (/api/v1/lib/emprestimos), com as lógicas de negócio e conflitos de limite_disp (HTTP 409).
5. src/api/main.py (configurando lifespan para inicializar o banco e seed, CORS e middlewares).

Atualize os checkboxes da Fase 5 no @PLAN.md ao finalizar.
```

---

### Prompt 6 — Execução da Fase 6: Suíte de Testes de Contrato, ORM e RBAC (`[QA Engineer]`)
```text
Atuando como [QA Engineer], execute a Fase 6 do @PLAN.md:
1. Crie src/api/tests/conftest.py sobrescrevendo a dependência get_db para usar um banco SQLite isolado por teste e fornecendo fixtures com tokens JWT para ADMIN e BIBLIOTECARIO.
2. Crie os arquivos de teste: test_auth.py, test_livros.py, test_emprestimos.py, test_funcionarios.py, test_usuarios.py e test_errors.py testando todos os fluxos de contrato, regras de exclusividade de acesso (403 Forbidden para BIBLIOTECARIOs manipulando funcionários, por ex.), limite de itens, conflitos 409 (CPF duplicado) e relacionamentos ORM.
3. Execute o pytest no terminal para comprovar 100% de aprovação e marque todos os itens do @PLAN.md como concluídos!
```