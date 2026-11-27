"""Montagem das estatísticas do painel (US04)."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Optional, Protocol

from app.core.exceptions import RecursoNaoEncontrado, RequisicaoInvalida
from app.estatisticas.schemas import (
    FORA_DAS_REGIOES,
    FUSO,
    Agrupamento,
    EstatisticaRegiao,
    Evolucao,
    FiltroEstatisticas,
    Granularidade,
    ItemSazonal,
    PontoEvolucao,
    PontoReincidencia,
    PorStatus,
    Reincidencia,
    Resumo,
    Sazonalidade,
)

#: Máximo de períodos numa série (ex.: ~2 anos e 9 meses por dia).
MAX_PONTOS = 1000

_MESES = ["jan", "fev", "mar", "abr", "mai", "jun"]
_MESES += ["jul", "ago", "set", "out", "nov", "dez"]
_DIAS = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]

#: Chaves e rótulos de cada agrupamento sazonal, na ordem do gráfico.
_ROTULOS: dict[Agrupamento, list[tuple[int, str]]] = {
    Agrupamento.MES: list(enumerate(_MESES, start=1)),
    Agrupamento.DIA_SEMANA: list(enumerate(_DIAS, start=1)),
    Agrupamento.HORA: [(h, f"{h:02d}h") for h in range(24)],
}


class RegiaoNaoEncontrada(RecursoNaoEncontrado):
    """O filtro pede uma região que não está cadastrada (HTTP 404)."""


@dataclass(frozen=True)
class ContagemRegiao:
    """Contagem por status numa região (``regiao_id`` nulo = fora de todas)."""

    regiao_id: Optional[int]
    nome: str
    por_status: PorStatus


@dataclass(frozen=True)
class GrupoReincidencia:
    """Ocorrências próximas agrupadas (centro médio e contagem por status)."""

    latitude: float
    longitude: float
    por_status: PorStatus


class FonteEstatisticas(Protocol):
    """Consultas de que o painel depende.

    A implementação real é ``RepositorioEstatisticasSQL``; os testes do
    serviço usam uma fonte falsa.
    """

    def regiao_existe(self, regiao_id: int) -> bool:
        """Indica se a região está cadastrada."""

    def contar_por_status(self, filtro: FiltroEstatisticas) -> PorStatus:
        """Quantidade de ocorrências em cada status."""

    def contar_por_regiao(self, filtro: FiltroEstatisticas) -> list[ContagemRegiao]:
        """Contagem por status em cada região, mais a das de fora."""

    def contar_por_periodo(
        self, filtro: FiltroEstatisticas, granularidade: Granularidade
    ) -> Mapping[date, PorStatus]:
        """Contagem por status em cada período com ocorrências.

        A chave é o primeiro dia do período no fuso local (semana começa na
        segunda-feira).
        """

    def contar_sazonal(
        self, filtro: FiltroEstatisticas, por: Agrupamento
    ) -> Mapping[int, PorStatus]:
        """Contagem por status em cada mês, dia da semana ou hora (local)."""

    def agrupar_reincidencia(
        self, filtro: FiltroEstatisticas, celula_m: int, minimo: int, limite: int
    ) -> list[GrupoReincidencia]:
        """Grupos de ocorrências próximas, do maior para o menor."""


def _dia_local(instante: datetime) -> date:
    """Data do instante no horário de Brasília."""
    return instante.astimezone(FUSO).date()


def _inicio_do_periodo(dia: date, granularidade: Granularidade) -> date:
    """Primeiro dia do período que contém ``dia``."""
    if granularidade is Granularidade.SEMANA:
        return dia - timedelta(days=dia.weekday())
    if granularidade is Granularidade.MES:
        return dia.replace(day=1)
    return dia


def _proximo_periodo(inicio: date, granularidade: Granularidade) -> date:
    """Primeiro dia do período seguinte."""
    if granularidade is Granularidade.SEMANA:
        return inicio + timedelta(days=7)
    if granularidade is Granularidade.MES:
        ano, mes = divmod(inicio.month, 12)
        return inicio.replace(year=inicio.year + ano, month=mes + 1)
    return inicio + timedelta(days=1)


def _limites(
    filtro: FiltroEstatisticas, dados: Mapping[date, PorStatus]
) -> Optional[tuple[date, date]]:
    """Primeiro e último dia da série: o do filtro ou, sem ele, o dos dados."""
    primeiro = _dia_local(filtro.inicio) if filtro.inicio else None
    # ``fim`` é exclusivo: o último dia é o do instante logo antes dele.
    ultimo = _dia_local(filtro.fim - timedelta(microseconds=1)) if filtro.fim else None
    if dados:
        primeiro = primeiro or min(dados)
        ultimo = ultimo or max(dados)
    primeiro = primeiro or ultimo
    ultimo = ultimo or primeiro
    if primeiro is None or ultimo is None:
        return None
    return primeiro, ultimo


def _ordem_das_regioes(item: EstatisticaRegiao) -> tuple[bool, int, str]:
    """Maior total primeiro, empate em ordem alfabética, "fora" no fim."""
    return (item.regiao_id is None, -item.total, item.regiao)


class ServicoEstatisticas:
    """Calcula as estatísticas a partir de uma fonte de dados.

    Args:
        fonte: Consultas de contagem.
    """

    def __init__(self, fonte: FonteEstatisticas) -> None:
        self._fonte = fonte

    def _checar_regiao(self, filtro: FiltroEstatisticas) -> None:
        if filtro.regiao_id is not None and not self._fonte.regiao_existe(
            filtro.regiao_id
        ):
            raise RegiaoNaoEncontrada(f"região {filtro.regiao_id} não encontrada")

    def resumo(self, filtro: FiltroEstatisticas) -> Resumo:
        """Totais do filtro: resolvidas × pendentes e taxa de resolução.

        Raises:
            RegiaoNaoEncontrada: ``regiao_id`` não cadastrada.
        """
        self._checar_regiao(filtro)
        return Resumo.de(self._fonte.contar_por_status(filtro))

    def regioes(self, filtro: FiltroEstatisticas) -> list[EstatisticaRegiao]:
        """Resolvidas × pendentes em cada região (distribuição espacial).

        Raises:
            RegiaoNaoEncontrada: ``regiao_id`` não cadastrada.
        """
        self._checar_regiao(filtro)
        itens = [
            EstatisticaRegiao(
                regiao_id=c.regiao_id,
                regiao=c.nome if c.regiao_id is not None else FORA_DAS_REGIOES,
                **EstatisticaRegiao.campos(c.por_status),
            )
            for c in self._fonte.contar_por_regiao(filtro)
        ]
        return sorted(itens, key=_ordem_das_regioes)

    def evolucao(
        self, filtro: FiltroEstatisticas, granularidade: Granularidade
    ) -> Evolucao:
        """Série temporal com todos os períodos do intervalo.

        Períodos sem ocorrências entram com zero, para o gráfico não pular
        datas. Sem ``inicio``/``fim``, a série vai do primeiro ao último
        período com dados.

        Raises:
            RegiaoNaoEncontrada: ``regiao_id`` não cadastrada.
            RequisicaoInvalida: Mais de :data:`MAX_PONTOS` períodos.
        """
        self._checar_regiao(filtro)
        dados = self._fonte.contar_por_periodo(filtro, granularidade)
        limites = _limites(filtro, dados)
        pontos: list[PontoEvolucao] = []
        if limites is not None:
            atual = _inicio_do_periodo(limites[0], granularidade)
            fim = _inicio_do_periodo(limites[1], granularidade)
            while atual <= fim:
                if len(pontos) == MAX_PONTOS:
                    raise RequisicaoInvalida(
                        f"a série passaria de {MAX_PONTOS} períodos; "
                        "use uma granularidade maior ou um intervalo menor"
                    )
                pontos.append(
                    PontoEvolucao(
                        periodo=atual, **PontoEvolucao.campos(dados.get(atual, {}))
                    )
                )
                atual = _proximo_periodo(atual, granularidade)
        return Evolucao(granularidade=granularidade, pontos=pontos)

    def sazonalidade(
        self, filtro: FiltroEstatisticas, por: Agrupamento
    ) -> Sazonalidade:
        """Distribuição por mês do ano, dia da semana ou hora do dia.

        Todas as chaves aparecem, mesmo sem ocorrências.

        Raises:
            RegiaoNaoEncontrada: ``regiao_id`` não cadastrada.
        """
        self._checar_regiao(filtro)
        dados = self._fonte.contar_sazonal(filtro, por)
        itens = [
            ItemSazonal(
                chave=chave, rotulo=rotulo, **ItemSazonal.campos(dados.get(chave, {}))
            )
            for chave, rotulo in _ROTULOS[por]
        ]
        return Sazonalidade(por=por, itens=itens)

    def reincidencia(
        self, filtro: FiltroEstatisticas, celula_m: int, minimo: int, limite: int
    ) -> Reincidencia:
        """Locais com mais ocorrências próximas (para o mapa de calor).

        Args:
            filtro: Filtros comuns.
            celula_m: Lado da célula da grade, em metros.
            minimo: Ocorrências mínimas para um local entrar.
            limite: Quantos locais devolver.

        Raises:
            RegiaoNaoEncontrada: ``regiao_id`` não cadastrada.
        """
        self._checar_regiao(filtro)
        grupos = self._fonte.agrupar_reincidencia(filtro, celula_m, minimo, limite)
        pontos = [
            PontoReincidencia(
                latitude=round(g.latitude, 6),
                longitude=round(g.longitude, 6),
                **PontoReincidencia.campos(g.por_status),
            )
            for g in grupos
        ]
        return Reincidencia(celula_m=celula_m, minimo=minimo, pontos=pontos)
