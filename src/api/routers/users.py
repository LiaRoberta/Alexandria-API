"""
Roteador para Gestão de Colaboradores (Funcionários) e Leitores (Usuários).

Implementa os endpoints do contrato formal Alexandria.Apidog.json:
- /api/v1/lib/users/funcionarios: listagem, consulta, cadastro e atualização
- /api/v1/lib/users/usuarios: listagem, consulta, cadastro e atualização
"""

import math
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.api.database import get_db
from src.api.exceptions import DomainConflictException, DomainNotFoundException
from src.api.models import FuncionarioModel, UserModel, UsuarioModel
from src.api.schemas import (
    CreateFuncionario,
    CreateUsuario,
    FuncionarioListResponse,
    FuncionarioResponse,
    PageMeta,
    UpdateFuncionario,
    UpdateUsuario,
    UsuarioListResponse,
    UsuarioResponse,
)
from src.api.security import require_roles

router = APIRouter(prefix="/api/v1/lib/users", tags=["Usuários & Funcionários"])


# ==============================================================================
# FUNCIONÁRIOS (COLABORADORES)
# ==============================================================================

@router.get(
    "/funcionarios",
    response_model=FuncionarioListResponse,
    status_code=status.HTTP_200_OK,
    summary="Listar funcionários cadastrados",
)
def list_funcionarios(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> FuncionarioListResponse:
    query = select(FuncionarioModel)
    if search:
        query = query.where(
            (FuncionarioModel.nome.ilike(f"%{search}%"))
            | (FuncionarioModel.cpf.ilike(f"%{search}%"))
        )

    total_items = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    total_pages = math.ceil(total_items / limit) if total_items > 0 else 0

    items = db.scalars(query.offset((page - 1) * limit).limit(limit)).all()

    return FuncionarioListResponse(
        data=[
            FuncionarioResponse(
                funcionario_id=f.id,
                matricula=f.matricula,
                CPF=f.cpf,
                nome=f.nome,
                email=f.email,
                telefone=f.telefone,
                dt_nascimento=f.dt_nascimento,
                salario=f.salario,
                dt_admissao=f.dt_admissao,
            )
            for f in items
        ],
        meta=PageMeta(
            page=page,
            limit=limit,
            totalItems=total_items,
            totalPages=total_pages,
            hasNext=page < total_pages,
        ),
    )


@router.get(
    "/funcionarios/{funcionario_id}",
    response_model=FuncionarioResponse,
    status_code=status.HTTP_200_OK,
    summary="Selecionar funcionário por ID",
)
def get_funcionario(funcionario_id: int, db: Session = Depends(get_db)) -> FuncionarioResponse:
    f = db.get(FuncionarioModel, funcionario_id)
    if not f:
        raise DomainNotFoundException(detail=f"Funcionário com ID {funcionario_id} não encontrado.")
    return FuncionarioResponse(
        funcionario_id=f.id,
        matricula=f.matricula,
        CPF=f.cpf,
        nome=f.nome,
        email=f.email,
        telefone=f.telefone,
        dt_nascimento=f.dt_nascimento,
        salario=f.salario,
        dt_admissao=f.dt_admissao,
    )


@router.post(
    "/funcionarios/cadastrarFuncionario",
    response_model=FuncionarioResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastrar novo funcionário (ADMIN)",
)
def create_funcionario(
    payload: CreateFuncionario,
    current_user: UserModel = Depends(require_roles("ADMIN")),
    db: Session = Depends(get_db),
) -> FuncionarioResponse:
    existing = db.scalar(
        select(FuncionarioModel).where(
            (FuncionarioModel.matricula == payload.matricula)
            | (FuncionarioModel.cpf == payload.CPF)
        )
    )
    if existing:
        raise DomainConflictException(detail="Já existe colaborador com esta matrícula ou CPF.")

    new_f = FuncionarioModel(
        matricula=payload.matricula,
        cpf=payload.CPF,
        nome=payload.nome,
        email=payload.email,
        telefone=payload.telefone,
        salario=payload.salario,
        dt_nascimento=payload.dt_nascimento,
        dt_admissao=datetime.utcnow(),
    )
    db.add(new_f)
    db.commit()
    db.refresh(new_f)

    return FuncionarioResponse(
        funcionario_id=new_f.id,
        matricula=new_f.matricula,
        CPF=new_f.cpf,
        nome=new_f.nome,
        email=new_f.email,
        telefone=new_f.telefone,
        dt_nascimento=new_f.dt_nascimento,
        salario=new_f.salario,
        dt_admissao=new_f.dt_admissao,
    )


@router.patch(
    "/funcionarios/{funcionario_id}",
    response_model=FuncionarioResponse,
    status_code=status.HTTP_200_OK,
    summary="Atualizar funcionário (ADMIN)",
)
def update_funcionario(
    funcionario_id: int,
    payload: UpdateFuncionario,
    current_user: UserModel = Depends(require_roles("ADMIN")),
    db: Session = Depends(get_db),
) -> FuncionarioResponse:
    f = db.get(FuncionarioModel, funcionario_id)
    if not f:
        raise DomainNotFoundException(detail=f"Funcionário com ID {funcionario_id} não encontrado.")

    if payload.nome is not None:
        f.nome = payload.nome
    if payload.email is not None:
        f.email = payload.email
    if payload.telefone is not None:
        f.telefone = payload.telefone
    if payload.salario is not None:
        f.salario = payload.salario

    db.commit()
    db.refresh(f)

    return FuncionarioResponse(
        funcionario_id=f.id,
        matricula=f.matricula,
        CPF=f.cpf,
        nome=f.nome,
        email=f.email,
        telefone=f.telefone,
        dt_nascimento=f.dt_nascimento,
        salario=f.salario,
        dt_admissao=f.dt_admissao,
    )


# ==============================================================================
# USUÁRIOS (LEITORES)
# ==============================================================================

@router.get(
    "/usuarios",
    response_model=UsuarioListResponse,
    status_code=status.HTTP_200_OK,
    summary="Listar usuários leitores",
)
def list_usuarios(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> UsuarioListResponse:
    query = select(UsuarioModel)
    if search:
        query = query.where(
            (UsuarioModel.nome.ilike(f"%{search}%"))
            | (UsuarioModel.cpf.ilike(f"%{search}%"))
        )

    total_items = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    total_pages = math.ceil(total_items / limit) if total_items > 0 else 0

    items = db.scalars(query.offset((page - 1) * limit).limit(limit)).all()

    return UsuarioListResponse(
        data=[
            UsuarioResponse(
                usuario_id=u.id,
                CPF=u.cpf,
                nome=u.nome,
                email=u.email,
                telefone=u.telefone,
                CEP=u.cep,
                dt_nascimento=u.dt_nascimento,
                dt_cadastro=u.dt_cadastro,
                limite_disp=u.limite_disp,
            )
            for u in items
        ],
        meta=PageMeta(
            page=page,
            limit=limit,
            totalItems=total_items,
            totalPages=total_pages,
            hasNext=page < total_pages,
        ),
    )


@router.get(
    "/usuarios/{usuario_id}",
    response_model=UsuarioResponse,
    status_code=status.HTTP_200_OK,
    summary="Selecionar usuário por ID",
)
def get_usuario(usuario_id: int, db: Session = Depends(get_db)) -> UsuarioResponse:
    u = db.get(UsuarioModel, usuario_id)
    if not u:
        raise DomainNotFoundException(detail=f"Usuário com ID {usuario_id} não encontrado.")
    return UsuarioResponse(
        usuario_id=u.id,
        CPF=u.cpf,
        nome=u.nome,
        email=u.email,
        telefone=u.telefone,
        CEP=u.cep,
        dt_nascimento=u.dt_nascimento,
        dt_cadastro=u.dt_cadastro,
        limite_disp=u.limite_disp,
    )


@router.post(
    "/usuarios",
    response_model=UsuarioResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastrar novo usuário leitor",
)
def create_usuario(payload: CreateUsuario, db: Session = Depends(get_db)) -> UsuarioResponse:
    existing = db.scalar(select(UsuarioModel).where(UsuarioModel.cpf == payload.CPF))
    if existing:
        raise DomainConflictException(detail=f"Já existe leitor cadastrado com o CPF '{payload.CPF}'.")

    new_u = UsuarioModel(
        cpf=payload.CPF,
        nome=payload.nome,
        email=payload.email,
        telefone=payload.telefone,
        cep=payload.CEP,
        dt_nascimento=payload.dt_nascimento,
        dt_cadastro=datetime.utcnow(),
        limite_disp=4,
    )
    db.add(new_u)
    db.commit()
    db.refresh(new_u)

    return UsuarioResponse(
        usuario_id=new_u.id,
        CPF=new_u.cpf,
        nome=new_u.nome,
        email=new_u.email,
        telefone=new_u.telefone,
        CEP=new_u.cep,
        dt_nascimento=new_u.dt_nascimento,
        dt_cadastro=new_u.dt_cadastro,
        limite_disp=new_u.limite_disp,
    )


@router.patch(
    "/usuarios/{usuario_id}",
    response_model=UsuarioResponse,
    status_code=status.HTTP_200_OK,
    summary="Atualizar usuário leitor",
)
def update_usuario(
    usuario_id: int,
    payload: UpdateUsuario,
    db: Session = Depends(get_db),
) -> UsuarioResponse:
    u = db.get(UsuarioModel, usuario_id)
    if not u:
        raise DomainNotFoundException(detail=f"Usuário com ID {usuario_id} não encontrado.")

    if payload.nome is not None:
        u.nome = payload.nome
    if payload.email is not None:
        u.email = payload.email
    if payload.telefone is not None:
        u.telefone = payload.telefone
    if payload.CEP is not None:
        u.cep = payload.CEP
    if payload.dt_nascimento is not None:
        u.dt_nascimento = payload.dt_nascimento
    if payload.limite_disp is not None:
        u.limite_disp = payload.limite_disp

    db.commit()
    db.refresh(u)

    return UsuarioResponse(
        usuario_id=u.id,
        CPF=u.cpf,
        nome=u.nome,
        email=u.email,
        telefone=u.telefone,
        CEP=u.cep,
        dt_nascimento=u.dt_nascimento,
        dt_cadastro=u.dt_cadastro,
        limite_disp=u.limite_disp,
    )
