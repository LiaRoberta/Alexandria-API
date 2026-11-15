"""exceptions.py — Exceções de Domínio e Handlers Globais RFC 9457 (Problem Details).

Padroniza 100% das respostas de erro da Alexandria API no formato Problem Details
(RFC 9457), garantindo o cabeçalho 'application/problem+json' e o schema ApiError
para os status HTTP 400, 401, 403, 404, 409 e 422.
"""

from typing import Any, Optional
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


# -----------------------------------------------------------------------------
# Classe Base de Exceções da Alexandria API
# -----------------------------------------------------------------------------
class AlexandriaException(Exception):
    """Exceção base com metadados para formatação RFC 9457 (Problem Details)."""

    def __init__(
        self,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        title: str = "Erro Interno do Servidor",
        detail: str = "Ocorreu um erro inesperado no processamento da requisição.",
        type_uri: str = "https://api.alexandria.dev/errors/internal-error",
        invalid_params: Optional[list[dict[str, Any]]] = None,
    ):
        super().__init__(detail)
        self.status_code = status_code
        self.title = title
        self.detail = detail
        self.type_uri = type_uri
        self.invalid_params = invalid_params


# -----------------------------------------------------------------------------
# Exceções Semânticas Específicas
# -----------------------------------------------------------------------------
class BadRequestException(AlexandriaException):
    """Erro HTTP 400 — Requisição inválida ou parâmetros de consulta incorretos."""

    def __init__(
        self,
        detail: str = "Os parâmetros ou a estrutura da requisição são inválidos.",
        title: str = "Solicitação Incorreta",
        type_uri: str = "https://api.alexandria.dev/errors/bad-request",
        invalid_params: Optional[list[dict[str, Any]]] = None,
    ):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            title=title,
            detail=detail,
            type_uri=type_uri,
            invalid_params=invalid_params,
        )


class UnauthorizedException(AlexandriaException):
    """Erro HTTP 401 — Falha de autenticação ou ausência/expiração de token JWT."""

    def __init__(
        self,
        detail: str = "Credenciais ausentes, expiradas ou inválidas.",
        title: str = "Não Autorizado",
        type_uri: str = "https://api.alexandria.dev/errors/unauthorized",
    ):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            title=title,
            detail=detail,
            type_uri=type_uri,
        )


class ForbiddenException(AlexandriaException):
    """Erro HTTP 403 — Acesso negado por falta de permissão ou perfil RBAC insuficiente."""

    def __init__(
        self,
        detail: str = "Acesso negado: você não possui permissão para executar esta operação.",
        title: str = "Acesso Proibido",
        type_uri: str = "https://api.alexandria.dev/errors/forbidden",
    ):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            title=title,
            detail=detail,
            type_uri=type_uri,
        )


class NotFoundException(AlexandriaException):
    """Erro HTTP 404 — Recurso solicitado não foi localizado na base de dados."""

    def __init__(
        self,
        detail: str = "O recurso solicitado não foi encontrado.",
        title: str = "Recurso Não Encontrado",
        type_uri: str = "https://api.alexandria.dev/errors/not-found",
    ):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            title=title,
            detail=detail,
            type_uri=type_uri,
        )


class ConflictException(AlexandriaException):
    """Erro HTTP 409 — Conflito de integridade (duplicidade de ISBN/CPF, exemplar local, etc.)."""

    def __init__(
        self,
        detail: str = "Ocorreu um conflito com o estado atual do recurso.",
        title: str = "Conflito de Dados",
        type_uri: str = "https://api.alexandria.dev/errors/conflict",
    ):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            title=title,
            detail=detail,
            type_uri=type_uri,
        )


class ValidationException(AlexandriaException):
    """Erro HTTP 422 — Falha de validação sintática ou semântica nos campos de entrada."""

    def __init__(
        self,
        detail: str = "Um ou mais campos contêm erros de validação.",
        title: str = "Entidade Não Processável",
        type_uri: str = "https://api.alexandria.dev/errors/validation-error",
        invalid_params: Optional[list[dict[str, Any]]] = None,
    ):
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            title=title,
            detail=detail,
            type_uri=type_uri,
            invalid_params=invalid_params or [],
        )


# -----------------------------------------------------------------------------
# Handlers Globais FastAPI (application/problem+json)
# -----------------------------------------------------------------------------
async def alexandria_exception_handler(request: Request, exc: AlexandriaException) -> JSONResponse:
    """Serializa qualquer AlexandriaException no formato RFC 9457 (Problem Details)."""
    payload: dict[str, Any] = {
        "type": exc.type_uri,
        "title": exc.title,
        "status": exc.status_code,
        "detail": exc.detail,
        "instance": request.url.path,
    }
    if exc.invalid_params:
        payload["invalidParams"] = exc.invalid_params

    return JSONResponse(
        status_code=exc.status_code,
        content=payload,
        media_type="application/problem+json",
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Interrompe o formato padrão do FastAPI e converte erros Pydantic para RFC 9457."""
    invalid_params = []
    for err in exc.errors():
        loc = err.get("loc", ())
        # Obtém o último elemento da localização do campo (ex: 'titulo', 'ISBN')
        field_name = str(loc[-1]) if loc else "body"
        reason_msg = err.get("msg", "Valor inválido informado.")
        invalid_params.append({"name": field_name, "reason": reason_msg})

    payload = {
        "type": "https://api.alexandria.dev/errors/validation-error",
        "title": "Erro de Validação",
        "status": status.HTTP_422_UNPROCESSABLE_ENTITY,
        "detail": "Um ou mais campos contêm erros de validação sintática ou de schema.",
        "instance": request.url.path,
        "invalidParams": invalid_params,
    }

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=payload,
        media_type="application/problem+json",
    )


async def starlette_http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Intercepta exceções HTTP genéricas do framework e formata como Problem Details."""
    slug_map = {
        400: ("bad-request", "Solicitação Incorreta"),
        401: ("unauthorized", "Não Autorizado"),
        403: ("forbidden", "Acesso Proibido"),
        404: ("not-found", "Recurso Não Encontrado"),
        405: ("method-not-allowed", "Método Não Permitido"),
        409: ("conflict", "Conflito de Dados"),
        422: ("validation-error", "Entidade Não Processável"),
    }
    slug, title_default = slug_map.get(exc.status_code, ("http-error", "Erro HTTP"))
    detail_str = exc.detail if isinstance(exc.detail, str) else "Falha no processamento HTTP."

    payload = {
        "type": f"https://api.alexandria.dev/errors/{slug}",
        "title": title_default,
        "status": exc.status_code,
        "detail": detail_str,
        "instance": request.url.path,
    }

    return JSONResponse(
        status_code=exc.status_code,
        content=payload,
        media_type="application/problem+json",
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Registra os handlers globais de erro RFC 9457 na instância FastAPI da aplicação."""
    app.add_exception_handler(AlexandriaException, alexandria_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(StarletteHTTPException, starlette_http_exception_handler)
