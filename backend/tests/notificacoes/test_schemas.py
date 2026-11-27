"""Validação do corpo de inscrição (US03)."""

import pytest
from pydantic import ValidationError

from app.notificacoes.schemas import RAIO_MAX_METROS, InscricaoEntrada

ZONA = {"latitude": -15.79, "longitude": -47.88, "raio_metros": 300.0}


def test_modo_ocorrencia():
    assert InscricaoEntrada.model_validate({"ocorrencia_id": 3}).ocorrencia_id == 3


def test_modo_zona_com_e_sem_categoria():
    assert InscricaoEntrada.model_validate(ZONA).categoria_id is None
    assert (
        InscricaoEntrada.model_validate({**ZONA, "categoria_id": 2}).categoria_id == 2
    )


@pytest.mark.parametrize(
    "corpo",
    [
        {},
        {"latitude": -15.79, "longitude": -47.88},  # sem raio
        {"raio_metros": 300.0},  # sem centro
        {"ocorrencia_id": 1, **ZONA},  # os dois modos
        {"ocorrencia_id": 1, "categoria_id": 2},
        {**ZONA, "raio_metros": 0},
        {**ZONA, "raio_metros": -5.0},
        {**ZONA, "raio_metros": RAIO_MAX_METROS + 1},
        {**ZONA, "latitude": 91.0},
        {**ZONA, "longitude": -181.0},
        {"ocorrencia_id": 0},
        {"ocorrencia_id": "1"},  # modo estrito
        {"ocorrencia_id": 1, "usuario_id": 9},  # campo extra
    ],
)
def test_corpos_invalidos(corpo):
    with pytest.raises(ValidationError):
        InscricaoEntrada.model_validate(corpo)
