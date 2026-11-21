"""routers/funcionarios.py — Endpoints da Coleção /api/v1/lib/users/funcionarios.

Gerencia o cadastro, consulta, atualização e remoção de membros da equipe.
Acesso estritamente exclusivo para usuários com perfil funcional ADMIN (RBAC).
"""

from datetime import datetime
import math
from typing import Optional
from fastapi import APIRouter, Depends, Path, Query, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from database import get_db
from exceptions import ConflictException, NotFoundException, ValidationException
from models import FuncionarioModel
from schemas import (
    CreateFuncionarioDTO,
    Funcionario,
    FuncionarioListResponse,
    PageMeta,
    UpdateFuncionarioDTO,
)
from security import hash_password, require_roles

router = APIRouter(
    prefix="/api/v1/lib/users/funcionarios",
    tags=["funcionarios"],
    dependencies=[Depends(require_roles(["ADMIN"]))],
)


@router.get(
    "",
    response_model=FuncionarioListResponse,
    status_code=status.HTTP_200_OK,
    summary="Listar Funcionários (Exclusivo ADMIN)",
    description="Consulta paginada da equipe administrativa da biblioteca.",
)
def listar_funcionarios(
    page: int = Query(default=1, ge=1, description="Número da página"),
    limit: int = Query(default=10, ge=1, le=50, description="Itens por página"),
    search: Optional[str] = Query(default=None, description="Busca por nome, e-mail ou matrícula"),
    db: Session = Depends(get_db),
) -> FuncionarioListResponse:
    """Retorna listagem paginada de funcionários cadastrados."""
    query = select(FuncionarioModel)

    if search:
        search_filter = f"%{search}%"
        query = query.where(
            or_(
                FuncionarioModel.nome.ilike(search_filter),
                FuncionarioModel.email.ilike(search_filter),
            )
        )

    total_items = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    total_pages = math.ceil(total_items / limit) if total_items > 0 else 0
    has_next = page < total_pages

    offset_val = (page - 1) * limit
    funcionarios = db.scalars(
        query.order_by(FuncionarioModel.id).offset(offset_val).limit(limit)
    ).all()

    return FuncionarioListResponse(
        data=[Funcionario.model_validate(f) for f in funcionarios],
        meta=PageMeta(
            page=page,
            limit=limit,
            totalItems=total_items,
            totalPages=total_pages,
            hasNext=has_next,
        ),
    )


@router.get(
    "/{funcionario_id}",
    response_model=Funcionario,
    status_code=status.HTTP_200_OK,
    summary="Selecionar Funcionário por ID (Exclusivo ADMIN)",
    description="Recupera o cadastro de um funcionário específico.",
)
def selecionar_funcionario(
    funcionario_id: int = Path(..., ge=1, description="ID do funcionário"),
    db: Session = Depends(get_db),
) -> Funcionario:
    """Busca funcionário por ID com validação 404 RFC 9457."""
    funcionario = db.scalar(
        select(FuncionarioModel).where(FuncionarioModel.id == funcionario_id)
    )
    if not funcionario:
        raise NotFoundException(
            detail="O funcionário informado não existe.",
            title="Funcionário Não Encontrado",
        )
    return Funcionario.model_validate(funcionario)


@router.post(
    "",
    response_model=Funcionario,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastrar Funcionário (Exclusivo ADMIN)",
    description="Cadastra um novo membro da equipe com hash de senha seguro e papel RBAC.",
)
def cadastrar_funcionario(
    payload: CreateFuncionarioDTO,
    response: Response,
    db: Session = Depends(get_db),
) -> Funcionario:
    """Cadastra funcionário validando unicidade de CPF, e-mail e matrícula."""
    # 1. Validação de duplicidade de CPF
    if db.scalar(select(FuncionarioModel).where(FuncionarioModel.cpf == payload.CPF)):
        raise ConflictException(
            detail=f"Já existe um funcionário cadastrado com o CPF '{payload.CPF}'.",
            title="Conflito de CPF",
        )

    # 2. Validação de duplicidade de E-mail
    if db.scalar(select(FuncionarioModel).where(FuncionarioModel.email == payload.email)):
        raise ConflictException(
            detail=f"Já existe um funcionário cadastrado com o e-mail '{payload.email}'.",
            title="Conflito de E-mail",
        )

    # 3. Validação de duplicidade de Matrícula
    if db.scalar(select(FuncionarioModel).where(FuncionarioModel.matricula == payload.matricula)):
        raise ConflictException(
            detail=f"Já existe um funcionário cadastrado com a matrícula '{payload.matricula}'.",
            title="Conflito de Matrícula",
        )

    # 4. Validação de Salário Mínimo (R$ 1.621,00)
    if payload.salario < 1621.0:
        raise ValidationException(
            detail="O salário informado deve ser no mínimo R$ 1.621,00.",
            title="Salário Inválido",
            invalid_params=[{"name": "salario", "reason": "O valor deve ser maior ou igual a 1621.0."}],
        )

    novo_funcionario = FuncionarioModel(
        matricula=payload.matricula,
        cpf=payload.CPF,
        nome=payload.nome,
        email=payload.email,
        telefone=payload.telefone,
        dt_nascimento=payload.dt_nascimento,
        dt_admissao=payload.dt_admissao or datetime.utcnow(),
        salario=payload.salario,
        password_hash=hash_password(payload.password),
        role=payload.role.value,
    )
    db.add(novo_funcionario)
    db.commit()
    db.refresh(novo_funcionario)

    response.headers["Location"] = f"/api/v1/lib/users/funcionarios/{novo_funcionario.id}"
    return Funcionario.model_validate(novo_funcionario)


@router.patch(
    "/{funcionario_id}",
    response_model=Funcionario,
    status_code=status.HTTP_200_OK,
    summary="Atualizar Cadastro de Funcionário (Exclusivo ADMIN)",
    description="Atualiza informações cadastrais ou remuneração de um membro da equipe.",
)
def atualizar_funcionario(
    payload: UpdateFuncionarioDTO,
    funcionario_id: int = Path(..., ge=1, description="ID do funcionário"),
    db: Session = Depends(get_db),
) -> Funcionario:
    """Atualiza dados cadastrais com validação de salário mínimo."""
    funcionario = db.scalar(
        select(FuncionarioModel).where(FuncionarioModel.id == funcionario_id)
    )
    if not funcionario:
        raise NotFoundException(
            detail="O funcionário informado não existe.",
            title="Funcionário Não Encontrado",
        )

    update_data = payload.model_dump(exclude_unset=True)

    if "salario" in update_data and update_data["salario"] is not None:
        if update_data["salario"] < 1621.0:
            raise ValidationException(
                detail="O salário informado deve ser no mínimo R$ 1.621,00.",
                title="Salário Inválido",
                invalid_params=[{"name": "salario", "reason": "O valor deve ser maior ou igual a 1621.0."}],
            )

    for field, val in update_data.items():
        setattr(funcionario, field, val)

    db.commit()
    db.refresh(funcionario)
    return Funcionario.model_validate(funcionario)

