"""Montagem do relatório gerencial com uma fonte de dados falsa (US06)."""

from datetime import datetime, timedelta, timezone

import pytest

from app.relatorios.schemas import (
    FORA_DAS_REGIOES,
    ChamadosPorRegiao,
    FiltroRelatorio,
    ResumoUsuarios,
    TermoPesquisado,
)
from app.relatorios.servico import ServicoRelatorio

AGORA = datetime(2026, 11, 23, 18, 0, tzinfo=timezone.utc)
USUARIOS = ResumoUsuarios(
    contas_ativas=8, contas_inativas=1, novos_no_periodo=3, com_ocorrencia_no_periodo=2
)


def regiao(nome, total):
    return ChamadosPorRegiao(
        regiao=nome, total=total, registrado=total, em_analise=0, resolvido=0
    )


class FonteFalsa:
    """Devolve dados prontos e guarda os filtros recebidos."""

    def __init__(self, termos=(), regioes=()):
        self.termos = list(termos)
        self.regioes = list(regioes)
        self.filtros = []

    def resumo_usuarios(self, filtro):
        self.filtros.append(("usuarios", filtro))
        return USUARIOS

    def termos_mais_pesquisados(self, filtro):
        self.filtros.append(("termos", filtro))
        return self.termos

    def chamados_por_regiao(self, filtro):
        self.filtros.append(("regioes", filtro))
        return self.regioes


def gerar(fonte, filtro=None, relogio=lambda: AGORA):
    return ServicoRelatorio(fonte, relogio=relogio).gerar(filtro or FiltroRelatorio())


def test_junta_os_tres_blocos_da_fonte():
    termos = [TermoPesquisado(termo="buraco", quantidade=4)]
    rel = gerar(FonteFalsa(termos=termos, regioes=[regiao("Asa Sul", 2)]))
    assert rel.usuarios == USUARIOS
    assert rel.termos_mais_pesquisados == termos
    assert [r.regiao for r in rel.chamados_por_regiao] == ["Asa Sul"]


def test_repassa_o_mesmo_filtro_para_todas_as_consultas():
    fonte = FonteFalsa()
    filtro = FiltroRelatorio(inicio=AGORA - timedelta(days=7), limite_termos=3)
    gerar(fonte, filtro)
    assert [nome for nome, _ in fonte.filtros] == ["usuarios", "termos", "regioes"]
    assert all(f is filtro for _, f in fonte.filtros)


def test_registra_quando_foi_gerado():
    assert gerar(FonteFalsa()).gerado_em == AGORA


def test_relogio_sem_fuso_e_erro_de_configuracao():
    with pytest.raises(ValueError, match="fuso"):
        gerar(FonteFalsa(), relogio=lambda: datetime(2026, 11, 23))


def test_informa_o_periodo_consultado():
    inicio, fim = AGORA - timedelta(days=30), AGORA
    rel = gerar(FonteFalsa(), FiltroRelatorio(inicio=inicio, fim=fim))
    assert (rel.periodo.inicio, rel.periodo.fim) == (inicio, fim)


def test_periodo_aberto_fica_sem_limites():
    rel = gerar(FonteFalsa())
    assert rel.periodo.inicio is None and rel.periodo.fim is None


def test_regioes_vem_da_maior_para_a_menor():
    regioes = [regiao("Guará", 1), regiao("Asa Norte", 5), regiao("Taguatinga", 3)]
    rel = gerar(FonteFalsa(regioes=regioes))
    assert [r.regiao for r in rel.chamados_por_regiao] == [
        "Asa Norte",
        "Taguatinga",
        "Guará",
    ]


def test_empate_de_regioes_em_ordem_alfabetica():
    regioes = [regiao("Taguatinga", 2), regiao("Asa Sul", 2)]
    rel = gerar(FonteFalsa(regioes=regioes))
    assert [r.regiao for r in rel.chamados_por_regiao] == ["Asa Sul", "Taguatinga"]


def test_ocorrencias_fora_das_regioes_ficam_sempre_no_fim():
    regioes = [regiao(FORA_DAS_REGIOES, 9), regiao("Asa Sul", 1)]
    rel = gerar(FonteFalsa(regioes=regioes))
    assert [r.regiao for r in rel.chamados_por_regiao] == ["Asa Sul", FORA_DAS_REGIOES]
