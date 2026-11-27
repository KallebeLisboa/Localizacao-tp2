"""Sazonalidade e grade de reincidência no PostGIS (US04)."""

import pytest

from app.estatisticas.repositorio_sql import RepositorioEstatisticasSQL
from app.estatisticas.schemas import Agrupamento, FiltroEstatisticas
from app.models import StatusOcorrencia as S

from .conftest import NOVEMBRO, P1, P2


def repo(db_session):
    return RepositorioEstatisticasSQL(db_session)


def totais(contagens):
    return {chave: sum(por_status.values()) for chave, por_status in contagens.items()}


# ---------- Sazonalidade (horário de Brasília) ----------


def test_por_mes_do_ano(db_session, cenario):
    meses = repo(db_session).contar_sazonal(FiltroEstatisticas(), Agrupamento.MES)
    assert totais(meses) == {9: 1, 10: 1, 11: 4}


def test_por_dia_da_semana_iso(db_session, cenario):
    dias = repo(db_session).contar_sazonal(FiltroEstatisticas(), Agrupamento.DIA_SEMANA)
    # 1 = segunda ... 7 = domingo
    assert totais(dias) == {1: 2, 2: 1, 4: 1, 5: 1, 6: 1}


def test_por_hora_local(db_session, cenario):
    horas = repo(db_session).contar_sazonal(FiltroEstatisticas(), Agrupamento.HORA)
    # 23h30 de Brasília conta às 23h, não às 2h (UTC).
    assert totais(horas) == {8: 1, 9: 1, 10: 1, 12: 1, 14: 1, 23: 1}


def test_sazonalidade_separa_status_e_respeita_filtros(db_session, cenario):
    f = FiltroEstatisticas(**NOVEMBRO, regiao_id=cenario.asa_norte)
    meses = repo(db_session).contar_sazonal(f, Agrupamento.MES)
    assert meses == {11: {S.REGISTRADO: 1, S.RESOLVIDO: 1, S.EM_ANALISE: 1}}


# ---------- Reincidência ----------


def agrupar(db_session, filtro=None, celula_m=500, minimo=2, limite=10):
    return repo(db_session).agrupar_reincidencia(
        filtro or FiltroEstatisticas(), celula_m, minimo, limite
    )


def test_locais_com_mais_ocorrencias_primeiro(db_session, cenario):
    grupos = agrupar(db_session)
    assert [sum(g.por_status.values()) for g in grupos] == [3, 2]
    assert (grupos[0].latitude, grupos[0].longitude) == pytest.approx(P1)
    assert (grupos[1].latitude, grupos[1].longitude) == pytest.approx(P2)
    assert dict(grupos[0].por_status) == {
        S.REGISTRADO: 1,
        S.RESOLVIDO: 1,
        S.EM_ANALISE: 1,
    }


def test_minimo_de_ocorrencias_por_local(db_session, cenario):
    assert len(agrupar(db_session, minimo=3)) == 1
    assert len(agrupar(db_session, minimo=1)) == 3  # inclui o ponto isolado


def test_limite_de_locais(db_session, cenario):
    assert len(agrupar(db_session, limite=1)) == 1


def test_reincidencia_respeita_os_filtros(db_session, cenario):
    so_asa_sul = FiltroEstatisticas(regiao_id=cenario.asa_sul)
    grupos = agrupar(db_session, so_asa_sul)
    assert [(g.latitude, g.longitude) for g in grupos] == [pytest.approx(P2)]
    assert agrupar(db_session, FiltroEstatisticas(**NOVEMBRO))[0].latitude == (
        pytest.approx(P1[0])
    )


def test_pontos_proximos_caem_no_mesmo_local(db_session, cenario):
    # Com células de 1000 km, as seis ocorrências do DF viram um só local,
    # com o centro na média dos pontos.
    (grupo,) = agrupar(db_session, celula_m=1_000_000)
    assert sum(grupo.por_status.values()) == 6
    assert -15.82 < grupo.latitude < -15.60 and -47.90 < grupo.longitude < -47.70


def test_sem_ocorrencias_nao_ha_locais(db_session):
    assert agrupar(db_session) == []
