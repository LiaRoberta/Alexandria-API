"""routers/usuarios.py — Endpoints da Coleção /api/v1/lib/users/usuarios.

Gerencia o cadastro, consulta, atualização e remoção de leitores da biblioteca.
"""

from datetime import datetime
import math
from typing import Optional
from fastapi import APIRouter, Depends, Path, Query, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from database import get_db
from exceptions import ConflictException, NotFoundException
from models import FuncionarioModel, UsuarioModel
from schemas import (
    CreateUsuarioDTO,
    PageMeta,
    UpdateUsuarioDTO,
    Usuario,
    UsuarioListResponse,
)
from security import get_current_user

router = APIRouter(
    prefix="/api/v1/lib/users/usuarios",
    tags=["usuarios"],
)


@router.get(
    "",
    response_model=UsuarioListResponse,
    status_code=status.HTTP_200_OK,
    summary="Listar Usuários (Leitores)",
    description="Consulta paginada de leitores cadastrados com filtros por nome e CPF.",
)
def listar_usuarios(
    page: int = Query(default=1, ge=1, description="Número da página"),
    limit: int = Query(default=10, ge=1, le=50, description="Itens por página"),
    search: Optional[str] = Query(default=None, description="Busca por nome, e-mail ou CPF"),
    db: Session = Depends(get_db),
    current_user: FuncionarioModel = Depends(get_current_user),
) -> UsuarioListResponse:
    """Retorna listagem paginada de leitores cadastrados."""
    query = select(UsuarioModel)

    if search:
        search_filter = f"%{search}%"
        query = query.where(
            or_(
                UsuarioModel.nome.ilike(search_filter),
                UsuarioModel.email.ilike(search_filter),
                UsuarioModel.cpf.ilike(search_filter),
            )
        )

    total_items = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    total_pages = math.ceil(total_items / limit) if total_items > 0 else 0
    has_next = page < total_pages

    offset_val = (page - 1) * limit
    usuarios = db.scalars(query.order_by(UsuarioModel.id).offset(offset_val).limit(limit)).all()

    return UsuarioListResponse(
        data=[Usuario.model_validate(u) for u in usuarios],
        meta=PageMeta(
            page=page,
            limit=limit,
            totalItems=total_items,
            totalPages=total_pages,
            hasNext=has_next,
        ),
    )


@router.get(
    "/{usuario_id}",
    response_model=Usuario,
    status_code=status.HTTP_200_OK,
    summary="Selecionar Usuário por ID",
    description="Recupera o cadastro completo de um leitor pelo seu identificador primário.",
)
def selecionar_usuario(
    usuario_id: int = Path(..., ge=1, description="ID do leitor"),
    db: Session = Depends(get_db),
    current_user: FuncionarioModel = Depends(get_current_user),
) -> Usuario:
    """Busca o leitor pelo identificador numérico com tratamento semântico de 404."""
    usuario = db.scalar(select(UsuarioModel).where(UsuarioModel.id == usuario_id))
    if not usuario:
        raise NotFoundException(
            detail="O usuário leitor informado não existe.",
            title="Usuário Não Encontrado",
        )
    return Usuario.model_validate(usuario)


@router.post(
    "",
    response_model=Usuario,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastrar Usuário (Leitor)",
    description="Cadastra um novo leitor com cota inicial de 4 livros disponíveis.",
)
def cadastrar_usuario(
    payload: CreateUsuarioDTO,
    response: Response,
    db: Session = Depends(get_db),
    current_user: FuncionarioModel = Depends(get_current_user),
) -> Usuario:
    """Cadastra o leitor após validar a unicidade do CPF."""
    existente = db.scalar(select(UsuarioModel).where(UsuarioModel.cpf == payload.CPF))
    if existente:
        raise ConflictException(
            detail=f"Já existe um leitor cadastrado com o CPF '{payload.CPF}'.",
            title="Conflito de Usuário",
        )

    novo_usuario = UsuarioModel(
        cpf=payload.CPF,
        nome=payload.nome,
        email=payload.email,
        telefone=payload.telefone,
        dt_nascimento=payload.dt_nascimento,
        cep=payload.CEP,
        limite_disp=4,
        dt_cadastro=datetime.utcnow(),
    )
    db.add(novo_usuario)
    db.commit()
    db.refresh(novo_usuario)

    response.headers["Location"] = f"/api/v1/lib/users/usuarios/{novo_usuario.id}"
    return Usuario.model_validate(novo_usuario)


@router.patch(
    "/{usuario_id}",
    response_model=Usuario,
    status_code=status.HTTP_200_OK,
    summary="Atualizar Cadastro de Usuário",
    description="Atualiza parcialmente informações pessoais ou limite disponível de um leitor.",
)
def atualizar_usuario(
    payload: UpdateUsuarioDTO,
    usuario_id: int = Path(..., ge=1, description="ID do leitor"),
    db: Session = Depends(get_db),
    current_user: FuncionarioModel = Depends(get_current_user),
) -> Usuario:
    """Aplica atualizações nos campos de cadastro do leitor."""
    usuario = db.scalar(select(UsuarioModel).where(UsuarioModel.id == usuario_id))
    if not usuario:
        raise NotFoundException(
            detail="O usuário leitor informado não existe.",
            title="Usuário Não Encontrado",
        )

    update_data = payload.model_dump(exclude_unset=True)
    for field, val in update_data.items():
        if field == "CEP":
            usuario.cep = val
        else:
            setattr(usuario, field, val)

    db.commit()
    db.refresh(usuario)
    return Usuario.model_validate(usuario)

