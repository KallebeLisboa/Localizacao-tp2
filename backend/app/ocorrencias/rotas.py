"""Rotas REST de ocorrências (US01 e US02).

Para publicar as rotas, ``app/main.py`` precisa de::

    from app.ocorrencias.rotas import router as ocorrencias_router
    app.include_router(ocorrencias_router)
"""

from datetime import datetime
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import StatusOcorrencia
from app.ocorrencias.erros import ErroOcorrencia
from app.ocorrencias.filtros import (
    BUSCA_MAX,
    LIMITE_MAX,
    LIMITE_PADRAO,
    FiltroOcorrencias,
)
from app.ocorrencias.repositorio_sql import (
    CatalogoCategoriasSQL,
    PerimetrosSQL,
    RegistroPesquisasSQL,
    RepositorioSQL,
)
from app.ocorrencias.schemas import DetalheOcorrencia, OcorrenciaEntrada, ResumoMapa
from app.ocorrencias.servico import ServicoOcorrencias

from app.api.deps import UsuarioAtual, UsuarioOpcional

router = APIRouter(prefix="/ocorrencias", tags=["Ocorrências"])


def usuario_atual_id(usuario: UsuarioAtual) -> int:
    """Identifica o usuário autenticado a partir do token JWT."""
    return usuario.id


def usuario_opcional_id(usuario: UsuarioOpcional) -> Optional[int]:
    """Usuário do token, se houver; ``None`` para consultas anônimas."""
    return None if usuario is None else usuario.id


def obter_servico(db: Annotated[Session, Depends(get_db)]) -> ServicoOcorrencias:
    """Monta o serviço com os adaptadores do banco."""
    return ServicoOcorrencias(
        RepositorioSQL(db),
        CatalogoCategoriasSQL(db),
        PerimetrosSQL(db),
        pesquisas=RegistroPesquisasSQL(db),
    )


Servico = Annotated[ServicoOcorrencias, Depends(obter_servico)]


def _http(erro: ErroOcorrencia) -> HTTPException:
    """Converte um erro de domínio em resposta HTTP."""
    return HTTPException(
        status_code=erro.status_http,
        detail={"codigo": erro.codigo, "mensagem": str(erro)},
    )


class PaginaResumo(BaseModel):
    """Página de marcadores do mapa."""

    itens: list[ResumoMapa]
    proximo_offset: Optional[int]


@router.post("", status_code=201, response_model=DetalheOcorrencia)
def registrar(
    entrada: OcorrenciaEntrada,
    servico: Servico,
    usuario_id: Annotated[Optional[int], Depends(usuario_atual_id)],
) -> DetalheOcorrencia:
    """Registra uma ocorrência georreferenciada (US01)."""
    try:
        oc = servico.registrar(usuario_id, entrada)
    except ErroOcorrencia as erro:
        raise _http(erro) from erro
    return DetalheOcorrencia.de(oc)


@router.get("", response_model=PaginaResumo)
def listar(
    servico: Servico,
    usuario_id: Annotated[Optional[int], Depends(usuario_opcional_id)],
    busca: Annotated[Optional[str], Query(max_length=BUSCA_MAX)] = None,
    categorias: Annotated[Optional[list[int]], Query()] = None,
    status: Annotated[Optional[list[StatusOcorrencia]], Query()] = None,
    inicio: Optional[datetime] = None,
    fim: Optional[datetime] = None,
    sul: Optional[float] = None,
    oeste: Optional[float] = None,
    norte: Optional[float] = None,
    leste: Optional[float] = None,
    limite: Annotated[int, Query(ge=1, le=LIMITE_MAX)] = LIMITE_PADRAO,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PaginaResumo:
    """Lista marcadores do mapa com filtros combinados (US02).

    Sem ``status``, retorna apenas ocorrências ativas. Datas exigem fuso;
    o intervalo é ``[inicio, fim)``. O retângulo exige as quatro bordas.
    ``busca`` procura o texto no título e na descrição, sem diferenciar
    maiúsculas, e é gravada para o relatório gerencial (US06) junto com o
    usuário, se houver token válido.
    """
    valores = {
        "categorias": categorias,
        "status": status,
        "inicio": inicio,
        "fim": fim,
        "sul": sul,
        "oeste": oeste,
        "norte": norte,
        "leste": leste,
        "busca": busca,
        "limite": limite,
        "offset": offset,
    }
    try:
        filtro = FiltroOcorrencias.model_validate(
            {k: v for k, v in valores.items() if v is not None}
        )
    except ValidationError as exc:
        erros = exc.errors(include_url=False, include_context=False)
        raise RequestValidationError(erros) from exc
    pagina = servico.consultar(filtro, usuario_id=usuario_id)
    return PaginaResumo(
        itens=[ResumoMapa.de(oc) for oc in pagina.itens],
        proximo_offset=pagina.proximo_offset,
    )


@router.get("/{ocorrencia_id}", response_model=DetalheOcorrencia)
def detalhar(ocorrencia_id: int, servico: Servico) -> DetalheOcorrencia:
    """Retorna o detalhe de uma ocorrência (US02)."""
    try:
        oc = servico.detalhar(ocorrencia_id)
    except ErroOcorrencia as erro:
        raise _http(erro) from erro
    return DetalheOcorrencia.de(oc)
