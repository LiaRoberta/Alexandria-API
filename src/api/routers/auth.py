"""
Roteador de Autenticação JWT e Perfil do Usuário.

Implementa:
- POST /api/v1/auth/login: valida credenciais e emite token JWT HS256
- GET /api/v1/auth/me: retorna dados do usuário autenticado a partir do token
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.database import get_db
from src.api.exceptions import DomainUnauthorizedException
from src.api.models import UserModel
from src.api.schemas import (
    LoginRequestDTO,
    TokenResponseDTO,
    UserResponse,
    UserRoleEnum,
)
from src.api.security import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    create_access_token,
    get_current_user,
    verify_password,
)

router = APIRouter(prefix="/api/v1/auth", tags=["Autenticação"])


@router.post(
    "/login",
    response_model=TokenResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Autenticar usuário e emitir token JWT",
    description="Recebe e-mail e senha, valida as credenciais e retorna o token de acesso Bearer JWT.",
)
def login(
    payload: LoginRequestDTO,
    db: Session = Depends(get_db),
) -> TokenResponseDTO:
    """Valida credenciais do usuário e emite token JWT com claims sub, email e role."""
    user = db.scalar(select(UserModel).where(UserModel.email == payload.email))

    if not user or not verify_password(payload.password, user.hashed_password):
        raise DomainUnauthorizedException(
            detail="Credenciais inválidas: e-mail ou senha incorretos."
        )

    # Geração do JWT assinado com HS256
    token_claims = {
        "sub": str(user.id),
        "email": user.email,
        "role": user.role,
    }
    token = create_access_token(data=token_claims)

    return TokenResponseDTO(
        accessToken=token,
        tokenType="Bearer",
        expiresIn=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Obter perfil do usuário autenticado",
    description="Retorna informações cadastrais e papel RBAC do usuário autenticado via Bearer Token.",
)
def get_me(
    current_user: UserModel = Depends(get_current_user),
) -> UserResponse:
    """Retorna os dados cadastrais do usuário identificado pelo token de autorização."""
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        role=UserRoleEnum(current_user.role),
        createdAt=current_user.created_at,
    )
