"""Rotas de notificações de ponta a ponta com PostGIS (US03)."""

import pytest
from geoalchemy2.elements import WKTElement

from app.models import (
    LogEvento,
    Ocorrencia,
    PerimetroAutorizado,
    StatusOcorrencia,
)
from tests.conftest import headers_de

POLIGONO_DF = (
    "POLYGON((-48.30 -16.10, -47.30 -16.10, -47.30 -15.50, "
    "-48.30 -15.50, -48.30 -16.10))"
)
CENTRO = (-15.7942, -47.8825)  # (latitude, longitude)
PERTO = (-15.7969, -47.8825)  # ~300 m ao sul
LONGE = (-15.8400, -47.8825)  # ~5 km ao sul


@pytest.fixture
def cat(criar_categoria):
    return criar_categoria("Buraco")


@pytest.fixture
def outra_cat(criar_categoria):
    return criar_categoria("Iluminação")


@pytest.fixture
def fazer_ocorrencia(db_session, cidadao, cat):
    """Fábrica de ocorrências gravadas direto no banco."""

    def _fazer(ponto=CENTRO, categoria=None, titulo="Buraco na via"):
        oc = Ocorrencia(
            titulo=titulo,
            descricao="descrição",
            localizacao=WKTElement(f"POINT({ponto[1]} {ponto[0]})", srid=4326),
            usuario_id=cidadao.id,
            categoria_id=(categoria or cat).id,
        )
        db_session.add(oc)
        db_session.commit()
        db_session.refresh(oc)
        return oc

    return _fazer


def seguir(client, headers, **corpo):
    return client.post("/notificacoes/inscricoes", json=corpo, headers=headers)


def zona(ponto=CENTRO, raio=1000.0, **extra):
    return {"latitude": ponto[0], "longitude": ponto[1], "raio_metros": raio, **extra}


def avancar(client, headers_admin, oc_id, status):
    return client.patch(
        f"/admin/ocorrencias/{oc_id}/status",
        json={"status": status},
        headers=headers_admin,
    )


# ---------- inscrições ----------


def test_exige_autenticacao(client):
    assert client.get("/notificacoes").status_code == 401
    assert client.get("/notificacoes/inscricoes").status_code == 401
    assert client.post("/notificacoes/inscricoes", json={}).status_code == 401
    assert client.delete("/notificacoes/inscricoes/1").status_code == 401


def test_seguir_ocorrencia_201(client, headers_cidadao, fazer_ocorrencia):
    oc = fazer_ocorrencia()
    r = seguir(client, headers_cidadao, ocorrencia_id=oc.id)
    assert r.status_code == 201
    dados = r.json()
    assert dados["tipo"] == "ocorrencia" and dados["ocorrencia_id"] == oc.id
    assert dados["latitude"] is None and dados["raio_metros"] is None


def test_seguir_duas_vezes_409(client, headers_cidadao, fazer_ocorrencia):
    oc = fazer_ocorrencia()
    seguir(client, headers_cidadao, ocorrencia_id=oc.id)
    r = seguir(client, headers_cidadao, ocorrencia_id=oc.id)
    assert r.status_code == 409
    assert r.json()["detail"]["codigo"] == "inscricao_duplicada"


def test_seguir_ocorrencia_inexistente_404(client, headers_cidadao):
    r = seguir(client, headers_cidadao, ocorrencia_id=999)
    assert r.status_code == 404
    assert r.json()["detail"]["codigo"] == "ocorrencia_inexistente"


def test_assinar_zona_201(client, headers_cidadao, cat):
    r = seguir(client, headers_cidadao, **zona(categoria_id=cat.id))
    assert r.status_code == 201
    dados = r.json()
    assert dados["tipo"] == "zona" and dados["categoria_id"] == cat.id
    assert (dados["latitude"], dados["longitude"]) == CENTRO
    assert dados["raio_metros"] == 1000.0


def test_zona_com_categoria_inexistente_422(client, headers_cidadao):
    r = seguir(client, headers_cidadao, **zona(categoria_id=999))
    assert r.status_code == 422
    assert r.json()["detail"]["codigo"] == "categoria_inexistente"


@pytest.mark.parametrize(
    "corpo",
    [{}, {"latitude": -15.0}, {"ocorrencia_id": 1, **zona()}, zona(raio=0)],
)
def test_corpo_invalido_422(client, headers_cidadao, corpo):
    assert seguir(client, headers_cidadao, **corpo).status_code == 422


def test_listar_inscricoes_so_as_proprias(
    client, headers_cidadao, headers_admin, fazer_ocorrencia
):
    oc = fazer_ocorrencia()
    seguir(client, headers_cidadao, ocorrencia_id=oc.id)
    seguir(client, headers_cidadao, **zona())
    seguir(client, headers_admin, **zona())
    r = client.get("/notificacoes/inscricoes", headers=headers_cidadao)
    assert r.status_code == 200
    assert [i["tipo"] for i in r.json()] == ["ocorrencia", "zona"]


def test_cancelar_inscricao(client, headers_cidadao, fazer_ocorrencia):
    oc = fazer_ocorrencia()
    id_ = seguir(client, headers_cidadao, ocorrencia_id=oc.id).json()["id"]
    assert (
        client.delete(
            f"/notificacoes/inscricoes/{id_}", headers=headers_cidadao
        ).status_code
        == 204
    )
    assert client.get("/notificacoes/inscricoes", headers=headers_cidadao).json() == []


def test_cancelar_inscricao_alheia_404(
    client, headers_cidadao, headers_admin, fazer_ocorrencia
):
    oc = fazer_ocorrencia()
    id_ = seguir(client, headers_cidadao, ocorrencia_id=oc.id).json()["id"]
    r = client.delete(f"/notificacoes/inscricoes/{id_}", headers=headers_admin)
    assert r.status_code == 404
    assert (
        len(client.get("/notificacoes/inscricoes", headers=headers_cidadao).json()) == 1
    )


# ---------- mudança de status (admin) ----------


def test_status_exige_admin(client, headers_cidadao, fazer_ocorrencia):
    oc = fazer_ocorrencia()
    r = avancar(client, headers_cidadao, oc.id, "EM_ANALISE")
    assert r.status_code == 403
    assert (
        client.patch(
            f"/admin/ocorrencias/{oc.id}/status", json={"status": "EM_ANALISE"}
        ).status_code
        == 401
    )


def test_admin_avanca_status_e_grava_log(
    client, headers_admin, db_session, fazer_ocorrencia
):
    oc = fazer_ocorrencia()
    r = avancar(client, headers_admin, oc.id, "EM_ANALISE")
    assert r.status_code == 200
    assert r.json() == {"ocorrencia_id": oc.id, "status": "EM_ANALISE"}
    db_session.refresh(oc)
    assert oc.status is StatusOcorrencia.EM_ANALISE
    log = db_session.query(LogEvento).one()
    assert log.status_anterior is StatusOcorrencia.REGISTRADO
    assert log.status_novo is StatusOcorrencia.EM_ANALISE


def test_status_pulando_etapa_409(client, headers_admin, fazer_ocorrencia):
    oc = fazer_ocorrencia()
    r = avancar(client, headers_admin, oc.id, "RESOLVIDO")
    assert r.status_code == 409
    assert r.json()["detail"]["codigo"] == "transicao_invalida"


def test_status_de_ocorrencia_inexistente_404(client, headers_admin):
    assert avancar(client, headers_admin, 999, "EM_ANALISE").status_code == 404


def test_status_invalido_422(client, headers_admin, fazer_ocorrencia):
    oc = fazer_ocorrencia()
    assert avancar(client, headers_admin, oc.id, "ARQUIVADO").status_code == 422


# ---------- feed de notificações ----------


def feed(client, headers, **params):
    r = client.get("/notificacoes", params=params, headers=headers)
    assert r.status_code == 200
    return r.json()


def test_feed_vazio_sem_inscricoes(
    client, headers_cidadao, headers_admin, fazer_ocorrencia
):
    oc = fazer_ocorrencia()
    avancar(client, headers_admin, oc.id, "EM_ANALISE")
    assert feed(client, headers_cidadao) == {"itens": [], "proximo_offset": None}


def test_quem_segue_recebe_a_mudanca(
    client, headers_cidadao, headers_admin, fazer_ocorrencia
):
    oc = fazer_ocorrencia(titulo="Poste apagado")
    seguir(client, headers_cidadao, ocorrencia_id=oc.id)
    avancar(client, headers_admin, oc.id, "EM_ANALISE")
    avancar(client, headers_admin, oc.id, "RESOLVIDO")
    itens = feed(client, headers_cidadao)["itens"]
    assert [(n["status_anterior"], n["status_novo"]) for n in itens] == [
        ("EM_ANALISE", "RESOLVIDO"),  # mais recente primeiro
        ("REGISTRADO", "EM_ANALISE"),
    ]
    assert all(
        n["ocorrencia_id"] == oc.id and n["titulo"] == "Poste apagado" for n in itens
    )


def test_quem_nao_segue_nao_recebe(
    client, headers_cidadao, headers_admin, fazer_ocorrencia
):
    seguida = fazer_ocorrencia()
    outra = fazer_ocorrencia(titulo="Outra")
    seguir(client, headers_cidadao, ocorrencia_id=seguida.id)
    avancar(client, headers_admin, outra.id, "EM_ANALISE")
    assert feed(client, headers_cidadao)["itens"] == []


def test_zona_notifica_ocorrencia_dentro_do_raio(
    client, headers_cidadao, headers_admin, fazer_ocorrencia
):
    perto = fazer_ocorrencia(PERTO, titulo="Perto")
    longe = fazer_ocorrencia(LONGE, titulo="Longe")
    seguir(client, headers_cidadao, **zona(raio=1000.0))
    avancar(client, headers_admin, perto.id, "EM_ANALISE")
    avancar(client, headers_admin, longe.id, "EM_ANALISE")
    assert [n["titulo"] for n in feed(client, headers_cidadao)["itens"]] == ["Perto"]


def test_raio_e_em_metros(client, headers_cidadao, headers_admin, fazer_ocorrencia):
    perto = fazer_ocorrencia(PERTO)  # ~300 m
    avancar(client, headers_admin, perto.id, "EM_ANALISE")
    seguir(client, headers_cidadao, **zona(raio=100.0))
    assert feed(client, headers_cidadao)["itens"] == []
    seguir(client, headers_cidadao, **zona(raio=400.0))
    assert len(feed(client, headers_cidadao)["itens"]) == 1


def test_zona_com_categoria_filtra_por_tipo(
    client, headers_cidadao, headers_admin, fazer_ocorrencia, cat, outra_cat
):
    buraco = fazer_ocorrencia(PERTO, categoria=cat, titulo="Buraco")
    luz = fazer_ocorrencia(PERTO, categoria=outra_cat, titulo="Luz")
    seguir(client, headers_cidadao, **zona(categoria_id=outra_cat.id))
    avancar(client, headers_admin, buraco.id, "EM_ANALISE")
    avancar(client, headers_admin, luz.id, "EM_ANALISE")
    assert [n["titulo"] for n in feed(client, headers_cidadao)["itens"]] == ["Luz"]


def test_varias_inscricoes_nao_duplicam_o_evento(
    client, headers_cidadao, headers_admin, fazer_ocorrencia
):
    oc = fazer_ocorrencia()
    seguir(client, headers_cidadao, ocorrencia_id=oc.id)
    seguir(client, headers_cidadao, **zona())
    seguir(client, headers_cidadao, **zona(raio=2000.0))
    avancar(client, headers_admin, oc.id, "EM_ANALISE")
    assert len(feed(client, headers_cidadao)["itens"]) == 1


def test_cancelar_para_de_notificar(
    client, headers_cidadao, headers_admin, fazer_ocorrencia
):
    oc = fazer_ocorrencia()
    id_ = seguir(client, headers_cidadao, ocorrencia_id=oc.id).json()["id"]
    client.delete(f"/notificacoes/inscricoes/{id_}", headers=headers_cidadao)
    avancar(client, headers_admin, oc.id, "EM_ANALISE")
    assert feed(client, headers_cidadao)["itens"] == []


def test_feed_e_isolado_por_usuario(
    client, headers_cidadao, headers_admin, fazer_ocorrencia
):
    oc = fazer_ocorrencia()
    seguir(client, headers_admin, ocorrencia_id=oc.id)
    avancar(client, headers_admin, oc.id, "EM_ANALISE")
    assert feed(client, headers_cidadao)["itens"] == []
    assert len(feed(client, headers_admin)["itens"]) == 1


def test_paginacao(client, headers_cidadao, headers_admin, fazer_ocorrencia):
    oc = fazer_ocorrencia()
    seguir(client, headers_cidadao, ocorrencia_id=oc.id)
    avancar(client, headers_admin, oc.id, "EM_ANALISE")
    avancar(client, headers_admin, oc.id, "RESOLVIDO")
    p1 = feed(client, headers_cidadao, limite=1)
    assert len(p1["itens"]) == 1 and p1["proximo_offset"] == 1
    p2 = feed(client, headers_cidadao, limite=1, offset=1)
    assert len(p2["itens"]) == 1 and p2["proximo_offset"] is None
    assert p1["itens"][0]["log_id"] != p2["itens"][0]["log_id"]


@pytest.mark.parametrize("params", [{"limite": 0}, {"limite": 101}, {"offset": -1}])
def test_paginacao_invalida_422(client, headers_cidadao, params):
    r = client.get("/notificacoes", params=params, headers=headers_cidadao)
    assert r.status_code == 422


def test_novo_registro_notifica_a_zona(
    client, db_session, cidadao, admin, cat, headers_cidadao
):
    """US03: alerta de *novos registros* via log criado em POST /ocorrencias."""
    db_session.add(
        PerimetroAutorizado(nome_regiao="DF", area=WKTElement(POLIGONO_DF, srid=4326))
    )
    db_session.commit()
    seguir(client, headers_cidadao, **zona(categoria_id=cat.id))
    corpo = {
        "titulo": "Buraco novo",
        "categoria_id": cat.id,
        "descricao": "fundo",
        "latitude": PERTO[0],
        "longitude": PERTO[1],
    }
    r = client.post("/ocorrencias", json=corpo, headers=headers_de(admin))
    assert r.status_code == 201
    itens = feed(client, headers_cidadao)["itens"]
    assert len(itens) == 1
    assert itens[0]["status_anterior"] is None
    assert itens[0]["status_novo"] == "REGISTRADO"
    assert itens[0]["titulo"] == "Buraco novo"
