"""Padrões sazonais e locais de maior reincidência, com fonte falsa (US04)."""

import pytest

from app.core.exceptions import RecursoNaoEncontrado
from app.estatisticas.schemas import Agrupamento, FiltroEstatisticas
from app.estatisticas.servico import GrupoReincidencia, ServicoEstatisticas
from app.models import StatusOcorrencia as S

from .fakes import FonteFalsa

A = Agrupamento


def sazonalidade(por, sazonal=None, **filtro):
    fonte = FonteFalsa(sazonal=sazonal)
    return ServicoEstatisticas(fonte).sazonalidade(FiltroEstatisticas(**filtro), por)


# ---------- Sazonalidade ----------


def test_por_mes_traz_os_doze_meses_com_rotulo():
    r = sazonalidade(A.MES, {3: {S.REGISTRADO: 2}, 12: {S.RESOLVIDO: 1}})
    assert [i.chave for i in r.itens] == list(range(1, 13))
    assert [i.rotulo for i in r.itens][:3] == ["jan", "fev", "mar"]
    assert r.itens[2].total == 2 and r.itens[11].resolvidas == 1
    assert sum(i.total for i in r.itens) == 3


def test_por_dia_da_semana_comeca_na_segunda():
    r = sazonalidade(A.DIA_SEMANA, {7: {S.REGISTRADO: 4}})
    assert [(i.chave, i.rotulo) for i in r.itens] == [
        (1, "seg"),
        (2, "ter"),
        (3, "qua"),
        (4, "qui"),
        (5, "sex"),
        (6, "sáb"),
        (7, "dom"),
    ]
    assert r.itens[6].pendentes == 4


def test_por_hora_traz_as_24_horas():
    r = sazonalidade(A.HORA, {0: {S.REGISTRADO: 1}, 23: {S.RESOLVIDO: 1}})
    assert [i.rotulo for i in r.itens][::6] == ["00h", "06h", "12h", "18h"]
    assert (r.itens[0].total, r.itens[23].total, len(r.itens)) == (1, 1, 24)


def test_informa_agrupamento_e_fuso():
    r = sazonalidade(A.HORA)
    assert (r.por, r.fuso) == (A.HORA, "America/Sao_Paulo")


def test_sazonalidade_valida_a_regiao():
    with pytest.raises(RecursoNaoEncontrado):
        sazonalidade(A.MES, regiao_id=99)


# ---------- Reincidência ----------


def test_reincidencia_devolve_os_grupos_na_ordem_da_fonte():
    grupos = [
        GrupoReincidencia(-15.7801234567, -47.8809876543, {S.REGISTRADO: 3}),
        GrupoReincidencia(-15.8, -47.9, {S.RESOLVIDO: 1, S.EM_ANALISE: 1}),
    ]
    fonte = FonteFalsa(reincidencia=grupos)
    r = ServicoEstatisticas(fonte).reincidencia(
        FiltroEstatisticas(), celula_m=500, minimo=2, limite=10
    )
    assert (r.celula_m, r.minimo) == (500, 2)
    primeiro = r.pontos[0]
    assert (primeiro.latitude, primeiro.longitude) == (-15.780123, -47.880988)
    assert (primeiro.total, primeiro.pendentes) == (3, 3)
    assert (r.pontos[1].resolvidas, r.pontos[1].pendentes) == (1, 1)


def test_reincidencia_repassa_os_parametros():
    fonte = FonteFalsa()
    filtro = FiltroEstatisticas(categorias=[1])
    ServicoEstatisticas(fonte).reincidencia(filtro, celula_m=300, minimo=4, limite=5)
    assert fonte.chamadas == [("reincidencia", filtro, 300, 4, 5)]


def test_reincidencia_valida_a_regiao():
    with pytest.raises(RecursoNaoEncontrado):
        ServicoEstatisticas(FonteFalsa()).reincidencia(
            FiltroEstatisticas(regiao_id=99), celula_m=500, minimo=2, limite=10
        )
