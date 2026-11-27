"""Resumo e distribuição por região, com fonte falsa (US04).

Critério de aceitação: volume total de ocorrências resolvidas versus
pendentes, com filtro por região.
"""

import pytest

from app.core.exceptions import RecursoNaoEncontrado
from app.estatisticas.schemas import FORA_DAS_REGIOES, FiltroEstatisticas
from app.estatisticas.servico import ContagemRegiao, ServicoEstatisticas
from app.models import StatusOcorrencia as S

from .fakes import FonteFalsa


def servico(**dados):
    fonte = FonteFalsa(**dados)
    return ServicoEstatisticas(fonte), fonte


# ---------- Resumo ----------


def test_resumo_resolvidas_versus_pendentes():
    s, _ = servico(por_status={S.REGISTRADO: 4, S.EM_ANALISE: 1, S.RESOLVIDO: 5})
    r = s.resumo(FiltroEstatisticas())
    assert (r.total, r.resolvidas, r.pendentes, r.taxa_resolucao) == (10, 5, 5, 0.5)


def test_resumo_repassa_o_filtro_para_a_fonte():
    s, fonte = servico()
    filtro = FiltroEstatisticas(regiao_id=2, categorias=[1])
    s.resumo(filtro)
    assert fonte.chamadas == [("status", filtro)]


def test_regiao_inexistente_e_404():
    s, fonte = servico(regioes_existentes=())
    with pytest.raises(RecursoNaoEncontrado, match="região 9 não encontrada"):
        s.resumo(FiltroEstatisticas(regiao_id=9))
    assert fonte.chamadas == []


# ---------- Regiões ----------


def regiao(id_, nome, resolvidas, pendentes):
    return ContagemRegiao(
        regiao_id=id_,
        nome=nome,
        por_status={S.RESOLVIDO: resolvidas, S.REGISTRADO: pendentes},
    )


def test_regioes_com_resolvidas_e_pendentes():
    s, _ = servico(por_regiao=[regiao(1, "Asa Sul", 2, 3)])
    (item,) = s.regioes(FiltroEstatisticas())
    assert item.model_dump() == {
        "regiao_id": 1,
        "regiao": "Asa Sul",
        "total": 5,
        "resolvidas": 2,
        "pendentes": 3,
    }


def test_regioes_da_maior_para_a_menor_com_fora_no_fim():
    s, _ = servico(
        por_regiao=[
            regiao(None, FORA_DAS_REGIOES, 9, 9),
            regiao(1, "Guará", 0, 1),
            regiao(2, "Asa Norte", 3, 3),
            regiao(3, "Asa Sul", 3, 3),
        ]
    )
    nomes = [r.regiao for r in s.regioes(FiltroEstatisticas())]
    assert nomes == ["Asa Norte", "Asa Sul", "Guará", FORA_DAS_REGIOES]


def test_regioes_tambem_validam_a_regiao_do_filtro():
    s, _ = servico(regioes_existentes=())
    with pytest.raises(RecursoNaoEncontrado):
        s.regioes(FiltroEstatisticas(regiao_id=1))
