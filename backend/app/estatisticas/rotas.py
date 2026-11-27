"""Rotas REST de estatísticas (US04): análise temporal e espacial.

As rotas são públicas e aceitam os mesmos filtros: período ``[inicio, fim)``
com fuso, ``regiao_id`` e ``categorias`` (pode repetir o parâmetro).
"""

from datetime import datetime
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from app.api.deps import DbSession
from app.estatisticas.repositorio_sql import RepositorioEstatisticasSQL
from app.estatisticas.schemas import (
    Agrupamento,
    EstatisticaRegiao,
    Evolucao,
    FiltroEstatisticas,
    Granularidade,
    Reincidencia,
    Resumo,
    Sazonalidade,
)
from app.estatisticas.servico import ServicoEstatisticas

router = APIRouter(prefix="/estatisticas", tags=["Estatísticas (US04)"])

#: Lado da célula da grade de reincidência, em metros.
CELULA_PADRAO, CELULA_MIN, CELULA_MAX = 500, 50, 50_000
#: Quantidade de locais devolvidos na reincidência.
LIMITE_PADRAO, LIMITE_MAX = 50, 500


def obter_servico(db: DbSession) -> ServicoEstatisticas:
    """Monta o serviço com as consultas no banco."""
    return ServicoEstatisticas(RepositorioEstatisticasSQL(db))


def obter_filtro(
    inicio: Optional[datetime] = None,
    fim: Optional[datetime] = None,
    regiao_id: Optional[int] = None,
    categorias: Annotated[Optional[list[int]], Query()] = None,
) -> FiltroEstatisticas:
    """Valida os filtros juntos (ex.: ``inicio`` antes de ``fim``)."""
    valores = {
        "inicio": inicio,
        "fim": fim,
        "regiao_id": regiao_id,
        "categorias": categorias,
    }
    try:
        return FiltroEstatisticas.model_validate(
            {k: v for k, v in valores.items() if v is not None}
        )
    except ValidationError as exc:
        erros = exc.errors(include_url=False, include_context=False)
        raise RequestValidationError(erros) from exc


Servico = Annotated[ServicoEstatisticas, Depends(obter_servico)]
Filtro = Annotated[FiltroEstatisticas, Depends(obter_filtro)]


@router.get("/resumo", response_model=Resumo)
def resumo(servico: Servico, filtro: Filtro) -> Resumo:
    """Totais por status, resolvidas × pendentes e taxa de resolução.

    ``taxa_resolucao`` é ``null`` quando não há ocorrências no filtro.
    """
    return servico.resumo(filtro)


@router.get("/evolucao", response_model=Evolucao)
def evolucao(
    servico: Servico,
    filtro: Filtro,
    granularidade: Granularidade = Granularidade.DIA,
) -> Evolucao:
    """Quantidade de ocorrências por dia, semana (segunda) ou mês.

    Períodos sem ocorrências aparecem com zero. Os períodos seguem o horário
    de Brasília. Séries com mais de 1000 pontos retornam 400.
    """
    return servico.evolucao(filtro, granularidade)


@router.get("/regioes", response_model=list[EstatisticaRegiao])
def regioes(servico: Servico, filtro: Filtro) -> list[EstatisticaRegiao]:
    """Resolvidas × pendentes em cada região cadastrada.

    Ordem: maior total primeiro; as ocorrências fora de todas as regiões
    ficam na última linha, com ``regiao_id`` nulo.
    """
    return servico.regioes(filtro)


@router.get("/sazonalidade", response_model=Sazonalidade)
def sazonalidade(
    servico: Servico,
    filtro: Filtro,
    por: Agrupamento = Agrupamento.MES,
) -> Sazonalidade:
    """Distribuição por mês do ano, dia da semana ou hora do dia.

    Todas as chaves aparecem (12 meses, 7 dias de segunda a domingo ou
    24 horas), mesmo sem ocorrências.
    """
    return servico.sazonalidade(filtro, por)


@router.get("/reincidencia", response_model=Reincidencia)
def reincidencia(
    servico: Servico,
    filtro: Filtro,
    celula_m: Annotated[int, Query(ge=CELULA_MIN, le=CELULA_MAX)] = CELULA_PADRAO,
    minimo: Annotated[int, Query(ge=1)] = 2,
    limite: Annotated[int, Query(ge=1, le=LIMITE_MAX)] = LIMITE_PADRAO,
) -> Reincidencia:
    """Locais com ocorrências repetidas, para o mapa de calor.

    Junta as ocorrências em células de ``celula_m`` metros e devolve as que
    têm pelo menos ``minimo`` ocorrências, da maior para a menor.
    """
    return servico.reincidencia(filtro, celula_m, minimo, limite)
