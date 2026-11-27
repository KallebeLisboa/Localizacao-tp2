"""Evolução no tempo, com fonte falsa (US04).

Os períodos seguem o horário de Brasília e o gráfico recebe todos eles,
inclusive os vazios (zero).
"""

from datetime import date, datetime, timedelta, timezone

import pytest

from app.core.exceptions import RequisicaoInvalida
from app.estatisticas.schemas import FiltroEstatisticas, Granularidade
from app.estatisticas.servico import MAX_PONTOS, ServicoEstatisticas
from app.models import StatusOcorrencia as S

from .fakes import FonteFalsa

BRT = timezone(timedelta(hours=-3))
G = Granularidade


def evolucao(granularidade=G.DIA, por_periodo=None, **filtro):
    fonte = FonteFalsa(por_periodo=por_periodo)
    resultado = ServicoEstatisticas(fonte).evolucao(
        FiltroEstatisticas(**filtro), granularidade
    )
    return resultado, fonte


def periodos(resultado):
    return [p.periodo for p in resultado.pontos]


def test_preenche_os_dias_sem_ocorrencias_com_zero():
    r, _ = evolucao(
        por_periodo={date(2026, 11, 2): {S.RESOLVIDO: 1, S.REGISTRADO: 2}},
        inicio=datetime(2026, 11, 1, tzinfo=BRT),
        fim=datetime(2026, 11, 4, tzinfo=BRT),
    )
    assert [(p.periodo, p.total, p.resolvidas, p.pendentes) for p in r.pontos] == [
        (date(2026, 11, 1), 0, 0, 0),
        (date(2026, 11, 2), 3, 1, 2),
        (date(2026, 11, 3), 0, 0, 0),
    ]


def test_inicio_usa_o_dia_no_horario_de_brasilia():
    # 02h UTC do dia 1 ainda é 23h do dia 31 em Brasília.
    r, _ = evolucao(
        inicio=datetime(2026, 11, 1, 2, tzinfo=timezone.utc),
        fim=datetime(2026, 11, 2, tzinfo=BRT),
    )
    assert periodos(r) == [date(2026, 10, 31), date(2026, 11, 1)]


def test_fim_exclusivo_nao_cria_periodo_extra():
    r, _ = evolucao(
        inicio=datetime(2026, 11, 1, tzinfo=BRT),
        fim=datetime(2026, 11, 2, tzinfo=BRT),
    )
    assert periodos(r) == [date(2026, 11, 1)]


def test_semanas_comecam_na_segunda_feira():
    r, _ = evolucao(
        G.SEMANA,
        inicio=datetime(2026, 11, 4, tzinfo=BRT),  # quarta-feira
        fim=datetime(2026, 11, 20, tzinfo=BRT),
    )
    assert periodos(r) == [date(2026, 11, 2), date(2026, 11, 9), date(2026, 11, 16)]


def test_meses_atravessando_a_virada_do_ano():
    r, _ = evolucao(
        G.MES,
        inicio=datetime(2026, 10, 15, tzinfo=BRT),
        fim=datetime(2027, 1, 10, tzinfo=BRT),
    )
    assert periodos(r) == [
        date(2026, 10, 1),
        date(2026, 11, 1),
        date(2026, 12, 1),
        date(2027, 1, 1),
    ]


def test_sem_periodo_usa_o_primeiro_e_o_ultimo_dado():
    r, _ = evolucao(
        G.MES,
        por_periodo={
            date(2026, 9, 1): {S.REGISTRADO: 1},
            date(2026, 11, 1): {S.RESOLVIDO: 2},
        },
    )
    assert [(p.periodo, p.total) for p in r.pontos] == [
        (date(2026, 9, 1), 1),
        (date(2026, 10, 1), 0),
        (date(2026, 11, 1), 2),
    ]


def test_sem_periodo_e_sem_dados_a_serie_fica_vazia():
    r, _ = evolucao()
    assert r.pontos == []


def test_so_inicio_e_sem_dados_traz_o_periodo_do_inicio():
    r, _ = evolucao(G.MES, inicio=datetime(2026, 11, 10, tzinfo=BRT))
    assert periodos(r) == [date(2026, 11, 1)]


def test_so_fim_usa_o_primeiro_dado_como_inicio():
    r, _ = evolucao(
        por_periodo={date(2026, 11, 2): {S.REGISTRADO: 1}},
        fim=datetime(2026, 11, 4, tzinfo=BRT),
    )
    assert periodos(r) == [date(2026, 11, 2), date(2026, 11, 3)]


def test_informa_granularidade_e_fuso():
    r, _ = evolucao(G.SEMANA)
    assert (r.granularidade, r.fuso) == (G.SEMANA, "America/Sao_Paulo")


def test_repassa_filtro_e_granularidade_para_a_fonte():
    r, fonte = evolucao(G.MES, regiao_id=2)
    _, filtro, granularidade = fonte.chamadas[0]
    assert (filtro.regiao_id, granularidade) == (2, G.MES)


def test_serie_longa_demais_pede_granularidade_maior():
    inicio = datetime(2026, 1, 1, tzinfo=BRT)
    with pytest.raises(RequisicaoInvalida, match="granularidade maior"):
        evolucao(inicio=inicio, fim=inicio + timedelta(days=MAX_PONTOS + 1))


def test_serie_no_limite_e_aceita():
    inicio = datetime(2026, 1, 1, tzinfo=BRT)
    r, _ = evolucao(inicio=inicio, fim=inicio + timedelta(days=MAX_PONTOS))
    assert len(r.pontos) == MAX_PONTOS
