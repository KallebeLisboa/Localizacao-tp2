"""Filtro e modelos do relatório gerencial (US06)."""

from datetime import datetime
from typing import Annotated, Optional

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from app.schemas.comum import DataHoraUTC

LIMITE_TERMOS_PADRAO = 10
LIMITE_TERMOS_MAX = 50

#: Nome da linha que agrupa as ocorrências fora de todas as regiões.
FORA_DAS_REGIOES = "Fora das regiões cadastradas"


class FiltroRelatorio(BaseModel):
    """Parâmetros da consulta do relatório.

    O período vale para os dados com data (novos usuários, ocorrências e
    pesquisas) e é o intervalo ``[inicio, fim)``. Sem ``inicio``/``fim``, não
    há limite naquele lado.

    Attributes:
        inicio: Data/hora inicial, inclusiva, com fuso obrigatório.
        fim: Data/hora final, exclusiva, com fuso obrigatório.
        limite_termos: Quantos termos entram no ranking de pesquisas.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    inicio: Optional[AwareDatetime] = None
    fim: Optional[AwareDatetime] = None
    limite_termos: Annotated[int, Field(ge=1, le=LIMITE_TERMOS_MAX)] = (
        LIMITE_TERMOS_PADRAO
    )

    @model_validator(mode="after")
    def _validar_periodo(self) -> "FiltroRelatorio":
        if self.inicio is not None and self.fim is not None and self.inicio >= self.fim:
            raise ValueError("inicio deve ser anterior a fim")
        return self


class ResumoUsuarios(BaseModel):
    """Quantidade de usuários.

    Attributes:
        contas_ativas: Contas ativas hoje (não depende do período).
        contas_inativas: Contas inativadas hoje (não depende do período).
        novos_no_periodo: Contas criadas dentro do período.
        com_ocorrencia_no_periodo: Usuários que registraram ao menos uma
            ocorrência dentro do período.
    """

    contas_ativas: int
    contas_inativas: int
    novos_no_periodo: int
    com_ocorrencia_no_periodo: int


class TermoPesquisado(BaseModel):
    """Termo do ranking de pesquisas, já normalizado (minúsculas, sem
    espaços nas pontas)."""

    termo: str
    quantidade: int


class ChamadosPorRegiao(BaseModel):
    """Ocorrências de uma região no período, separadas por status.

    Se as regiões se sobrepõem, uma ocorrência conta em cada região que a
    contém.
    """

    regiao: str
    total: int
    registrado: int
    em_analise: int
    resolvido: int


class Periodo(BaseModel):
    """Período consultado (``None`` = sem limite naquele lado)."""

    inicio: Optional[DataHoraUTC]
    fim: Optional[DataHoraUTC]


class RelatorioGerencial(BaseModel):
    """Dados consolidados de uso do sistema."""

    gerado_em: DataHoraUTC
    periodo: Periodo
    usuarios: ResumoUsuarios
    termos_mais_pesquisados: list[TermoPesquisado]
    chamados_por_regiao: list[ChamadosPorRegiao]


def periodo_de(filtro: FiltroRelatorio) -> Periodo:
    """Período do relatório a partir do filtro."""
    inicio: Optional[datetime] = filtro.inicio
    fim: Optional[datetime] = filtro.fim
    return Periodo(inicio=inicio, fim=fim)
