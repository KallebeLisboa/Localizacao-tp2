"""Rotas REST de acompanhamento e notificações (US03).

Para publicar as rotas, ``app/main.py`` precisa de::

    from app.notificacoes.rotas import router as notificacoes_router
    from app.notificacoes.rotas import router_admin as status_admin_router
    app.include_router(notificacoes_router)
    app.include_router(status_admin_router)
"""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import AdminAtual, UsuarioAtual
from app.database import get_db
from app.models import StatusOcorrencia
from app.notificacoes.erros import ErroNotificacao
from app.notificacoes.repositorio_sql import (
    FonteNotificacoesSQL,
    RegistroStatusSQL,
    RepositorioInscricoesSQL,
)
from app.notificacoes.schemas import (
    InscricaoEntrada,
    InscricaoSaida,
    MudancaStatusEntrada,
    NotificacaoSaida,
)
from app.notificacoes.servico import ServicoNotificacoes
from app.ocorrencias.repositorio_sql import CatalogoCategoriasSQL

LIMITE_PADRAO = 20
LIMITE_MAX = 100

router = APIRouter(prefix="/notificacoes", tags=["Notificações (US03)"])
router_admin = APIRouter(
    prefix="/admin/ocorrencias", tags=["Admin — Status de Ocorrências (US03)"]
)


def obter_servico(db: Annotated[Session, Depends(get_db)]) -> ServicoNotificacoes:
    """Monta o serviço com os adaptadores do banco."""
    return ServicoNotificacoes(
        RepositorioInscricoesSQL(db),
        RegistroStatusSQL(db),
        FonteNotificacoesSQL(db),
        CatalogoCategoriasSQL(db),
    )


Servico = Annotated[ServicoNotificacoes, Depends(obter_servico)]


def _http(erro: ErroNotificacao) -> HTTPException:
    """Converte um erro de domínio em resposta HTTP."""
    return HTTPException(
        status_code=erro.status_http,
        detail={"codigo": erro.codigo, "mensagem": str(erro)},
    )


class PaginaNotificacoesSaida(BaseModel):
    """Página de notificações."""

    itens: list[NotificacaoSaida]
    proximo_offset: Optional[int]


class StatusSaida(BaseModel):
    """Status resultante de uma mudança."""

    ocorrencia_id: int
    status: StatusOcorrencia


@router.post("/inscricoes", status_code=201, response_model=InscricaoSaida)
def inscrever(
    entrada: InscricaoEntrada, servico: Servico, usuario: UsuarioAtual
) -> InscricaoSaida:
    """Segue uma ocorrência ou assina alertas de uma zona (raio em metros)."""
    try:
        insc = servico.inscrever(usuario.id, entrada)
    except ErroNotificacao as erro:
        raise _http(erro) from erro
    return InscricaoSaida.de(insc)


@router.get("/inscricoes", response_model=list[InscricaoSaida])
def listar_inscricoes(servico: Servico, usuario: UsuarioAtual) -> list[InscricaoSaida]:
    """Lista as inscrições do usuário autenticado."""
    return [InscricaoSaida.de(i) for i in servico.listar_inscricoes(usuario.id)]


@router.delete("/inscricoes/{inscricao_id}", status_code=204)
def cancelar_inscricao(
    inscricao_id: int, servico: Servico, usuario: UsuarioAtual
) -> Response:
    """Cancela uma inscrição do usuário autenticado."""
    try:
        servico.cancelar(usuario.id, inscricao_id)
    except ErroNotificacao as erro:
        raise _http(erro) from erro
    return Response(status_code=204)


@router.get("", response_model=PaginaNotificacoesSaida)
def listar_notificacoes(
    servico: Servico,
    usuario: UsuarioAtual,
    limite: Annotated[int, Query(ge=1, le=LIMITE_MAX)] = LIMITE_PADRAO,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PaginaNotificacoesSaida:
    """Eventos de status das ocorrências seguidas ou das zonas assinadas."""
    pagina = servico.consultar(usuario.id, limite, offset)
    return PaginaNotificacoesSaida(
        itens=[NotificacaoSaida.de(n) for n in pagina.itens],
        proximo_offset=pagina.proximo_offset,
    )


@router_admin.patch("/{ocorrencia_id}/status", response_model=StatusSaida)
def alterar_status(
    ocorrencia_id: int,
    entrada: MudancaStatusEntrada,
    servico: Servico,
    _admin: AdminAtual,
) -> StatusSaida:
    """Avança o status (Registrado → Em análise → Resolvido) e gera o log."""
    try:
        novo = servico.alterar_status(ocorrencia_id, entrada.status)
    except ErroNotificacao as erro:
        raise _http(erro) from erro
    return StatusSaida(ocorrencia_id=ocorrencia_id, status=novo)
