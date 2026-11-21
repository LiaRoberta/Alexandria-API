"""routers/auth.py — Endpoints de Autenticação da Alexandria API.

Implementa POST /api/v1/auth/login para emissão de tokens JWT com verificação
de senha criptografada em bcrypt e respostas semânticas RFC 9457.
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import get_db
from exceptions import UnauthorizedException
from models import FuncionarioModel
from schemas import AuthResponse, FuncionarioRole, LoginRequestDTO, TokenResponseDTO
from security import ACCESS_TOKEN_EXPIRE_MINUTES, create_access_token, verify_password

router = APIRouter(
    prefix="/api/v1/auth",
    tags=["auth"],
)


@router.post(
    "/login",
    response_model=TokenResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Login de Funcionário",
    description="Autentica um membro da equipe e retorna um token de acesso Bearer JWT.",
)
def login(
    payload: LoginRequestDTO,
    db: Session = Depends(get_db),
) -> TokenResponseDTO:
    """Valida as credenciais do colaborador e emite o token JWT de autorização."""
    funcionario = db.scalar(
        select(FuncionarioModel).where(FuncionarioModel.email == payload.email)
    )

    if not funcionario or not verify_password(payload.password, funcionario.password_hash):
        raise UnauthorizedException(
            detail="Credenciais inválidas. Verifique seu e-mail e senha de acesso.",
        )

    # Gera token contendo identificador, email e papel funcional (RBAC)
    token_claims = {
        "sub": str(funcionario.id),
        "email": funcionario.email,
        "role": funcionario.role,
        "nome": funcionario.nome,
    }
    access_token = create_access_token(data=token_claims)

    return TokenResponseDTO(
        accessToken=access_token,
        tokenType="bearer",
        expiresIn=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=AuthResponse(
            id=funcionario.id,
            nome=funcionario.nome,
            email=funcionario.email,
            role=FuncionarioRole(funcionario.role),
        ),
    )
