"""
Roteador da Coleção de Projetos e Acervo (Projects / Livros).

Implementa:
- GET /api/v1/projects: listagem paginada de livros/projetos com filtros
- GET /api/v1/projects/{id}: consulta de projeto/livro por ID
- POST /api/v1/projects: inclusão de livro/projeto no acervo (ADMIN)
- PATCH /api/v1/projects/{id}: atualização parcial de dados (ADMIN)
- DELETE /api/v1/projects/{id}: remoção física de livro/projeto do acervo (ADMIN)
- GET /api/v1/projects/{projectId}/tasks: consulta das tarefas vinculadas utilizando
  selectinload(ProjectModel.tasks) para erradicar o problema de queries N+1 (Aula 09).
- Suporte simultâneo às rotas do contrato Alexandria: /api/v1/lib/acervo
"""

import math
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from src.api.database import get_db
from src.api.exceptions import DomainConflictException, DomainNotFoundException
from src.api.models import LivroModel, ProjectModel, UserModel
from src.api.schemas import (
    CategoriaLivroEnum,
    CreateLivro,
    EmprestimoResponse,
    LivroListResponse,
    LivroResponse,
    PageMeta,
    StatusEmprestimoEnum,
    StatusLivroEnum,
    UpdateLivro,
)
from src.api.security import require_roles

router = APIRouter(prefix="/api/v1", tags=["Projetos & Acervo"])


# ==============================================================================
# ENDPOINT COM PREVENÇÃO DE QUERIES N+1 (SELECTINLOAD)
# ==============================================================================

@router.get(
    "/projects/{projectId}/tasks",
    response_model=list[EmprestimoResponse],
    status_code=status.HTTP_200_OK,
    summary="Listar tarefas vinculadas ao projeto (Prevenção N+1)",
    description="Utiliza selectinload(ProjectModel.tasks) para carregar todas as tarefas filhas em uma única query otimizada.",
)
@router.get(
    "/lib/acervo/{projectId}/emprestimos",
    response_model=list[EmprestimoResponse],
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
def get_project_tasks(
    projectId: int,
    db: Session = Depends(get_db),
) -> list[EmprestimoResponse]:
    """
    Carrega o projeto e todas as suas tarefas vinculadas utilizando eager loading com selectinload,
    garantindo a prevenção definitiva do problema de consultas N+1.
    """
    stmt = (
        select(ProjectModel)
        .options(selectinload(ProjectModel.tasks))
        .where(ProjectModel.id == projectId)
    )
    project = db.scalar(stmt)

    if not project:
        raise DomainNotFoundException(
            detail=f"Projeto / Livro com identificador {projectId} não foi encontrado."
        )

    # project.tasks já se encontra totalmente carregado na memória sem disparar novas queries SQL
    return [
        EmprestimoResponse(
            emprestimo_id=task.id,
            livro_id=task.livro_id,
            usuario_id=task.usuario_id or 1,
            funcionario_id=task.funcionario_id or 1,
            status=StatusEmprestimoEnum(task.status),
            dt_emprestimo=task.dt_emprestimo,
            dt_vencimento=task.dt_vencimento or datetime.utcnow(),
            dt_devolucao=task.dt_devolucao,
        )
        for task in project.tasks
    ]


# ==============================================================================
# CRUD DA COLEÇÃO PROJECTS / LIB/ACERVO
# ==============================================================================

@router.get(
    "/projects",
    response_model=LivroListResponse,
    status_code=status.HTTP_200_OK,
    summary="Listar projetos / livros do acervo",
)
@router.get(
    "/lib/acervo",
    response_model=LivroListResponse,
    status_code=status.HTTP_200_OK,
    summary="Listar livros do acervo",
    include_in_schema=True,
)
def list_projects(
    page: int = Query(1, ge=1, description="Número da página (1..N)"),
    limit: int = Query(10, ge=1, le=100, description="Registros por página"),
    search: Optional[str] = Query(None, description="Busca textual por título, autor ou editora"),
    categoria: Optional[CategoriaLivroEnum] = Query(None, description="Filtrar por categoria literária"),
    status_livro: Optional[StatusLivroEnum] = Query(None, alias="status", description="Filtrar por estado de conservação"),
    exemplar: Optional[bool] = Query(None, description="Filtrar por exemplar exclusivo de consulta"),
    titulo: Optional[str] = Query(None, description="Filtrar exatamente pelo título"),
    db: Session = Depends(get_db),
) -> LivroListResponse:
    """Retorna listagem paginada dos livros do acervo aplicando filtros combinados."""
    query = select(ProjectModel)

    if search:
        query = query.where(
            (ProjectModel.titulo.ilike(f"%{search}%"))
            | (ProjectModel.autor.ilike(f"%{search}%"))
            | (ProjectModel.editora.ilike(f"%{search}%"))
        )
    if titulo:
        query = query.where(ProjectModel.titulo.ilike(f"%{titulo}%"))
    if categoria:
        query = query.where(ProjectModel.categoria == categoria.value)
    if status_livro:
        query = query.where(ProjectModel.status == status_livro.value)
    if exemplar is not None:
        query = query.where(ProjectModel.exemplar == exemplar)

    # Total de registros
    count_stmt = select(func.count()).select_from(query.subquery())
    total_items = db.scalar(count_stmt) or 0

    total_pages = math.ceil(total_items / limit) if total_items > 0 else 0
    has_next = page < total_pages

    # Consulta paginada
    stmt = query.offset((page - 1) * limit).limit(limit)
    items = db.scalars(stmt).all()

    response_items = [
        LivroResponse(
            livro_id=item.id,
            ISBN=item.isbn,
            titulo=item.titulo,
            autor=item.autor,
            editora=item.editora,
            publicacao=item.publicacao,
            categoria=CategoriaLivroEnum(item.categoria),
            exemplar=item.exemplar,
            num_paginas=item.num_paginas,
            qtd_emprestimos=item.qtd_emprestimos,
            dt_cadastro=item.dt_cadastro,
            status=StatusLivroEnum(item.status),
        )
        for item in items
    ]

    return LivroListResponse(
        data=response_items,
        meta=PageMeta(
            page=page,
            limit=limit,
            totalItems=total_items,
            totalPages=total_pages,
            hasNext=has_next,
        ),
    )


@router.get(
    "/projects/{project_id}",
    response_model=LivroResponse,
    status_code=status.HTTP_200_OK,
    summary="Selecionar projeto / livro por ID",
)
@router.get(
    "/lib/acervo/{project_id}",
    response_model=LivroResponse,
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
def get_project(
    project_id: int,
    db: Session = Depends(get_db),
) -> LivroResponse:
    """Busca um livro/projeto por ID, retornando 404 RFC 9457 se não encontrado."""
    livro = db.get(ProjectModel, project_id)
    if not livro:
        raise DomainNotFoundException(
            detail=f"Livro / Projeto com identificador {project_id} não foi encontrado."
        )

    return LivroResponse(
        livro_id=livro.id,
        ISBN=livro.isbn,
        titulo=livro.titulo,
        autor=livro.autor,
        editora=livro.editora,
        publicacao=livro.publicacao,
        categoria=CategoriaLivroEnum(livro.categoria),
        exemplar=livro.exemplar,
        num_paginas=livro.num_paginas,
        qtd_emprestimos=livro.qtd_emprestimos,
        dt_cadastro=livro.dt_cadastro,
        status=StatusLivroEnum(livro.status),
    )


@router.post(
    "/projects",
    response_model=LivroResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Adicionar livro / projeto (ADMIN)",
)
@router.post(
    "/lib/acervo",
    response_model=LivroResponse,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
def create_project(
    payload: CreateLivro,
    current_user: UserModel = Depends(require_roles("ADMIN")),
    db: Session = Depends(get_db),
) -> LivroResponse:
    """
    Adiciona um novo livro ao acervo.
    Operação restrita a usuários com perfil ADMIN.
    Valida duplicidade de ISBN retornando HTTP 409 Conflict.
    """
    existing_isbn = db.scalar(select(ProjectModel).where(ProjectModel.isbn == payload.ISBN))
    if existing_isbn:
        raise DomainConflictException(
            detail=f"Já existe uma obra cadastrada no acervo com o ISBN '{payload.ISBN}'."
        )

    new_livro = LivroModel(
        isbn=payload.ISBN,
        titulo=payload.titulo,
        autor=payload.autor,
        editora=payload.editora,
        publicacao=payload.publicacao,
        categoria=payload.categoria.value,
        exemplar=payload.exemplar,
        num_paginas=payload.num_paginas,
        qtd_emprestimos=0,
        status=payload.status.value,
        dt_cadastro=datetime.utcnow(),
    )

    db.add(new_livro)
    db.commit()
    db.refresh(new_livro)

    return LivroResponse(
        livro_id=new_livro.id,
        ISBN=new_livro.isbn,
        titulo=new_livro.titulo,
        autor=new_livro.autor,
        editora=new_livro.editora,
        publicacao=new_livro.publicacao,
        categoria=CategoriaLivroEnum(new_livro.categoria),
        exemplar=new_livro.exemplar,
        num_paginas=new_livro.num_paginas,
        qtd_emprestimos=new_livro.qtd_emprestimos,
        dt_cadastro=new_livro.dt_cadastro,
        status=StatusLivroEnum(new_livro.status),
    )


@router.patch(
    "/projects/{project_id}",
    response_model=LivroResponse,
    status_code=status.HTTP_200_OK,
    summary="Atualizar livro / projeto (ADMIN)",
)
@router.patch(
    "/lib/acervo/{project_id}",
    response_model=LivroResponse,
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
def update_project(
    project_id: int,
    payload: UpdateLivro,
    current_user: UserModel = Depends(require_roles("ADMIN")),
    db: Session = Depends(get_db),
) -> LivroResponse:
    """Atualização parcial de atributos do livro no acervo. Restrito a ADMIN."""
    livro = db.get(ProjectModel, project_id)
    if not livro:
        raise DomainNotFoundException(
            detail=f"Livro / Projeto com identificador {project_id} não foi encontrado."
        )

    if payload.titulo is not None:
        livro.titulo = payload.titulo
    if payload.autor is not None:
        livro.autor = payload.autor
    if payload.editora is not None:
        livro.editora = payload.editora
    if payload.publicacao is not None:
        livro.publicacao = payload.publicacao
    if payload.categoria is not None:
        livro.categoria = payload.categoria.value
    if payload.num_paginas is not None:
        livro.num_paginas = payload.num_paginas
    if payload.status is not None:
        livro.status = payload.status.value

    db.commit()
    db.refresh(livro)

    return LivroResponse(
        livro_id=livro.id,
        ISBN=livro.isbn,
        titulo=livro.titulo,
        autor=livro.autor,
        editora=livro.editora,
        publicacao=livro.publicacao,
        categoria=CategoriaLivroEnum(livro.categoria),
        exemplar=livro.exemplar,
        num_paginas=livro.num_paginas,
        qtd_emprestimos=livro.qtd_emprestimos,
        dt_cadastro=livro.dt_cadastro,
        status=StatusLivroEnum(livro.status),
    )


@router.delete(
    "/projects/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remover livro / projeto do acervo (ADMIN)",
)
@router.delete(
    "/lib/acervo/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    include_in_schema=False,
)
def delete_project(
    project_id: int,
    current_user: UserModel = Depends(require_roles("ADMIN")),
    db: Session = Depends(get_db),
) -> Response:
    """Exclui permanentemente um livro do acervo. Restrito a ADMIN."""
    livro = db.get(ProjectModel, project_id)
    if not livro:
        raise DomainNotFoundException(
            detail=f"Livro / Projeto com identificador {project_id} não foi encontrado."
        )

    db.delete(livro)
    db.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)
