"""
Módulo de Exceções de Domínio e Tratamento de Erros Semântico (RFC 9457).

Implementa:
- Hierarquia de exceções de domínio padronizadas (DomainException e subclasses)
- Handlers globais para FastAPI/Starlette que erradicam o formato padrão {"detail": "..."}
- Respostas estritamente aderentes ao RFC 9457 (Problem Details) com Content-Type application/problem+json
"""

from typing import Any, Optional
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.api.schemas import ApiError, InvalidParam


# ==============================================================================
# URIS CANÔNICAS DE ERRO (STYLEGUIDE.MD - SEÇÃO 3.1)
# ==============================================================================

ERROR_TYPE_MAP = {
    400: "https://api.taskflow.dev/errors/bad-request",
    401: "https://api.taskflow.dev/errors/unauthorized",
    403: "https://api.taskflow.dev/errors/forbidden",
    404: "https://api.taskflow.dev/errors/not-found",
    409: "https://api.taskflow.dev/errors/conflict",
    422: "https://api.taskflow.dev/errors/validation-error",
    500: "https://api.taskflow.dev/errors/internal-error",
}

ERROR_TITLE_MAP = {
    400: "Bad Request",
    401: "Unauthorized",
    403: "Forbidden",
    404: "Not Found",
    409: "Conflict",
    422: "Unprocessable Entity",
    500: "Internal Server Error",
}


# ==============================================================================
# FORMATADOR PADRONIZADO RFC 9457
# ==============================================================================

def create_problem_response(
    status_code: int,
    detail: str,
    title: Optional[str] = None,
    error_type: Optional[str] = None,
    instance: Optional[str] = None,
    invalid_params: Optional[list[InvalidParam | dict[str, str]]] = None,
    headers: Optional[dict[str, str]] = None,
) -> JSONResponse:
    """
    Constrói uma resposta HTTP no padrão RFC 9457 (Problem Details).
    Garante o cabeçalho 'Content-Type: application/problem+json' e a estrutura do schema ApiError.
    """
    resolved_type = error_type or ERROR_TYPE_MAP.get(status_code, "https://api.taskflow.dev/errors/internal-error")
    resolved_title = title or ERROR_TITLE_MAP.get(status_code, "HTTP Error")

    formatted_invalid_params: Optional[list[InvalidParam]] = None
    if invalid_params:
        formatted_invalid_params = [
            p if isinstance(p, InvalidParam) else InvalidParam(name=p["name"], reason=p["reason"])
            for p in invalid_params
        ]

    error_schema = ApiError(
        type=resolved_type,
        title=resolved_title,
        status=status_code,
        detail=detail,
        instance=instance,
        invalid_params=formatted_invalid_params,
    )

    response_headers = {"Content-Type": "application/problem+json"}
    if headers:
        response_headers.update(headers)

    return JSONResponse(
        status_code=status_code,
        content=error_schema.model_dump(by_alias=True, exclude_none=False if invalid_params else False),
        headers=response_headers,
    )


# ==============================================================================
# HIERARQUIA DE EXCEÇÕES DE DOMÍNIO
# ==============================================================================

class DomainException(Exception):
    """Exceção base de domínio para erros negociais e operacionais da aplicação."""

    def __init__(
        self,
        detail: str,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        title: Optional[str] = None,
        error_type: Optional[str] = None,
        invalid_params: Optional[list[dict[str, str] | InvalidParam]] = None,
        headers: Optional[dict[str, str]] = None,
    ):
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code
        self.title = title or ERROR_TITLE_MAP.get(status_code, "Domain Error")
        self.error_type = error_type or ERROR_TYPE_MAP.get(status_code)
        self.invalid_params = invalid_params
        self.headers = headers


class DomainBadRequestException(DomainException):
    """Exceção para requisições malformadas ou com sintaxe incorreta (HTTP 400)."""

    def __init__(
        self,
        detail: str = "A requisição possui sintaxe inválida ou parâmetros incorretos.",
        invalid_params: Optional[list[dict[str, str] | InvalidParam]] = None,
        headers: Optional[dict[str, str]] = None,
    ):
        super().__init__(
            detail=detail,
            status_code=status.HTTP_400_BAD_REQUEST,
            title="Bad Request",
            error_type="https://api.taskflow.dev/errors/bad-request",
            invalid_params=invalid_params,
            headers=headers,
        )


class DomainUnauthorizedException(DomainException):
    """Exceção para falha de autenticação ou token ausente/inválido/expirado (HTTP 401)."""

    def __init__(
        self,
        detail: str = "Autenticação requerida: token de acesso ausente, inválido ou expirado.",
        headers: Optional[dict[str, str]] = None,
    ):
        auth_headers = {"WWW-Authenticate": "Bearer"}
        if headers:
            auth_headers.update(headers)
        super().__init__(
            detail=detail,
            status_code=status.HTTP_401_UNAUTHORIZED,
            title="Unauthorized",
            error_type="https://api.taskflow.dev/errors/unauthorized",
            headers=auth_headers,
        )


class DomainForbiddenException(DomainException):
    """Exceção para autorização insuficiente / violação de papel RBAC (HTTP 403)."""

    def __init__(
        self,
        detail: str = "Acesso proibido: privilégios insuficientes para acessar este recurso.",
        headers: Optional[dict[str, str]] = None,
    ):
        super().__init__(
            detail=detail,
            status_code=status.HTTP_403_FORBIDDEN,
            title="Forbidden",
            error_type="https://api.taskflow.dev/errors/forbidden",
            headers=headers,
        )


class DomainNotFoundException(DomainException):
    """Exceção para recursos solicitados que não foram encontrados (HTTP 404)."""

    def __init__(
        self,
        detail: str = "O recurso solicitado não foi encontrado no servidor.",
        headers: Optional[dict[str, str]] = None,
    ):
        super().__init__(
            detail=detail,
            status_code=status.HTTP_404_NOT_FOUND,
            title="Not Found",
            error_type="https://api.taskflow.dev/errors/not-found",
            headers=headers,
        )


class DomainConflictException(DomainException):
    """Exceção para conflito de estado ou duplicidade de chave primária/única (HTTP 409)."""

    def __init__(
        self,
        detail: str = "Conflito: já existe um registro com os identificadores fornecidos.",
        headers: Optional[dict[str, str]] = None,
    ):
        super().__init__(
            detail=detail,
            status_code=status.HTTP_409_CONFLICT,
            title="Conflict",
            error_type="https://api.taskflow.dev/errors/conflict",
            headers=headers,
        )


class DomainValidationException(DomainException):
    """Exceção para violações de validação de dados em regras de negócio (HTTP 422)."""

    def __init__(
        self,
        detail: str = "Falha de validação dos dados fornecidos.",
        invalid_params: Optional[list[dict[str, str] | InvalidParam]] = None,
        headers: Optional[dict[str, str]] = None,
    ):
        super().__init__(
            detail=detail,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            title="Unprocessable Entity",
            error_type="https://api.taskflow.dev/errors/validation-error",
            invalid_params=invalid_params,
            headers=headers,
        )


# ==============================================================================
# HANDLERS GLOBAIS DE EXCEÇÃO PARA O FASTAPI
# ==============================================================================

async def domain_exception_handler(request: Request, exc: DomainException) -> JSONResponse:
    """Intercepta exceções customizadas do domínio e formata em RFC 9457."""
    return create_problem_response(
        status_code=exc.status_code,
        title=exc.title,
        detail=exc.detail,
        error_type=exc.error_type,
        instance=request.url.path,
        invalid_params=exc.invalid_params,
        headers=exc.headers,
    )


async def request_validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """
    Intercepta falhas de validação de schemas do Pydantic v2 (RequestValidationError).
    Converte os erros nativos do FastAPI no array de 'invalidParams' do RFC 9457.
    """
    invalid_params: list[InvalidParam] = []

    for err in exc.errors():
        # Filtra localização interna do body/query para destacar o nome limpo do campo
        loc_parts = [str(x) for x in err.get("loc", []) if x not in ("body", "__root__")]
        field_name = " -> ".join(loc_parts) if loc_parts else "payload"
        reason = err.get("msg", "Valor inválido")

        invalid_params.append(
            InvalidParam(name=field_name, reason=reason)
        )

    return create_problem_response(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        title="Unprocessable Entity",
        detail="A validação dos parâmetros enviados na requisição falhou.",
        error_type="https://api.taskflow.dev/errors/validation-error",
        instance=request.url.path,
        invalid_params=invalid_params,
    )


async def http_exception_handler(
    request: Request,
    exc: StarletteHTTPException,
) -> JSONResponse:
    """
    Intercepta exceções HTTP genéricas do Starlette/FastAPI (ex.: rotas 404, 405).
    Substitui a resposta padrão {"detail": "..."} pela estrutura semântica RFC 9457.
    """
    status_code = exc.status_code
    detail = str(exc.detail) if exc.detail else ERROR_TITLE_MAP.get(status_code, "Ocorreu um erro HTTP.")

    # Trata caso de mensagem de 401 ou 403 do FastAPI
    error_type = ERROR_TYPE_MAP.get(status_code, "https://api.taskflow.dev/errors/internal-error")
    title = ERROR_TITLE_MAP.get(status_code, "HTTP Error")

    return create_problem_response(
        status_code=status_code,
        title=title,
        detail=detail,
        error_type=error_type,
        instance=request.url.path,
        headers=exc.headers,
    )


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Intercepta exceções não tratadas (500), garantindo que nada escape ao RFC 9457."""
    return create_problem_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        title="Internal Server Error",
        detail=f"Ocorreu um erro interno inesperado no servidor: {str(exc)}",
        error_type="https://api.taskflow.dev/errors/internal-error",
        instance=request.url.path,
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Registra todos os exception handlers da RFC 9457 na instância do FastAPI."""
    app.add_exception_handler(DomainException, domain_exception_handler)
    app.add_exception_handler(DomainBadRequestException, domain_exception_handler)
    app.add_exception_handler(DomainUnauthorizedException, domain_exception_handler)
    app.add_exception_handler(DomainForbiddenException, domain_exception_handler)
    app.add_exception_handler(DomainNotFoundException, domain_exception_handler)
    app.add_exception_handler(DomainConflictException, domain_exception_handler)
    app.add_exception_handler(DomainValidationException, domain_exception_handler)
    app.add_exception_handler(RequestValidationError, request_validation_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(Exception, global_exception_handler)
