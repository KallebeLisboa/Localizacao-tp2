"""Gravação das buscas na tabela logs_pesquisa (US06)."""

from datetime import datetime, timezone

from sqlalchemy import select

from app.models import LogPesquisa
from app.ocorrencias.portas import Pesquisa
from app.ocorrencias.repositorio_sql import RegistroPesquisasSQL

T0 = datetime(2026, 11, 27, 15, 0, tzinfo=timezone.utc)


def logs(db):
    return db.scalars(select(LogPesquisa).order_by(LogPesquisa.id)).all()


def test_grava_termo_usuario_regiao_e_horario(db, massa):
    RegistroPesquisasSQL(db).registrar(
        Pesquisa(
            termo="buraco",
            usuario_id=massa.usuario_id,
            regiao="-15.8000,-47.9000,-15.7800,-47.8700",
            momento=T0,
        )
    )
    (log,) = logs(db)
    assert log.termo_buscado == "buraco"
    assert log.usuario_id == massa.usuario_id
    assert log.regiao_filtrada == "-15.8000,-47.9000,-15.7800,-47.8700"
    assert log.pesquisado_em == T0


def test_grava_busca_anonima(db, massa):
    RegistroPesquisasSQL(db).registrar(
        Pesquisa(termo="poste", usuario_id=None, regiao=None, momento=T0)
    )
    (log,) = logs(db)
    assert (log.usuario_id, log.regiao_filtrada) == (None, None)


def test_cada_busca_vira_uma_linha(db, massa):
    registro = RegistroPesquisasSQL(db)
    for _ in range(3):
        registro.registrar(
            Pesquisa(termo="buraco", usuario_id=None, regiao=None, momento=T0)
        )
    assert len(logs(db)) == 3
