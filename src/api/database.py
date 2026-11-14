"""
Módulo de Gerenciamento de Banco de Dados e Carga Inicial (Seed).

Configura:
- Engine SQLAlchemy e SessionLocal conectado ao SQLite
- Injeção de dependência get_db()
- Rotina idempotente init_db_and_seed() para inicializar tabelas e dados padrão:
  * Usuários de autenticação: admin@fatec.sp.gov.br (ADMIN) e aluno@fatec.sp.gov.br (MEMBER)
  * Registros iniciais de Funcionário, Usuário leitor, Livro (Projeto) e Empréstimo (Tarefa)
"""

import os
from datetime import date, datetime, timedelta
from typing import Generator
import bcrypt
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from src.api.models import (
    Base,
    EmprestimoModel,
    FuncionarioModel,
    LivroModel,
    ProjectModel,
    TaskModel,
    UserModel,
    UsuarioModel,
)


# Configuração de conexão do SQLite
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./alexandria.db")
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    echo=False,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def get_db() -> Generator[Session, None, None]:
    """
    Dependência FastAPI que provê uma sessão transacional do banco de dados,
    garantindo fechamento seguro após o término da requisição.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def hash_password(password: str) -> str:
    """Gera hash seguro da senha em texto plano utilizando bcrypt diretamente."""
    pwd_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")


def init_db_and_seed(db: Session = None) -> None:
    """
    Cria as tabelas declaradas no metadata e popula o banco de dados de maneira idempotente.
    Cria:
    - Usuário ADMIN: admin@fatec.sp.gov.br (senha: admin123)
    - Usuário MEMBER: aluno@fatec.sp.gov.br (senha: aluno123)
    - Funcionário colaborador inicial
    - Usuário leitor inicial
    - Livro/Projeto inicial
    - Empréstimo/Tarefa vinculado com relacionamento 1:N
    """
    # 1. Criação física de todas as tabelas mapeadas
    Base.metadata.create_all(bind=engine)

    # 2. Gerenciamento de sessão local ou injetada
    close_session_at_end = False
    if db is None:
        db = SessionLocal()
        close_session_at_end = True

    try:
        # 3. Seed dos usuários de autenticação (ADMIN e MEMBER)
        admin_user = db.scalar(select(UserModel).where(UserModel.email == "admin@fatec.sp.gov.br"))
        if not admin_user:
            admin_user = UserModel(
                email="admin@fatec.sp.gov.br",
                hashed_password=hash_password("admin123"),
                role="ADMIN",
                created_at=datetime.utcnow(),
            )
            db.add(admin_user)

        aluno_user = db.scalar(select(UserModel).where(UserModel.email == "aluno@fatec.sp.gov.br"))
        if not aluno_user:
            aluno_user = UserModel(
                email="aluno@fatec.sp.gov.br",
                hashed_password=hash_password("aluno123"),
                role="MEMBER",
                created_at=datetime.utcnow(),
            )
            db.add(aluno_user)

        db.flush()

        # 4. Seed do Funcionário da biblioteca
        funcionario = db.scalar(select(FuncionarioModel).where(FuncionarioModel.matricula == 1001))
        if not funcionario:
            funcionario = FuncionarioModel(
                matricula=1001,
                cpf="111.222.333-44",
                nome="Bibliotecário FATEC",
                email="admin@fatec.sp.gov.br",
                telefone="(16)99999-1111",
                salario=3800.0,
                dt_nascimento=date(1988, 3, 15),
                dt_admissao=datetime.utcnow(),
            )
            db.add(funcionario)
            db.flush()

        # 5. Seed do Usuário leitor
        usuario = db.scalar(select(UsuarioModel).where(UsuarioModel.cpf == "555.666.777-88"))
        if not usuario:
            usuario = UsuarioModel(
                cpf="555.666.777-88",
                nome="Aluno FATEC",
                email="aluno@fatec.sp.gov.br",
                telefone="(16)98888-2222",
                cep="14000-000",
                dt_nascimento=date(2002, 7, 10),
                dt_cadastro=datetime.utcnow(),
                limite_disp=4,
            )
            db.add(usuario)
            db.flush()

        # 6. Seed do Livro / Projeto do acervo
        livro_1 = db.scalar(select(LivroModel).where(LivroModel.isbn == "978-85-12345-67-8"))
        if not livro_1:
            livro_1 = LivroModel(
                isbn="978-85-12345-67-8",
                titulo="Engenharia de Software Moderna",
                autor="Marco Tulio Valente",
                editora="Independente",
                publicacao=2020,
                categoria="Estudantil",
                exemplar=False,
                num_paginas=394,
                qtd_emprestimos=1,
                status="Conservado",
                dt_cadastro=datetime.utcnow(),
            )
            db.add(livro_1)
            db.flush()

        livro_2 = db.scalar(select(LivroModel).where(LivroModel.isbn == "978-85-98765-43-2"))
        if not livro_2:
            livro_2 = LivroModel(
                isbn="978-85-98765-43-2",
                titulo="O Senhor dos Anéis: A Sociedade do Anel",
                autor="J. R. R. Tolkien",
                editora="HarperCollins",
                publicacao=1954,
                categoria="Fantasia",
                exemplar=True,
                num_paginas=576,
                qtd_emprestimos=0,
                status="Novo",
                dt_cadastro=datetime.utcnow(),
            )
            db.add(livro_2)
            db.flush()

        # 7. Seed do Empréstimo / Tarefa (relação 1:N com Livro)
        emprestimo = db.scalar(select(EmprestimoModel).where(EmprestimoModel.livro_id == livro_1.id))
        if not emprestimo:
            emprestimo = EmprestimoModel(
                livro_id=livro_1.id,
                usuario_id=usuario.id,
                funcionario_id=funcionario.id,
                status="Emprestado",
                dt_emprestimo=datetime.utcnow(),
                dt_vencimento=datetime.utcnow() + timedelta(days=14),
                dt_devolucao=None,
            )
            db.add(emprestimo)

        db.commit()

    except Exception:
        db.rollback()
        raise
    finally:
        if close_session_at_end:
            db.close()
