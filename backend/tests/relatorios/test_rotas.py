"""Rota do relatório gerencial, de ponta a ponta (US06).

Critério de aceitação: consulta parametrizada com exportação estruturada dos
dados consolidados de uso.
"""

import csv
import io
import re

import pytest

from app.relatorios.schemas import FORA_DAS_REGIOES

URL = "/relatorios/gerencial"
NOVEMBRO = {"inicio": "2026-11-01T00:00:00Z", "fim": "2026-12-01T00:00:00Z"}


# ---------- Acesso ----------


def test_sem_token_retorna_401(client):
    assert client.get(URL).status_code == 401


def test_usuario_comum_nao_acessa(client, headers_cidadao):
    assert client.get(URL, headers=headers_cidadao).status_code == 403


def test_admin_acessa(client, headers_admin):
    assert client.get(URL, headers=headers_admin).status_code == 200


# ---------- Consulta parametrizada (JSON) ----------


def test_json_traz_os_tres_blocos_consolidados(client, headers_admin, cenario):
    corpo = client.get(URL, params=NOVEMBRO, headers=headers_admin).json()
    assert set(corpo) == {
        "gerado_em",
        "periodo",
        "usuarios",
        "termos_mais_pesquisados",
        "chamados_por_regiao",
    }
    assert corpo["usuarios"]["contas_inativas"] == 1
    # O admin do teste nasce "hoje"; por isso a checagem usa uma métrica que
    # não depende da data atual.
    assert corpo["usuarios"]["com_ocorrencia_no_periodo"] == 3
    assert corpo["termos_mais_pesquisados"][0] == {"termo": "buraco", "quantidade": 3}
    regioes = [r["regiao"] for r in corpo["chamados_por_regiao"]]
    assert regioes == ["Asa Norte", "Asa Sul", "Guará", FORA_DAS_REGIOES]


def test_json_informa_periodo_e_data_de_geracao_em_utc(client, headers_admin):
    corpo = client.get(URL, params=NOVEMBRO, headers=headers_admin).json()
    assert corpo["periodo"] == {
        "inicio": "2026-11-01T00:00:00Z",
        "fim": "2026-12-01T00:00:00Z",
    }
    assert corpo["gerado_em"].endswith("Z")


def test_aceita_datas_com_fuso_de_brasilia(client, headers_admin):
    params = {"inicio": "2026-11-01T00:00:00-03:00"}
    corpo = client.get(URL, params=params, headers=headers_admin).json()
    assert corpo["periodo"]["inicio"] == "2026-11-01T03:00:00Z"


def test_sem_periodo_considera_todo_o_historico(client, headers_admin, cenario):
    corpo = client.get(URL, headers=headers_admin).json()
    assert corpo["periodo"] == {"inicio": None, "fim": None}
    assert corpo["termos_mais_pesquisados"][0]["termo"] == "iluminação"


def test_limite_de_termos(client, headers_admin, cenario):
    params = {**NOVEMBRO, "limite_termos": 1}
    corpo = client.get(URL, params=params, headers=headers_admin).json()
    assert [t["termo"] for t in corpo["termos_mais_pesquisados"]] == ["buraco"]


def test_sem_dados_o_relatorio_sai_zerado(client, headers_admin):
    corpo = client.get(URL, headers=headers_admin).json()
    assert corpo["termos_mais_pesquisados"] == []
    assert corpo["chamados_por_regiao"] == [
        {
            "regiao": FORA_DAS_REGIOES,
            "total": 0,
            "registrado": 0,
            "em_analise": 0,
            "resolvido": 0,
        }
    ]


@pytest.mark.parametrize(
    "params",
    [
        {"inicio": "2026-11-01T00:00:00"},  # sem fuso
        {"inicio": "ontem"},
        {"inicio": "2026-12-01T00:00:00Z", "fim": "2026-11-01T00:00:00Z"},
        {"limite_termos": 0},
        {"limite_termos": 51},
        {"formato": "xml"},
    ],
)
def test_parametros_invalidos_retornam_422(client, headers_admin, params):
    assert client.get(URL, params=params, headers=headers_admin).status_code == 422


# ---------- Exportação estruturada (CSV) ----------


def test_csv_e_baixado_como_arquivo(client, headers_admin, cenario):
    resp = client.get(URL, params={"formato": "csv"}, headers=headers_admin)
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    disposicao = resp.headers["content-disposition"]
    assert re.fullmatch(
        r'attachment; filename="relatorio_gerencial_\d{8}_\d{6}\.csv"', disposicao
    )


def test_csv_tem_bom_para_o_excel_mostrar_acentos(client, headers_admin):
    resp = client.get(URL, params={"formato": "csv"}, headers=headers_admin)
    assert resp.content.startswith(b"\xef\xbb\xbf")


def test_csv_traz_os_mesmos_dados_do_json(client, headers_admin, cenario):
    params = {**NOVEMBRO, "formato": "csv"}
    texto = client.get(URL, params=params, headers=headers_admin).content.decode(
        "utf-8-sig"
    )
    linhas = list(csv.reader(io.StringIO(texto), delimiter=";"))
    assert linhas[0] == ["secao", "item", "metrica", "valor"]
    assert ["usuarios", "", "com_ocorrencia_no_periodo", "3"] in linhas
    assert ["termos", "buraco", "quantidade", "3"] in linhas
    assert ["regioes", "Asa Norte", "total", "2"] in linhas
    assert ["relatorio", "periodo_inicio", "", "2026-11-01T00:00:00Z"] in linhas


def test_csv_tambem_exige_admin(client, headers_cidadao):
    resp = client.get(URL, params={"formato": "csv"}, headers=headers_cidadao)
    assert resp.status_code == 403
