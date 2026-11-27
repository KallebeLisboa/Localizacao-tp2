"""Cenário para as consultas de estatísticas no PostGIS (US04).

Seis ocorrências, horários em Brasília (UTC-3):

====  ==========  ==========  =====  ==================  ==========
 nº   local       status      cat.   registro (BRT)      dia/sem.
====  ==========  ==========  =====  ==================  ==========
 1    Asa Norte   registrado  1      02/11/2026 12h00    segunda
 2    Asa Norte   resolvido   1      02/11/2026 23h30*   segunda
 3    Asa Norte   em análise  2      10/11/2026 09h00    terça
 4    Asa Sul     resolvido   1      15/10/2026 08h00    quinta
 5    fora        registrado  2      20/11/2026 14h00    sexta
 6    Asa Sul     registrado  1      05/09/2026 10h00    sábado
====  ==========  ==========  =====  ==================  ==========

\\* Em UTC já é 03/11 02h30: pega erro de fuso no agrupamento.
As de nº 1-3 estão no mesmo ponto (P1); as de nº 4 e 6 também (P2).
A região "Guará" não tem nenhuma ocorrência.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import pytest
from geoalchemy2.elements import WKTElement

from app.models import (
    Categoria,
    Ocorrencia,
    PerimetroAutorizado,
    StatusOcorrencia,
    Usuario,
)

BRT = timezone(timedelta(hours=-3))
NOVEMBRO = {
    "inicio": datetime(2026, 11, 1, tzinfo=BRT),
    "fim": datetime(2026, 12, 1, tzinfo=BRT),
}

P1 = (-15.76, -47.88)  # Asa Norte (latitude, longitude)
P2 = (-15.82, -47.90)  # Asa Sul
P3 = (-15.60, -47.70)  # fora das regiões


def retangulo(oeste, sul, leste, norte):
    wkt = (
        f"POLYGON(({oeste} {sul}, {leste} {sul}, {leste} {norte}, "
        f"{oeste} {norte}, {oeste} {sul}))"
    )
    return WKTElement(wkt, srid=4326)


@dataclass
class Cenario:
    asa_norte: int
    asa_sul: int
    guara: int
    cat1: int
    cat2: int


@pytest.fixture
def cenario(db_session) -> Cenario:
    db = db_session
    usuario = Usuario(nome="U", email="u@unb.br", senha_hash="x")
    cat1, cat2 = Categoria(nome="Buraco"), Categoria(nome="Iluminação")
    norte = PerimetroAutorizado(
        nome_regiao="Asa Norte", area=retangulo(-47.90, -15.77, -47.86, -15.74)
    )
    sul = PerimetroAutorizado(
        nome_regiao="Asa Sul", area=retangulo(-47.92, -15.84, -47.88, -15.80)
    )
    guara = PerimetroAutorizado(
        nome_regiao="Guará", area=retangulo(-48.00, -15.84, -47.96, -15.80)
    )
    db.add_all([usuario, cat1, cat2, norte, sul, guara])
    db.flush()

    s = StatusOcorrencia

    def oc(ponto, status, cat, quando):
        lat, lon = ponto
        return Ocorrencia(
            titulo="t",
            descricao="d",
            status=status,
            localizacao=WKTElement(f"POINT({lon} {lat})", srid=4326),
            usuario_id=usuario.id,
            categoria_id=cat.id,
            criado_em=quando,
            atualizado_em=quando,
        )

    db.add_all(
        [
            oc(P1, s.REGISTRADO, cat1, datetime(2026, 11, 2, 12, 0, tzinfo=BRT)),
            oc(P1, s.RESOLVIDO, cat1, datetime(2026, 11, 2, 23, 30, tzinfo=BRT)),
            oc(P1, s.EM_ANALISE, cat2, datetime(2026, 11, 10, 9, 0, tzinfo=BRT)),
            oc(P2, s.RESOLVIDO, cat1, datetime(2026, 10, 15, 8, 0, tzinfo=BRT)),
            oc(P3, s.REGISTRADO, cat2, datetime(2026, 11, 20, 14, 0, tzinfo=BRT)),
            oc(P2, s.REGISTRADO, cat1, datetime(2026, 9, 5, 10, 0, tzinfo=BRT)),
        ]
    )
    db.commit()
    return Cenario(norte.id, sul.id, guara.id, cat1.id, cat2.id)
