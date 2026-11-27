"""Rota REST do relatório gerencial (US06), restrita a administradores."""

from datetime import datetime
from typing import Annotated, Literal, Optional

from fastapi import APIRouter, Depends, Query, Response
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from app.api.deps import AdminAtual, DbSession
from app.relatorios.exportacao import para_csv
from app.relatorios.repositorio_sql import RepositorioRelatorioSQL
from app.relatorios.schemas import (
    LIMITE_TERMOS_MAX,
    LIMITE_TERMOS_PADRAO,
    FiltroRelatorio,
    RelatorioGerencial,
)
from app.relatorios.servico import ServicoRelatorio

router = APIRouter(prefix="/relatorios", tags=["Relatórios (US06)"])


def obter_servico(db: DbSession) -> ServicoRelatorio:
    """Monta o serviço com as consultas no banco."""
    return ServicoRelatorio(RepositorioRelatorioSQL(db))


Servico = Annotated[ServicoRelatorio, Depends(obter_servico)]

_RESPOSTA_CSV = {
    200: {
        "description": "Relatório em JSON ou, com `formato=csv`, arquivo CSV.",
        "content": {"text/csv": {"schema": {"type": "string"}}},
    }
}


def _filtro(**valores) -> FiltroRelatorio:
    """Valida os parâmetros juntos (ex.: ``inicio`` antes de ``fim``)."""
    try:
        return FiltroRelatorio.model_validate(
            {k: v for k, v in valores.items() if v is not None}
        )
    except ValidationError as exc:
        erros = exc.errors(include_url=False, include_context=False)
        raise RequestValidationError(erros) from exc


@router.get("/gerencial", response_model=RelatorioGerencial, responses=_RESPOSTA_CSV)
def relatorio_gerencial(
    servico: Servico,
    _admin: AdminAtual,
    inicio: Optional[datetime] = None,
    fim: Optional[datetime] = None,
    limite_termos: Annotated[
        int, Query(ge=1, le=LIMITE_TERMOS_MAX)
    ] = LIMITE_TERMOS_PADRAO,
    formato: Literal["json", "csv"] = "json",
) -> RelatorioGerencial | Response:
    """Dados consolidados de uso: usuários, termos pesquisados e regiões.

    O período ``[inicio, fim)`` exige datas com fuso (ex.: ``...Z`` ou
    ``...-03:00``) e vale para novos usuários, ocorrências e pesquisas. Com
    ``formato=csv``, a resposta é um arquivo para download.
    """
    filtro = _filtro(inicio=inicio, fim=fim, limite_termos=limite_termos)
    relatorio = servico.gerar(filtro)
    if formato == "json":
        return relatorio
    nome = f"relatorio_gerencial_{relatorio.gerado_em:%Y%m%d_%H%M%S}.csv"
    return Response(
        # BOM no início: o Excel só reconhece os acentos em UTF-8 com ele.
        content=para_csv(relatorio).encode("utf-8-sig"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{nome}"'},
    )
