"""
Módulo de Schemas e DTOs Pydantic v2 para a Alexandria API v2.

Define os contratos de dados estáticos para validação, serialização e documentação
da API, espelhando fielmente o contrato Alexandria.Apidog.json e incorporando
os DTOs de autenticação JWT/RBAC e tratamento de erros RFC 9457 conforme o STYLEGUIDE.md.
"""

from datetime import date, datetime
from enum import Enum
from typing import Optional
from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
)


# ==============================================================================
# ENUMS TIPADOS
# ==============================================================================

class CategoriaLivroEnum(str, Enum):
    """Categorias literárias aceitas no acervo da biblioteca."""
    AVENTURA = "Aventura"
    TERROR = "Terror"
    ROMANCE = "Romance"
    FANTASIA = "Fantasia"
    FICCAO_CIENTIFICA = "Ficção Científica"
    SUSPENSE = "Suspense"
    ESTUDANTIL = "Estudantil"


class StatusLivroEnum(str, Enum):
    """Estados físicos de conservação dos livros do acervo."""
    NOVO = "Novo"
    CONSERVADO = "Conservado"
    REGULAR = "Regular"
    DANIFICADO = "Danificado"


class StatusEmprestimoEnum(str, Enum):
    """Ciclo de vida e situação do empréstimo de um exemplar."""
    EMPRESTADO = "Emprestado"
    DEVOLVIDO = "Devolvido"
    VENCIDO = "Vencido"


class UserRoleEnum(str, Enum):
    """Papéis de controle de acesso baseado em função (RBAC)."""
    ADMIN = "ADMIN"
    MEMBER = "MEMBER"


# ==============================================================================
# SCHEMAS DE INFRAESTRUTURA & RFC 9457 (PROBLEM DETAILS)
# ==============================================================================

class PageMeta(BaseModel):
    """Metadados padronizados para respostas paginadas."""
    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

    page: int = Field(..., ge=1, description="Número da página consultada (iniciando em 1)")
    limit: int = Field(..., ge=1, description="Quantidade máxima de registros por página")
    total_items: int = Field(
        ...,
        ge=0,
        validation_alias=AliasChoices("totalItems", "total_items"),
        serialization_alias="totalItems",
        description="Quantidade total de registros encontrados"
    )
    total_pages: int = Field(
        ...,
        ge=0,
        validation_alias=AliasChoices("totalPages", "total_pages"),
        serialization_alias="totalPages",
        description="Quantidade total de páginas calculadas"
    )
    has_next: bool = Field(
        ...,
        validation_alias=AliasChoices("hasNext", "has_next"),
        serialization_alias="hasNext",
        description="Booleano indicando existência de páginas subsequentes"
    )


class InvalidParam(BaseModel):
    """Representação detalhada de falha de validação de campo conforme RFC 9457."""
    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

    name: str = Field(..., description="Nome do campo que falhou na validação")
    reason: str = Field(..., description="Descrição legível da inconsistência identificada")


class ApiError(BaseModel):
    """
    Especificação de erro padronizada conforme RFC 9457 / RFC 7807 (Problem Details).
    Substitui integralmente o formato padrão {'detail': '...'} do FastAPI.
    """
    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

    type: Optional[str] = Field(
        default=None,
        description="URI identificadora do tipo de erro no ecossistema da API"
    )
    title: str = Field(..., description="Resumo curto e legível do tipo de erro HTTP ocorrido")
    status: int = Field(..., description="Código numérico de status HTTP correspondente")
    detail: str = Field(..., description="Explicação detalhada e contextualizada sobre a ocorrência")
    instance: Optional[str] = Field(
        default=None,
        description="Caminho relativo da requisição onde o erro se originou"
    )
    invalid_params: Optional[list[InvalidParam]] = Field(
        default=None,
        validation_alias=AliasChoices("invalidParams", "invalid_params"),
        serialization_alias="invalidParams",
        description="Lista de violações paramétricas detalhadas (obrigatório em 400 e 422)"
    )


# ==============================================================================
# SCHEMAS DE LIVROS / ACERVO (CORRESPONDÊNCIA COM PROJECTS NO STYLEGUIDE)
# ==============================================================================

class LivroBase(BaseModel):
    """Campos fundamentais para representação de um livro no acervo."""
    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

    titulo: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Título completo da obra literária"
    )
    autor: Optional[str] = Field(
        default=None,
        description="Nome completo do autor ou autores"
    )
    editora: Optional[str] = Field(
        default=None,
        description="Nome da editora responsável pela publicação"
    )
    publicacao: Optional[int] = Field(
        default=None,
        ge=0,
        description="Ano de publicação da obra"
    )
    categoria: CategoriaLivroEnum = Field(
        ...,
        description="Categoria ou gênero literário da obra"
    )
    exemplar: bool = Field(
        default=False,
        description="Indica se é um exemplar restrito apenas a consulta local"
    )
    num_paginas: Optional[int] = Field(
        default=None,
        ge=1,
        validation_alias=AliasChoices("num-paginas", "numPaginas", "num_paginas"),
        serialization_alias="num-paginas",
        description="Número total de páginas do livro"
    )
    ISBN: str = Field(
        ...,
        pattern=r"^[0-9]{3}-[0-9]{2}-[0-9]{5}-[0-9]{2}-[0-9]{1}$",
        description="Código identificador ISBN no formato canônico 978-85-12345-67-8"
    )
    status: StatusLivroEnum = Field(
        ...,
        description="Condição física e estado de conservação do livro"
    )


class CreateLivro(LivroBase):
    """Contrato de entrada para cadastro de um novo livro no acervo."""
    pass


class UpdateLivro(BaseModel):
    """Contrato de entrada para atualização parcial (PATCH) de livro no acervo."""
    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

    titulo: Optional[str] = Field(default=None, min_length=1, max_length=200)
    autor: Optional[str] = None
    editora: Optional[str] = None
    publicacao: Optional[int] = Field(default=None, ge=0)
    categoria: Optional[CategoriaLivroEnum] = None
    num_paginas: Optional[int] = Field(
        default=None,
        ge=1,
        validation_alias=AliasChoices("num-paginas", "numPaginas", "num_paginas"),
        serialization_alias="num-paginas"
    )
    status: Optional[StatusLivroEnum] = None


class LivroResponse(LivroBase):
    """Contrato de saída completo de um livro cadastrado no acervo."""
    livro_id: int = Field(
        ...,
        ge=1,
        le=9999,
        validation_alias=AliasChoices("livro-id", "livroId", "livro_id", "id"),
        serialization_alias="livro-id",
        description="Identificador único primário do livro"
    )
    qtd_emprestimos: int = Field(
        default=0,
        ge=0,
        validation_alias=AliasChoices("qtd-emprestimos", "qtdEmprestimos", "qtd_emprestimos"),
        serialization_alias="qtd-emprestimos",
        description="Contador acumulado de empréstimos deste exemplar"
    )
    dt_cadastro: datetime = Field(
        ...,
        validation_alias=AliasChoices("dt-cadastro", "dtCadastro", "dt_cadastro"),
        serialization_alias="dt-cadastro",
        description="Data e hora de inclusão do registro no banco de dados"
    )


class LivroListResponse(BaseModel):
    """Contrato de saída para listagem paginada de livros do acervo."""
    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

    data: list[LivroResponse] = Field(..., description="Coleção de livros na página atual")
    meta: PageMeta = Field(..., description="Metadados de paginação")


# ==============================================================================
# SCHEMAS DE EMPRÉSTIMOS (CORRESPONDÊNCIA COM TASKS NO STYLEGUIDE - RELAÇÃO 1:N)
# ==============================================================================

class EmprestimoBase(BaseModel):
    """Campos fundamentais para registro de um empréstimo."""
    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

    livro_id: int = Field(
        ...,
        ge=1,
        le=9999,
        validation_alias=AliasChoices("livro-id", "livroId", "livro_id"),
        serialization_alias="livro-id",
        description="Chave estrangeira referenciando o exemplar do livro emprestado"
    )
    usuario_id: int = Field(
        ...,
        ge=1,
        le=9999,
        validation_alias=AliasChoices("usuario-id", "usuarioId", "usuario_id"),
        serialization_alias="usuario-id",
        description="Chave estrangeira referenciando o leitor que pegou o livro"
    )
    funcionario_id: int = Field(
        ...,
        ge=1,
        le=9999,
        validation_alias=AliasChoices("funcionario-id", "funcionarioId", "funcionario_id"),
        serialization_alias="funcionario-id",
        description="Chave estrangeira referenciando o funcionário que autorizou o empréstimo"
    )
    dt_vencimento: datetime = Field(
        ...,
        validation_alias=AliasChoices("dt-vencimento", "dtVencimento", "dt_vencimento"),
        serialization_alias="dt-vencimento",
        description="Data limite estipulada para a devolução do livro"
    )


class CreateEmprestimo(EmprestimoBase):
    """Contrato de entrada para realização de novo empréstimo."""
    pass


class UpdateEmprestimo(BaseModel):
    """Contrato de entrada para atualização parcial de empréstimo (devolução/status)."""
    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

    status: Optional[StatusEmprestimoEnum] = Field(
        default=None,
        description="Novo status do empréstimo (ex.: Devolvido ou Vencido)"
    )
    dt_devolucao: Optional[datetime] = Field(
        default=None,
        validation_alias=AliasChoices("dt-devolucao", "dtDevolucao", "dt_devolucao"),
        serialization_alias="dt-devolucao",
        description="Data e hora em que a devolução foi efetuada"
    )


class EmprestimoResponse(EmprestimoBase):
    """Contrato de saída completo de um empréstimo."""
    emprestimo_id: int = Field(
        ...,
        ge=1,
        le=9999,
        validation_alias=AliasChoices("emprestimo-id", "emprestimoId", "emprestimo_id", "id"),
        serialization_alias="emprestimo-id",
        description="Identificador único do empréstimo"
    )
    status: StatusEmprestimoEnum = Field(
        default=StatusEmprestimoEnum.EMPRESTADO,
        description="Situação atual do empréstimo"
    )
    dt_emprestimo: datetime = Field(
        ...,
        validation_alias=AliasChoices("dt-emprestimo", "dtEmprestimo", "dt_emprestimo"),
        serialization_alias="dt-emprestimo",
        description="Data e hora de realização do empréstimo"
    )
    dt_devolucao: Optional[datetime] = Field(
        default=None,
        validation_alias=AliasChoices("dt-devolucao", "dtDevolucao", "dt_devolucao"),
        serialization_alias="dt-devolucao",
        description="Data e hora da devolução efetiva, ou nulo se ainda ativo"
    )


class EmprestimoListResponse(BaseModel):
    """Contrato de saída para listagem paginada de empréstimos."""
    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

    data: list[EmprestimoResponse] = Field(..., description="Coleção de empréstimos na página")
    meta: PageMeta = Field(..., description="Metadados de paginação")


# ==============================================================================
# SCHEMAS DE FUNCIONÁRIOS (COLABORADORES)
# ==============================================================================

class FuncionarioBase(BaseModel):
    """Campos fundamentais para cadastro e representação de colaboradores."""
    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

    matricula: int = Field(..., ge=1, le=99999, description="Número de matrícula funcional")
    CPF: str = Field(
        ...,
        pattern=r"^[0-9]{3}\.[0-9]{3}\.[0-9]{3}-[0-9]{2}$",
        description="Cadastro de Pessoa Física formatado (000.000.000-00)"
    )
    nome: str = Field(..., min_length=3, max_length=120, description="Nome completo")
    email: Optional[EmailStr] = Field(default=None, description="Endereço de e-mail profissional")
    telefone: Optional[str] = Field(
        default=None,
        pattern=r"^\([0-9]{2}\)[0-9]{4,5}-[0-9]{4}$",
        description="Telefone de contato com DDD: (XX)XXXXX-XXXX"
    )
    dt_nascimento: date = Field(
        ...,
        validation_alias=AliasChoices("dt-nascimento", "dtNascimento", "dt_nascimento"),
        serialization_alias="dt-nascimento",
        description="Data de nascimento do funcionário"
    )
    salario: float = Field(
        ...,
        ge=1621.0,
        description="Remuneração salarial contratual (mínimo R$ 1621,00)"
    )


class CreateFuncionario(FuncionarioBase):
    """Contrato de entrada para admissão de novo funcionário."""
    pass


class UpdateFuncionario(BaseModel):
    """Contrato de entrada para atualização de dados do funcionário."""
    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

    nome: Optional[str] = Field(default=None, min_length=3, max_length=120)
    email: Optional[EmailStr] = None
    telefone: Optional[str] = Field(
        default=None,
        pattern=r"^\([0-9]{2}\)[0-9]{4,5}-[0-9]{4}$"
    )
    salario: Optional[float] = Field(default=None, ge=1621.0)


class FuncionarioResponse(FuncionarioBase):
    """Contrato de saída completo de funcionário."""
    funcionario_id: int = Field(
        ...,
        ge=1,
        le=9999,
        validation_alias=AliasChoices("funcionario-id", "funcionarioId", "funcionario_id", "id"),
        serialization_alias="funcionario-id",
        description="Identificador único primário do funcionário"
    )
    dt_admissao: datetime = Field(
        ...,
        validation_alias=AliasChoices("dt-admissao", "dtAdmissao", "dt_admissao"),
        serialization_alias="dt-admissao",
        description="Data e hora de admissão registrada"
    )


class FuncionarioListResponse(BaseModel):
    """Contrato de saída para listagem paginada de funcionários."""
    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

    data: list[FuncionarioResponse] = Field(..., description="Lista de funcionários da página")
    meta: PageMeta = Field(..., description="Metadados de paginação")


# ==============================================================================
# SCHEMAS DE USUÁRIOS LEITORES
# ==============================================================================

class UsuarioBase(BaseModel):
    """Campos fundamentais para cadastro e representação de leitores."""
    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

    CPF: str = Field(
        ...,
        pattern=r"^[0-9]{3}\.[0-9]{3}\.[0-9]{3}-[0-9]{2}$",
        description="CPF do leitor formatado (000.000.000-00)"
    )
    nome: Optional[str] = Field(default=None, description="Nome completo do leitor")
    email: Optional[EmailStr] = Field(default=None, description="Endereço de e-mail do leitor")
    telefone: Optional[str] = Field(
        default=None,
        pattern=r"^\([0-9]{2}\)[0-9]{4,5}-[0-9]{4}$",
        description="Telefone de contato com DDD"
    )
    CEP: Optional[str] = Field(
        default=None,
        pattern=r"^[0-9]{5}-[0-9]{3}$",
        description="Código de Endereçamento Postal formatado"
    )
    dt_nascimento: Optional[date] = Field(
        default=None,
        validation_alias=AliasChoices("dt-nascimento", "dtNascimento", "dt_nascimento"),
        serialization_alias="dt-nascimento",
        description="Data de nascimento do leitor"
    )


class CreateUsuario(UsuarioBase):
    """Contrato de entrada para cadastro de leitor na biblioteca."""
    pass


class UpdateUsuario(BaseModel):
    """Contrato de entrada para atualização parcial de dados do leitor."""
    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

    nome: Optional[str] = None
    email: Optional[EmailStr] = None
    telefone: Optional[str] = Field(
        default=None,
        pattern=r"^\([0-9]{2}\)[0-9]{4,5}-[0-9]{4}$"
    )
    CEP: Optional[str] = Field(default=None, pattern=r"^[0-9]{5}-[0-9]{3}$")
    dt_nascimento: Optional[date] = Field(
        default=None,
        validation_alias=AliasChoices("dt-nascimento", "dtNascimento", "dt_nascimento"),
        serialization_alias="dt-nascimento"
    )
    limite_disp: Optional[int] = Field(
        default=None,
        ge=0,
        le=4,
        validation_alias=AliasChoices("limite-disp", "limiteDisp", "limite_disp"),
        serialization_alias="limite-disp"
    )


class UsuarioResponse(UsuarioBase):
    """Contrato de saída completo de um leitor cadastrado."""
    usuario_id: int = Field(
        ...,
        ge=1,
        le=9999,
        validation_alias=AliasChoices("usuario-id", "usuarioId", "usuario_id", "id"),
        serialization_alias="usuario-id",
        description="Identificador único primário do leitor"
    )
    limite_disp: int = Field(
        default=4,
        ge=0,
        le=4,
        validation_alias=AliasChoices("limite-disp", "limiteDisp", "limite_disp"),
        serialization_alias="limite-disp",
        description="Limite de empréstimos simultâneos disponíveis para o leitor (0 a 4)"
    )
    dt_cadastro: datetime = Field(
        ...,
        validation_alias=AliasChoices("dt-cadastro", "dtCadastro", "dt_cadastro"),
        serialization_alias="dt-cadastro",
        description="Data e hora de realização do cadastro"
    )


class UsuarioListResponse(BaseModel):
    """Contrato de saída para listagem paginada de leitores."""
    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

    data: list[UsuarioResponse] = Field(..., description="Coleção de usuários da página atual")
    meta: PageMeta = Field(..., description="Metadados de paginação")


# ==============================================================================
# DTOS DE AUTENTICAÇÃO E RBAC (AULA 08 & STYLEGUIDE)
# ==============================================================================

class LoginRequestDTO(BaseModel):
    """Payload de entrada para requisição de login (/api/v1/auth/login)."""
    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

    email: EmailStr = Field(..., description="E-mail cadastrado do usuário")
    password: str = Field(..., min_length=6, description="Senha em texto plano (mínimo 6 caracteres)")


# Alias de conveniência
LoginRequest = LoginRequestDTO


class TokenResponseDTO(BaseModel):
    """Payload de resposta para emissão de token JWT após autenticação bem-sucedida."""
    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

    access_token: str = Field(
        ...,
        validation_alias=AliasChoices("accessToken", "access_token"),
        serialization_alias="accessToken",
        description="Token de acesso assinado digitalmente com JWT HS256"
    )
    token_type: str = Field(
        default="Bearer",
        validation_alias=AliasChoices("tokenType", "token_type"),
        serialization_alias="tokenType",
        description="Esquema de autorização HTTP (padrão 'Bearer')"
    )
    expires_in: int = Field(
        default=3600,
        validation_alias=AliasChoices("expiresIn", "expires_in"),
        serialization_alias="expiresIn",
        description="Tempo de validade do token em segundos"
    )


# Alias de conveniência
TokenResponse = TokenResponseDTO


class UserResponse(BaseModel):
    """Representação de usuário retornada em /api/v1/auth/me e consultas seguras."""
    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

    id: int = Field(..., description="Identificador único primário do usuário")
    email: EmailStr = Field(..., description="E-mail principal do usuário")
    role: UserRoleEnum = Field(..., description="Papel RBAC atribuído ao usuário (ADMIN ou MEMBER)")
    created_at: datetime = Field(
        ...,
        validation_alias=AliasChoices("createdAt", "created_at"),
        serialization_alias="createdAt",
        description="Data e hora de criação da conta de usuário"
    )


# Alias de conveniência
UserResponseDTO = UserResponse


# ==============================================================================
# ALIASES DE COMPATIBILIDADE ARQUITETURAL (STYLEGUIDE: PROJECTS & TASKS)
# ==============================================================================

ProjectBase = LivroBase
ProjectCreate = CreateLivro
ProjectUpdate = UpdateLivro
ProjectResponse = LivroResponse
ProjectListResponse = LivroListResponse

TaskBase = EmprestimoBase
TaskCreate = CreateEmprestimo
TaskUpdate = UpdateEmprestimo
TaskResponse = EmprestimoResponse
TaskListResponse = EmprestimoListResponse
