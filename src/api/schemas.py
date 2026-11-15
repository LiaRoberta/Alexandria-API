"""schemas.py — Contratos Pydantic v2 da Alexandria API.

Define enums de domínio, DTOs de autenticação, schemas de dados do Apidog com
chaves em kebab-case (via alias), modelos de resposta envelopada e tratamento
padronizado de erros no padrão RFC 9457 (Problem Details).
"""

from datetime import date, datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


# -----------------------------------------------------------------------------
# Base Schema com configuração global Pydantic v2
# -----------------------------------------------------------------------------
class AlexandriaBaseSchema(BaseModel):
    """Modelo base para serialização bidirecional e compatibilidade ORM."""
    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True,
    )


# -----------------------------------------------------------------------------
# Enums de Domínio e Segurança
# -----------------------------------------------------------------------------
class CategoriaLivro(str, Enum):
    """Categorias literárias do acervo da biblioteca."""
    AVENTURA = "Aventura"
    TERROR = "Terror"
    ROMANCE = "Romance"
    FANTASIA = "Fantasia"
    FICCAO_CIENTIFICA = "Ficção Científica"
    SUSPENSE = "Suspense"
    ESTUDANTIL = "Estudantil"


class StatusLivro(str, Enum):
    """Estado de conservação física do livro."""
    NOVO = "Novo"
    CONSERVADO = "Conservado"
    REGULAR = "Regular"
    DANIFICADO = "Danificado"


class StatusEmprestimo(str, Enum):
    """Ciclo de vida e situação temporal do empréstimo."""
    EMPRESTADO = "Emprestado"
    DEVOLVIDO = "Devolvido"
    VENCIDO = "Vencido"


class FuncionarioRole(str, Enum):
    """Papéis hierárquicos para controle de acesso RBAC."""
    ADMIN = "ADMIN"
    BIBLIOTECARIO = "BIBLIOTECARIO"


# -----------------------------------------------------------------------------
# Schemas de Erro Padronizados (RFC 9457 — Problem Details)
# -----------------------------------------------------------------------------
class InvalidParam(AlexandriaBaseSchema):
    """Detalhe de violação de regra em parâmetro ou campo de entrada."""
    name: str = Field(..., description="Nome do campo ou parâmetro com falha")
    reason: str = Field(..., description="Motivo detalhado da rejeição")


class ApiError(AlexandriaBaseSchema):
    """Schema estruturado de erro HTTP em conformidade estrita com a RFC 9457."""
    type: str = Field(
        default="https://api.alexandria.dev/errors/validation-error",
        description="URI identificadora do tipo de erro",
    )
    title: str = Field(..., description="Resumo curto e legível do erro")
    status: int = Field(..., description="Código de status HTTP numérico")
    detail: str = Field(..., description="Explicação detalhada da falha ocorrida")
    instance: str = Field(..., description="URI da rota onde o erro se originou")
    invalid_params: Optional[list[InvalidParam]] = Field(
        default=None,
        alias="invalidParams",
        description="Lista de parâmetros com falhas de validação sintática ou de negócio",
    )


# -----------------------------------------------------------------------------
# Schemas de Autenticação e Segurança (Auth DTOs)
# -----------------------------------------------------------------------------
class LoginRequestDTO(AlexandriaBaseSchema):
    """Payload de autenticação para login de funcionários."""
    email: str = Field(
        ...,
        pattern=r"^[\w\.-]+@[\w\.-]+\.\w+$",
        description="Endereço de e-mail institucional corporativo",
        examples=["joao.souza@biblioteca.com"],
    )
    password: str = Field(
        ...,
        min_length=6,
        description="Senha de acesso (mínimo de 6 caracteres)",
        examples=["Admin@2026"],
    )


class AuthResponse(AlexandriaBaseSchema):
    """Dados cadastrais resumidos do funcionário autenticado."""
    id: int = Field(..., description="Identificador único do funcionário")
    nome: str = Field(..., description="Nome completo do funcionário")
    email: str = Field(..., description="E-mail corporativo do funcionário")
    role: FuncionarioRole = Field(..., description="Papel funcional do funcionário")


class TokenResponseDTO(AlexandriaBaseSchema):
    """Resposta com token de acesso JWT emitida após login bem-sucedido."""
    access_token: str = Field(
        ...,
        alias="accessToken",
        description="Token de autorização JWT codificado em HS256",
    )
    token_type: str = Field(
        default="bearer",
        alias="tokenType",
        description="Tipo do token (padrão Bearer)",
    )
    expires_in: int = Field(
        ...,
        alias="expiresIn",
        description="Tempo de vida do token em segundos",
    )
    user: AuthResponse = Field(..., description="Metadados do usuário autenticado")


# -----------------------------------------------------------------------------
# Metadados de Paginação
# -----------------------------------------------------------------------------
class PageMeta(AlexandriaBaseSchema):
    """Metadados de controle de paginação de listas de recursos."""
    page: int = Field(..., ge=1, description="Página atual consultada")
    limit: int = Field(..., ge=1, le=100, description="Quantidade de registros por página")
    total_items: int = Field(..., ge=0, alias="totalItems", description="Total geral de registros")
    total_pages: int = Field(..., ge=0, alias="totalPages", description="Total de páginas existentes")
    has_next: bool = Field(..., alias="hasNext", description="Indica se existe próxima página")


# -----------------------------------------------------------------------------
# Entidade Acervo: Livros
# -----------------------------------------------------------------------------
class Livro(AlexandriaBaseSchema):
    """Entidade completa de livro cadastrado no acervo."""
    livro_id: int = Field(
        ...,
        alias="livro-id",
        ge=1,
        le=9999,
        description="Identificador único do livro",
    )
    ISBN: str = Field(
        ...,
        pattern=r"^[0-9]{3}-[0-9]{2}-[0-9]{5}-[0-9]{2}-[0-9]{1}$",
        description="Número de ISBN formatado com hífens",
    )
    titulo: str = Field(..., min_length=1, max_length=200, description="Título do livro")
    autor: Optional[str] = Field(default=None, min_length=2, max_length=100, description="Autor do livro")
    num_paginas: Optional[int] = Field(
        default=None,
        alias="num-paginas",
        ge=1,
        le=5000,
        description="Número total de páginas",
    )
    editora: Optional[str] = Field(default=None, min_length=2, max_length=100, description="Editora da publicação")
    publicacao: Optional[int] = Field(default=None, ge=1500, le=2026, description="Ano de publicação")
    categoria: CategoriaLivro = Field(..., description="Categoria literária do livro")
    qtd_emprestimos: int = Field(
        default=0,
        alias="qtd-emprestimos",
        ge=0,
        description="Quantidade acumulada de empréstimos",
    )
    dt_cadastro: datetime = Field(..., alias="dt-cadastro", description="Data/hora UTC de cadastro")
    status: StatusLivro = Field(..., description="Estado de conservação do livro")
    exemplar: bool = Field(
        default=False,
        description="Indica se é exemplar de consulta local exclusiva",
    )


class CreateLivroDTO(AlexandriaBaseSchema):
    """Payload para cadastramento de um novo livro no acervo."""
    ISBN: str = Field(
        ...,
        pattern=r"^[0-9]{3}-[0-9]{2}-[0-9]{5}-[0-9]{2}-[0-9]{1}$",
        description="Número de ISBN formatado",
    )
    titulo: str = Field(..., min_length=1, max_length=200, description="Título do livro")
    autor: Optional[str] = Field(default=None, min_length=2, max_length=100)
    num_paginas: Optional[int] = Field(default=None, alias="num-paginas", ge=1, le=5000)
    editora: Optional[str] = Field(default=None, min_length=2, max_length=100)
    publicacao: Optional[int] = Field(default=None, ge=1500, le=2026)
    categoria: CategoriaLivro
    status: StatusLivro = StatusLivro.NOVO
    exemplar: bool = False


class UpdateLivroDTO(AlexandriaBaseSchema):
    """Payload para atualização parcial de dados de um livro."""
    titulo: Optional[str] = Field(default=None, min_length=1, max_length=200)
    autor: Optional[str] = Field(default=None, min_length=2, max_length=100)
    num_paginas: Optional[int] = Field(default=None, alias="num-paginas", ge=1, le=5000)
    editora: Optional[str] = Field(default=None, min_length=2, max_length=100)
    publicacao: Optional[int] = Field(default=None, ge=1500, le=2026)
    categoria: Optional[CategoriaLivro] = None
    status: Optional[StatusLivro] = None


class LivroListResponse(AlexandriaBaseSchema):
    """Resposta envelopada de listagem paginada de livros."""
    data: list[Livro] = Field(..., description="Lista de livros na página")
    meta: PageMeta = Field(..., description="Metadados de paginação")


# -----------------------------------------------------------------------------
# Entidade Usuários (Leitores)
# -----------------------------------------------------------------------------
class Usuario(AlexandriaBaseSchema):
    """Entidade completa de usuário leitor cadastrado."""
    usuario_id: int = Field(
        ...,
        alias="usuario-id",
        ge=1,
        le=9999,
        description="Identificador único do leitor",
    )
    CPF: str = Field(
        ...,
        pattern=r"^[0-9]{3}\.[0-9]{3}\.[0-9]{3}-[0-9]{2}$",
        description="CPF formatado",
    )
    nome: str = Field(..., min_length=3, max_length=120, description="Nome completo do leitor")
    email: str = Field(
        ...,
        pattern=r"^[\w\.-]+@[\w\.-]+\.\w+$",
        description="Endereço de e-mail do leitor",
    )
    telefone: Optional[str] = Field(
        default=None,
        pattern=r"^\([0-9]{2}\)[0-9]{4,5}-[0-9]{4}$",
        description="Telefone com DDD",
    )
    dt_nascimento: Optional[date] = Field(
        default=None,
        alias="dt-nascimento",
        description="Data de nascimento do leitor",
    )
    CEP: Optional[str] = Field(
        default=None,
        pattern=r"^[0-9]{5}-[0-9]{3}$",
        description="CEP com traço",
    )
    limite_disp: int = Field(
        default=4,
        alias="limite-disp",
        ge=0,
        le=4,
        description="Saldo disponível de empréstimos simultâneos",
    )
    dt_cadastro: datetime = Field(
        ...,
        alias="dt-cadastro",
        description="Data/hora UTC de efetivação do cadastro",
    )


class CreateUsuarioDTO(AlexandriaBaseSchema):
    """Payload para cadastramento de um novo usuário leitor."""
    CPF: str = Field(
        ...,
        pattern=r"^[0-9]{3}\.[0-9]{3}\.[0-9]{3}-[0-9]{2}$",
        description="CPF formatado com pontos e traço",
    )
    nome: str = Field(..., min_length=3, max_length=120, description="Nome completo")
    email: str = Field(
        ...,
        pattern=r"^[\w\.-]+@[\w\.-]+\.\w+$",
        description="E-mail de contato",
    )
    telefone: Optional[str] = Field(
        default=None,
        pattern=r"^\([0-9]{2}\)[0-9]{4,5}-[0-9]{4}$",
    )
    dt_nascimento: Optional[date] = Field(default=None, alias="dt-nascimento")
    CEP: Optional[str] = Field(default=None, pattern=r"^[0-9]{5}-[0-9]{3}$")


class UpdateUsuarioDTO(AlexandriaBaseSchema):
    """Payload para atualização de dados cadastrais de leitor."""
    nome: Optional[str] = Field(default=None, min_length=3, max_length=120)
    email: Optional[str] = Field(
        default=None,
        pattern=r"^[\w\.-]+@[\w\.-]+\.\w+$",
    )
    telefone: Optional[str] = Field(
        default=None,
        pattern=r"^\([0-9]{2}\)[0-9]{4,5}-[0-9]{4}$",
    )
    dt_nascimento: Optional[date] = Field(default=None, alias="dt-nascimento")
    CEP: Optional[str] = Field(default=None, pattern=r"^[0-9]{5}-[0-9]{3}$")
    limite_disp: Optional[int] = Field(default=None, alias="limite-disp", ge=0, le=4)


class UsuarioListResponse(AlexandriaBaseSchema):
    """Resposta envelopada de listagem paginada de leitores."""
    data: list[Usuario] = Field(..., description="Lista de usuários na página")
    meta: PageMeta = Field(..., description="Metadados de paginação")


# -----------------------------------------------------------------------------
# Entidade Funcionários (Equipe Administrativa)
# -----------------------------------------------------------------------------
class Funcionario(AlexandriaBaseSchema):
    """Entidade completa de funcionário da equipe."""
    funcionario_id: int = Field(
        ...,
        alias="funcionario-id",
        ge=1,
        le=9999,
        description="Identificador único do funcionário",
    )
    matricula: int = Field(..., ge=1, le=99999, description="Matrícula funcional")
    CPF: str = Field(
        ...,
        pattern=r"^[0-9]{3}\.[0-9]{3}\.[0-9]{3}-[0-9]{2}$",
        description="CPF do funcionário",
    )
    nome: str = Field(..., min_length=3, max_length=120, description="Nome completo")
    email: str = Field(
        ...,
        pattern=r"^[\w\.-]+@[\w\.-]+\.\w+$",
        description="E-mail corporativo institucional",
    )
    telefone: Optional[str] = Field(
        default=None,
        pattern=r"^\([0-9]{2}\)[0-9]{4,5}-[0-9]{4}$",
    )
    dt_nascimento: date = Field(..., alias="dt-nascimento", description="Data de nascimento")
    dt_admissao: datetime = Field(..., alias="dt-admissao", description="Data/hora UTC de admissão")
    salario: float = Field(..., ge=1621.0, description="Salário bruto mensal em reais")


class CreateFuncionarioDTO(AlexandriaBaseSchema):
    """Payload para cadastramento de um novo funcionário."""
    matricula: int = Field(..., ge=1, le=99999, description="Matrícula única")
    CPF: str = Field(
        ...,
        pattern=r"^[0-9]{3}\.[0-9]{3}\.[0-9]{3}-[0-9]{2}$",
        description="CPF formatado",
    )
    nome: str = Field(..., min_length=3, max_length=120, description="Nome completo")
    email: str = Field(
        ...,
        pattern=r"^[\w\.-]+@[\w\.-]+\.\w+$",
        description="E-mail institucional",
    )
    telefone: Optional[str] = Field(
        default=None,
        pattern=r"^\([0-9]{2}\)[0-9]{4,5}-[0-9]{4}$",
    )
    dt_nascimento: date = Field(..., alias="dt-nascimento", description="Data de nascimento")
    dt_admissao: Optional[datetime] = Field(
        default=None,
        alias="dt-admissao",
        description="Data de admissão (padrão agora)",
    )
    salario: float = Field(..., ge=1621.0, description="Salário bruto (mínimo de R$ 1.621,00)")
    password: str = Field(..., min_length=6, description="Senha inicial de acesso do funcionário")
    role: FuncionarioRole = Field(
        default=FuncionarioRole.BIBLIOTECARIO,
        description="Papel funcional no sistema (ADMIN ou BIBLIOTECARIO)",
    )


class UpdateFuncionarioDTO(AlexandriaBaseSchema):
    """Payload para atualização de dados cadastrais de funcionário."""
    nome: Optional[str] = Field(default=None, min_length=3, max_length=120)
    email: Optional[str] = Field(
        default=None,
        pattern=r"^[\w\.-]+@[\w\.-]+\.\w+$",
    )
    telefone: Optional[str] = Field(
        default=None,
        pattern=r"^\([0-9]{2}\)[0-9]{4,5}-[0-9]{4}$",
    )
    salario: Optional[float] = Field(default=None, ge=1621.0)


class FuncionarioListResponse(AlexandriaBaseSchema):
    """Resposta envelopada de listagem paginada de funcionários."""
    data: list[Funcionario] = Field(..., description="Lista de funcionários na página")
    meta: PageMeta = Field(..., description="Metadados de paginação")


# -----------------------------------------------------------------------------
# Entidade Transacional: Empréstimos
# -----------------------------------------------------------------------------
class Emprestimo(AlexandriaBaseSchema):
    """Entidade completa de empréstimo de livro."""
    emprestimo_id: int = Field(
        ...,
        alias="emprestimo-id",
        ge=1,
        le=9999,
        description="Identificador único do empréstimo",
    )
    livro_id: int = Field(
        ...,
        alias="livro-id",
        ge=1,
        le=9999,
        description="ID do livro emprestado",
    )
    usuario_id: int = Field(
        ...,
        alias="usuario-id",
        ge=1,
        le=9999,
        description="ID do usuário leitor",
    )
    funcionario_id: int = Field(
        ...,
        alias="funcionario-id",
        ge=1,
        le=9999,
        description="ID do funcionário responsável pela operação",
    )
    status: StatusEmprestimo = Field(..., description="Situação atual do empréstimo")
    dt_emprestimo: datetime = Field(
        ...,
        alias="dt-emprestimo",
        description="Data e hora UTC de retirada do livro",
    )
    dt_vencimento: datetime = Field(
        ...,
        alias="dt-vencimento",
        description="Data e hora UTC limite de devolução",
    )
    dt_devolucao: Optional[datetime] = Field(
        default=None,
        alias="dt-devolucao",
        description="Data e hora UTC em que o livro foi devolvido",
    )


class CreateEmprestimoDTO(AlexandriaBaseSchema):
    """Payload para registro de um novo empréstimo."""
    livro_id: int = Field(..., alias="livro-id", ge=1, le=9999)
    usuario_id: int = Field(..., alias="usuario-id", ge=1, le=9999)
    funcionario_id: int = Field(..., alias="funcionario-id", ge=1, le=9999)
    dt_vencimento: datetime = Field(..., alias="dt-vencimento")


class UpdateEmprestimoDTO(AlexandriaBaseSchema):
    """Payload para atualização de status de empréstimo (devolução)."""
    status: StatusEmprestimo
    dt_devolucao: Optional[datetime] = Field(default=None, alias="dt-devolucao")


class EmprestimoListResponse(AlexandriaBaseSchema):
    """Resposta envelopada de listagem paginada de empréstimos."""
    data: list[Emprestimo] = Field(..., description="Lista de empréstimos na página")
    meta: PageMeta = Field(..., description="Metadados de paginação")
