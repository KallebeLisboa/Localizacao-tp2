"""Rotas de estatísticas, de ponta a ponta (US04).

Critério de aceitação: análise temporal e espacial das ocorrências, com
filtros por período, região e categoria.
"""

import pytest

from app.estatisticas.schemas import FORA_DAS_REGIOES, NOME_FUSO

NOVEMBRO = {"inicio": "2026-11-01T00:00:00-03:00", "fim": "2026-12-01T00:00:00-03:00"}


def get(client, caminho, **params):
    return client.get(f"/estatisticas/{caminho}", params=params)


# ---------- Acesso e documentação ----------


@pytest.mark.parametrize(
    "caminho", ["resumo", "evolucao", "regioes", "sazonalidade", "reincidencia"]
)
def test_rotas_sao_publicas(client, caminho):
    assert get(client, caminho).status_code == 200


def test_rotas_aparecem_na_documentacao(client):
    esquema = client.get("/openapi.json").json()
    assert "Estatísticas (US04)" in [t["name"] for t in esquema["tags"]]
    assert "/estatisticas/resumo" in esquema["paths"]


# ---------- Resumo e filtros ----------


def test_resumo_sem_filtros(client, cenario):
    assert get(client, "resumo").json() == {
        "total": 6,
        "resolvidas": 2,
        "pendentes": 4,
        "registradas": 3,
        "em_analise": 1,
        "taxa_resolucao": 0.3333,
    }


def test_resumo_no_periodo(client, cenario):
    corpo = get(client, "resumo", **NOVEMBRO).json()
    assert (corpo["total"], corpo["resolvidas"], corpo["taxa_resolucao"]) == (
        4,
        1,
        0.25,
    )


def test_resumo_por_categorias(client, cenario):
    assert get(client, "resumo", categorias=[cenario.cat2]).json()["total"] == 2
    ambas = [cenario.cat1, cenario.cat2]
    assert get(client, "resumo", categorias=ambas).json()["total"] == 6


def test_resumo_por_regiao(client, cenario):
    corpo = get(client, "resumo", regiao_id=cenario.asa_norte).json()
    assert (corpo["total"], corpo["resolvidas"]) == (3, 1)


def test_resumo_sem_ocorrencias_nao_tem_taxa(client):
    assert get(client, "resumo").json()["taxa_resolucao"] is None


def test_regiao_inexistente_retorna_404(client, cenario):
    resposta = get(client, "resumo", regiao_id=9999)
    assert resposta.status_code == 404
    assert resposta.json() == {"detail": "região 9999 não encontrada"}


@pytest.mark.parametrize(
    "params",
    [
        {"inicio": "2026-11-01T00:00:00"},  # sem fuso
        {"inicio": "2026-12-01T00:00:00Z", "fim": "2026-11-01T00:00:00Z"},
        {"regiao_id": 0},
        {"categorias": "abc"},
    ],
)
def test_filtros_invalidos_retornam_422(client, params):
    assert get(client, "resumo", **params).status_code == 422


def test_periodo_invertido_explica_o_erro(client):
    params = {"inicio": "2026-12-01T00:00:00Z", "fim": "2026-11-01T00:00:00Z"}
    erros = get(client, "regioes", **params).json()["detail"]
    assert any("inicio deve ser anterior a fim" in e["msg"] for e in erros)


# ---------- Evolução no tempo ----------


def test_evolucao_por_mes(client, cenario):
    corpo = get(client, "evolucao", granularidade="mes").json()
    assert corpo["granularidade"] == "mes"
    assert corpo["fuso"] == NOME_FUSO
    assert [(p["periodo"], p["total"]) for p in corpo["pontos"]] == [
        ("2026-09-01", 1),
        ("2026-10-01", 1),
        ("2026-11-01", 4),
    ]


def test_evolucao_por_semana_preenche_semanas_vazias(client, cenario):
    corpo = get(client, "evolucao", granularidade="semana", **NOVEMBRO).json()
    assert [(p["periodo"], p["total"]) for p in corpo["pontos"]] == [
        ("2026-10-26", 0),
        ("2026-11-02", 2),
        ("2026-11-09", 1),
        ("2026-11-16", 1),
        ("2026-11-23", 0),
        ("2026-11-30", 0),
    ]


def test_evolucao_padrao_e_por_dia(client, cenario):
    corpo = get(client, "evolucao", **NOVEMBRO).json()
    assert corpo["granularidade"] == "dia"
    assert len(corpo["pontos"]) == 30


def test_evolucao_granularidade_invalida_retorna_422(client):
    assert get(client, "evolucao", granularidade="ano").status_code == 422


def test_evolucao_longa_demais_retorna_400(client):
    params = {"inicio": "2020-01-01T00:00:00Z", "fim": "2026-12-01T00:00:00Z"}
    resposta = get(client, "evolucao", granularidade="dia", **params)
    assert resposta.status_code == 400
    assert "granularidade maior" in resposta.json()["detail"]


# ---------- Regiões ----------


def test_regioes(client, cenario):
    corpo = get(client, "regioes").json()
    assert [(r["regiao"], r["total"], r["resolvidas"]) for r in corpo] == [
        ("Asa Norte", 3, 1),
        ("Asa Sul", 2, 1),
        ("Guará", 0, 0),
        (FORA_DAS_REGIOES, 1, 0),
    ]
    assert corpo[0]["regiao_id"] == cenario.asa_norte
    assert corpo[-1]["regiao_id"] is None


def test_regioes_filtradas_por_uma_regiao(client, cenario):
    corpo = get(client, "regioes", regiao_id=cenario.asa_sul).json()
    assert [r["regiao"] for r in corpo] == ["Asa Sul"]


# ---------- Sazonalidade ----------


def test_sazonalidade_padrao_e_por_mes(client, cenario):
    corpo = get(client, "sazonalidade").json()
    assert corpo["por"] == "mes"
    assert len(corpo["itens"]) == 12
    novembro = corpo["itens"][10]
    assert (novembro["chave"], novembro["rotulo"], novembro["total"]) == (
        11,
        "nov",
        4,
    )


def test_sazonalidade_por_dia_da_semana(client, cenario):
    itens = get(client, "sazonalidade", por="dia_semana").json()["itens"]
    assert [(i["rotulo"], i["total"]) for i in itens] == [
        ("seg", 2),
        ("ter", 1),
        ("qua", 0),
        ("qui", 1),
        ("sex", 1),
        ("sáb", 1),
        ("dom", 0),
    ]


def test_sazonalidade_por_hora_usa_horario_de_brasilia(client, cenario):
    itens = get(client, "sazonalidade", por="hora").json()["itens"]
    assert len(itens) == 24
    assert itens[23] == {
        "chave": 23,
        "rotulo": "23h",
        "total": 1,
        "resolvidas": 1,
        "pendentes": 0,
    }


def test_sazonalidade_agrupamento_invalido_retorna_422(client):
    assert get(client, "sazonalidade", por="ano").status_code == 422


# ---------- Reincidência ----------


def test_reincidencia_padrao(client, cenario):
    corpo = get(client, "reincidencia").json()
    assert (corpo["celula_m"], corpo["minimo"]) == (500, 2)
    assert [p["total"] for p in corpo["pontos"]] == [3, 2]
    primeiro = corpo["pontos"][0]
    assert primeiro["latitude"] == pytest.approx(-15.76)
    assert primeiro["longitude"] == pytest.approx(-47.88)
    assert (primeiro["resolvidas"], primeiro["pendentes"]) == (1, 2)


def test_reincidencia_com_parametros(client, cenario):
    corpo = get(client, "reincidencia", minimo=1, limite=2, celula_m=100).json()
    assert (corpo["celula_m"], corpo["minimo"]) == (100, 1)
    assert [p["total"] for p in corpo["pontos"]] == [3, 2]


def test_reincidencia_respeita_filtros(client, cenario):
    corpo = get(client, "reincidencia", regiao_id=cenario.asa_sul).json()
    assert [p["total"] for p in corpo["pontos"]] == [2]


@pytest.mark.parametrize(
    "params",
    [
        {"celula_m": 10},
        {"celula_m": 100_000},
        {"minimo": 0},
        {"limite": 0},
        {"limite": 1000},
    ],
)
def test_reincidencia_parametros_invalidos_retornam_422(client, params):
    assert get(client, "reincidencia", **params).status_code == 422
