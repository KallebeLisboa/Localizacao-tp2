"""Montagem do relatório gerencial (US06)."""

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Protocol

from app.relatorios.schemas import (
    FORA_DAS_REGIOES,
    ChamadosPorRegiao,
    FiltroRelatorio,
    RelatorioGerencial,
    ResumoUsuarios,
    TermoPesquisado,
    periodo_de,
)

Relogio = Callable[[], datetime]


def agora_utc() -> datetime:
    """Relógio padrão, sempre em UTC."""
    return datetime.now(timezone.utc)


class FonteRelatorio(Protocol):
    """Consultas de que o relatório depende.

    A implementação real é ``RepositorioRelatorioSQL``; os testes do serviço
    usam uma fonte falsa.
    """

    def resumo_usuarios(self, filtro: FiltroRelatorio) -> ResumoUsuarios:
        """Contagens de usuários."""

    def termos_mais_pesquisados(self, filtro: FiltroRelatorio) -> list[TermoPesquisado]:
        """Ranking de termos pesquisados, do mais ao menos frequente."""

    def chamados_por_regiao(self, filtro: FiltroRelatorio) -> list[ChamadosPorRegiao]:
        """Ocorrências por região, em qualquer ordem."""


def _ordem_das_regioes(item: ChamadosPorRegiao) -> tuple[bool, int, str]:
    """Maior total primeiro, empate em ordem alfabética, "fora" no fim."""
    return (item.regiao == FORA_DAS_REGIOES, -item.total, item.regiao)


class ServicoRelatorio:
    """Gera o relatório gerencial a partir de uma fonte de dados.

    Args:
        fonte: Consultas de agregação.
        relogio: Fonte de data/hora com fuso; padrão UTC.
    """

    def __init__(self, fonte: FonteRelatorio, relogio: Relogio = agora_utc) -> None:
        self._fonte = fonte
        self._relogio = relogio

    def gerar(self, filtro: FiltroRelatorio) -> RelatorioGerencial:
        """Consolida os dados de uso conforme o filtro.

        Raises:
            ValueError: Relógio configurado sem fuso horário.
        """
        momento = self._relogio()
        if momento.utcoffset() is None:
            raise ValueError("o relógio deve fornecer data/hora com fuso")
        return RelatorioGerencial(
            gerado_em=momento,
            periodo=periodo_de(filtro),
            usuarios=self._fonte.resumo_usuarios(filtro),
            termos_mais_pesquisados=self._fonte.termos_mais_pesquisados(filtro),
            chamados_por_regiao=sorted(
                self._fonte.chamados_por_regiao(filtro), key=_ordem_das_regioes
            ),
        )
