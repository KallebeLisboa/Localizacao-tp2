"""Gravação automática das buscas pelo serviço (base do relatório da US06)."""

from datetime import datetime, timezone

import pytest

from app.ocorrencias.filtros import FiltroOcorrencias
from app.ocorrencias.portas import Pesquisa
from app.ocorrencias.servico import ServicoOcorrencias

from .fakes import AreaFake, CatalogoFake, RelogioFake, RepositorioFake

T0 = datetime(2026, 11, 27, 15, 0, tzinfo=timezone.utc)


class RegistroPesquisasFake:
    """Guarda as pesquisas registradas."""

    def __init__(self):
        self.pesquisas = []

    def registrar(self, pesquisa):
        self.pesquisas.append(pesquisa)


@pytest.fixture
def registro():
    return RegistroPesquisasFake()


@pytest.fixture
def repo():
    return RepositorioFake()


@pytest.fixture
def servico(repo, registro):
    return ServicoOcorrencias(
        repo, CatalogoFake(), AreaFake(), RelogioFake(T0), pesquisas=registro
    )


def test_busca_e_registrada_com_usuario_e_horario(servico, registro):
    servico.consultar(FiltroOcorrencias(busca="buraco"), usuario_id=7)
    assert registro.pesquisas == [
        Pesquisa(termo="buraco", usuario_id=7, regiao=None, momento=T0)
    ]


def test_busca_anonima_fica_sem_usuario(servico, registro):
    servico.consultar(FiltroOcorrencias(busca="buraco"))
    assert registro.pesquisas[0].usuario_id is None


def test_consulta_sem_busca_nao_registra(servico, registro):
    servico.consultar(FiltroOcorrencias(categorias=[1]), usuario_id=7)
    assert registro.pesquisas == []


def test_proximas_paginas_da_mesma_busca_nao_contam_de_novo(servico, registro):
    servico.consultar(FiltroOcorrencias(busca="buraco", offset=100))
    assert registro.pesquisas == []


def test_registra_o_retangulo_do_mapa_como_regiao(servico, registro):
    filtro = FiltroOcorrencias(
        busca="poste", sul=-15.8, oeste=-47.9, norte=-15.78, leste=-47.87
    )
    servico.consultar(filtro)
    assert registro.pesquisas[0].regiao == "-15.8000,-47.9000,-15.7800,-47.8700"


def test_registra_mesmo_quando_nada_e_encontrado(servico, registro, repo):
    pagina = servico.consultar(FiltroOcorrencias(busca="inexistente"))
    assert pagina.itens == [] and len(registro.pesquisas) == 1


def test_devolve_o_resultado_do_repositorio(servico, repo):
    filtro = FiltroOcorrencias(busca="buraco")
    servico.consultar(filtro)
    assert repo.filtros == [filtro]


def test_sem_registro_configurado_a_consulta_segue_normal(repo):
    servico = ServicoOcorrencias(repo, CatalogoFake(), AreaFake(), RelogioFake(T0))
    assert servico.consultar(FiltroOcorrencias(busca="buraco")).itens == []


def test_relogio_sem_fuso_e_erro_de_configuracao(repo, registro):
    servico = ServicoOcorrencias(
        repo,
        CatalogoFake(),
        AreaFake(),
        lambda: datetime(2026, 11, 27),
        pesquisas=registro,
    )
    with pytest.raises(ValueError, match="fuso"):
        servico.consultar(FiltroOcorrencias(busca="buraco"))
