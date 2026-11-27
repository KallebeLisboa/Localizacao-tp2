"""GET /ocorrencias?busca=...: filtra e grava a busca (base da US06)."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.security import criar_token_acesso
from app.database import get_db
from app.models import LogPesquisa, Usuario
from app.ocorrencias.filtros import BUSCA_MAX
from app.ocorrencias.rotas import router

URL = "/ocorrencias"


@pytest.fixture
def cliente(db, massa):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


@pytest.fixture
def com_ocorrencias(cliente, massa):
    token = {"Authorization": f"Bearer {criar_token_acesso(str(massa.usuario_id))}"}
    for titulo in ("Buraco na via", "Poste apagado"):
        corpo = {
            "titulo": titulo,
            "categoria_id": massa.cat_buraco,
            "descricao": "detalhes",
            "latitude": -15.7942,
            "longitude": -47.8825,
        }
        assert cliente.post(URL, json=corpo, headers=token).status_code == 201


def logs(db):
    return db.scalars(select(LogPesquisa).order_by(LogPesquisa.id)).all()


def test_busca_filtra_os_marcadores(cliente, com_ocorrencias):
    r = cliente.get(URL, params={"busca": "buraco"})
    assert r.status_code == 200
    assert [i["titulo"] for i in r.json()["itens"]] == ["Buraco na via"]


def test_busca_anonima_e_gravada_sem_usuario(cliente, db):
    cliente.get(URL, params={"busca": "  Buraco  "})
    (log,) = logs(db)
    assert (log.termo_buscado, log.usuario_id) == ("Buraco", None)


def test_busca_de_usuario_logado_guarda_quem_buscou(cliente, db, massa):
    token = criar_token_acesso(str(massa.usuario_id))
    cliente.get(
        URL, params={"busca": "poste"}, headers={"Authorization": f"Bearer {token}"}
    )
    assert logs(db)[0].usuario_id == massa.usuario_id


def test_token_invalido_nao_impede_a_busca(cliente, db):
    r = cliente.get(
        URL, params={"busca": "poste"}, headers={"Authorization": "Bearer lixo"}
    )
    assert r.status_code == 200
    assert logs(db)[0].usuario_id is None


def test_grava_o_retangulo_do_mapa(cliente, db):
    params = {"busca": "poste", "sul": -15.8, "oeste": -47.9}
    params.update({"norte": -15.78, "leste": -47.87})
    cliente.get(URL, params=params)
    assert logs(db)[0].regiao_filtrada == "-15.8000,-47.9000,-15.7800,-47.8700"


def test_consulta_sem_busca_nao_grava(cliente, db):
    assert cliente.get(URL, params={"categorias": [1]}).status_code == 200
    assert logs(db) == []


def test_busca_so_com_espacos_lista_tudo_e_nao_grava(cliente, db, com_ocorrencias):
    r = cliente.get(URL, params={"busca": "   "})
    assert len(r.json()["itens"]) == 2
    assert logs(db) == []


def test_proxima_pagina_nao_grava_de_novo(cliente, db):
    cliente.get(URL, params={"busca": "buraco", "offset": 100})
    assert logs(db) == []


def test_busca_longa_demais_retorna_422(cliente, db):
    r = cliente.get(URL, params={"busca": "a" * (BUSCA_MAX + 1)})
    assert r.status_code == 422
    assert logs(db) == []


@pytest.mark.parametrize("situacao", ["inexistente", "inativo"])
def test_token_de_usuario_inexistente_ou_inativo_vira_busca_anonima(
    cliente, db, massa, situacao
):
    usuario_id = 9999
    if situacao == "inativo":
        usuario = db.get(Usuario, massa.usuario_id)
        usuario.ativo = False
        db.commit()
        usuario_id = massa.usuario_id
    token = criar_token_acesso(str(usuario_id))
    r = cliente.get(
        URL, params={"busca": "poste"}, headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 200
    assert logs(db)[0].usuario_id is None
