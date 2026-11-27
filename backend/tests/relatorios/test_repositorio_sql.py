"""Consultas de agregação do relatório no PostgreSQL/PostGIS (US06)."""

from app.models import LogPesquisa, PerimetroAutorizado, Usuario
from app.relatorios.repositorio_sql import RepositorioRelatorioSQL
from app.relatorios.schemas import FORA_DAS_REGIOES, FiltroRelatorio
from tests.relatorios.conftest import NOV_FIM, NOV_INICIO, retangulo

NOVEMBRO = FiltroRelatorio(inicio=NOV_INICIO, fim=NOV_FIM)


def repo(db_session):
    return RepositorioRelatorioSQL(db_session)


def por_regiao(itens):
    return {i.regiao: i for i in itens}


# ---------- Usuários ----------


def test_usuarios_no_periodo(db_session, cenario):
    resumo = repo(db_session).resumo_usuarios(NOVEMBRO)
    assert resumo.contas_ativas == 4
    assert resumo.contas_inativas == 1
    assert resumo.novos_no_periodo == 2
    assert resumo.com_ocorrencia_no_periodo == 3


def test_usuarios_sem_periodo_contam_tudo(db_session, cenario):
    resumo = repo(db_session).resumo_usuarios(FiltroRelatorio())
    assert resumo.novos_no_periodo == 5
    assert resumo.com_ocorrencia_no_periodo == 4


def test_contas_ativas_nao_dependem_do_periodo(db_session, cenario):
    so_outubro = FiltroRelatorio(inicio=NOV_INICIO.replace(month=10), fim=NOV_INICIO)
    resumo = repo(db_session).resumo_usuarios(so_outubro)
    assert (resumo.contas_ativas, resumo.contas_inativas) == (4, 1)
    assert resumo.novos_no_periodo == 1


def test_inicio_inclusivo_e_fim_exclusivo(db_session, cenario):
    # Período [1/11 00:00, 1/12 00:00): quem nasce no instante do início
    # entra; quem nasce no instante do fim fica de fora.
    db_session.add_all(
        [
            Usuario(nome="I", email="i@unb.br", senha_hash="x", criado_em=NOV_INICIO),
            Usuario(nome="F", email="f@unb.br", senha_hash="x", criado_em=NOV_FIM),
        ]
    )
    db_session.commit()
    assert repo(db_session).resumo_usuarios(NOVEMBRO).novos_no_periodo == 3


def test_banco_vazio_da_zero_em_tudo(db_session):
    resumo = repo(db_session).resumo_usuarios(FiltroRelatorio())
    assert resumo.model_dump() == {
        "contas_ativas": 0,
        "contas_inativas": 0,
        "novos_no_periodo": 0,
        "com_ocorrencia_no_periodo": 0,
    }


# ---------- Termos pesquisados ----------


def test_termos_normalizados_e_ordenados_por_frequencia(db_session, cenario):
    termos = repo(db_session).termos_mais_pesquisados(NOVEMBRO)
    assert [(t.termo, t.quantidade) for t in termos] == [
        ("buraco", 3),
        ("poste", 2),
        ("lixo", 1),
    ]


def test_termos_respeitam_o_limite(db_session, cenario):
    filtro = NOVEMBRO.model_copy(update={"limite_termos": 2})
    termos = repo(db_session).termos_mais_pesquisados(filtro)
    assert [t.termo for t in termos] == ["buraco", "poste"]


def test_termos_ignoram_buscas_vazias(db_session, cenario):
    termos = repo(db_session).termos_mais_pesquisados(NOVEMBRO)
    assert all(t.termo for t in termos)


def test_termos_sem_periodo_incluem_meses_anteriores(db_session, cenario):
    termos = repo(db_session).termos_mais_pesquisados(FiltroRelatorio())
    assert (termos[0].termo, termos[0].quantidade) == ("iluminação", 5)


def test_empate_de_termos_em_ordem_alfabetica(db_session, cenario):
    # "asfalto" empata com "poste" (2 cada) e vem antes por ordem alfabética.
    db_session.add_all(
        LogPesquisa(termo_buscado="asfalto", pesquisado_em=NOV_INICIO) for _ in range(2)
    )
    db_session.commit()
    termos = repo(db_session).termos_mais_pesquisados(NOVEMBRO)
    assert [t.termo for t in termos] == ["buraco", "asfalto", "poste", "lixo"]


def test_sem_pesquisas_o_ranking_fica_vazio(db_session):
    assert repo(db_session).termos_mais_pesquisados(FiltroRelatorio()) == []


# ---------- Chamados por região ----------


def test_chamados_por_regiao_separados_por_status(db_session, cenario):
    regioes = por_regiao(repo(db_session).chamados_por_regiao(NOVEMBRO))
    norte = regioes["Asa Norte"]
    assert (norte.total, norte.registrado, norte.em_analise, norte.resolvido) == (
        2,
        1,
        0,
        1,
    )
    sul = regioes["Asa Sul"]
    assert (sul.total, sul.em_analise) == (1, 1)


def test_regiao_sem_chamados_aparece_com_zero(db_session, cenario):
    guara = por_regiao(repo(db_session).chamados_por_regiao(NOVEMBRO))["Guará"]
    assert guara.total == 0


def test_conta_ocorrencias_fora_de_todas_as_regioes(db_session, cenario):
    fora = por_regiao(repo(db_session).chamados_por_regiao(NOVEMBRO))[FORA_DAS_REGIOES]
    assert (fora.total, fora.registrado) == (1, 1)


def test_periodo_vale_para_os_chamados(db_session, cenario):
    regioes = por_regiao(repo(db_session).chamados_por_regiao(FiltroRelatorio()))
    assert regioes["Asa Norte"].total == 3


def test_regioes_sobrepostas_contam_a_ocorrencia_em_cada_uma(db_session, cenario):
    db_session.add(
        PerimetroAutorizado(
            nome_regiao="Plano Piloto", area=retangulo(-47.95, -15.85, -47.85, -15.70)
        )
    )
    db_session.commit()
    regioes = por_regiao(repo(db_session).chamados_por_regiao(NOVEMBRO))
    assert regioes["Plano Piloto"].total == 3
    assert regioes["Asa Norte"].total == 2


def test_sem_regioes_tudo_fica_fora(db_session):
    regioes = repo(db_session).chamados_por_regiao(FiltroRelatorio())
    assert [(r.regiao, r.total) for r in regioes] == [(FORA_DAS_REGIOES, 0)]
