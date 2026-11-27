"""Busca por texto no título e na descrição, no PostGIS."""

from datetime import timedelta

import pytest

from app.models import StatusOcorrencia as S
from app.ocorrencias.filtros import FiltroOcorrencias
from app.ocorrencias.geo import Ponto
from app.ocorrencias.repositorio_sql import RepositorioSQL
from app.ocorrencias.schemas import NovaOcorrencia

from .conftest import T0


@pytest.fixture
def repo(db):
    return RepositorioSQL(db)


@pytest.fixture
def criar(repo, massa):
    contador = {"n": 0}

    def _criar(titulo, descricao="sem detalhes", lat=-15.8, lon=-47.9):
        contador["n"] += 1
        return repo.adicionar(
            NovaOcorrencia(
                usuario_id=massa.usuario_id,
                categoria_id=massa.cat_buraco,
                titulo=titulo,
                descricao=descricao,
                ponto=Ponto(latitude=lat, longitude=lon),
                status=S.REGISTRADO,
                criado_em=T0 + timedelta(minutes=contador["n"]),
            )
        )

    return _criar


def titulos(repo, **filtro):
    return [oc.titulo for oc in repo.listar(FiltroOcorrencias(**filtro)).itens]


def test_encontra_pelo_titulo(repo, criar):
    criar("Buraco na via")
    criar("Poste apagado")
    assert titulos(repo, busca="buraco") == ["Buraco na via"]


def test_encontra_pela_descricao(repo, criar):
    criar("Problema na rua", descricao="Tem um BURACO enorme")
    criar("Poste apagado")
    assert titulos(repo, busca="buraco") == ["Problema na rua"]


def test_nao_diferencia_maiusculas(repo, criar):
    criar("Buraco na via")
    assert titulos(repo, busca="BURACO") == ["Buraco na via"]


def test_encontra_trecho_no_meio_da_palavra(repo, criar):
    criar("Esburacado")
    assert titulos(repo, busca="burac") == ["Esburacado"]


def test_sem_resultado_devolve_pagina_vazia(repo, criar):
    criar("Buraco na via")
    assert titulos(repo, busca="árvore") == []


@pytest.mark.parametrize("curinga", ["%", "_"])
def test_curingas_do_sql_sao_tratados_como_texto(repo, criar, curinga):
    criar("Tudo certo")
    criar(f"Desconto de 50{curinga}")
    assert titulos(repo, busca=curinga) == [f"Desconto de 50{curinga}"]


def test_barra_invertida_e_tratada_como_texto(repo, criar):
    criar("Placa A\\B")
    criar("Placa AB")
    assert titulos(repo, busca="A\\B") == ["Placa A\\B"]


def test_busca_se_soma_aos_outros_filtros(repo, criar):
    criar("Buraco no centro", lat=-15.79, lon=-47.88)
    criar("Buraco longe", lat=-15.60, lon=-47.60)
    resultado = titulos(
        repo, busca="buraco", sul=-15.80, oeste=-47.90, norte=-15.78, leste=-47.87
    )
    assert resultado == ["Buraco no centro"]


def test_sem_busca_lista_tudo(repo, criar):
    criar("Buraco na via")
    criar("Poste apagado")
    assert len(titulos(repo)) == 2
