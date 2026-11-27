"""Filtro de busca por texto nas ocorrências (base dos logs da US06)."""

import pytest
from pydantic import ValidationError

from app.ocorrencias.filtros import BUSCA_MAX, FiltroOcorrencias


def test_sem_busca_por_padrao():
    assert FiltroOcorrencias().busca is None


def test_remove_espacos_das_pontas():
    assert FiltroOcorrencias(busca="  poste apagado  ").busca == "poste apagado"


@pytest.mark.parametrize("vazio", ["", "   ", "\t\n"])
def test_busca_vazia_e_o_mesmo_que_nao_buscar(vazio):
    assert FiltroOcorrencias(busca=vazio).busca is None


def test_aceita_o_tamanho_maximo():
    assert len(FiltroOcorrencias(busca="a" * BUSCA_MAX).busca) == BUSCA_MAX


def test_rejeita_busca_longa_demais():
    with pytest.raises(ValidationError):
        FiltroOcorrencias(busca="a" * (BUSCA_MAX + 1))


def test_combina_com_os_outros_filtros():
    filtro = FiltroOcorrencias.model_validate(
        {"busca": "buraco", "categorias": ["1"], "limite": "10"}
    )
    assert (filtro.busca, filtro.categorias, filtro.limite) == (
        "buraco",
        frozenset({1}),
        10,
    )
