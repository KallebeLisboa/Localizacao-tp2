"""Dependências do FastAPI: sessão do banco e controle de acesso."""

from typing import Annotated, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.security import decodificar_token
from app.database import get_db
from app.models import Usuario

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
# Mesma origem do token, mas sem exigir: usado em rotas públicas.
oauth2_opcional = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)

DbSession = Annotated[Session, Depends(get_db)]


def get_usuario_atual(
    token: Annotated[str, Depends(oauth2_scheme)], db: DbSession
) -> Usuario:
    """Resolve o usuário autenticado a partir do token Bearer.

    Raises:
        HTTPException: 401 se o token for inválido ou o usuário não existir
            ou estiver inativo.
    """
    nao_autorizado = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciais inválidas",
        headers={"WWW-Authenticate": "Bearer"},
    )
    sujeito = decodificar_token(token)
    if sujeito is None or not sujeito.isdigit():
        raise nao_autorizado
    usuario = db.get(Usuario, int(sujeito))
    if usuario is None or not usuario.ativo:
        raise nao_autorizado
    return usuario


UsuarioAtual = Annotated[Usuario, Depends(get_usuario_atual)]


def get_usuario_opcional(
    token: Annotated[Optional[str], Depends(oauth2_opcional)], db: DbSession
) -> Optional[Usuario]:
    """Usuário do token, se houver um válido; senão ``None``.

    Para rotas públicas que só querem saber quem está usando (ex.: registrar
    quem fez uma busca). Token ausente, inválido ou de usuário inativo não é
    erro: a requisição segue como anônima.
    """
    if token is None:
        return None
    sujeito = decodificar_token(token)
    if sujeito is None or not sujeito.isdigit():
        return None
    usuario = db.get(Usuario, int(sujeito))
    if usuario is None or not usuario.ativo:
        return None
    return usuario


UsuarioOpcional = Annotated[Optional[Usuario], Depends(get_usuario_opcional)]


def exigir_admin(usuario: UsuarioAtual) -> Usuario:
    """Só deixa passar administradores.

    Raises:
        HTTPException: 403 se o usuário autenticado não for admin.
    """
    if not usuario.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso restrito",
        )
    return usuario


AdminAtual = Annotated[Usuario, Depends(exigir_admin)]
