"""
Roteador da Coleção de Tarefas e Empréstimos (Tasks / Empréstimos).

Implementa:
- GET /api/v1/tasks: listagem paginada com metadados PageMeta e filtros
- GET /api/v1/tasks/{id}: consulta unitária por identificador
- POST /api/v1/tasks: criação vinculada ao ORM, exigindo usuário autenticado (get_current_user)
- PATCH /api/v1/tasks/{id}: atualização parcial, exigindo usuário autenticado (get_current_user)
- DELETE /api/v1/tasks/{id}: exclusão restrita a administradores (require_roles('ADMIN'))
- Suporte simultâneo às rotas do contrato Alexandria: /api/v1/lib/emprestimos
"""

import math
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from src.api.database import get_db
from src.api.exceptions import DomainNotFoundException
from src.api.models import EmprestimoModel, LivroModel, TaskModel, UserModel
from src.api.schemas import (
    CreateEmprestimo,
    EmprestimoListResponse,
    EmprestimoResponse,
    PageMeta,
    StatusEmprestimoEnum,
    UpdateEmprestimo,
)
from src.api.security import get_current_user, require_roles

router = APIRouter(prefix="/api/v1", tags=["Tarefas & Empréstimos"])


# ==============================================================================
# ENDPOINTS DA COLEÇÃO /TASKS E /LIB/EMPRESTIMOS
# ==============================================================================

@router.get(
    "/tasks",
    response_model=EmprestimoListResponse,
    status_code=status.HTTP_200_OK,
    summary="Listar tarefas / empréstimos",
)
@router.get(
    "/lib/emprestimos",
    response_model=EmprestimoListResponse,
    status_code=status.HTTP_200_OK,
    summary="Listar empréstimos da biblioteca",
    include_in_schema=True,
)
def list_tasks(
    page: int = Query(1, ge=1, description="Número da página (1..N)"),
    limit: int = Query(10, ge=1, le=100, description="Registros por página"),
    search: Optional[str] = Query(None, description="Busca textual por status"),
    status_filter: Optional[StatusEmprestimoEnum] = Query(None, alias="status", description="Filtrar por status"),
    project_id: Optional[int] = Query(None, alias="projectId", description="Filtrar por ID do projeto / livro"),
    db: Session = Depends(get_db),
) -> EmprestimoListResponse:
    """Retorna listagem paginada de tarefas/empréstimos com eager loading dos modelos relacionados."""
    base_query = select(TaskModel)

    if status_filter:
        base_query = base_query.where(TaskModel.status == status_filter.value)
    if search:
        base_query = base_query.where(TaskModel.status.ilike(f"%{search}%"))
    if project_id:
        base_query = base_query.where(TaskModel.livro_id == project_id)

    # Contagem total
    count_stmt = select(func.count()).select_from(base_query.subquery())
    total_items = db.scalar(count_stmt) or 0

    total_pages = math.ceil(total_items / limit) if total_items > 0 else 0
    has_next = page < total_pages

    # Consulta paginada com eager loading prevenindo queries N+1
    stmt = (
        base_query.options(
            selectinload(TaskModel.livro),
            selectinload(TaskModel.usuario),
            selectinload(TaskModel.funcionario),
        )
        .offset((page - 1) * limit)
        .limit(limit)
    )
    items = db.scalars(stmt).all()

    response_items = [
        EmprestimoResponse(
            emprestimo_id=item.id,
            livro_id=item.livro_id,
            usuario_id=item.usuario_id or 1,
            funcionario_id=item.funcionario_id or 1,
            status=StatusEmprestimoEnum(item.status),
            dt_emprestimo=item.dt_emprestimo,
            dt_vencimento=item.dt_vencimento or datetime.utcnow(),
            dt_devolucao=item.dt_devolucao,
        )
        for item in items
    ]

    return EmprestimoListResponse(
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
    "/tasks/{task_id}",
    response_model=EmprestimoResponse,
    status_code=status.HTTP_200_OK,
    summary="Selecionar tarefa / empréstimo por ID",
)
@router.get(
    "/lib/emprestimos/{task_id}",
    response_model=EmprestimoResponse,
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
def get_task(
    task_id: int,
    db: Session = Depends(get_db),
) -> EmprestimoResponse:
    """Busca uma tarefa ou empréstimo por ID, retornando 404 RFC 9457 se inexistente."""
    stmt = (
        select(TaskModel)
        .options(
            selectinload(TaskModel.livro),
            selectinload(TaskModel.usuario),
            selectinload(TaskModel.funcionario),
        )
        .where(TaskModel.id == task_id)
    )
    task = db.scalar(stmt)

    if not task:
        raise DomainNotFoundException(detail=f"Tarefa com identificador {task_id} não encontrada.")

    return EmprestimoResponse(
        emprestimo_id=task.id,
        livro_id=task.livro_id,
        usuario_id=task.usuario_id or 1,
        funcionario_id=task.funcionario_id or 1,
        status=StatusEmprestimoEnum(task.status),
        dt_emprestimo=task.dt_emprestimo,
        dt_vencimento=task.dt_vencimento or datetime.utcnow(),
        dt_devolucao=task.dt_devolucao,
    )


@router.post(
    "/tasks",
    response_model=EmprestimoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Criar nova tarefa / realizar empréstimo",
)
@router.post(
    "/lib/emprestimos",
    response_model=EmprestimoResponse,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
def create_task(
    payload: CreateEmprestimo,
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EmprestimoResponse:
    """
    Cria uma nova tarefa / realiza empréstimo.
    Exige autenticação via Bearer JWT (get_current_user).
    """
    # Valida existência do livro/projeto associado
    livro = db.get(LivroModel, payload.livro_id)
    if not livro:
        raise DomainNotFoundException(
            detail=f"Livro / Projeto com identificador {payload.livro_id} não foi encontrado."
        )

    # Instanciação da entidade ORM
    new_task = EmprestimoModel(
        livro_id=payload.livro_id,
        usuario_id=payload.usuario_id,
        funcionario_id=payload.funcionario_id,
        status=StatusEmprestimoEnum.EMPRESTADO.value,
        dt_emprestimo=datetime.utcnow(),
        dt_vencimento=payload.dt_vencimento,
        dt_devolucao=None,
    )

    livro.qtd_emprestimos += 1
    db.add(new_task)
    db.commit()
    db.refresh(new_task)

    return EmprestimoResponse(
        emprestimo_id=new_task.id,
        livro_id=new_task.livro_id,
        usuario_id=new_task.usuario_id or 1,
        funcionario_id=new_task.funcionario_id or 1,
        status=StatusEmprestimoEnum(new_task.status),
        dt_emprestimo=new_task.dt_emprestimo,
        dt_vencimento=new_task.dt_vencimento or datetime.utcnow(),
        dt_devolucao=new_task.dt_devolucao,
    )


@router.patch(
    "/tasks/{task_id}",
    response_model=EmprestimoResponse,
    status_code=status.HTTP_200_OK,
    summary="Atualizar tarefa / empréstimo",
)
@router.patch(
    "/lib/emprestimos/{task_id}",
    response_model=EmprestimoResponse,
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
def update_task(
    task_id: int,
    payload: UpdateEmprestimo,
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EmprestimoResponse:
    """
    Atualiza status e devolução de uma tarefa/empréstimo existente.
    Exige autenticação via Bearer JWT (get_current_user).
    """
    task = db.get(TaskModel, task_id)
    if not task:
        raise DomainNotFoundException(detail=f"Tarefa com identificador {task_id} não encontrada.")

    if payload.status is not None:
        task.status = payload.status.value
        if payload.status == StatusEmprestimoEnum.DEVOLVIDO and not task.dt_devolucao:
            task.dt_devolucao = datetime.utcnow()

    if payload.dt_devolucao is not None:
        task.dt_devolucao = payload.dt_devolucao

    db.commit()
    db.refresh(task)

    return EmprestimoResponse(
        emprestimo_id=task.id,
        livro_id=task.livro_id,
        usuario_id=task.usuario_id or 1,
        funcionario_id=task.funcionario_id or 1,
        status=StatusEmprestimoEnum(task.status),
        dt_emprestimo=task.dt_emprestimo,
        dt_vencimento=task.dt_vencimento or datetime.utcnow(),
        dt_devolucao=task.dt_devolucao,
    )


@router.delete(
    "/tasks/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remover tarefa / empréstimo (ADMIN)",
)
@router.delete(
    "/lib/emprestimos/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    include_in_schema=False,
)
def delete_task(
    task_id: int,
    current_user: UserModel = Depends(require_roles("ADMIN")),
    db: Session = Depends(get_db),
) -> Response:
    """
    Remove uma tarefa ou empréstimo do sistema.
    Exige estritamente papel ADMIN (require_roles('ADMIN')). Usuários MEMBER recebem HTTP 403 Forbidden.
    """
    task = db.get(TaskModel, task_id)
    if not task:
        raise DomainNotFoundException(detail=f"Tarefa com identificador {task_id} não encontrada.")

    db.delete(task)
    db.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)
