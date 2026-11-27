"""Cenário de dados para as consultas do relatório gerencial (US06).

Período de referência: novembro de 2026, ``[2026-11-01, 2026-12-01)``.
"""

from dataclasses import dataclass
from datetime import datetime, timezone

import pytest
from geoalchemy2.elements import WKTElement

from app.models import (
    Categoria,
    LogPesquisa,
    Ocorrencia,
    PerimetroAutorizado,
    StatusOcorrencia,
    Usuario,
)

NOV_INICIO = datetime(2026, 11, 1, tzinfo=timezone.utc)
NOV_FIM = datetime(2026, 12, 1, tzinfo=timezone.utc)


def data(mes: int, dia: int, ano: int = 2026) -> datetime:
    return datetime(ano, mes, dia, 12, tzinfo=timezone.utc)


def retangulo(oeste: float, sul: float, leste: float, norte: float) -> WKTElement:
    wkt = (
        f"POLYGON(({oeste} {sul}, {leste} {sul}, {leste} {norte}, "
        f"{oeste} {norte}, {oeste} {sul}))"
    )
    return WKTElement(wkt, srid=4326)


def ponto(longitude: float, latitude: float) -> WKTElement:
    return WKTElement(f"POINT({longitude} {latitude})", srid=4326)


ASA_NORTE = retangulo(-47.90, -15.77, -47.86, -15.74)
ASA_SUL = retangulo(-47.92, -15.84, -47.88, -15.80)
GUARA = retangulo(-48.00, -15.84, -47.96, -15.80)

EM_ASA_NORTE = ponto(-47.88, -15.76)
EM_ASA_SUL = ponto(-47.90, -15.82)
FORA = ponto(-47.70, -15.60)


@dataclass
class Cenario:
    """Objetos criados, para os testes que precisam acrescentar dados."""

    categoria_id: int
    usuario_id: int


@pytest.fixture
def cenario(db_session) -> Cenario:
    """Usuários, regiões, ocorrências e pesquisas dentro e fora de novembro.

    Usuários (5): 4 ativos e 1 inativo; 2 criados em novembro.
    Ocorrências em novembro: Asa Norte 2 (registrado, resolvido), Asa Sul 1
    (em análise), Guará 0, fora das regiões 1 (registrado); feitas por 3
    usuários diferentes. Há ainda uma ocorrência de outubro na Asa Norte,
    de um quarto usuário.
    Pesquisas em novembro: buraco 3x (grafias diferentes), poste 2x, lixo 1x,
    além de termos vazios. Em outubro: iluminação 5x.
    """
    db = db_session
    cat = Categoria(nome="Buraco")
    antigo = Usuario(nome="A", email="a@unb.br", senha_hash="x", criado_em=data(9, 1))
    u1 = Usuario(nome="B", email="b@unb.br", senha_hash="x", criado_em=data(10, 15))
    u2 = Usuario(nome="C", email="c@unb.br", senha_hash="x", criado_em=data(11, 5))
    u3 = Usuario(
        nome="D", email="d@unb.br", senha_hash="x", criado_em=data(11, 10), ativo=False
    )
    u4 = Usuario(nome="E", email="e@unb.br", senha_hash="x", criado_em=data(12, 2))
    db.add_all(
        [
            cat,
            antigo,
            u1,
            u2,
            u3,
            u4,
            PerimetroAutorizado(nome_regiao="Asa Norte", area=ASA_NORTE),
            PerimetroAutorizado(nome_regiao="Asa Sul", area=ASA_SUL),
            PerimetroAutorizado(nome_regiao="Guará", area=GUARA),
        ]
    )
    db.flush()

    def ocorrencia(autor, onde, status, quando):
        return Ocorrencia(
            titulo="Ocorrência",
            descricao="Descrição",
            status=status,
            localizacao=onde,
            usuario_id=autor.id,
            categoria_id=cat.id,
            criado_em=quando,
            atualizado_em=quando,
        )

    s = StatusOcorrencia
    db.add_all(
        [
            ocorrencia(antigo, EM_ASA_NORTE, s.REGISTRADO, data(10, 20)),
            ocorrencia(u1, EM_ASA_NORTE, s.REGISTRADO, data(11, 3)),
            ocorrencia(u2, EM_ASA_NORTE, s.RESOLVIDO, data(11, 4)),
            ocorrencia(u2, EM_ASA_SUL, s.EM_ANALISE, data(11, 6)),
            ocorrencia(u3, FORA, s.REGISTRADO, data(11, 30)),
        ]
    )

    pesquisas = [("iluminação", data(10, 5))] * 5 + [
        ("Buraco", data(11, 2)),
        (" buraco ", data(11, 3)),
        ("BURACO", data(11, 4)),
        ("poste", data(11, 5)),
        ("Poste", data(11, 6)),
        ("lixo", data(11, 7)),
        ("", data(11, 8)),
        ("   ", data(11, 8)),
        (None, data(11, 9)),
    ]
    db.add_all(
        LogPesquisa(termo_buscado=termo, pesquisado_em=quando)
        for termo, quando in pesquisas
    )
    db.commit()
    return Cenario(categoria_id=cat.id, usuario_id=u1.id)
