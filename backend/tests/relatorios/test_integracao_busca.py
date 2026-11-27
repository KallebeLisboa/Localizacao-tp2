"""Ponta a ponta: o que é buscado no mapa aparece no relatório (US06)."""


def test_buscas_do_mapa_entram_no_ranking_do_relatorio(client, headers_admin):
    for termo in ("Buraco", "buraco ", "poste"):
        assert client.get("/ocorrencias", params={"busca": termo}).status_code == 200

    relatorio = client.get("/relatorios/gerencial", headers=headers_admin).json()
    assert relatorio["termos_mais_pesquisados"] == [
        {"termo": "buraco", "quantidade": 2},
        {"termo": "poste", "quantidade": 1},
    ]
