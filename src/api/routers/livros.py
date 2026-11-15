"""routers/livros.py — Endpoints da Coleção /api/v1/lib/acervo.

Gerencia o catálogo de livros da biblioteca: consulta pública paginada,
cadastro e atualização autenticados e remoção exclusiva para perfil ADMIN.
"""

import math
from typing import Optional
from fastapi import APIRouter, Depends, Path, Query, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from api.database import get_db
from api.exceptions import ConflictException, NotFoundException
from api.models import FuncionarioModel, LivroModel
from api.schemas import (
    CategoriaLivro,
    CreateLivroDTO,
    Livro,
    LivroListResponse,
    PageMeta,
    StatusLivro,
    UpdateLivroDTO,
)
from api.security import get_current_user, require_roles

router = APIRouter(
    prefix="/api/v1/lib/acervo",
    tags=["livros"],
)


@router.get(
    "",
    response_model=LivroListResponse,
    status_code=status.HTTP_200_OK,
    summary="Listar Livros do Acervo",
    description="Consulta pública paginada do acervo de livros com suporte a múltiplos filtros.",
)
def listar_livros(
    page: int = Query(default=1, ge=1, description="Número da página atual"),
    limit: int = Query(default=10, ge=1, le=50, description="Itens por página"),
    search: Optional[str] = Query(default=None, description="Busca textual por título ou autor"),
    categoria: Optional[CategoriaLivro] = Query(default=None, description="Filtro por gênero literário"),
    status_livro: Optional[StatusLivro] = Query(default=None, alias="status", description="Filtro por conservação"),
    exemplar: Optional[bool] = Query(default=None, description="Filtro para exemplar de consulta local"),
    titulo: Optional[str] = Query(default=None, description="Filtro por título exato ou aproximado"),
    db: Session = Depends(get_db),
) -> LivroListResponse:
    """Retorna lista paginada de livros cadastrados com metadados de paginação."""
    query = select(LivroModel)

    if search:
        search_filter = f"%{search}%"
        query = query.where(
            or_(
                LivroModel.titulo.ilike(search_filter),
                LivroModel.autor.ilike(search_filter),
            )
        )
    if categoria:
        query = query.where(LivroModel.categoria == categoria.value)
    if status_livro:
        query = query.where(LivroModel.status == status_livro.value)
    if exemplar is not None:
        query = query.where(LivroModel.exemplar == exemplar)
    if titulo:
        query = query.where(LivroModel.titulo.ilike(f"%{titulo}%"))

    # Contagem total para metadados
    total_items = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    total_pages = math.ceil(total_items / limit) if total_items > 0 else 0
    has_next = page < total_pages

    # Consulta paginada ordenada por ID
    offset_val = (page - 1) * limit
    livros = db.scalars(query.order_by(LivroModel.id).offset(offset_val).limit(limit)).all()

    return LivroListResponse(
        data=[Livro.model_validate(l) for l in livros],
        meta=PageMeta(
            page=page,
            limit=limit,
            totalItems=total_items,
            totalPages=total_pages,
            hasNext=has_next,
        ),
    )


@router.get(
    "/{livro_id}",
    response_model=Livro,
    status_code=status.HTTP_200_OK,
    summary="Selecionar Livro por ID",
    description="Recupera os detalhes completos de uma obra através de seu ID numérico.",
)
def selecionar_livro(
    livro_id: int = Path(..., ge=1, description="Identificador único do livro"),
    db: Session = Depends(get_db),
) -> Livro:
    """Busca um livro específico pelo seu identificador primário."""
    livro = db.scalar(select(LivroModel).where(LivroModel.id == livro_id))
    if not livro:
        raise NotFoundException(
            detail="O livro informado não existe no acervo.",
            title="Livro Inexistente",
        )
    return Livro.model_validate(livro)


@router.post(
    "",
    response_model=Livro,
    status_code=status.HTTP_201_CREATED,
    summary="Adicionar Livro ao Acervo",
    description="Cadastra uma nova obra no catálogo. Requer autenticação de funcionário.",
)
def adicionar_livro(
    payload: CreateLivroDTO,
    response: Response,
    db: Session = Depends(get_db),
    current_user: FuncionarioModel = Depends(get_current_user),
) -> Livro:
    """Cadastra um novo livro garantindo a unicidade do ISBN."""
    existente = db.scalar(select(LivroModel).where(LivroModel.isbn == payload.ISBN))
    if existente:
        raise ConflictException(
            detail=f"Já existe uma obra cadastrada com o ISBN '{payload.ISBN}'.",
            title="Conflito de Acervo",
        )

    novo_livro = LivroModel(
        isbn=payload.ISBN,
        titulo=payload.titulo,
        autor=payload.autor,
        num_paginas=payload.num_paginas,
        editora=payload.editora,
        publicacao=payload.publicacao,
        categoria=payload.categoria.value,
        status=payload.status.value,
        exemplar=payload.exemplar,
        qtd_emprestimos=0,
    )
    db.add(novo_livro)
    db.commit()
    db.refresh(novo_livro)

    response.headers["Location"] = f"/api/v1/lib/acervo/{novo_livro.id}"
    return Livro.model_validate(novo_livro)


@router.patch(
    "/{livro_id}",
    response_model=Livro,
    status_code=status.HTTP_200_OK,
    summary="Atualizar Dados do Livro",
    description="Atualiza parcialmente metadados ou conservação de um livro existente.",
)
def atualizar_livro(
    payload: UpdateLivroDTO,
    livro_id: int = Path(..., ge=1, description="ID do livro"),
    db: Session = Depends(get_db),
    current_user: FuncionarioModel = Depends(get_current_user),
) -> Livro:
    """Atualiza seletivamente os campos informados no payload."""
    livro = db.scalar(select(LivroModel).where(LivroModel.id == livro_id))
    if not livro:
        raise NotFoundException(
            detail="O livro informado para atualização não existe.",
            title="Livro Inexistente",
        )

    update_data = payload.model_dump(exclude_unset=True)
    for field, val in update_data.items():
        if field == "categoria" and val is not None:
            livro.categoria = val.value if hasattr(val, "value") else str(val)
        elif field == "status" and val is not None:
            livro.status = val.value if hasattr(val, "value") else str(val)
        else:
            setattr(livro, field, val)

    db.commit()
    db.refresh(livro)
    return Livro.model_validate(livro)


@router.delete(
    "/{livro_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remover Livro do Acervo (Exclusivo ADMIN)",
    description="Exclui definitivamente uma obra do catálogo. Exige papel funcional ADMIN.",
)
def remover_livro(
    livro_id: int = Path(..., ge=1, description="ID do livro"),
    db: Session = Depends(get_db),
    current_user: FuncionarioModel = Depends(require_roles(["ADMIN"])),
) -> Response:
    """Remove o livro do acervo respeitando as permissões de acesso RBAC."""
    livro = db.scalar(select(LivroModel).where(LivroModel.id == livro_id))
    if not livro:
        raise NotFoundException(
            detail="O livro informado não existe.",
            title="Livro Inexistente",
        )

    db.delete(livro)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
