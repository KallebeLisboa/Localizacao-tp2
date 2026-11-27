"""Filtro da consulta parametrizada do relatório gerencial (US06)."""

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.relatorios.schemas import (
    LIMITE_TERMOS_MAX,
    LIMITE_TERMOS_PADRAO,
    FiltroRelatorio,
)

T0 = datetime(2026, 11, 1, tzinfo=timezone.utc)


def test_sem_parametros_usa_padroes():
    filtro = FiltroRelatorio()
    assert filtro.inicio is None
    assert filtro.fim is None
    assert filtro.limite_termos == LIMITE_TERMOS_PADRAO


def test_aceita_periodo_com_fuso():
    filtro = FiltroRelatorio(inicio=T0, fim=T0 + timedelta(days=30))
    assert filtro.fim - filtro.inicio == timedelta(days=30)


def test_aceita_datas_em_texto_como_chegam_na_query():
    filtro = FiltroRelatorio.model_validate(
        {"inicio": "2026-11-01T00:00:00-03:00", "fim": "2026-12-01T00:00:00Z"}
    )
    assert filtro.inicio == datetime(2026, 11, 1, 3, tzinfo=timezone.utc)


def test_aceita_so_inicio_ou_so_fim():
    assert FiltroRelatorio(inicio=T0).fim is None
    assert FiltroRelatorio(fim=T0).inicio is None


def test_rejeita_data_sem_fuso():
    with pytest.raises(ValidationError):
        FiltroRelatorio(inicio=datetime(2026, 11, 1))


@pytest.mark.parametrize("fim", [T0, T0 - timedelta(seconds=1)])
def test_rejeita_inicio_igual_ou_depois_do_fim(fim):
    with pytest.raises(ValidationError, match="inicio deve ser anterior a fim"):
        FiltroRelatorio(inicio=T0, fim=fim)


@pytest.mark.parametrize("limite", [0, -1, LIMITE_TERMOS_MAX + 1])
def test_rejeita_limite_de_termos_fora_da_faixa(limite):
    with pytest.raises(ValidationError):
        FiltroRelatorio(limite_termos=limite)


def test_aceita_limite_maximo_de_termos():
    assert FiltroRelatorio(limite_termos=LIMITE_TERMOS_MAX).limite_termos == 50


def test_rejeita_parametro_desconhecido():
    with pytest.raises(ValidationError):
        FiltroRelatorio.model_validate({"regiao": "Asa Norte"})


def test_filtro_e_imutavel():
    filtro = FiltroRelatorio()
    with pytest.raises(ValidationError):
        filtro.limite_termos = 5
