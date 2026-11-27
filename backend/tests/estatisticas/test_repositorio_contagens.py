"""Contagens por status, região e período no PostGIS (US04)."""

from datetime import date

from app.estatisticas.repositorio_sql import RepositorioEstatisticasSQL
from app.estatisticas.schemas import FiltroEstatisticas, Granularidade
from app.models import StatusOcorrencia as S

from .conftest import NOVEMBRO


def repo(db_session):
    return RepositorioEstatisticasSQL(db_session)


def filtro(**campos):
    return FiltroEstatisticas(**campos)


# ---------- Região existe ----------


def test_regiao_existe(db_session, cenario):
    assert repo(db_session).regiao_existe(cenario.guara)
    assert not repo(db_session).regiao_existe(9999)


# ---------- Por status ----------


def test_por_status_sem_filtros(db_session, cenario):
    assert repo(db_session).contar_por_status(filtro()) == {
        S.REGISTRADO: 3,
        S.EM_ANALISE: 1,
        S.RESOLVIDO: 2,
    }


def test_por_status_no_periodo(db_session, cenario):
    assert repo(db_session).contar_por_status(filtro(**NOVEMBRO)) == {
        S.REGISTRADO: 2,
        S.EM_ANALISE: 1,
        S.RESOLVIDO: 1,
    }


def test_por_status_na_regiao(db_session, cenario):
    contagem = repo(db_session).contar_por_status(filtro(regiao_id=cenario.asa_sul))
    assert contagem == {S.REGISTRADO: 1, S.RESOLVIDO: 1}


def test_por_status_por_categoria(db_session, cenario):
    contagem = repo(db_session).contar_por_status(filtro(categorias=[cenario.cat2]))
    assert contagem == {S.EM_ANALISE: 1, S.REGISTRADO: 1}


def test_filtros_combinados(db_session, cenario):
    f = filtro(**NOVEMBRO, regiao_id=cenario.asa_norte, categorias=[cenario.cat1])
    assert repo(db_session).contar_por_status(f) == {S.REGISTRADO: 1, S.RESOLVIDO: 1}


def test_banco_vazio(db_session):
    assert repo(db_session).contar_por_status(filtro()) == {}


# ---------- Por região ----------


def por_nome(itens):
    return {c.nome: (c.regiao_id, dict(c.por_status)) for c in itens}


def test_por_regiao_inclui_vazias_e_as_de_fora(db_session, cenario):
    regioes = por_nome(repo(db_session).contar_por_regiao(filtro()))
    assert regioes["Asa Norte"] == (
        cenario.asa_norte,
        {S.REGISTRADO: 1, S.RESOLVIDO: 1, S.EM_ANALISE: 1},
    )
    assert regioes["Asa Sul"][1] == {S.RESOLVIDO: 1, S.REGISTRADO: 1}
    assert regioes["Guará"] == (cenario.guara, {})
    fora = [
        c for c in repo(db_session).contar_por_regiao(filtro()) if c.regiao_id is None
    ]
    assert len(fora) == 1 and dict(fora[0].por_status) == {S.REGISTRADO: 1}


def test_por_regiao_respeita_periodo(db_session, cenario):
    regioes = por_nome(repo(db_session).contar_por_regiao(filtro(**NOVEMBRO)))
    assert regioes["Asa Sul"][1] == {}


def test_por_regiao_com_filtro_traz_so_ela(db_session, cenario):
    itens = repo(db_session).contar_por_regiao(filtro(regiao_id=cenario.asa_sul))
    assert [(c.nome, dict(c.por_status)) for c in itens] == [
        ("Asa Sul", {S.RESOLVIDO: 1, S.REGISTRADO: 1})
    ]


# ---------- Por período (horário de Brasília) ----------


def test_por_dia_usa_o_horario_de_brasilia(db_session, cenario):
    dias = repo(db_session).contar_por_periodo(filtro(**NOVEMBRO), Granularidade.DIA)
    # A ocorrência das 23h30 do dia 2 (03/11 em UTC) fica no dia 2.
    assert dias == {
        date(2026, 11, 2): {S.REGISTRADO: 1, S.RESOLVIDO: 1},
        date(2026, 11, 10): {S.EM_ANALISE: 1},
        date(2026, 11, 20): {S.REGISTRADO: 1},
    }


def test_por_semana_comeca_na_segunda(db_session, cenario):
    semanas = repo(db_session).contar_por_periodo(
        filtro(**NOVEMBRO), Granularidade.SEMANA
    )
    assert sorted(semanas) == [date(2026, 11, 2), date(2026, 11, 9), date(2026, 11, 16)]


def test_por_mes(db_session, cenario):
    meses = repo(db_session).contar_por_periodo(filtro(), Granularidade.MES)
    assert {m: sum(c.values()) for m, c in meses.items()} == {
        date(2026, 9, 1): 1,
        date(2026, 10, 1): 1,
        date(2026, 11, 1): 4,
    }
