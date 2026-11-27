"""Filtro, opções e modelos das estatísticas (US04)."""

import enum
from collections.abc import Mapping
from datetime import date
from typing import Annotated, Optional
from zoneinfo import ZoneInfo

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from app.models import StatusOcorrencia

#: Fuso usado para agrupar por dia, semana, mês e hora.
NOME_FUSO = "America/Sao_Paulo"
FUSO = ZoneInfo(NOME_FUSO)

#: Nome da linha das ocorrências fora de todas as regiões cadastradas.
FORA_DAS_REGIOES = "Fora das regiões cadastradas"

Categorias = Annotated[frozenset[int], Field(min_length=1)]


class FiltroEstatisticas(BaseModel):
    """Filtros aceitos por todas as rotas de estatísticas.

    Attributes:
        inicio: Data/hora inicial do registro, inclusiva, com fuso.
        fim: Data/hora final do registro, exclusiva, com fuso.
        regiao_id: Só ocorrências dentro desta região cadastrada.
        categorias: Só estas categorias; ``None`` = todas.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    inicio: Optional[AwareDatetime] = None
    fim: Optional[AwareDatetime] = None
    regiao_id: Optional[Annotated[int, Field(ge=1)]] = None
    categorias: Optional[Categorias] = None

    @model_validator(mode="after")
    def _validar_periodo(self) -> "FiltroEstatisticas":
        if self.inicio is not None and self.fim is not None and self.inicio >= self.fim:
            raise ValueError("inicio deve ser anterior a fim")
        return self


class Granularidade(str, enum.Enum):
    """Tamanho de cada período da evolução no tempo."""

    DIA = "dia"
    SEMANA = "semana"
    MES = "mes"


class Agrupamento(str, enum.Enum):
    """Como juntar as ocorrências na análise de sazonalidade."""

    MES = "mes"
    DIA_SEMANA = "dia_semana"
    HORA = "hora"


#: Contagem por status, como vem das consultas.
PorStatus = Mapping[StatusOcorrencia, int]


class Contagem(BaseModel):
    """Volume total e a divisão resolvidas × pendentes.

    Pendente = registrada ou em análise.
    """

    total: int
    resolvidas: int
    pendentes: int

    @staticmethod
    def campos(por_status: PorStatus) -> dict[str, int]:
        """Total, resolvidas e pendentes a partir da contagem por status."""
        resolvidas = por_status.get(StatusOcorrencia.RESOLVIDO, 0)
        pendentes = por_status.get(StatusOcorrencia.REGISTRADO, 0) + por_status.get(
            StatusOcorrencia.EM_ANALISE, 0
        )
        return {
            "total": resolvidas + pendentes,
            "resolvidas": resolvidas,
            "pendentes": pendentes,
        }

    @classmethod
    def de(cls, por_status: PorStatus) -> "Contagem":
        """Monta a contagem a partir da contagem por status."""
        return cls(**cls.campos(por_status))


class Resumo(Contagem):
    """Totais do período, com cada status e a taxa de resolução."""

    registradas: int
    em_analise: int
    taxa_resolucao: Optional[float] = Field(
        description="Fração resolvida (0 a 1, 4 casas); nula sem ocorrências."
    )

    @classmethod
    def de(cls, por_status: PorStatus) -> "Resumo":
        """Monta o resumo a partir da contagem por status."""
        campos = Contagem.campos(por_status)
        total = campos["total"]
        return cls(
            **campos,
            registradas=por_status.get(StatusOcorrencia.REGISTRADO, 0),
            em_analise=por_status.get(StatusOcorrencia.EM_ANALISE, 0),
            taxa_resolucao=(round(campos["resolvidas"] / total, 4) if total else None),
        )


class PontoEvolucao(Contagem):
    """Volume de um período (``periodo`` = primeiro dia, no fuso local)."""

    periodo: date


class Evolucao(BaseModel):
    """Série temporal, com todos os períodos do intervalo (vazios = zero)."""

    granularidade: Granularidade
    fuso: str = NOME_FUSO
    pontos: list[PontoEvolucao]


class EstatisticaRegiao(Contagem):
    """Volume numa região (``regiao_id`` nulo = fora de todas)."""

    regiao_id: Optional[int]
    regiao: str


class ItemSazonal(Contagem):
    """Volume num mês do ano, dia da semana ou hora do dia.

    Attributes:
        chave: Mês (1-12), dia da semana ISO (1 = segunda, 7 = domingo) ou
            hora (0-23).
        rotulo: Texto curto para o eixo do gráfico.
    """

    chave: int
    rotulo: str


class Sazonalidade(BaseModel):
    """Distribuição sazonal, com todas as chaves do agrupamento."""

    por: Agrupamento
    fuso: str = NOME_FUSO
    itens: list[ItemSazonal]


class PontoReincidencia(Contagem):
    """Local com várias ocorrências próximas (centro médio dos pontos)."""

    latitude: float
    longitude: float


class Reincidencia(BaseModel):
    """Locais de maior reincidência, do mais ao menos frequente."""

    celula_m: int
    minimo: int
    pontos: list[PontoReincidencia]
