"""database.py — Gerenciador de Banco de Dados SQLite e Seed Inicial.

Configura a engine SQLAlchemy 2.0, a fábrica de sessões (SessionLocal), a
dependência de injeção FastAPI (get_db) e a rotina de inicialização e seed
idempotente com dados pré-configurados do Apidog e SPEC.md.
"""

from datetime import date, datetime
from typing import Generator
import bcrypt
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from api.models import Base, FuncionarioModel, LivroModel, UsuarioModel


# -----------------------------------------------------------------------------
# Configuração da Engine SQLite
# -----------------------------------------------------------------------------
DATABASE_URL = "sqlite:///./alexandria.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


# -----------------------------------------------------------------------------
# Injeção de Dependência FastAPI (get_db)
# -----------------------------------------------------------------------------
def get_db() -> Generator[Session, None, None]:
    """Fornece uma sessão do SQLAlchemy por requisição e garante seu fechamento."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# -----------------------------------------------------------------------------
# Hashes de Senha Pré-computados para o Seed Inicial (Bcrypt rápido)
# -----------------------------------------------------------------------------
ADMIN_SEED_PASSWORD_HASH = "$2b$10$CazhvInVIUfILvSbYHZuBeHYGvZwgf194QI3.jfZ625.fzBTOz286"
BIBLIO_SEED_PASSWORD_HASH = "$2b$10$qe18Pb5ykX2v.ylk8idkRuKMd/dIxRa8C8EjIdjDEW1Q5VMp3GlhW"


# -----------------------------------------------------------------------------
# Inicialização Idempotente e Seed do Banco
# -----------------------------------------------------------------------------
def init_db(target_engine=None) -> None:
    """Cria tabelas e insere dados iniciais de forma estritamente idempotente."""
    active_engine = target_engine or engine
    
    # 1. Cria todas as tabelas caso não existam
    Base.metadata.create_all(bind=active_engine)
    
    # 2. Executa o seed de registros fundamentais
    with Session(bind=active_engine) as session:
        # Seed Funcionario ID 1 (ADMIN)
        admin = session.scalar(select(FuncionarioModel).where(FuncionarioModel.id == 1))
        if not admin:
            admin = FuncionarioModel(
                id=1,
                matricula=20260,
                cpf="987.654.321-00",
                nome="João Souza",
                email="joao.souza@biblioteca.com",
                telefone="(16)98888-7777",
                dt_nascimento=date(1990, 3, 12),
                dt_admissao=datetime(2024, 2, 1, 0, 0, 0),
                salario=3200.50,
                password_hash=ADMIN_SEED_PASSWORD_HASH,
                role="ADMIN",
            )
            session.add(admin)

        # Seed Funcionario ID 2 (BIBLIOTECARIO)
        biblio = session.scalar(select(FuncionarioModel).where(FuncionarioModel.id == 2))
        if not biblio:
            biblio = FuncionarioModel(
                id=2,
                matricula=20261,
                cpf="321.654.987-11",
                nome="Ana Lima",
                email="ana.lima@biblioteca.com",
                telefone="(16)97777-6666",
                dt_nascimento=date(1995, 7, 20),
                dt_admissao=datetime(2024, 3, 15, 0, 0, 0),
                salario=2450.00,
                password_hash=BIBLIO_SEED_PASSWORD_HASH,
                role="BIBLIOTECARIO",
            )
            session.add(biblio)

        # Seed Livro ID 1 (Acervo Base)
        livro = session.scalar(select(LivroModel).where(LivroModel.id == 1))
        if not livro:
            livro = LivroModel(
                id=1,
                isbn="978-85-12345-67-8",
                titulo="O Hobbit",
                autor="J. R. R. Tolkien",
                num_paginas=310,
                editora="HarperCollins",
                publicacao=1937,
                categoria="Fantasia",
                qtd_emprestimos=0,
                dt_cadastro=datetime(2026, 1, 10, 10, 0, 0),
                status="Conservado",
                exemplar=False,
            )
            session.add(livro)

        # Seed Usuario ID 7 (Leitor Base do Mock)
        usuario = session.scalar(select(UsuarioModel).where(UsuarioModel.id == 7))
        if not usuario:
            usuario = UsuarioModel(
                id=7,
                cpf="123.456.789-09",
                nome="Maria Silva",
                email="maria.silva@email.com",
                telefone="(16)99999-9999",
                dt_nascimento=date(2000, 5, 20),
                cep="14000-000",
                limite_disp=3,
                dt_cadastro=datetime(2026, 2, 15, 9, 0, 0),
            )
            session.add(usuario)

        session.commit()
