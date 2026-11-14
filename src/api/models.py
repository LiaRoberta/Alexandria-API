"""
Módulo de Modelos ORM SQLAlchemy 2.0 para a Alexandria API v2.

Implementa mapeamento declarativo moderno (DeclarativeBase, Mapped, mapped_column,
relationship, ForeignKey) para:
- UserModel: Controle de autenticação e RBAC (ADMIN, MEMBER)
- LivroModel (ProjectModel): Entidade principal do acervo com relacionamento 1:N
- EmprestimoModel (TaskModel): Entidade transacional de empréstimo (1:N com LivroModel)
- UsuarioModel: Leitores cadastrados na biblioteca
- FuncionarioModel: Colaboradores do corpo funcional da biblioteca
"""

from datetime import date, datetime
from typing import Optional
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
    synonym,
)


class Base(DeclarativeBase):
    """Classe base declarativa do SQLAlchemy 2.0 para todas as entidades ORM."""
    pass


# ==============================================================================
# MODELO DE AUTENTICAÇÃO E RBAC (AULA 08)
# ==============================================================================

class UserModel(Base):
    """
    Entidade de segurança para credenciais e controle de acesso baseado em papéis (RBAC).
    Papeis válidos: 'ADMIN' e 'MEMBER'.
    """
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="MEMBER", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"<UserModel(id={self.id}, email='{self.email}', role='{self.role}')>"


# ==============================================================================
# MODELOS DE DOMÍNIO: ACERVO (LIVROS / PROJETOS)
# ==============================================================================

class LivroModel(Base):
    """
    Entidade pai que representa uma obra cadastrada no acervo da biblioteca Alexandria.
    Atua também como a entidade agregadora 'ProjectModel' do STYLEGUIDE.
    Mantém relacionamento 1:N com 'EmprestimoModel' (TaskModel).
    """
    __tablename__ = "livros"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    isbn: Mapped[str] = mapped_column(String(30), unique=True, index=True, nullable=False)
    titulo: Mapped[str] = mapped_column(String(200), nullable=False)
    autor: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    editora: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    publicacao: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    categoria: Mapped[str] = mapped_column(String(50), default="Aventura", nullable=False)
    exemplar: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    num_paginas: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    qtd_emprestimos: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    dt_cadastro: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="Novo", nullable=False)

    # Synonyms para interoperabilidade com o contrato de TaskFlow/Project
    title = synonym("titulo")

    # Relacionamento 1:N com EmprestimoModel
    emprestimos: Mapped[list["EmprestimoModel"]] = relationship(
        "EmprestimoModel",
        back_populates="livro",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    # Synonym para navegação via project.tasks
    tasks = synonym("emprestimos")

    def __repr__(self) -> str:
        return f"<LivroModel(id={self.id}, titulo='{self.titulo}', isbn='{self.isbn}')>"


# Alias arquitetural exigido pelo STYLEGUIDE
ProjectModel = LivroModel


# ==============================================================================
# MODELOS DE USUÁRIOS LEITORES E FUNCIONÁRIOS
# ==============================================================================

class UsuarioModel(Base):
    """
    Entidade que representa os leitores cadastrados no sistema Alexandria.
    Mantém relacionamento 1:N com EmprestimoModel.
    """
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cpf: Mapped[str] = mapped_column(String(20), unique=True, index=True, nullable=False)
    nome: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    telefone: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    cep: Mapped[Optional[str]] = mapped_column(String(15), nullable=True)
    dt_nascimento: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    dt_cadastro: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    limite_disp: Mapped[int] = mapped_column(Integer, default=4, nullable=False)

    # Relacionamento 1:N com Empréstimos
    emprestimos: Mapped[list["EmprestimoModel"]] = relationship(
        "EmprestimoModel",
        back_populates="usuario",
    )

    def __repr__(self) -> str:
        return f"<UsuarioModel(id={self.id}, nome='{self.nome}', cpf='{self.cpf}')>"


class FuncionarioModel(Base):
    """
    Entidade que representa os colaboradores da biblioteca.
    Mantém relacionamento 1:N com EmprestimoModel.
    """
    __tablename__ = "funcionarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    matricula: Mapped[int] = mapped_column(Integer, unique=True, index=True, nullable=False)
    cpf: Mapped[str] = mapped_column(String(20), unique=True, index=True, nullable=False)
    nome: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    telefone: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    salario: Mapped[float] = mapped_column(Float, nullable=False)
    dt_nascimento: Mapped[date] = mapped_column(Date, nullable=False)
    dt_admissao: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Relacionamento 1:N com Empréstimos
    emprestimos: Mapped[list["EmprestimoModel"]] = relationship(
        "EmprestimoModel",
        back_populates="funcionario",
    )

    def __repr__(self) -> str:
        return f"<FuncionarioModel(id={self.id}, nome='{self.nome}', matricula={self.matricula})>"


# ==============================================================================
# MODELO DE EMPRÉSTIMO (TASKMODEL / DEPENDENTE 1:N COM LIVROMODEL)
# ==============================================================================

class EmprestimoModel(Base):
    """
    Entidade dependente que representa o empréstimo de um exemplar do acervo.
    Atua também como a entidade dependente 'TaskModel' do STYLEGUIDE.
    Vincula-se por ForeignKey('livros.id') a LivroModel (ProjectModel).
    """
    __tablename__ = "emprestimos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    livro_id: Mapped[int] = mapped_column(
        ForeignKey("livros.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    usuario_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("usuarios.id"),
        nullable=True,
        index=True,
    )
    funcionario_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("funcionarios.id"),
        nullable=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(50), default="Emprestado", nullable=False)
    dt_emprestimo: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    dt_vencimento: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    dt_devolucao: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Synonyms para interoperabilidade com o contrato TaskModel
    project_id = synonym("livro_id")
    due_date = synonym("dt_vencimento")

    # Relacionamentos N:1
    livro: Mapped["LivroModel"] = relationship(
        "LivroModel",
        back_populates="emprestimos",
    )
    project = synonym("livro")

    usuario: Mapped[Optional["UsuarioModel"]] = relationship(
        "UsuarioModel",
        back_populates="emprestimos",
    )
    funcionario: Mapped[Optional["FuncionarioModel"]] = relationship(
        "FuncionarioModel",
        back_populates="emprestimos",
    )

    def __repr__(self) -> str:
        return f"<EmprestimoModel(id={self.id}, livro_id={self.livro_id}, status='{self.status}')>"


# Alias arquitetural exigido pelo STYLEGUIDE
TaskModel = EmprestimoModel
