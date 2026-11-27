"""Exportação estruturada do relatório em CSV (US06)."""

import csv
import io
from datetime import datetime, timezone

import pytest

from app.relatorios.exportacao import CABECALHO, para_csv
from app.relatorios.schemas import (
    ChamadosPorRegiao,
    Periodo,
    RelatorioGerencial,
    ResumoUsuarios,
    TermoPesquisado,
)

GERADO = datetime(2026, 11, 23, 15, 30, tzinfo=timezone.utc)
INICIO = datetime(2026, 11, 1, tzinfo=timezone.utc)


def relatorio(termos=None, regioes=None, inicio=INICIO, fim=None):
    return RelatorioGerencial(
        gerado_em=GERADO,
        periodo=Periodo(inicio=inicio, fim=fim),
        usuarios=ResumoUsuarios(
            contas_ativas=10,
            contas_inativas=2,
            novos_no_periodo=4,
            com_ocorrencia_no_periodo=3,
        ),
        termos_mais_pesquisados=termos or [],
        chamados_por_regiao=regioes or [],
    )


def linhas(texto: str) -> list[list[str]]:
    return list(csv.reader(io.StringIO(texto), delimiter=";"))


def test_primeira_linha_e_o_cabecalho():
    assert linhas(para_csv(relatorio()))[0] == list(CABECALHO)
    assert CABECALHO == ("secao", "item", "metrica", "valor")


def test_usa_ponto_e_virgula_para_abrir_direto_no_excel_em_portugues():
    assert para_csv(relatorio()).splitlines()[0] == "secao;item;metrica;valor"


def test_traz_metadados_com_datas_em_utc():
    dados = linhas(para_csv(relatorio()))
    assert ["relatorio", "gerado_em", "", "2026-11-23T15:30:00Z"] in dados
    assert ["relatorio", "periodo_inicio", "", "2026-11-01T00:00:00Z"] in dados


def test_periodo_sem_limite_fica_vazio():
    dados = linhas(para_csv(relatorio(fim=None)))
    assert ["relatorio", "periodo_fim", "", ""] in dados


def test_traz_as_quatro_metricas_de_usuarios():
    dados = linhas(para_csv(relatorio()))
    assert ["usuarios", "", "contas_ativas", "10"] in dados
    assert ["usuarios", "", "contas_inativas", "2"] in dados
    assert ["usuarios", "", "novos_no_periodo", "4"] in dados
    assert ["usuarios", "", "com_ocorrencia_no_periodo", "3"] in dados


def test_traz_termos_na_ordem_do_ranking():
    termos = [
        TermoPesquisado(termo="buraco", quantidade=7),
        TermoPesquisado(termo="poste", quantidade=3),
    ]
    dados = [
        ln for ln in linhas(para_csv(relatorio(termos=termos))) if ln[0] == "termos"
    ]
    assert dados == [
        ["termos", "buraco", "quantidade", "7"],
        ["termos", "poste", "quantidade", "3"],
    ]


def test_traz_cada_regiao_com_total_e_status():
    regioes = [
        ChamadosPorRegiao(
            regiao="Asa Norte", total=5, registrado=2, em_analise=1, resolvido=2
        )
    ]
    dados = [
        ln for ln in linhas(para_csv(relatorio(regioes=regioes))) if ln[0] == "regioes"
    ]
    assert dados == [
        ["regioes", "Asa Norte", "total", "5"],
        ["regioes", "Asa Norte", "registrado", "2"],
        ["regioes", "Asa Norte", "em_analise", "1"],
        ["regioes", "Asa Norte", "resolvido", "2"],
    ]


def test_texto_com_ponto_e_virgula_e_aspas_nao_quebra_as_colunas():
    termos = [TermoPesquisado(termo='lixo; "entulho"', quantidade=1)]
    dados = [
        ln for ln in linhas(para_csv(relatorio(termos=termos))) if ln[0] == "termos"
    ]
    assert dados == [["termos", 'lixo; "entulho"', "quantidade", "1"]]


@pytest.mark.parametrize("perigoso", ["=1+1", "+cmd", "-2+3", "@SOMA(A1)"])
def test_neutraliza_formula_em_texto_digitado_por_usuario(perigoso):
    # Um termo pesquisado como "=..." viraria fórmula ao abrir no Excel.
    termos = [TermoPesquisado(termo=perigoso, quantidade=1)]
    dados = [
        ln for ln in linhas(para_csv(relatorio(termos=termos))) if ln[0] == "termos"
    ]
    assert dados[0][1] == "'" + perigoso


def test_relatorio_sem_termos_nem_regioes_ainda_exporta_o_resto():
    dados = linhas(para_csv(relatorio()))
    secoes = {ln[0] for ln in dados[1:]}
    assert secoes == {"relatorio", "usuarios"}
