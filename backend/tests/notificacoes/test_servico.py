"""Regras do serviço de notificações com doubles (US03)."""

from datetime import datetime, timezone

import pytest

from app.models import StatusOcorrencia
from app.notificacoes.erros import (
    CategoriaInexistente,
    InscricaoDuplicada,
    InscricaoNaoEncontrada,
    OcorrenciaInexistente,
    TransicaoInvalida,
)
from app.notificacoes.schemas import InscricaoEntrada
from app.notificacoes.servico import ServicoNotificacoes
from tests.ocorrencias.fakes import CatalogoFake

from .fakes import FonteFake, InscricoesFake, StatusFake

T0 = datetime(2026, 11, 20, 9, 0, tzinfo=timezone.utc)
REG, ANA, RES = (
    StatusOcorrencia.REGISTRADO,
    StatusOcorrencia.EM_ANALISE,
    StatusOcorrencia.RESOLVIDO,
)


@pytest.fixture
def inscricoes():
    return InscricoesFake()


@pytest.fixture
def status():
    return StatusFake({1: REG})


@pytest.fixture
def fonte():
    return FonteFake()


@pytest.fixture
def servico(inscricoes, status, fonte):
    return ServicoNotificacoes(inscricoes, status, fonte, CatalogoFake(), lambda: T0)


def zona(**kw):
    base = {"latitude": -15.79, "longitude": -47.88, "raio_metros": 500.0}
    return InscricaoEntrada.model_validate({**base, **kw})


def test_seguir_ocorrencia(servico, inscricoes):
    insc = servico.inscrever(7, InscricaoEntrada(ocorrencia_id=1))
    assert (insc.usuario_id, insc.ocorrencia_id, insc.centro) == (7, 1, None)
    assert len(inscricoes.dados) == 1


def test_seguir_ocorrencia_inexistente(servico):
    with pytest.raises(OcorrenciaInexistente):
        servico.inscrever(7, InscricaoEntrada(ocorrencia_id=99))


def test_seguir_duas_vezes_e_duplicado(servico):
    servico.inscrever(7, InscricaoEntrada(ocorrencia_id=1))
    with pytest.raises(InscricaoDuplicada):
        servico.inscrever(7, InscricaoEntrada(ocorrencia_id=1))


def test_outro_usuario_pode_seguir_a_mesma_ocorrencia(servico):
    servico.inscrever(7, InscricaoEntrada(ocorrencia_id=1))
    assert servico.inscrever(8, InscricaoEntrada(ocorrencia_id=1)).usuario_id == 8


def test_zona_sem_categoria(servico):
    insc = servico.inscrever(7, zona())
    assert insc.ocorrencia_id is None and insc.categoria_id is None
    assert (insc.centro.latitude, insc.centro.longitude) == (-15.79, -47.88)
    assert insc.raio_metros == 500.0


def test_zona_com_categoria_existente(servico):
    assert servico.inscrever(7, zona(categoria_id=1)).categoria_id == 1


def test_zona_com_categoria_inexistente(servico):
    with pytest.raises(CategoriaInexistente):
        servico.inscrever(7, zona(categoria_id=500))


def test_zona_aceita_categoria_inativa(servico):
    assert servico.inscrever(7, zona(categoria_id=9)).categoria_id == 9


def test_cancelar_propria_inscricao(servico, inscricoes):
    insc = servico.inscrever(7, InscricaoEntrada(ocorrencia_id=1))
    servico.cancelar(7, insc.id)
    assert inscricoes.dados == {}


def test_cancelar_inscricao_alheia_parece_inexistente(servico, inscricoes):
    insc = servico.inscrever(7, InscricaoEntrada(ocorrencia_id=1))
    with pytest.raises(InscricaoNaoEncontrada):
        servico.cancelar(8, insc.id)
    assert len(inscricoes.dados) == 1


def test_cancelar_inexistente(servico):
    with pytest.raises(InscricaoNaoEncontrada):
        servico.cancelar(7, 123)


def test_listar_so_as_do_usuario(servico):
    servico.inscrever(7, InscricaoEntrada(ocorrencia_id=1))
    servico.inscrever(8, zona())
    assert [i.usuario_id for i in servico.listar_inscricoes(7)] == [7]


def test_ciclo_completo_registra_log(servico, status):
    assert servico.alterar_status(1, ANA) is ANA
    assert servico.alterar_status(1, RES) is RES
    assert status.transicoes == [(1, REG, ANA, T0), (1, ANA, RES, T0)]


@pytest.mark.parametrize("novo", [REG, RES])
def test_nao_pula_nem_repete_etapa(servico, status, novo):
    with pytest.raises(TransicaoInvalida):
        servico.alterar_status(1, novo)
    assert status.transicoes == []


def test_resolvida_nao_muda_mais(servico, status):
    status.status[1] = RES
    for novo in (REG, ANA, RES):
        with pytest.raises(TransicaoInvalida):
            servico.alterar_status(1, novo)


def test_alterar_status_de_ocorrencia_inexistente(servico):
    with pytest.raises(OcorrenciaInexistente):
        servico.alterar_status(99, ANA)


def test_consultar_delega_a_fonte(servico, fonte):
    servico.consultar(7, 20, 40)
    assert fonte.chamadas == [(7, 20, 40)]
