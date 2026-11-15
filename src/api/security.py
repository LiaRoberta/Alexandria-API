"""security.py — Autenticação Stateless JWT, Hashing e Controle de Acesso RBAC.

Implementa funções para geração/validação de tokens JWT (HS256), hashing e
verificação de senhas com bcrypt, e as dependências FastAPI get_current_user
(HTTP 401 RFC 9457) e require_roles (HTTP 403 RFC 9457).
"""

from datetime import datetime, timedelta, timezone
from typing import Annotated, Callable, Optional
import bcrypt
import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.database import get_db
from api.exceptions import ForbiddenException, UnauthorizedException
from api.models import FuncionarioModel


# -----------------------------------------------------------------------------
# Configurações de Segurança e JWT
# -----------------------------------------------------------------------------
SECRET_KEY = "alexandria-jwt-super-secret-key-production-sdd-2026-sha256-compliance-token"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

# Esquema de autenticação Bearer com auto_error=False para controlar o formato 401 RFC 9457
http_bearer = HTTPBearer(auto_error=False)


# -----------------------------------------------------------------------------
# Funções de Hashing de Senha (bcrypt)
# -----------------------------------------------------------------------------
def hash_password(password: str) -> str:
    """Gera um hash bcrypt seguro para a senha fornecida."""
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Compara uma senha em texto puro com o hash bcrypt armazenado."""
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except Exception:
        return False


# -----------------------------------------------------------------------------
# Geração e Decodificação de Tokens JWT
# -----------------------------------------------------------------------------
def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Gera um token JWT assinado contendo as claims especificadas e tempo de expiração."""
    to_encode = data.copy()
    now_utc = datetime.now(timezone.utc)
    if expires_delta:
        expire = now_utc + expires_delta
    else:
        expire = now_utc + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire, "iat": now_utc})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Decodifica e valida a assinatura e expiração do token JWT."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise UnauthorizedException(detail="Token de acesso expirado. Realize login novamente.")
    except jwt.PyJWTError:
        raise UnauthorizedException(detail="Token de acesso inválido ou malformado.")


# -----------------------------------------------------------------------------
# Dependências FastAPI: Usuário Atual e Autorização RBAC
# -----------------------------------------------------------------------------
def get_current_user(
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(http_bearer)],
    db: Annotated[Session, Depends(get_db)],
) -> FuncionarioModel:
    """Valida o Bearer token e retorna a instância do funcionário autenticado."""
    if not credentials or not credentials.credentials:
        raise UnauthorizedException(
            detail="Cabeçalho de autorização 'Authorization: Bearer <token>' ausente ou vazio.",
        )

    token = credentials.credentials
    payload = decode_access_token(token)

    # O 'sub' deve conter o identificador numérico do funcionário
    funcionario_id = payload.get("sub")
    if not funcionario_id:
        raise UnauthorizedException(detail="Token inválido: identificador de usuário ausente.")

    try:
        user_id_int = int(funcionario_id)
    except (ValueError, TypeError):
        raise UnauthorizedException(detail="Token inválido: formato de identificador incorreto.")

    user = db.scalar(select(FuncionarioModel).where(FuncionarioModel.id == user_id_int))
    if not user:
        raise UnauthorizedException(detail="Usuário associado ao token não encontrado ou inativo.")

    return user


def require_roles(allowed_roles: list[str]) -> Callable:
    """Fábrica de dependência para autorização baseada em papéis (RBAC)."""
    allowed_roles_upper = [r.upper() for r in allowed_roles]

    def role_checker(
        current_user: Annotated[FuncionarioModel, Depends(get_current_user)],
    ) -> FuncionarioModel:
        user_role = str(current_user.role).upper()
        if user_role not in allowed_roles_upper:
            raise ForbiddenException(
                detail=(
                    f"Acesso negado: o perfil '{user_role}' não possui permissão para executar esta "
                    f"operação. Perfis autorizados: {allowed_roles}."
                ),
            )
        return current_user

    return role_checker
