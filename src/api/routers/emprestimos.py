"""routers/emprestimos.py — Endpoints da Coleção /api/v1/lib/emprestimos.

Controla as transações de empréstimo e devolução de livros, gerenciando
limite de exemplares por leitor, conflitos de disponibilidade e prevenção N+1.
"""

from datetime import datetime
import math
from typing import Optional
from fastapi import APIRouter, Depends, Path, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from api.database import get_db
from api.exceptions import ConflictException, NotFoundException, ValidationException
from api.models import EmprestimoModel, FuncionarioModel, LivroModel, UsuarioModel
from api.schemas import (
    CreateEmprestimoDTO,
    Emprestimo,
    EmprestimoListResponse,
    PageMeta,
    StatusEmprestimo,
    UpdateEmprestimoDTO,
)
from api.security import get_current_user

router = APIRouter(
    prefix="/api/v1/lib/emprestimos",
    tags=["emprestimos"],
)


@router.get(
    "",
    response_model=EmprestimoListResponse,
    status_code=status.HTTP_200_OK,
    summary="Listar Empréstimos",
    description="Listagem paginada de empréstimos com carregamento eagerly dos relacionamentos para evitar N+1.",
)
def listar_emprestimos(
    page: int = Query(default=1, ge=1, description="Número da página"),
    limit: int = Query(default=10, ge=1, le=50, description="Itens por página"),
    status_emp: Optional[StatusEmprestimo] = Query(default=None, alias="status", description="Filtro por status"),
    usuario_id: Optional[int] = Query(default=None, alias="usuario-id", description="Filtro por leitor"),
    livro_id: Optional[int] = Query(default=None, alias="livro-id", description="Filtro por livro"),
    db: Session = Depends(get_db),
    current_user: FuncionarioModel = Depends(get_current_user),
) -> EmprestimoListResponse:
    """Consulta lista de empréstimos com prevenção N+1 através de selectinload."""
    query = (
        select(EmprestimoModel)
        .options(
            selectinload(EmprestimoModel.livro),
            selectinload(EmprestimoModel.usuario),
            selectinload(EmprestimoModel.funcionario),
        )
    )

    if status_emp:
        query = query.where(EmprestimoModel.status == status_emp.value)
    if usuario_id:
        query = query.where(EmprestimoModel.usuario_id == usuario_id)
    if livro_id:
        query = query.where(EmprestimoModel.livro_id == livro_id)

    total_items = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    total_pages = math.ceil(total_items / limit) if total_items > 0 else 0
    has_next = page < total_pages

    offset_val = (page - 1) * limit
    emprestimos = db.scalars(
        query.order_by(EmprestimoModel.id.desc()).offset(offset_val).limit(limit)
    ).all()

    return EmprestimoListResponse(
        data=[Emprestimo.model_validate(e) for e in emprestimos],
        meta=PageMeta(
            page=page,
            limit=limit,
            totalItems=total_items,
            totalPages=total_pages,
            hasNext=has_next,
        ),
    )


@router.get(
    "/{emprestimo_id}",
    response_model=Emprestimo,
    status_code=status.HTTP_200_OK,
    summary="Selecionar Empréstimo",
    description="Recupera os detalhes de um empréstimo específico.",
)
def selecionar_emprestimo(
    emprestimo_id: int = Path(..., ge=1, description="ID do empréstimo"),
    db: Session = Depends(get_db),
    current_user: FuncionarioModel = Depends(get_current_user),
) -> Emprestimo:
    """Busca empréstimo por ID garantindo retorno semântico 404 em caso de ausência."""
    emprestimo = db.scalar(
        select(EmprestimoModel)
        .options(
            selectinload(EmprestimoModel.livro),
            selectinload(EmprestimoModel.usuario),
            selectinload(EmprestimoModel.funcionario),
        )
        .where(EmprestimoModel.id == emprestimo_id)
    )
    if not emprestimo:
        raise NotFoundException(
            detail="O empréstimo informado não existe.",
            title="Empréstimo Inexistente",
        )
    return Emprestimo.model_validate(emprestimo)


@router.post(
    "",
    response_model=Emprestimo,
    status_code=status.HTTP_201_CREATED,
    summary="Realizar Empréstimo",
    description="Registra uma nova retirada de livro, validando limite do leitor e regras de exemplar.",
)
def realizar_emprestimo(
    payload: CreateEmprestimoDTO,
    response: Response,
    db: Session = Depends(get_db),
    current_user: FuncionarioModel = Depends(get_current_user),
) -> Emprestimo:
    """Aplica as regras de negócio de empréstimo com transação ACID."""
    # 1. Validação de existência do Livro
    livro = db.scalar(select(LivroModel).where(LivroModel.id == payload.livro_id))
    if not livro:
        raise ValidationException(
            detail="O livro informado para empréstimo não foi localizado.",
            title="Erro de Validação",
            invalid_params=[{"name": "livro-id", "reason": "Livro com o ID informado não existe."}],
        )

    # 2. Validação de existência do Usuário
    usuario = db.scalar(select(UsuarioModel).where(UsuarioModel.id == payload.usuario_id))
    if not usuario:
        raise ValidationException(
            detail="O usuário leitor informado não foi localizado.",
            title="Erro de Validação",
            invalid_params=[{"name": "usuario-id", "reason": "Usuário com o ID informado não existe."}],
        )

    # 3. Regra de Negócio: Livro exemplar de consulta local não pode ser emprestado (409)
    if livro.exemplar:
        raise ConflictException(
            detail=f"O livro '{livro.titulo}' é um exemplar de consulta local exclusiva e não pode ser emprestado.",
            title="Livro Restrito a Consulta Local",
        )

    # 4. Regra de Negócio: Livro já emprestado não pode ter empréstimo concomitante (409)
    ativo = db.scalar(
        select(EmprestimoModel).where(
            EmprestimoModel.livro_id == payload.livro_id,
            EmprestimoModel.status == "Emprestado",
        )
    )
    if ativo:
        raise ConflictException(
            detail=f"O livro '{livro.titulo}' já possui um empréstimo ativo em andamento.",
            title="Livro Indisponível",
        )

    # 5. Regra de Negócio: Saldo de limite disponível do leitor (409)
    if usuario.limite_disp <= 0:
        raise ConflictException(
            detail=f"O leitor '{usuario.nome}' atingiu o limite máximo de livros retirados simultaneamente.",
            title="Limite de Empréstimos Atingido",
        )

    # 6. Efetivação da transação
    usuario.limite_disp -= 1
    livro.qtd_emprestimos += 1

    novo_emprestimo = EmprestimoModel(
        livro_id=payload.livro_id,
        usuario_id=payload.usuario_id,
        funcionario_id=current_user.id,
        status="Emprestado",
        dt_emprestimo=datetime.utcnow(),
        dt_vencimento=payload.dt_vencimento,
    )
    db.add(novo_emprestimo)
    db.commit()
    db.refresh(novo_emprestimo)

    response.headers["Location"] = f"/api/v1/lib/emprestimos/{novo_emprestimo.id}"
    return Emprestimo.model_validate(novo_emprestimo)


@router.patch(
    "/{emprestimo_id}",
    response_model=Emprestimo,
    status_code=status.HTTP_200_OK,
    summary="Atualizar Empréstimo (Devolução)",
    description="Atualiza a situação de um empréstimo, restaurando o limite de livros do leitor ao devolver.",
)
def atualizar_emprestimo(
    payload: UpdateEmprestimoDTO,
    emprestimo_id: int = Path(..., ge=1, description="ID do empréstimo"),
    db: Session = Depends(get_db),
    current_user: FuncionarioModel = Depends(get_current_user),
) -> Emprestimo:
    """Processa devolução ou atualização de status com restauração de cota do leitor."""
    emprestimo = db.scalar(
        select(EmprestimoModel).where(EmprestimoModel.id == emprestimo_id)
    )
    if not emprestimo:
        raise NotFoundException(
            detail="O empréstimo informado não existe.",
            title="Empréstimo Inexistente",
        )

    # Se estiver transitando para Devolvido, registrar data e restaurar limite do leitor (+1)
    if payload.status == StatusEmprestimo.DEVOLVIDO and emprestimo.status != "Devolvido":
        emprestimo.dt_devolucao = payload.dt_devolucao or datetime.utcnow()
        usuario = db.scalar(select(UsuarioModel).where(UsuarioModel.id == emprestimo.usuario_id))
        if usuario and usuario.limite_disp < 4:
            usuario.limite_disp += 1

    emprestimo.status = payload.status.value
    db.commit()
    db.refresh(emprestimo)
    return Emprestimo.model_validate(emprestimo)


@router.delete(
    "/{emprestimo_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remover Empréstimo",
    description="Exclui o registro de um empréstimo e restaura a cota do leitor se o empréstimo estiver ativo.",
)
def remover_emprestimo(
    emprestimo_id: int = Path(..., ge=1, description="ID do empréstimo"),
    db: Session = Depends(get_db),
    current_user: FuncionarioModel = Depends(get_current_user),
) -> Response:
    """Exclui o empréstimo da base de dados e restaura limite se aplicável."""
    emprestimo = db.scalar(
        select(EmprestimoModel).where(EmprestimoModel.id == emprestimo_id)
    )
    if not emprestimo:
        raise NotFoundException(
            detail="O empréstimo informado não existe.",
            title="Empréstimo Inexistente",
        )

    # Se excluído enquanto ativo, restaurar a cota do usuário
    if emprestimo.status == "Emprestado":
        usuario = db.scalar(select(UsuarioModel).where(UsuarioModel.id == emprestimo.usuario_id))
        if usuario and usuario.limite_disp < 4:
            usuario.limite_disp += 1

    db.delete(emprestimo)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
