"""
Módulo de Segurança, Criptografia, JWT e Controle de Acesso RBAC (Aula 08).

Implementa:
- Hashing e conferência de senhas com bcrypt
- Emissão e decodificação de tokens JWT no padrão HS256 com claims (sub, email, role, iat, exp)
- Dependência de autenticação get_current_user retornando HTTP 401 RFC 9457 em caso de falha
- Dependência de autorização require_roles / require_role retornando HTTP 403 RFC 9457 se o papel for insuficiente
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Optional, Sequence
import bcrypt
import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.database import get_db
from src.api.exceptions import (
    DomainForbiddenException,
    DomainUnauthorizedException,
)
from src.api.models import UserModel
from src.api.schemas import UserRoleEnum


# ==============================================================================
# CONFIGURAÇÕES DE CRIPTOGRAFIA E TOKENS JWT
# ==============================================================================

SECRET_KEY = os.getenv("SECRET_KEY", "fatec-alexandria-secret-jwt-key-taskflow-2026")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

# Esquema de autorização HTTP Bearer com auto_error=False para controle semântico RFC 9457
oauth2_scheme = HTTPBearer(auto_error=False)


# ==============================================================================
# HASHING E VERIFICAÇÃO DE SENHAS
# ==============================================================================

def hash_password(password: str) -> str:
    """Gera hash seguro da senha em texto plano com salt aleatório via bcrypt."""
    pwd_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Valida se a senha em texto plano confere com o hash armazenado."""
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except Exception:
        return False


# ==============================================================================
# GERAÇÃO E DECODIFICAÇÃO DE TOKENS JWT
# ==============================================================================

def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Cria e assina um novo token JWT com algoritmo HS256.
    Payload garantido: sub, email, role, iat, exp.
    """
    to_encode = data.copy()
    now = datetime.now(timezone.utc)

    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({
        "iat": now,
        "exp": expire,
    })

    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    """
    Decodifica e valida o token JWT.
    Levanta DomainUnauthorizedException (HTTP 401 RFC 9457) em caso de token expirado ou inválido.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise DomainUnauthorizedException(
            detail="O token de autenticação expirou. Faça login novamente para renovar seu acesso."
        )
    except jwt.InvalidTokenError:
        raise DomainUnauthorizedException(
            detail="Token de autenticação inválido ou corrompido."
        )


# ==============================================================================
# DEPENDÊNCIAS DE AUTENTICAÇÃO E RBAC PARA O FASTAPI
# ==============================================================================

def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> UserModel:
    """
    Dependência FastAPI que extrai, decodifica e valida o usuário a partir do cabeçalho
    'Authorization: Bearer <token>'.
    Retorna 401 RFC 9457 se o token não for fornecido, for inválido, estiver expirado
    ou o usuário correspondente não existir.
    """
    if credentials is None or not credentials.credentials:
        raise DomainUnauthorizedException(
            detail="Autenticação necessária: cabeçalho 'Authorization: Bearer <token>' ausente."
        )

    token = credentials.credentials
    payload = decode_access_token(token)

    user_sub = payload.get("sub")
    email = payload.get("email")

    if not user_sub and not email:
        raise DomainUnauthorizedException(
            detail="Token de autenticação com dados de identidade (claims) ausentes."
        )

    # Localiza o usuário no banco por email ou por ID
    query = select(UserModel)
    if email:
        query = query.where(UserModel.email == email)
    elif str(user_sub).isdigit():
        query = query.where(UserModel.id == int(user_sub))
    else:
        query = query.where(UserModel.email == str(user_sub))

    user = db.scalar(query)
    if not user:
        raise DomainUnauthorizedException(
            detail="Usuário associado ao token fornecido não foi encontrado no sistema."
        )

    return user


def require_roles(*allowed_roles: str | UserRoleEnum | Sequence[str | UserRoleEnum]):
    """
    Fábrica de dependência FastAPI para controle de acesso baseado em papéis (RBAC).
    Permite invocar:
        require_roles("ADMIN")
        require_roles("ADMIN", "MEMBER")
        require_roles(["ADMIN", "MEMBER"])
    Se o usuário autenticado não possuir uma das roles permitidas,
    levanta DomainForbiddenException (HTTP 403 RFC 9457).
    """
    # Normalização dos papéis permitidos para strings maiúsculas
    flattened_roles: list[str] = []
    for r in allowed_roles:
        if isinstance(r, (list, tuple, set)):
            flattened_roles.extend(
                str(x.value if hasattr(x, "value") else x).upper() for x in r
            )
        else:
            flattened_roles.append(
                str(r.value if hasattr(r, "value") else r).upper()
            )

    def role_verifier(current_user: UserModel = Depends(get_current_user)) -> UserModel:
        current_role = str(current_user.role).upper()
        if current_role not in flattened_roles:
            raise DomainForbiddenException(
                detail=(
                    f"Acesso negado: o papel '{current_role}' não possui permissão para executar esta operação. "
                    f"Papéis necessários: {', '.join(flattened_roles)}."
                )
            )
        return current_user

    return role_verifier


# Alias de conveniência no singular
require_role = require_roles
