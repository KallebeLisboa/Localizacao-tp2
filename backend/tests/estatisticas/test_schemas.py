"""Filtro comum e contagens das estatísticas (US04)."""

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.estatisticas.schemas import (
    Agrupamento,
    Contagem,
    FiltroEstatisticas,
    Granularidade,
    Resumo,
)
from app.models import StatusOcorrencia as S

T0 = datetime(2026, 11, 1, tzinfo=timezone.utc)


# ---------- Filtro ----------


def test_sem_filtros_por_padrao():
    filtro = FiltroEstatisticas()
    assert (filtro.inicio, filtro.fim, filtro.regiao_id, filtro.categorias) == (
        None,
        None,
        None,
        None,
    )


def test_aceita_valores_textuais_da_query():
    filtro = FiltroEstatisticas.model_validate(
        {
            "inicio": "2026-11-01T00:00:00-03:00",
            "regiao_id": "3",
            "categorias": ["1", "2"],
        }
    )
    assert filtro.inicio == datetime(2026, 11, 1, 3, tzinfo=timezone.utc)
    assert filtro.regiao_id == 3
    assert filtro.categorias == frozenset({1, 2})


def test_rejeita_data_sem_fuso():
    with pytest.raises(ValidationError):
        FiltroEstatisticas(inicio=datetime(2026, 11, 1))


@pytest.mark.parametrize("fim", [T0, T0 - timedelta(days=1)])
def test_rejeita_inicio_igual_ou_depois_do_fim(fim):
    with pytest.raises(ValidationError, match="inicio deve ser anterior a fim"):
        FiltroEstatisticas(inicio=T0, fim=fim)


@pytest.mark.parametrize("campos", [{"regiao_id": 0}, {"categorias": []}])
def test_rejeita_valores_vazios_ou_invalidos(campos):
    with pytest.raises(ValidationError):
        FiltroEstatisticas(**campos)


def test_rejeita_parametro_desconhecido():
    with pytest.raises(ValidationError):
        FiltroEstatisticas.model_validate({"status": "RESOLVIDO"})


def test_filtro_e_imutavel():
    with pytest.raises(ValidationError):
        FiltroEstatisticas().regiao_id = 2


# ---------- Contagens ----------


def test_pendentes_sao_registradas_mais_em_analise():
    c = Contagem.de({S.REGISTRADO: 3, S.EM_ANALISE: 2, S.RESOLVIDO: 5})
    assert (c.total, c.resolvidas, c.pendentes) == (10, 5, 5)


def test_status_ausente_conta_zero():
    c = Contagem.de({S.RESOLVIDO: 4})
    assert (c.total, c.resolvidas, c.pendentes) == (4, 4, 0)


def test_contagem_vazia_e_zero():
    assert Contagem.de({}).model_dump() == {"total": 0, "resolvidas": 0, "pendentes": 0}


def test_resumo_traz_cada_status_e_a_taxa_de_resolucao():
    r = Resumo.de({S.REGISTRADO: 1, S.EM_ANALISE: 2, S.RESOLVIDO: 1})
    assert (r.registradas, r.em_analise, r.resolvidas, r.pendentes) == (1, 2, 1, 3)
    assert r.taxa_resolucao == 0.25


def test_taxa_de_resolucao_arredondada():
    r = Resumo.de({S.REGISTRADO: 2, S.RESOLVIDO: 1})
    assert r.taxa_resolucao == 0.3333


def test_sem_ocorrencias_nao_ha_taxa():
    assert Resumo.de({}).taxa_resolucao is None


# ---------- Opções ----------


def test_granularidades_e_agrupamentos_disponiveis():
    assert [g.value for g in Granularidade] == ["dia", "semana", "mes"]
    assert [a.value for a in Agrupamento] == ["mes", "dia_semana", "hora"]
