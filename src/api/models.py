"""models.py — Mapeamento Objeto-Relacional (ORM) SQLAlchemy 2.0.

Implementa as entidades relacionais FuncionarioModel, UsuarioModel, LivroModel e
EmprestimoModel utilizando DeclarativeBase, Mapped e mapped_column, garantindo
integridade referencial via ForeignKey e relacionamentos bidirecionais.
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
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


# -----------------------------------------------------------------------------
# Base Declarativa SQLAlchemy 2.0
# -----------------------------------------------------------------------------
class Base(DeclarativeBase):
    """Classe base para todos os modelos ORM da Alexandria API."""
    pass


# -----------------------------------------------------------------------------
# 1. Tabela funcionarios: Equipe Administrativa & Autenticação
# -----------------------------------------------------------------------------
class FuncionarioModel(Base):
    """Representa um funcionário (Admin ou Bibliotecário) com credenciais de acesso."""
    __tablename__ = "funcionarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    matricula: Mapped[int] = mapped_column(Integer, unique=True, nullable=False, index=True)
    cpf: Mapped[str] = mapped_column(String(14), unique=True, nullable=False, index=True)
    nome: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)
    telefone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    dt_nascimento: Mapped[date] = mapped_column(Date, nullable=False)
    dt_admissao: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    salario: Mapped[float] = mapped_column(Float, nullable=False)
    
    # Campos específicos de autenticação e RBAC (ocultos no contrato público do Apidog)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="BIBLIOTECARIO", nullable=False)

    # Relacionamento 1:N com Empréstimos
    emprestimos: Mapped[list["EmprestimoModel"]] = relationship(
        back_populates="funcionario",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Funcionario id={self.id} matricula={self.matricula} nome='{self.nome}' role='{self.role}'>"


# -----------------------------------------------------------------------------
# 2. Tabela usuarios: Leitores da Biblioteca
# -----------------------------------------------------------------------------
class UsuarioModel(Base):
    """Representa um leitor cadastrado autorizado a realizar empréstimos de livros."""
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cpf: Mapped[str] = mapped_column(String(14), unique=True, nullable=False, index=True)
    nome: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(120), nullable=False)
    telefone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    dt_nascimento: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    cep: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    limite_disp: Mapped[int] = mapped_column(Integer, default=4, nullable=False)
    dt_cadastro: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Relacionamento 1:N com Empréstimos
    emprestimos: Mapped[list["EmprestimoModel"]] = relationship(
        back_populates="usuario",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Usuario id={self.id} cpf='{self.cpf}' nome='{self.nome}' limite_disp={self.limite_disp}>"


# -----------------------------------------------------------------------------
# 3. Tabela livros: Catálogo do Acervo
# -----------------------------------------------------------------------------
class LivroModel(Base):
    """Representa uma obra literária disponível no acervo da biblioteca."""
    __tablename__ = "livros"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    isbn: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    titulo: Mapped[str] = mapped_column(String(200), nullable=False)
    autor: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    num_paginas: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    editora: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    publicacao: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    categoria: Mapped[str] = mapped_column(String(50), nullable=False)
    qtd_emprestimos: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    dt_cadastro: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="Novo", nullable=False)
    exemplar: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relacionamento 1:N com Empréstimos
    emprestimos: Mapped[list["EmprestimoModel"]] = relationship(
        back_populates="livro",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Livro id={self.id} isbn='{self.isbn}' titulo='{self.titulo}' status='{self.status}'>"


# -----------------------------------------------------------------------------
# 4. Tabela emprestimos: Operações Transacionais
# -----------------------------------------------------------------------------
class EmprestimoModel(Base):
    """Representa o empréstimo de um livro para um usuário leitor por um funcionário."""
    __tablename__ = "emprestimos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    livro_id: Mapped[int] = mapped_column(ForeignKey("livros.id"), nullable=False, index=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), nullable=False, index=True)
    funcionario_id: Mapped[int] = mapped_column(ForeignKey("funcionarios.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), default="Emprestado", nullable=False)
    dt_emprestimo: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    dt_vencimento: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    dt_devolucao: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relacionamentos N:1
    livro: Mapped["LivroModel"] = relationship(back_populates="emprestimos")
    usuario: Mapped["UsuarioModel"] = relationship(back_populates="emprestimos")
    funcionario: Mapped["FuncionarioModel"] = relationship(back_populates="emprestimos")

    def __repr__(self) -> str:
        return f"<Emprestimo id={self.id} livro_id={self.livro_id} usuario_id={self.usuario_id} status='{self.status}'>"
